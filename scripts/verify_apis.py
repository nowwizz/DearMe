"""Run the PDF's domain acceptance probes without exposing credentials or raw responses."""

import concurrent.futures
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv


TOUR_URL = 'https://apis.data.go.kr/B551011/KorService2'
WEATHER_URL = 'https://archive-api.open-meteo.com/v1/archive'
TMAP_URL = 'https://apis.openapi.sk.com/tmap/routes/pedestrian'
WEATHER_FIELDS = ('temperature_2m', 'apparent_temperature', 'precipitation', 'wind_speed_10m')
KST = timezone(timedelta(hours=9))


class ProbeFailure(Exception):
    pass


def required(name):
    value = os.getenv(name, '').strip()
    if not value:
        code = 'MISSING_API_KEY' if name.endswith(('API_KEY', 'APP_KEY')) or name == 'GMS_KEY' else 'MISSING_CONFIG'
        raise ProbeFailure(code)
    return value


def probe(action):
    try:
        return {'ok': True, 'data': action()}
    except ProbeFailure as exc:
        code = str(exc)
    except requests.Timeout:
        code = 'TIMEOUT'
    except requests.RequestException:
        code = 'NETWORK_ERROR'
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, ElementTree.ParseError):
        code = 'INVALID_RESPONSE'
    return {'ok': False, 'error': code}


def fetch(method, url, *, decode=None, **kwargs):
    response = requests.request(method, url, timeout=(5, 15), allow_redirects=False, **kwargs)
    failure = {400: 'INVALID_INPUT', 401: 'AUTH_FAILED', 403: 'AUTH_FAILED', 429: 'RATE_LIMITED'}
    if not 200 <= response.status_code < 300:
        raise ProbeFailure(failure.get(response.status_code, 'UPSTREAM_ERROR'))
    return decode(response) if decode else response.json()


def decode_tour(response):
    try:
        payload = response.json()
    except ValueError:
        code = ElementTree.fromstring(response.content).findtext('.//returnReasonCode')
        if not code:
            raise ProbeFailure('INVALID_RESPONSE') from None
    else:
        gateway = payload.get('OpenAPI_ServiceResponse')
        if not gateway:
            return payload['response']
        code = gateway['cmmMsgHeader']['returnReasonCode']
    return {'header': {'resultCode': code}}


def tour_items(endpoint, **params):
    key = unquote(required('TOUR_API_KEY'))
    common = {'serviceKey': key, 'MobileOS': 'ETC', 'MobileApp': 'DearMeValidation', '_type': 'json'}
    payload = fetch('GET', f'{TOUR_URL}/{endpoint}', decode=decode_tour, params={**common, **params})
    code = str(payload['header']['resultCode']).strip()
    if code.isdecimal():
        code = code.lstrip('0').zfill(2)
    if code != '00':
        provider_errors = {'20': 'AUTH_FAILED', '22': 'RATE_LIMITED', '23': 'RATE_LIMITED',
                           '29': 'AUTH_FAILED', '30': 'AUTH_FAILED', '31': 'AUTH_FAILED',
                           '10': 'INVALID_INPUT', '11': 'INVALID_INPUT', '03': 'NO_RESULT'}
        raise ProbeFailure(provider_errors.get(code, 'UPSTREAM_ERROR'))
    items = payload['body'].get('items') or {}
    rows = items.get('item') or []
    if not rows:
        raise ProbeFailure('NO_RESULT')
    return [rows] if isinstance(rows, dict) else rows


def coordinates(candidate):
    longitude, latitude = float(candidate['mapx']), float(candidate['mapy'])
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ProbeFailure('INVALID_RESPONSE')
    return longitude, latitude


def search_tour():
    rows = tour_items('searchKeyword2', keyword='경복궁', contentTypeId=12, numOfRows=10, pageNo=1)
    usable = [row for row in rows if all(row.get(field) for field in
              ('contentid', 'contenttypeid', 'title', 'mapx', 'mapy', 'addr1'))]
    if not usable:
        raise ProbeFailure('MISSING_REQUIRED_ATTRIBUTE')
    origin = next((row for row in usable if row['title'] == '경복궁'), usable[0])
    coordinates(origin)
    return origin, len(usable)


def inspect_tour_detail(candidate):
    content_id = str(candidate['contentid'])
    common = tour_items('detailCommon2', contentId=content_id)
    intro = tour_items('detailIntro2', contentId=content_id, contentTypeId=candidate['contenttypeid'])
    if any(str(rows[0].get('contentid')) != content_id for rows in (common, intro)):
        raise ProbeFailure('CANDIDATE_ID_MISMATCH')
    info = {**common[0], **intro[0]}
    fields = ('overview', 'usetime', 'restdate', 'expguide', 'parking')
    present = [field for field in fields if str(info.get(field) or '').strip()]
    if not {'usetime', 'restdate'}.intersection(present):
        raise ProbeFailure('MISSING_REQUIRED_ATTRIBUTE')
    return {'matched_candidate_id': True, 'present_fields': present,
            'unavailable_fields': sorted(set(fields) - set(present)),
            'mentions_fee_field': any('fee' in key.lower() and value for key, value in info.items())}


def inspect_route(start=(126.9769, 37.5759), end=(126.9799, 37.5788)):
    key = required('TMAP_APP_KEY')
    payload = {'startX': start[0], 'startY': start[1], 'endX': end[0], 'endY': end[1],
               'startName': '출발', 'endName': '도착', 'reqCoordType': 'WGS84GEO',
               'resCoordType': 'WGS84GEO'}
    response = fetch('POST', TMAP_URL, params={'version': 1}, headers={'appKey': key}, json=payload)
    features = response.get('features') or []
    if not features:
        raise ProbeFailure('NO_RESULT')
    totals = features[0].get('properties') or {}
    has_line = any(feature['geometry']['type'] == 'LineString' and
                   len(feature['geometry']['coordinates']) >= 2 for feature in features)
    if not has_line or any(float(totals.get(key) or 0) <= 0 for key in ('totalTime', 'totalDistance')):
        raise ProbeFailure('MISSING_REQUIRED_ATTRIBUTE')
    return {'distance_available': True, 'duration_available': True, 'line_available': True}


def inspect_weather():
    today = datetime.now(KST).date()
    # Leave room for the historical archive's publication delay.
    last_year = today.year if today >= date(today.year, 12, 26) + timedelta(days=7) else today.year - 1
    years = list(range(last_year - 4, last_year + 1))
    values = {field: [] for field in WEATHER_FIELDS}
    missing = dict.fromkeys(WEATHER_FIELDS, 0)
    for year in years:
        first, last = date(year, 12, 20), date(year, 12, 26)
        result = fetch('GET', WEATHER_URL, params={
            'latitude': 37.57, 'longitude': 126.98, 'start_date': first.isoformat(),
            'end_date': last.isoformat(), 'hourly': ','.join(WEATHER_FIELDS), 'timezone': 'Asia/Seoul',
        })['hourly']
        timestamps = result.get('time') or []
        if not timestamps:
            raise ProbeFailure('NO_RESULT')
        offsets = {datetime.fromisoformat(value): i for i, value in enumerate(timestamps)}
        for day in range(7):
            for hour in range(14, 18):
                index = offsets.get(datetime.combine(first + timedelta(days=day), time(hour)))
                for field in WEATHER_FIELDS:
                    series = result.get(field) or []
                    value = series[index] if index is not None and index < len(series) else None
                    if isinstance(value, (int, float)):
                        values[field].append(value)
                    else:
                        missing[field] += 1
    if any(not samples for samples in values.values()):
        raise ProbeFailure('MISSING_REQUIRED_ATTRIBUTE')
    return {'years': years, 'window_kst': '12-20 through 12-26, 14:00–18:00',
            'expected_per_field': len(years) * 7 * 4, 'missing_counts': missing,
            'ranges': {field: [min(samples), max(samples)] for field, samples in values.items()}}


def inspect_llm():
    key = required('GMS_KEY')
    base = required('GMS_BASE_URL').rstrip('/')
    url = urlparse(base)
    if url.scheme != 'https' or not url.hostname or url.username or url.query or url.fragment:
        raise ProbeFailure('INVALID_CONFIG')
    model = required('GMS_MODEL')
    tools = [{
        'type': 'function',
        'name': 'search_places', 'description': 'Select when a user asks for place candidates.',
        'parameters': {'type': 'object', 'properties': {'keyword': {'type': 'string'}},
                       'required': ['keyword'], 'additionalProperties': False},
    }]
    response = fetch('POST', base + '/responses', headers={'Authorization': f'Bearer {key}'},
                     json={'model': model, 'tool_choice': 'auto', 'tools': tools, 'store': False,
                           'input': '경복궁 관광 후보를 검색해 줘.'})
    for item in response['output']:
        if item.get('type') == 'function_call' and item.get('name') == 'search_places':
            keyword = json.loads(item['arguments']).get('keyword')
            if isinstance(keyword, str) and keyword.strip():
                return {'received_llm_response': True, 'selected_search_places_with_keyword': True}
    raise ProbeFailure('TOOL_NOT_SELECTED')


def inspect_tour_chain():
    search = probe(search_tour)
    if not search['ok']:
        return {'tour_search': search,
                'tour_details': {'ok': False, 'error': 'SEARCH_REQUIRED'}}
    origin, count = search['data']
    return {'tour_search': {'ok': True, 'data': {'usable_candidate_count': count}},
            'tour_details': probe(lambda: inspect_tour_detail(origin))}


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    started_at = datetime.now(KST).isoformat(timespec='seconds')
    checks = {'tmap_route': inspect_route, 'open_meteo': inspect_weather, 'llm_and_tool_choice': inspect_llm}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tour = pool.submit(inspect_tour_chain)
        futures = {name: pool.submit(probe, check) for name, check in checks.items()}
        results = {**tour.result(), **{name: future.result() for name, future in futures.items()}}
    passed = all(result['ok'] for result in results.values())
    print(json.dumps({'started_at_kst': started_at, 'api_checks_passed': passed, 'checks': results}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
