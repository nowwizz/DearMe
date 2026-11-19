from datetime import datetime, timedelta
from itertools import combinations, permutations
import re
from urllib.parse import urlencode

from .conversation import ACTIVITIES
from .models import Invitation, Song, Stop, end_minutes
from .tools import STATION_RADIUS_M, gap_m, is_chain_cafe, station_name


TERMS = {
    '카페': ('카페', '커피', '찻집', '다과', '디저트', '베이커리', '케이크', '티룸'),
    '식사': ('식당', '식사', '음식점', '요리', '브런치', '레스토랑'),
    '실내': ('실내', '전시', '미술관', '박물관', '도서관', '카페', '찻집'),
    '야외': ('야외', '산책로', '정원', '공원'),
}
WEEKDAYS = '월화수목금토일'
CLOCK = r'([01]?\d|2[0-3]):([0-5]\d)'
STAY = {14: 50, 39: 40, 12: 35, 15: 45, 38: 30}
WALK_BUFFER = 5
MAX_WALK_LEG_MINUTES = 30
BUILDING_ADDRESS = re.compile(r'([가-힣A-Za-z\d·]+(?:대로|로|길|동|리|가))\s+(?:산\s*)?(\d+(?:-\d+)?)')
MEAL_WINDOWS = (('점심', 11 * 60 + 30, 14 * 60 + 30), ('저녁', 17 * 60 + 30, 22 * 60))
CUISINE_TERMS = {
    '양식': ('서양식', '양식', '이탈리안', '이탈리아', '프렌치', '프랑스', '파스타', '스테이크', '비스트로', '리조또'),
    '일식': ('일식', '일본식', '초밥', '스시', '오마카세', '가이세키', '사시미'),
    '한식': ('한식', '한정식', '감자탕', '국밥', '불고기'),
    '중식': ('중식', '중국식', '짜장', '딤섬', '마라'),
}
SNACKS = {'디저트', '케이크', '커피', '허브차', '홍차'}


def course_minutes(conditions):
    return end_minutes(conditions.end) - (conditions.start.hour * 60 + conditions.start.minute)


def target_stops(conditions):
    duration = course_minutes(conditions)
    meals = meal_slots(conditions)
    if meals:
        other = len(set(conditions.activities or []) - {'식사'})
        extras = max(1, other, 2 if duration >= 240 else 1, cafe_target(conditions))
        return min(4, len(meals) + extras)
    return 4 if duration >= 235 else 3 if duration >= 150 else 2 if duration >= 80 else 1


def meal_slots(conditions):
    avoided = set(conditions.avoids or [])
    if avoided & {'식사', '식당', '음식점', '밥집', '맛집'}:
        return []
    start = conditions.start.hour * 60 + conditions.start.minute
    end = end_minutes(conditions.end) - WALK_BUFFER
    slots = [(name, max(start, opens), min(end, closes)) for name, opens, closes in MEAL_WINDOWS
             if name not in avoided and min(end, closes) - max(start, opens) >= STAY[39]]
    if not slots and '식사' in (conditions.activities or []) and not avoided & {'점심', '저녁'}:
        return [('식사', start, end)]
    return slots


def cafe_target(conditions):
    if '카페' in (conditions.avoids or []):
        return 0
    meals = meal_slots(conditions)
    if len(meals) == 2 and course_minutes(conditions) >= 360:
        return 2
    return int(bool(meals) or '카페' in (conditions.activities or []))


def course_priority(categories, meals, meal_goal, cafe_goal):
    meal_count = sum(meal is not None for meal in meals)
    extras = categories.count('카페')
    if cafe_goal == 1 and meal_goal == 1 and '행사' in categories:
        extras = max(1, extras)
    afternoon = False
    spread = False
    if '점심' in meals and '저녁' in meals:
        lunch, dinner = meals.index('점심'), meals.index('저녁')
        afternoon = '카페' in categories[lunch + 1:dinner]
        spread = afternoon and '카페' in categories[dinner + 1:]
    return meal_count, min(extras, cafe_goal), len(categories), int(afternoon), int(spread)


def invitation_priority(invitation):
    conditions = invitation.conditions
    return course_priority([stop.category for stop in invitation.stops], [stop.meal for stop in invitation.stops],
                           len(meal_slots(conditions)), cafe_target(conditions))


def meal_terms(conditions):
    food = conditions.food
    if food and food not in SNACKS:
        return (food,)
    return ('양식', '일식')


def cuisine_for(cuisine, text):
    return cuisine or next((kind for kind, words in CUISINE_TERMS.items() if any(word in text for word in words)), None)


def dining_fit(conditions, cuisine, text):
    food = conditions.food
    if food and food not in SNACKS:
        return 4 if food == cuisine or food in text else 0
    if cuisine in ('양식', '일식'):
        return 3 + int(any(word in text for word in ('비스트로', '코스', '오마카세', '스테이크', '파스타')))
    return int(any(word in text for word in ('한정식', '코스', '다이닝', '룸', '기념일')))


def building_address(address):
    match = BUILDING_ADDRESS.search(address or '')
    return match.groups() if match else None


def same_building(a, b):
    a_key, b_key = building_address(a.address), building_address(b.address)
    if a_key and b_key:
        return a_key == b_key
    return bool(a.point and b.point and gap_m(a.point, b.point) < 28)


def building_repeats(stops):
    return sum(same_building(a, b) for a, b in combinations(stops, 2))


def dining_rank(priority, slots, visits, fit, repeats):
    targets = {meal: start for meal, start, _ in slots}
    delay = sum(max(0, (minute - targets[meal] - 12) // 10 + 1) for meal, minute in visits if meal)
    preferred = sum(score >= 3 for score, _ in fit)
    quality = sum(score * 3 + int(access == 'verified') for score, access in fit)
    return (priority[0], -delay, *priority[1:3], preferred, -repeats, quality, *priority[3:])


def invitation_rank(invitation):
    meals = [stop for stop in invitation.stops if stop.meal]
    times = [(stop.meal, int(stop.arrives[:2]) * 60 + int(stop.arrives[3:5])) for stop in meals]
    fit = [(dining_fit(invitation.conditions, stop.cuisine, ' '.join(
        filter(None, (stop.name, stop.description, stop.menu)))), stop.access) for stop in meals]
    return dining_rank(invitation_priority(invitation), meal_slots(invitation.conditions), times, fit,
                       building_repeats(invitation.stops))


def estimated_seconds(distance_m):
    return round(distance_m * 1.35 / 1.15)


def evidence(candidate, detail):
    return ' '.join(filter(None, (candidate.name, detail.category, detail.description, detail.menu, candidate.cuisine))).lower()


def matches(activity, candidate, detail):
    definition = ACTIVITIES.get(activity)
    text = evidence(candidate, detail)
    if activity in ('카페', '식사'):
        cafe = candidate.food_kind == 'cafe' if candidate.food_kind else any(word in text for word in TERMS['카페'])
        return detail.content_type_id == 39 and cafe == (activity == '카페')
    if definition:
        return detail.content_type_id == definition[0]
    return bool(re.search(re.escape(activity), text, re.I))


def is_indoor(candidate, detail):
    text = evidence(candidate, detail)
    if any(word in text for word in TERMS['야외']) and not any(word in text for word in TERMS['실내']):
        return False
    if any(word in text for word in TERMS['실내']) or detail.content_type_id == 39:
        return True
    return None


def preference(candidate, detail, conditions):
    inside = is_indoor(candidate, detail)
    text = evidence(candidate, detail)
    score = sum(bool(value and value in text) for value in (conditions.food, conditions.mood))
    if conditions.indoor == 'mostly_outdoor':
        return score + (2 if inside is False else 0)
    if conditions.indoor == 'mostly_indoor' or conditions.cold_sensitive:
        return score + (2 if inside is True else -2 if inside is False else 0)
    return score


def schedule_visits(order, details, seconds, origin, started, slots, restaurant_ids):
    cursor = started
    day_start = started.replace(hour=0, minute=0)
    meal_index = 0
    visits = []
    for index, item in enumerate(order):
        if index or origin:
            cursor += timedelta(seconds=seconds[index if origin else index - 1])
        stay = STAY.get(item.content_type_id, 35)
        detail = details[item.content_id]
        meal = None
        if item.content_id in restaurant_ids:
            while meal_index < len(slots):
                name, from_minute, to_minute = slots[meal_index]
                meal_index += 1
                arrives = max(cursor, day_start + timedelta(minutes=from_minute))
                leaves = arrives + timedelta(minutes=stay)
                if leaves <= day_start + timedelta(minutes=to_minute) and opening_status(detail, arrives, leaves) != 'closed':
                    cursor = arrives
                    meal = name
                    break
            if meal is None:
                return [], f'{item.name} · 이용할 수 있는 식사 시간대 안에 들르기 어려워요.'
        leaves = cursor + timedelta(minutes=stay)
        access = opening_status(detail, cursor, leaves)
        if access == 'closed':
            return [], f'{item.name} · 도착~체류 시간이 공개 이용 조건과 맞지 않아요.'
        visits.append((item, cursor, leaves, stay, access, meal))
        cursor = leaves
    return visits, None


def choose_candidates(candidates, details, conditions, tried, origin=None, long_legs=()):
    allowed, exclusions = [], []
    for candidate in candidates:
        if candidate.content_id in {row.content_id for row in allowed}:
            continue
        if origin and candidate.content_id == origin.content_id:
            continue
        detail = details.get(candidate.content_id)
        if not detail:
            exclusions.append(f'{candidate.name} · 상세 조건 미확인')
            continue
        if candidate.content_type_id == 39 and is_chain_cafe(
            candidate.name, (detail.description or '') if matches('카페', candidate, detail) else ''
        ):
            exclusions.append(f'{candidate.name} · 프랜차이즈 카페')
            continue
        text = evidence(candidate, detail)
        trigger = next((word for word in conditions.avoids or [] if word not in ('점심', '저녁') and
                        (word.lower() in text or any(term in text for term in TERMS.get(word, ())))), None)
        if trigger:
            exclusions.append(f'{candidate.name} · 피하고 싶은 조건 {trigger}')
            continue
        allowed.append(candidate)
    activities = conditions.activities or []
    slots = meal_slots(conditions)
    minimum = max(1, len(activities))
    desired = max(minimum, target_stops(conditions))
    length_limit = conditions.walking_limit * 60 * 1.15 if conditions.walking_limit is not None else float('inf')
    max_leg = min(MAX_WALK_LEG_MINUTES * 60 * 1.15, length_limit)
    meal_goal, cafe_goal = len(slots), cafe_target(conditions)
    place_activity = {item.content_id: frozenset(index for index, activity in enumerate(activities)
                       if matches(activity, item, details[item.content_id])) for item in allowed}
    types = {item.content_id: '카페' if matches('카페', item, details[item.content_id]) else item.content_type_id
             for item in allowed}
    restaurant_ids = {id for id, kind in types.items() if kind == 39}
    meal_scores = {}
    for item in allowed:
        if item.content_id in restaurant_ids:
            text = evidence(item, details[item.content_id])
            meal_scores[item.content_id] = dining_fit(conditions, cuisine_for(item.cuisine, text), text)
    if not slots:
        allowed = [item for item in allowed if item.content_id not in restaurant_ids]
    scores = {item.content_id: preference(item, details[item.content_id], conditions) for item in allowed}
    endpoints = [*allowed, *([origin] if origin else [])]
    distances = {(a.content_id, b.content_id): gap_m(a.point, b.point) for a in endpoints for b in allowed}
    colocated = {frozenset((a.content_id, b.content_id)) for a, b in combinations(allowed, 2) if same_building(a, b)}
    started = datetime.combine(conditions.date, conditions.start)
    duration = course_minutes(conditions)
    best = None
    for count in range(desired, minimum - 1, -1):
        for order in permutations(allowed, count):
            key = tuple(item.content_id for item in order)
            if key in tried:
                continue
            meal_count = sum(item in restaurant_ids for item in key)
            if meal_count > meal_goal or best and meal_count < -best[0][0]:
                continue
            if len(frozenset().union(*(place_activity[item] for item in key))) != len(activities):
                continue
            sequence = (origin.content_id, *key) if origin else key
            links = list(zip(sequence, sequence[1:]))
            if any(link in long_legs for link in links):
                continue
            gaps = [distances[link] for link in links]
            if any(distance > max_leg for distance in gaps) or sum(gaps) > length_limit:
                continue
            stays = [STAY.get(item.content_type_id, 35) for item in order]
            seconds = [estimated_seconds(distance) for distance in gaps]
            if sum(stays) + sum(seconds) / 60 + WALK_BUFFER > duration:
                continue
            visits, failure = schedule_visits(order, details, seconds, origin, started, slots, restaurant_ids)
            if failure or (visits[-1][2] - started).total_seconds() / 60 + WALK_BUFFER > duration:
                continue
            mix = {types[item] for item in key}
            priority = course_priority(['행사' if types[item] == 15 else types[item] for item in key],
                                       [visit[-1] for visit in visits], meal_goal, cafe_goal)
            times = [(meal, arrives.hour * 60 + arrives.minute) for _, arrives, _, _, _, meal in visits if meal]
            fit = [(meal_scores[item.content_id], access) for item, _, _, _, access, meal in visits if meal]
            repeats = sum(frozenset(pair) in colocated for pair in combinations(key, 2)) if colocated else 0
            dining = dining_rank(priority, slots, times, fit, repeats)
            culture_first = tuple(min(place_activity[item], default=len(activities)) for item in key)
            rank = (*(-value for value in dining), -len(mix),
                    sum(gaps) - 50 * sum(scores[item] for item in key), culture_first)
            if best is None or rank < best[0]:
                best = (rank, order)
        if best and best[0][:4] == (-meal_goal, 0, -cafe_goal, -desired):
            break
    return (list(best[1]) if best else []), exclusions


def opening_status(detail, arrived, left):
    hours, closure = detail.hours or '', detail.closure or ''
    compact = re.sub(r'\s+', '', closure)
    day = WEEKDAYS[arrived.weekday()]
    holiday = (arrived.month, arrived.day) == (12, 25)
    if day + '요일' in compact and re.fullmatch(r'(?:매주)?[월화수목금토일]요일(?:휴무|휴관)?', compact):
        return 'closed'
    if holiday and re.fullmatch(r'(?:매주)?(?:공휴일|성탄절|크리스마스)(?:휴무|휴관)?', compact):
        return 'closed'
    simple = re.fullmatch(r'\s*' + CLOCK + r'\s*[-~–～]\s*' + CLOCK + r'\s*', hours)
    if not simple:
        return 'unknown'
    if detail.content_type_id != 15 and compact not in {'연중무휴', '없음', '휴무없음'} and not re.fullmatch(
            r'(?:매주)?[월화수목금토일]요일(?:휴무|휴관)?', compact):
        return 'unknown'
    start_h, start_m, end_h, end_m = map(int, simple.groups())
    opens = arrived.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    closes = arrived.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if closes <= opens:
        return 'unknown'
    return 'verified' if opens <= arrived and left <= closes else 'closed'


def make_songs(conditions):
    tracks = {
        'jazz': [('Christmas Time Is Here', 'Vince Guaraldi Trio', '느긋하게 겨울 오후를 시작하기 좋아요.'),
                 ('The Christmas Song', 'Nat King Cole', '따뜻한 목소리가 잠깐 쉬는 시간에 어울려요.'),
                 ('Let It Snow! Let It Snow! Let It Snow!', 'Ella Fitzgerald', '가벼운 스윙으로 산책에 리듬을 더해요.')],
        'classic': [('The Nutcracker: Dance of the Sugar Plum Fairy', 'Pyotr Ilyich Tchaikovsky', '반짝이는 겨울 풍경에 어울려요.'),
                    ('Winter (The Four Seasons)', 'Antonio Vivaldi', '겨울 공기의 생동감을 느낄 수 있어요.'),
                    ('Clair de lune', 'Claude Debussy', '해가 진 뒤 하루를 차분하게 마무리하기 좋아요.')],
        'pop': [('Last Christmas', 'Wham!', '익숙한 멜로디로 크리스마스 기분을 더해요.'),
                ('Snowman', 'Sia', '차분한 겨울 오후에 어울리는 팝이에요.'),
                ('Underneath the Tree', 'Kelly Clarkson', '하루의 마지막에 기분을 밝게 끌어올려요.')],
        'indie': [('Christmas Lights', 'Coldplay', '도시의 겨울 불빛을 바라보며 듣기 좋아요.'),
                  ('River', 'Joni Mitchell', '고요한 휴식 시간에 어울려요.'),
                  ('Sister Winter', 'Sufjan Stevens', '따뜻한 실내에서 듣기 좋은 겨울 포크예요.')],
    }
    taste = conditions.music or ''
    group = 'classic' if '클래식' in taste else 'indie' if any(key in taste for key in ('인디', '록')) \
        else 'pop' if any(key in taste for key in ('팝', '캐럴', '캐롤')) \
        else 'pop' if '북적' in (conditions.mood or '') and not taste else 'jazz'
    return [Song(title=title, artist=artist, reason=reason,
                 url='https://www.youtube.com/results?' + urlencode({'search_query': f'{title} {artist}'}))
            for title, artist, reason in tracks[group]]


def clock(value):
    if value.second or value.microsecond:
        value += timedelta(minutes=1)
    return value.strftime('%H:%M')


def assess(conditions, order, details, routes, weather, mode, origin, notices, exclusions):
    verified = routes is not None
    sequence = ([origin] if origin else []) + order
    seconds = [route.seconds for route in routes] if verified else [
        estimated_seconds(gap_m(a.point, b.point)) for a, b in zip(sequence, sequence[1:])]
    walking = sum(seconds)
    started = datetime.combine(conditions.date, conditions.start)
    deadline = datetime.combine(conditions.date, datetime.min.time()) + timedelta(minutes=end_minutes(conditions.end))
    buffer = WALK_BUFFER
    stops, failures = [], []
    slots = meal_slots(conditions)
    restaurant_ids = {item.content_id for item in order if matches('식사', item, details[item.content_id])}
    visits, schedule_error = schedule_visits(order, details, seconds, origin, started, slots, restaurant_ids)
    if schedule_error or not visits:
        return None, [schedule_error or '공개 운영 시간에 맞는 방문 일정이 없어요.']
    for item, cursor, left, stay, access, meal in visits:
        detail = details[item.content_id]
        category = '카페' if matches('카페', item, detail) else detail.category
        reason = next((f'요청한 {activity} 활동을 담았어요.' for activity in conditions.activities or []
                       if matches(activity, item, detail)), '요청한 지역에서 조회한 방문 후보예요.')
        if meal:
            cuisine = cuisine_for(item.cuisine, evidence(item, detail))
            reason = f'{meal}에 들르는 {cuisine} 식당이에요.' if cuisine else f'{meal} 시간에 맞춰 들르는 식당이에요.'
            if detail.menu:
                menu = detail.menu.replace('\n', ' ').strip()
                if menu:
                    reason += f' 공개 대표 메뉴는 {menu[:90]}예요.'
        if (conditions.cold_sensitive or conditions.indoor == 'mostly_indoor') and is_indoor(item, detail):
            reason += ' 실내에서 쉬어갈 수 있어요.'
        stops.append(Stop(id=item.content_id, name=item.name, address=item.address, point=item.point,
                          category=category, description=detail.description, service_note=detail.fee_note,
                          source_url=detail.source_url, reason=reason, meal=meal, stay_minutes=stay, arrives=clock(cursor),
                          leaves=clock(left), hours=detail.hours, closure=detail.closure, access=access,
                          admission=detail.admission, provider=item.provider,
                          cuisine=cuisine if meal else None, menu=detail.menu if meal else None, photo=detail.photo))
    finish = visits[-1][2] + timedelta(minutes=buffer)
    if any(time > MAX_WALK_LEG_MINUTES * 60 for time in seconds):
        failures.append(f'한 번에 도보 {MAX_WALK_LEG_MINUTES}분 제한을 넘는 구간이 있어요.')
    if conditions.walking_limit is not None and walking > conditions.walking_limit * 60:
        failures.append(f'총 도보 {walking // 60}분 {walking % 60}초로 전체 {conditions.walking_limit}분 제한을 넘어요.')
    if finish > deadline:
        latest = deadline - (finish - started)
        failures.append(f'종료 시각을 넘겨요. 이 순서라면 늦어도 {latest:%m/%d %H:%M}에 출발해야 해요.')

    per_person = sum(stop.admission or 0 for stop in stops)
    known = per_person if conditions.budget_basis != 'total' else (
        per_person * conditions.party_size if conditions.party_size else 0)
    unit = '1인 입장료' if conditions.budget_basis != 'total' else (
        '일행 입장료 총액' if conditions.party_size else '인원 미확인')
    remaining = conditions.budget - known if conditions.budget is not None else None
    minimum_cost = per_person if not conditions.party_size and conditions.budget_basis == 'total' else known
    if conditions.budget is not None and conditions.budget_basis and minimum_cost > conditions.budget:
        failures.append(f'확인된 최소 입장료 {minimum_cost:,}원이 예산을 넘어요.')
    unknown_fee = any(stop.admission is None or stop.category in {'음식점', '카페', '쇼핑'} for stop in stops)
    if conditions.budget is not None and conditions.budget_basis == 'total' and not conditions.party_size and per_person:
        remaining = None
    if failures:
        return None, failures
    checks = {
        '종료 시각': '충족 · 제안 체류 시간과 여유 시간을 기준으로 계산했어요.' if verified else '예상 · 방문 및 이동 시간을 바탕으로 계산했어요.',
        '보행': f'각 구간 도보 {MAX_WALK_LEG_MINUTES}분 이내' if verified else
        '장소의 직선 거리를 바탕으로 시간을 추정했어요. 실제 보행 경로와 시간은 확인이 필요해요.',
        '이용 조건': '공개된 운영 시간 범위와 일치' if all(stop.access == 'verified' for stop in stops)
        else '일부 운영 시간 또는 휴무 정보는 현장 공지 확인이 필요해요.',
    }
    missing_meals = {slot[0] for slot in slots} - {stop.meal for stop in stops}
    if missing_meals:
        checks['식사'] = ', '.join(name for name, _, _ in slots if name in missing_meals) + ' 시간에 맞는 식당은 확인하지 못했어요.'
    if meal_terms(conditions) == ('양식', '일식') and any(stop.meal and stop.cuisine not in ('양식', '일식') for stop in stops):
        checks['식당 선택'] = '해당 시간과 도보 조건에 맞는 양식·일식 후보가 부족한 끼니는 다른 식당을 담았어요.'
    if conditions.budget is not None:
        checks['예산'] = '확인한 비용 외 항목이 있어 충족 여부를 보류했어요.' if (
            unknown_fee or remaining is None) else '공개된 입장료가 예산 이내예요.'
    elif unknown_fee:
        checks['비용'] = '일부 입장료 또는 현장 지출은 방문 전에 확인해 주세요.'
    if conditions.food and not any(conditions.food in evidence(item, details[item.content_id]) for item in order):
        checks['음식 선호'] = '선호 메뉴는 방문 전 직접 확인해 주세요.'
    if conditions.cold_sensitive and any(is_indoor(item, details[item.content_id]) is not True for item in order):
        checks['추위'] = '실내 여부가 확인되지 않은 장소가 있어요. 출발 전 운영 안내를 확인해 주세요.'
    if weather and weather.apparent[0] < 0 and walking > 0:
        checks['추운 날 대안'] = '야외 이동이 부담되면 대화에서 실내 위주와 더 짧은 보행 제한을 요청할 수 있어요.'
    name = conditions.name or '나'
    companion = conditions.companion
    letter = ('좋아하는 것들로 크리스마스 하루를 준비했어. ' +
              ('곁에 있는 사람과 따뜻한 장면을 하나씩 모아봐.' if companion and companion != '혼자'
               else '오늘은 네 속도로 걷고, 마음에 드는 순간에는 조금 더 오래 머물러도 좋아.'))
    if len(stops) < target_stops(conditions):
        checks['방문지 수'] = '요청한 시간과 보행 기준에서 확인한 장소만 담았어요.'
    if len(stops) > 1:
        checks['장소 구성'] = ('조건에 맞는 다른 건물의 후보가 부족해 같은 건물의 장소도 포함했어요.'
                           if building_repeats(stops) else '한 건물에 몰리지 않도록 서로 다른 장소를 골랐어요.')
    if cafe_target(conditions) == 2 and sum(stop.category == '카페' for stop in stops) < 2:
        checks['카페'] = '운영 시간과 도보 조건에 맞는 비프랜차이즈 카페 두 곳을 함께 찾지 못했어요.'
    if origin:
        origin_label = origin.name
    elif mode == 'live' and station_name(conditions.region):
        origin_label = f'{station_name(conditions.region)} 반경 {STATION_RADIUS_M / 1000:g}km · 첫 장소부터 일정 시작'
    else:
        origin_label = f'{order[0].name}에서 시작 · 첫 장소까지 이동 제외'
    return Invitation(title=f'{name}에게 도착한 크리스마스', letter=letter, conditions=conditions,
                      mode=mode, stops=stops, legs=routes or [], walking_seconds=walking if verified else None,
                      finishes=clock(finish), buffer_minutes=buffer, known_cost=known, cost_basis=unit,
                      budget_remaining=remaining, weather=weather, songs=make_songs(conditions), checks=checks,
                      warnings=notices, exclusions=exclusions, revalidation_required=not verified,
                      origin_label=origin_label), []
