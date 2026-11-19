"""Reproduce the PDF scenarios with explicit synthetic data and export sanitized evidence."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from unittest.mock import patch
from datetime import date, time

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.models import Conditions, Invitation
from backend.planning import choose_candidates
from backend.storage import durable_copy
from backend.tools import STATION_RADIUS_M, Candidate, DetailData, ToolMeta, call_tool, failure


PROMPT = '크리스마스에 종로에서 오후 2시부터 6시까지 혼자 조용한 전시와 카페에 가고 싶어. 도보는 {}분 이내, 재즈가 좋아.'


def chat(client, message, *, session=None, mode='demo'):
    started = monotonic()
    accepted = client.post('/api/chat', json={'message': message, 'session_id': session, 'mode': mode})
    assert accepted.status_code == 202, accepted.text
    reference = accepted.json()
    for _ in range(400):
        response = client.get('/api/chat/' + reference['run_id'])
        assert response.status_code == 200
        run = response.json()
        if run['status'] != 'running':
            assert run['status'] == 'complete', run['events']
            assert [event['sequence'] for event in run['events']] == list(range(1, len(run['events']) + 1))
            assert run['events'][-1]['event_type'] == 'run_completed'
            return {'prompt': message, 'elapsed_ms': round((monotonic() - started) * 1000), **run}
        sleep(.015)
    raise AssertionError('Run did not complete')


def tools():
    for name in ('search_places', 'get_place_details', 'get_walking_route', 'get_christmas_weather'):
        result = call_tool(name, {}, True)
        assert not result.ok and result.error.code == 'INVALID_INPUT'
    assert call_tool('unknown', {}).error.code == 'INVALID_INPUT'
    demo_search = call_tool('search_places', {'region': '종로'}, True)
    assert demo_search.ok and demo_search.data.requested_date is None and demo_search.data.consulted_on
    nonexistent = call_tool('search_places', {'region': '없는곳'}, True)
    assert nonexistent.error.code == 'NO_RESULT'
    required_detail = call_tool('get_place_details', {'content_id': '9999', 'content_type_id': 14}, True)
    assert required_detail.error.code == 'NO_RESULT'
    first = {'name': '신촌역[수도권2호선]', 'lowerBizName': '지하철역', 'detailBizName': '2호선',
             'upperAddrName': '서울', 'middleAddrName': '마포구', 'frontLon': '126.93697', 'frontLat': '37.55513'}
    second = {**first, 'name': '신촌역[경의중앙선]', 'detailBizName': '경의중앙선',
              'middleAddrName': '서대문구', 'frontLon': '126.94269', 'frontLat': '37.55974'}
    with patch('backend.tools.tmap_pois', return_value=[first, second]):
        ambiguous = call_tool('search_places', {'region': '신촌역', 'provider': 'tmap_station'})
        assert not ambiguous.ok and ambiguous.error.code == 'AMBIGUOUS_STATION'
        selected = call_tool('search_places', {'region': '신촌역 2호선', 'provider': 'tmap_station'})
        assert selected.ok and selected.data.candidates[0].point == (126.93697, 37.55513)
    near = {'contentid': '1', 'contenttypeid': '39', 'title': '근처 카페', 'addr1': '서울 서초구 서초대로 400',
            'mapx': 127.0271, 'mapy': 37.4984}
    far = {**near, 'contentid': '2', 'title': '먼 카페', 'mapx': 127.034, 'mapy': 37.52}
    chain = {**near, 'contentid': '3', 'title': '메가 MGC 커피 강남역점'}
    with patch('backend.tools.tour_items', return_value=[chain, near, far]):
        nearby = call_tool('search_places', {'region': '강남역', 'center': (127.028, 37.498),
                           'radius_m': STATION_RADIUS_M, 'category': 39})
        assert nearby.ok and [item.content_id for item in nearby.data.candidates] == ['1']
    tmap_cafe = {'id': '10', 'name': '작은 로스터리 역삼점', 'lowerBizName': '카페',
                 'upperAddrName': '서울', 'middleAddrName': '강남구', 'frontLon': '127.0282', 'frontLat': '37.4982'}
    with patch('backend.tools.tmap_pois', return_value=[
        {**tmap_cafe, 'id': '11', 'name': 'COMPOSE COFFEE 강남역점'},
        {**tmap_cafe, 'id': '12', 'name': '미등록 브랜드', 'detailBizName': '프랜차이즈 카페'}, tmap_cafe
    ]):
        nearby = call_tool('search_places', {'region': '강남역', 'center': (127.028, 37.498),
                                            'radius_m': STATION_RADIUS_M, 'provider': 'tmap_cafes'})
        assert nearby.ok and [item.content_id for item in nearby.data.candidates] == ['tmap:10']
    candidates = [
        Candidate(content_id='1', content_type_id=39, name='가까운 감자탕', address='예시', point=(127.028, 37.498),
                  food_kind='restaurant', cuisine='한식'),
        Candidate(content_id='2', content_type_id=39, name='비스트로', address='예시', point=(127.030, 37.499),
                  food_kind='restaurant', cuisine='양식'),
        Candidate(content_id='3', content_type_id=39, name='카페', address='예시', point=(127.0281, 37.4981), food_kind='cafe'),
    ]
    details = {item.content_id: DetailData(content_id=item.content_id, content_type_id=39,
               category='음식점', hours='11:00~22:00', missing=[], source_url='') for item in candidates}
    dinner = Conditions(date=date(2026, 12, 25), start=time(19), end=time(22), activities=['식사', '카페'])
    for food, expected in ((None, ['2', '3']), ('감자탕', ['1', '3'])):
        order, _ = choose_candidates(candidates, details, dinner.model_copy(update={'food': food}), set())
        assert [item.content_id for item in order] == expected
    details['3'].description = '프랜차이즈 카페입니다.'
    order, _ = choose_candidates(candidates, details, dinner, set())
    assert not order


def injected_weather_failure(name, args, demo):
    if name == 'get_christmas_weather':
        return failure('TIMEOUT', ToolMeta(source='로컬 검증용 데이터', fetched_at='2026-11-18T00:00:00Z', warnings=[]))
    return call_tool(name, args, demo)


def verify(path):
    tools()
    app = create_app(path / 'scenarios.sqlite3')
    with TestClient(app) as client:
        normal = chat(client, PROMPT.format(30))
        result = normal['result']
        plan = result['plan']
        assert result['replans'] == 0 and len(plan['stops']) == 4
        assert any(stop['category'] == '문화시설' for stop in plan['stops'])
        assert plan['walking_seconds'] == sum(leg['seconds'] for leg in plan['legs'])
        assert plan['weather'] and plan['mode'] == 'demo'
        target = next(stop for stop in plan['stops'] if stop['category'] == '카페')
        assert target['admission'] is None
        ids = {item for event in normal['events'] if event['tool_name'] == 'search_places' and event['sanitized_output']
               for item in event['sanitized_output']['candidate_ids']}
        assert set(stop['id'] for stop in plan['stops']) <= ids
        assert all(event['sanitized_input']['candidate_id'] in ids for event in normal['events']
                   if event['tool_name'] == 'get_place_details' and event['event_type'] == 'tool_requested')
        durable = durable_copy(Invitation.model_validate({**plan, 'mode': 'live'}))
        assert not durable.legs and durable.walking_seconds is None and durable.revalidation_required
        assert all(stop.arrives is None for stop in durable.stops)
        replan = chat(client, PROMPT.format(10))
        assert replan['result']['replans'] >= 1 and replan['result']['plan']['walking_seconds'] <= 600
        assert replan['result']['plan']['stops'][1]['name'] == '눈꽃 다과점'
        assert len([e for e in replan['events'] if e['tool_name'] == 'get_place_details'
                    and e['event_type'] == 'tool_requested']) == len(ids)
        capped = chat(client, PROMPT.format(1))
        assert capped['result']['replans'] == 3 and not capped['result']['plan']
        assert len([event for event in capped['events'] if event['event_type'] == 'replan_requested']) == 3

        greeting = chat(client, '안녕하세요.')
        assert not [event for event in greeting['events'] if event['tool_name'] or event['stage'] == 'plan']
        missing = chat(client, '오후 6시 전에는 끝나야 해.')
        assert '시작 시각' in missing['result']['message'] and not missing['result']['plan']
        assert missing['result']['conditions']['end'] == '18:00:00'
        followup = chat(client, '같은 조건에서 친구랑 가는 걸로 바꿔 줘.', session=normal['session_id'])
        before, after = result['conditions'], followup['result']['conditions']
        assert after['companion'] == '친구'
        assert all(after[key] == value for key, value in before.items() if key not in {'companion', 'party_size'})

        budget = chat(client, PROMPT.format(30) + ' 총예산은 3만원이야.')
        assert budget['result']['plan']['budget_remaining'] == 30000
        assert '보류' in budget['result']['plan']['checks']['예산']

        with patch.dict('os.environ', {'TOUR_API_KEY': '', 'TMAP_APP_KEY': '', 'GMS_KEY': ''}):
            no_station = chat(client, PROMPT.format(30), mode='live')
            assert '역 이름' in no_station['result']['message'] and no_station['result']['plan'] is None
            assert not any(event['tool_name'] for event in no_station['events'])
            live = chat(client, '종로3가역', session=no_station['session_id'], mode='live')
        assert live['result']['conditions']['region'] == '종로3가역'
        assert live['result']['conditions']['walking_limit'] == 30
        assert live['result']['replans'] == 0 and any(event['error_code'] == 'MISSING_API_KEY' for event in live['events'])

        first = client.post('/api/plans', json={'run_id': normal['run_id']})
        second = client.post('/api/plans', json={'run_id': replan['run_id']})
        assert first.status_code == second.status_code == 201
        a, b = first.json(), second.json()
        assert len(b['overlaps']) == 1 and b['overlaps'][0]['id'] == a['id']
        assert client.get('/api/plans/' + b['id']).json()['plan']['legs']
        assert len(client.get('/api/plans').json()) == 2
        modified = client.patch('/api/plans/' + b['id'], json={'start': '15:00', 'stops': [
            {'name': '변경한 장소', 'stay_minutes': 30}
        ]}).json()
        assert modified['revalidation_required'] and modified['stops'] == ['변경한 장소'] and not modified['plan']['legs']
        assert client.patch('/api/plans/' + b['id'], json={'end': '14:00'}).status_code == 422
        assert client.delete('/api/plans/' + b['id']).status_code == 204
        assert client.get('/api/plans/' + b['id']).status_code == 404
        assert len(client.get('/api/plans').json()) == 1

        summaries = client.get('/api/logs').json()
        assert next(row for row in summaries if row['session_id'] == normal['session_id'])['run_count'] == 2
        detail = client.get('/api/logs/' + normal['session_id']).json()
        assert {event['session_id'] for event in detail['events']} == {normal['session_id']}
        assert client.patch('/api/logs/' + normal['session_id'], json={}).status_code == 405
        assert client.delete('/api/logs/' + normal['session_id']).status_code == 204
        assert not client.get('/api/logs/' + normal['session_id']).json()['events']
        assert client.get('/api/logs/' + replan['session_id']).json()['events']
        assert client.get('/api/tools').status_code == 200
        assert client.get('/docs').status_code == 200

    with TestClient(create_app(path / 'logger-off.sqlite3', logging_enabled=False)) as client:
        result = chat(client, PROMPT.format(30))
        assert result['result']['plan'] and not client.get('/api/logs').json()
        late = chat(client, '12/25, 서울 종로, 13:00, 24:00')
        assert late['result']['conditions']['end'] == '00:00:00'
        lunch, afternoon, dinner, evening_cafe = late['result']['plan']['stops']
        assert (lunch['meal'], dinner['meal']) == ('점심', '저녁')
        assert afternoon['category'] == evening_cafe['category'] == '카페'
        assert lunch['arrives'] < afternoon['arrives'] < dinner['arrives'] < evening_cafe['arrives']
        assert client.post('/api/plans', json={'run_id': late['run_id']}).status_code == 201
        full_day = chat(client, '12/25, 종로, 13~22시')['result']['plan']
        assert len(full_day['stops']) == 4 and len(full_day['legs']) == 3
        assert [stop['meal'] for stop in full_day['stops']] == ['점심', None, '저녁', None]
        assert sum(stop['category'] == '카페' for stop in full_day['stops']) == 2
        assert all(leg['seconds'] <= 1800 for leg in full_day['legs'])
        evening = chat(client, '종로, 19:00, 22:00')
        assert evening['result']['conditions']['date'].endswith('-12-25')
        stops = evening['result']['plan']['stops']
        assert len(stops) == 2 and [stop['meal'] for stop in stops if stop['meal']] == ['저녁']
        assert stops[0]['meal'] == '저녁' and stops[0]['arrives'] == '19:00'
        companion = next(stop for stop in stops if not stop['meal'])
        assert companion['category'] in {'카페', '행사'}
    with TestClient(create_app(path / 'logger-failure.sqlite3')) as client:
        with patch('backend.storage.Store.append', side_effect=OSError('simulated failure')):
            result = chat(client, '안녕하세요.')
        assert result['result']['message'] and not client.get('/api/logs').json()
    with TestClient(create_app(path / 'failure.sqlite3', tool_runner=injected_weather_failure)) as client:
        partial = chat(client, PROMPT.format(30))
        assert partial['result']['plan'] and partial['result']['plan']['weather'] is None
        assert any(event['error_code'] == 'TIMEOUT' for event in partial['events'])
    return {'normal': normal, 'replan': replan, 'capped': capped, 'tool_failure': partial, 'no_tool': greeting}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', type=Path)
    arguments = parser.parse_args()
    with TemporaryDirectory() as folder, patch.dict('os.environ', {'MAX_REPLANS': '3', 'LOGGING_ENABLED': 'true'}):
        outcomes = verify(Path(folder))
    if arguments.export:
        arguments.export.mkdir(parents=True, exist_ok=True)
        for title, value in outcomes.items():
            (arguments.export / f'{title}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                                                           encoding='utf-8')
    print('PASS: API, Tool schemas and validation, 5 scenarios, session memory, logger isolation, plan CRUD/overlap.')
    for name, run in outcomes.items():
        print(f'{name}: {run["elapsed_ms"]}ms, {len(run["events"])} events, {run["result"]["replans"]} replans')
