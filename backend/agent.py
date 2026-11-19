from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import json
from time import monotonic
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .config import KST, integer_setting
from .conversation import ACTIVITIES, analyze, is_region_name, next_christmas, select_entry_tool
from .events import elapsed
from .models import ChatResult, Conditions, end_minutes
from .planning import (MAX_WALK_LEG_MINUTES, assess, building_repeats, cafe_target, choose_candidates, invitation_priority,
                       invitation_rank, meal_slots, meal_terms, target_stops)
from .tools import CUISINE_CODES, STATION_RADIUS_M, TOOLS, TMAP_SOURCE, Candidate, DetailData, ToolResult, call_tool, gap_m, station_name

FATAL = {'MISSING_API_KEY', 'AUTH_FAILED', 'RATE_LIMITED'}


class State(TypedDict, total=False):
    session_id: str
    request_id: str
    message: str
    previous: Conditions
    last: str
    mode: str
    conditions: Conditions
    intent: str
    question: str
    work: list[dict]
    candidates: list[Candidate]
    details: dict[str, DetailData]
    errors: list[str]
    notices: list[str]
    exclusions: list[str]
    tool_summaries: list[dict]
    attempt: int
    result: ChatResult


class Planner:
    def __init__(self, events, demo=False, invoke=call_tool, cap=None):
        self.events = events
        self.demo = demo
        self.invoke = invoke
        self.cap = integer_setting('MAX_REPLANS', 3, 0, 8) if cap is None else cap
        self.cache: dict[tuple, ToolResult] = {}
        self.tried = set()
        self.long_legs = set()
        self.error_keys = set()
        self.origin = None
        self.station = None
        self.weather = None
        self.order = []
        self.routes = []
        self.invitation = None
        self.best_invitation = None
        self.stop_reason = ''
        self.route_blocked = False
        self.has_long_leg = False

    def run(self, message, previous, last):
        return self.graph().invoke({
            'session_id': str(self.events.session_id), 'request_id': str(self.events.run_id),
            'message': message, 'previous': previous, 'last': last, 'mode': 'demo' if self.demo else 'live',
            'errors': [], 'notices': [], 'exclusions': [], 'tool_summaries': [],
            'candidates': [], 'details': {}, 'attempt': 0,
        }, {'recursion_limit': 48})['result']

    def graph(self):
        graph = StateGraph(State)
        for node in ('analysis', 'plan', 'execute', 'judge', 'replan', 'respond'):
            graph.add_node(node, self.events.stage(node, getattr(self, node)))
        graph.add_edge(START, 'analysis')
        graph.add_conditional_edges('analysis', lambda s: 'plan' if s['intent'] == 'plan' and not s['question']
                                    else 'respond', ['plan', 'respond'])
        graph.add_edge('plan', 'execute')
        graph.add_edge('execute', 'judge')
        graph.add_conditional_edges('judge', lambda s: 'respond' if self.invitation or self.stop_reason else 'replan',
                                    ['respond', 'replan'])
        graph.add_edge('replan', 'execute')
        graph.add_edge('respond', END)
        return graph.compile()

    def analysis(self, state):
        result, engine, unavailable = analyze(state['message'], state['previous'], state['last'], self.demo)
        values = state['previous'].model_dump()
        changes = result.patch.model_dump(exclude_unset=True)
        if result.intent == 'plan':
            origin = changes.get('origin', values.get('origin'))
            if is_region_name(origin):
                if 'origin' in changes or not values.get('region'):
                    changes.setdefault('region', origin)
                changes['origin'] = None
            if changes.get('region') and changes['region'] != values['region'] and 'origin' not in changes:
                changes['origin'] = None
            values.update(changes)
            if not values['date']:
                values['date'] = next_christmas(datetime.now(KST).date())
        conditions = Conditions.model_validate(values)
        self.events.emit('decision_made', 'analysis', decision=result.intent, reason=f'{engine} · {result.reason}',
                         sanitized_output={'changed_fields': sorted(changes)})
        question = ''
        if result.intent == 'plan':
            missing = [label for field, label in [('start', '시작 시각'), ('end', '종료 시각')]
                       if getattr(conditions, field) is None]
            if self.demo and not conditions.region:
                missing.insert(1, '활동 지역')
            needs_station = not self.demo and not station_name(conditions.region)
            if needs_station and missing:
                missing.insert(1, '활동할 역 이름')
            if missing:
                question = '초대장에 담을 ' + ', '.join(missing) + '을 알려줘.'
                if conditions.start is None or conditions.end is None:
                    question += ' 시각은 오전·오후나 24시간제로 알려줘.'
            elif needs_station:
                question = '어느 역 근처로 찾아볼까? 강남역처럼 역 이름을 알려줘.'
            elif end_minutes(conditions.end) <= conditions.start.hour * 60 + conditions.start.minute:
                question = '종료 시각이 시작보다 늦어야 해. 같은 날의 두 시각을 다시 알려줘.'
            elif conditions.budget is not None and not conditions.budget_basis:
                question = '그 예산은 한 사람 기준이야, 일행 전체 기준이야?'
            elif len(conditions.activities or []) > 3:
                question = '하루에 꼭 넣고 싶은 활동을 세 가지 이내로 골라줘.'
        notices = []
        if self.demo:
            notices.append('시연 모드 · 예시 장소, 경로, 날씨를 사용했어요.')
        elif unavailable:
            notices.append('LLM 설정 또는 연결을 확인해 주세요. 입력에서 확인한 조건을 규칙으로 읽었어요.')
        return {'conditions': conditions, 'intent': result.intent, 'question': question, 'notices': notices}

    def plan(self, state):
        entry, reason, llm = select_entry_tool(state['conditions'], self.demo)
        steps = [{'tool': entry, 'uses': '지역 · 활동 · 날짜'},
                 {'tool': 'get_place_details', 'uses': '후보 식별자와 유형'},
                 {'tool': 'get_walking_route', 'uses': '출발지와 선택한 후보의 좌표'},
                 {'tool': 'get_christmas_weather', 'uses': '첫 장소의 좌표와 활동 시각'}]
        self.events.emit('decision_made', 'plan', decision='work_plan', reason=reason,
                         sanitized_output={'steps': steps, 'chosen_by': 'LLM' if llm else 'rules'})
        return {'work': steps}

    def batch(self, state, name, arguments):
        if name not in {step['tool'] for step in state['work']}:
            raise RuntimeError('Unexpected tool in work plan')
        keys = [(name, json.dumps(args, sort_keys=True, default=str, ensure_ascii=False)) for args in arguments]
        todo = {}
        for key, args in zip(keys, arguments):
            if key in self.cache or key in todo:
                self.events.emit('tool_reused', 'execute', tool_name=name, reason='현재 실행에서 조회한 결과를 재사용했어요.')
                continue
            if name == 'get_place_details':
                safe_input = {'candidate_id': args['content_id'], 'category': args['content_type_id']}
            elif name == 'search_places':
                safe_input = {key: args[key] for key in ('category', 'page', 'provider') if key in args}
                safe_input['uses_keyword'] = bool(args.get('keyword'))
            elif name == 'get_christmas_weather':
                safe_input = {key: args[key] for key in ('start_hour', 'end_hour', 'years')}
            else:
                safe_input = {'coordinate_pair_available': True}
            call_id = self.events.sequence + 1
            self.events.emit('tool_requested', 'execute', tool_name=name,
                             sanitized_input={'call_id': call_id, **safe_input})
            todo[key] = (args, call_id)
        if todo:
            with ThreadPoolExecutor(max_workers=min(5, len(todo))) as pool:
                tasks = {pool.submit(self.timed_tool, name, args): key for key, (args, _) in todo.items()}
                for future in as_completed(tasks):
                    key = tasks[future]
                    outcome, duration = future.result()
                    self.cache[key] = outcome
                    summary = {'call_id': todo[key][1], 'ok': outcome.ok, 'source': outcome.meta.source}
                    data = outcome.data
                    if outcome.ok:
                        if name == 'search_places':
                            summary['candidate_ids'] = [item.content_id for item in data.candidates
                                                        if item.provider != 'tmap']
                            if todo[key][0].get('provider') in {'tmap_cafes', 'tmap_restaurants'}:
                                summary['candidate_count'] = len(data.candidates)
                            if data.coverage not in state['notices']:
                                state['notices'].append(data.coverage)
                        elif name == 'get_place_details':
                            summary.update(candidate_id=data.content_id, missing=data.missing)
                        elif name == 'get_walking_route':
                            summary['has_route'] = True
                        else:
                            summary.update(years=data.years, missing=data.missing)
                    code = outcome.error.code if outcome.error else None
                    if code:
                        summary['error_code'] = code
                        provider = todo[key][0].get('provider')
                        label = {'tmap_cafes': 'TMAP 카페 검색', 'tmap_station': 'TMAP 역 검색',
                                 'tmap_restaurants': 'TMAP 식당 검색'}.get(provider, name)
                        if (label, code) not in self.error_keys:
                            self.error_keys.add((label, code))
                            state['errors'].append(f'{label} · {outcome.error.message}')
                    state['tool_summaries'].append({'tool': name, **summary})
                    self.events.emit('tool_completed', 'execute', tool_name=name, sanitized_output=summary,
                                     duration_ms=duration, error_code=code)
        return [self.cache[key] for key in keys]

    def timed_tool(self, name, args):
        started = monotonic()
        outcome = self.invoke(name, args, self.demo)
        return outcome, elapsed(started)

    def execute(self, state):
        conditions = state['conditions']
        attempt = state['attempt']
        base = {'region': conditions.region, 'target_date': conditions.date, 'page': 1}
        wanted = list(dict.fromkeys(ACTIVITIES[a][0] for a in conditions.activities or [] if a in ACTIVITIES))
        meals = meal_slots(conditions)
        preferred_foods = meal_terms(conditions)
        cafes = cafe_target(conditions)
        categories = list(dict.fromkeys([*wanted, *([39] if meals else [])])) or [None]
        candidates = state['candidates']
        details = state['details']

        def in_region(item):
            return self.demo or self.near_station(item)

        if not self.demo:
            if not self.station:
                result, = self.batch(state, 'search_places', [{'region': conditions.region, 'provider': 'tmap_station'}])
                if not result.ok:
                    self.stop_reason = {
                        'AMBIGUOUS_STATION': '같은 이름의 역이 여러 곳 있어. 도시나 호선도 함께 알려줘.',
                        'NO_RESULT': '그 역을 찾지 못했어. 역 이름을 한 번 더 알려줄래?',
                    }.get(result.error.code, '역 위치를 확인하지 못했어. 잠시 후 다시 시도해 줘.')
                    return {key: state[key] for key in ('errors', 'notices', 'tool_summaries')}
                self.station = result.data.candidates[0]
            base.update(center=self.station.point, radius_m=STATION_RADIUS_M)
            if conditions.origin and station_name(conditions.origin) == self.station.name:
                self.origin = self.station

        if attempt == 0 or attempt >= 2:
            requests = [{**base, 'category': category, 'page': attempt or 1}
                        for category in categories]
            if not self.demo and cafes:
                requests.insert(0, {**base, 'category': 39, 'keyword': '카페', 'page': attempt or 1})
            if not self.demo and meals:
                requests += [{**base, 'category': 39, 'keyword': food} for food in preferred_foods if food in CUISINE_CODES]
            resolve_origin = attempt == 0 and conditions.origin and not self.origin
            if resolve_origin:
                requests = [{**base, 'keyword': conditions.origin}, *requests]
            results = self.batch(state, 'search_places', requests)
            if resolve_origin:
                initial, *results = results
                if initial.ok:
                    label = conditions.origin.replace(' ', '')
                    self.origin = next((item for item in initial.data.candidates
                                        if in_region(item) and label in item.name.replace(' ', '')), None)
                if not self.origin:
                    self.stop_reason = '출발 지점을 확인하지 못했어. 검색할 수 있도록 장소 이름을 조금 더 자세히 알려줘.'
            known = {item.content_id for item in candidates}
            for result in results:
                if not result.ok:
                    continue
                rows = [item for item in result.data.candidates if in_region(item)]
                if len(meals) == 2:
                    # Keep both restaurants and cafés when a generic food search returns a mixed page.
                    rows = [*filter(lambda item: item.food_kind != 'cafe', rows),
                            *filter(lambda item: item.food_kind == 'cafe', rows)]
                for item in rows[:8 if len(meals) == 2 else 5]:
                    if item.content_id not in known:
                        candidates.append(item)
                        known.add(item.content_id)
            if candidates and not self.stop_reason and (meals or target_stops(conditions) >= 3):
                anchor = self.station or self.origin or min(candidates, key=lambda item: sum(
                    min(1200, gap_m(item.point, other.point)) for other in candidates))
                nearby = {**base, 'page': 1}
                extras = [14, 39, 38 if conditions.indoor == 'mostly_indoor' or conditions.cold_sensitive else 12]
                if len(meals) == 1:
                    extras.insert(0, 15)
                supplements = [category for category in extras if category not in wanted or (category == 39 and meals)]
                extra_results = self.batch(state, 'search_places', [{**nearby, 'category': category} for category in supplements])
                for result in extra_results:
                    if result.ok:
                        for item in [candidate for candidate in result.data.candidates if in_region(candidate)][:5]:
                            if item.content_id not in known:
                                candidates.append(item)
                                known.add(item.content_id)
                candidates.sort(key=lambda item: gap_m(anchor.point, item.point))
            wants_cafe = cafes or (
                target_stops(conditions) >= 3 and '카페' not in (conditions.avoids or []))
            if wants_cafe and not self.demo and not self.stop_reason and sum(
                item.food_kind == 'cafe' for item in candidates
            ) < (4 if cafes == 2 else 2):
                self.add_tmap_food(state, candidates, details, ['카페'])
            if meals and not self.demo and not self.stop_reason and sum(
                item.cuisine in preferred_foods for item in candidates if item.food_kind != 'cafe'
            ) < len(meals) + 1:
                self.add_tmap_food(state, candidates, details, preferred_foods)
            if not candidates and not self.stop_reason and any(
                result.error and result.error.code in FATAL for result in results
            ):
                self.stop_reason = '후보를 조회하지 못했어. TourAPI 설정이나 사용 한도를 확인해 줘.'

        # Query detail only for newly discovered candidates; failed calls are cached for this run too.
        if candidates and not self.stop_reason:
            detail_inputs = [{'content_id': c.content_id, 'content_type_id': c.content_type_id}
                             for c in candidates[:20] if c.content_id not in details
                             and ('get_place_details', json.dumps({'content_id': c.content_id,
                                 'content_type_id': c.content_type_id}, sort_keys=True)) not in self.cache]
            detail_results = self.batch(state, 'get_place_details', detail_inputs)
            for result in detail_results:
                if result.ok:
                    details[result.data.content_id] = result.data
            if not details and any(result.error and result.error.code in FATAL for result in detail_results):
                self.stop_reason = '장소 상세를 확인하지 못했어. TourAPI 설정이나 사용 한도를 확인해 줘.'

        self.routes, self.order = [], []
        self.route_blocked = self.has_long_leg = False
        if candidates and not self.stop_reason:
            self.order, excluded = choose_candidates(candidates, details, conditions, self.tried, self.origin,
                                                     self.long_legs)
            extend_unique(state['exclusions'], excluded)
        if candidates and self.weather is None and attempt == 0:
            anchor = self.order[0] if self.order else candidates[0]
            hour = (end_minutes(conditions.end) + 59) // 60
            weather = self.batch(state, 'get_christmas_weather', [{
                'point': anchor.point, 'target_date': conditions.date, 'years': 5,
                'start_hour': conditions.start.hour, 'end_hour': hour,
            }])[0]
            if weather.ok:
                self.weather = weather.data
                extend_unique(state['notices'], weather.meta.warnings)
        if self.order:
            self.tried.add(tuple(item.content_id for item in self.order))
            sequence = ([self.origin] if self.origin else []) + self.order
            legs = self.batch(state, 'get_walking_route', [
                {'start': a.point, 'end': b.point, 'start_name': a.name, 'end_name': b.name}
                for a, b in zip(sequence, sequence[1:])
            ])
            self.routes = [leg.data for leg in legs if leg.ok]
            for a, b, leg in zip(sequence, sequence[1:], legs):
                if leg.ok and leg.data.seconds > MAX_WALK_LEG_MINUTES * 60:
                    self.long_legs.add((a.content_id, b.content_id))
                    self.has_long_leg = True
            self.route_blocked = len(self.routes) != len(legs)
            if any(leg.error and leg.error.code in FATAL for leg in legs):
                self.stop_reason = '보행 경로를 확인하지 못했어. TMAP 설정이나 사용 한도를 확인해 줘.'
        return {key: state[key] for key in ('candidates', 'details', 'errors', 'notices', 'exclusions', 'tool_summaries')}

    def add_tmap_food(self, state, candidates, details, keywords):
        conditions = state['conditions']
        cafes = keywords == ['카페']
        base = {'region': conditions.region, 'target_date': conditions.date, 'center': self.station.point,
                'radius_m': STATION_RADIUS_M, 'provider': 'tmap_cafes' if cafes else 'tmap_restaurants'}
        results = self.batch(state, 'search_places', [{**base, 'keyword': keyword} for keyword in keywords])
        for result in results:
            if not result.ok:
                continue
            added = 0
            for item in result.data.candidates:
                if not self.near_station(item):
                    continue
                normalized = ''.join(item.name.split()).casefold()
                if any(other.content_id == item.content_id or (
                    ''.join(other.name.split()).casefold() == normalized and gap_m(item.point, other.point) < 100
                ) for other in candidates):
                    continue
                candidates.append(item)
                details[item.content_id] = DetailData(content_id=item.content_id, content_type_id=39,
                    category='카페' if cafes else '음식점', missing=['운영 시간', '휴무', '비용'], source_url=TMAP_SOURCE)
                added += 1
                if added == (5 if cafes else 3):
                    break

    def near_station(self, item):
        return bool(item.address and gap_m(item.point, self.station.point) <= STATION_RADIUS_M)

    def judge(self, state):
        if self.stop_reason:
            self.invitation = self.best_invitation
            self.events.emit('decision_made', 'judge', decision='blocked', reason=self.stop_reason)
            return {}
        if not self.order:
            reasons = ['현재 후보에서 요청한 활동을 모두 충족하는 순서를 찾지 못했어요.']
        elif self.has_long_leg:
            reasons = [f'한 번에 도보 {MAX_WALK_LEG_MINUTES}분 제한을 넘는 구간이 있어요.']
        elif self.route_blocked:
            reasons = ['이 후보 순서의 보행 경로를 확인하지 못했어요.']
        else:
            proposal, reasons = assess(state['conditions'], self.order, state['details'], self.routes,
                                       self.weather, state['mode'], self.origin,
                                       state['notices'] + state['errors'], state['exclusions'])
            if proposal:
                return self.accept_proposal(proposal, state)
        extend_unique(state['exclusions'], [f'{" → ".join(c.name for c in self.order)} · {reason}' if self.order else reason
                                            for reason in reasons])
        if state['attempt'] >= self.cap:
            self.invitation = self.best_invitation
            if not self.invitation:
                self.stop_reason = ('한 번에 30분 안에 걸을 수 있는 코스를 찾기 어려웠어. 활동 지역이나 꼭 들를 곳을 조금 좁혀 줄래?'
                                    if self.long_legs else
                                    '지금 찾은 장소로는 요청한 활동을 모두 담기 어려웠어. 지역이나 시간을 조금 조정해 줄래?')
        # TMAP numeric derivatives are kept only in the temporary result, never in the persisted event.
        reasons_logged = [next((label for token, label in (
            ('제한을 넘', 'WALKING_LIMIT'), ('종료 시각', 'END_LIMIT'), ('이용 조건', 'OPENING_HOURS'),
            ('예산', 'BUDGET'), ('경로', 'ROUTE_UNAVAILABLE')) if token in reason), 'CANDIDATES_UNAVAILABLE')
            for reason in reasons]
        self.events.emit('decision_made', 'judge', decision='rejected',
                         reason='후보 부족, 경로 확인 실패 또는 사용자 제약 불충족으로 대안을 검토했어요.',
                         sanitized_output={'attempt': state['attempt'], 'reason_codes': reasons_logged,
                                           'candidate_ids': [item.content_id for item in self.order
                                                             if item.provider != 'tmap']})
        return {'exclusions': state['exclusions']}

    def accept_proposal(self, proposal, state):
        rank = invitation_priority(proposal)
        dining = invitation_rank(proposal)
        verified = not proposal.revalidation_required
        if not self.best_invitation or (*dining, verified) > (
            *invitation_rank(self.best_invitation), not self.best_invitation.revalidation_required
        ):
            self.best_invitation = proposal
        conditions = state['conditions']
        expected = (len(meal_slots(conditions)), cafe_target(conditions), target_stops(conditions))
        complete = dining[1] == 0 and all(actual >= goal for actual, goal in zip(rank, expected))
        repeats = building_repeats(proposal.stops)
        if (complete and not repeats) or state['attempt'] >= self.cap:
            self.invitation = self.best_invitation
            verified = not self.invitation.revalidation_required
            self.events.emit('decision_made', 'judge', decision='accepted' if verified and all(
                stop.access == 'verified' for stop in self.invitation.stops) else 'provisional',
                             reason='장소 간 거리를 바탕으로 예상 일정을 계산했어요.' if not verified else
                             '보행과 종료 시각을 계산하고 이용 및 비용 근거를 확인했어요.',
                             sanitized_output={'checks': list(self.invitation.checks), 'stop_count': len(self.invitation.stops)})
        else:
            self.events.emit('decision_made', 'judge', decision='partial',
                             reason='같은 건물에 모인 장소를 대신할 후보가 있는지 살펴봐요.' if repeats else
                             '도보 조건에 맞는 코스를 확보했어요. 식사와 방문지를 더 채울 수 있는지 살펴봐요.',
                             sanitized_output={'stop_count': len(proposal.stops)})
        return {}

    def replan(self, state):
        attempt = state['attempt'] + 1
        strategy = '조회한 후보 순서 변경' if attempt == 1 else '주변 후보 또는 추가 검색 페이지 확인'
        self.events.emit('replan_requested', 'replan', decision=str(attempt),
                         reason='기존 조회 결과 재사용 · ' + strategy,
                         sanitized_output={'strategy': strategy})
        return {'attempt': attempt, 'work': [
            {**step, 'uses': strategy} if step['tool'] == 'search_places' else step for step in state['work']
        ]}

    def respond(self, state):
        if state['intent'] == 'greeting':
            message = '반가워. 이번 크리스마스에는 어떤 하루를 너에게 선물하고 싶어?'
        elif state['intent'] == 'help':
            message = '역 이름과 시작·종료 시각을 알려줘. 날짜를 말하지 않으면 크리스마스 당일로 잡을게.'
        elif state['question']:
            message = state['question']
        elif self.invitation:
            message = f'{self.invitation.conditions.region}에서 들를 만한 곳 {len(self.invitation.stops)}곳을 골랐어. 봉투를 열어 코스를 확인해 봐.'
            if self.invitation.revalidation_required:
                message += ' 실제 보행 시간은 지도에서 한 번 더 확인해 줘.'
        else:
            message = self.stop_reason
        warnings = state['notices'] + state['errors']
        if not self.invitation:
            warnings += state['exclusions']
        return {'result': ChatResult(message=message, conditions=state['conditions'], plan=self.invitation,
                                     warnings=warnings, replans=state['attempt'])}


def extend_unique(existing, new):
    existing.extend(value for value in new if value not in existing)
