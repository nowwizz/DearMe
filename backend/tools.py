from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
import math
import re
from typing import Callable, Literal
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree

import requests
from pydantic import BaseModel, Field, ValidationError

from .config import KST, setting, timestamp
from .models import Leg, PlacePhoto, Point, Weather


TOUR = 'https://apis.data.go.kr/B551011/KorService2'
TOUR_SOURCE = 'https://www.data.go.kr/data/15101578/openapi.do'
TMAP = 'https://apis.openapi.sk.com/tmap/routes/pedestrian'
TMAP_POI = 'https://apis.openapi.sk.com/tmap/pois'
TMAP_SOURCE = 'https://tmapapi.tmapmobility.com/terms.html'
STATION_RADIUS_M = 1200
STATION_TOKEN = re.compile(
    r'(?<![가-힣0-9])(?P<station>[가-힣0-9]{2,24}역)(?=$|[^가-힣0-9]|근처|주변|부근|에서|으로|까지|부터|이야|이에요|으로|쪽|에)'
)
STATION_LINE = r'(?:\d{1,2}호선|신분당선|분당선|수인분당선|경의중앙선|경춘선|경강선|서해선|공항철도|KTX|SRT)'
METEO = 'https://archive-api.open-meteo.com/v1/archive'
METEO_SOURCE = 'https://open-meteo.com/en/docs/historical-weather-api'
CATEGORIES = {12: '관광지', 14: '문화시설', 15: '행사', 38: '쇼핑', 39: '음식점'}
CUISINE_CODES = {'한식': 'FD010100', '중식': 'FD020100', '일식': 'FD020200', '양식': 'FD020300'}
CHAIN_CAFE_PREFIXES = (
    '스타벅스', 'starbucks', '투썸플레이스', '투썸', 'atwosomeplace', 'twosomeplace',
    '이디야', 'ediya', '메가mgc커피', '메가커피', 'megamgccoffee', 'megacoffee',
    '컴포즈커피', 'composecoffee', '빽다방', 'paikscoffee', '더벤티', 'theventi',
    '할리스', 'hollys', '커피빈', 'thecoffeebean', 'coffeebean', '탐앤탐스', 'tomntoms',
    '폴바셋', 'paulbassett', '파스쿠찌', 'pascucci', '엔제리너스', 'angelinus',
    '카페베네', 'caffebene', '커피베이', 'coffeebay', '요거프레소', 'yogerpresso',
    '매머드커피', '매머드익스프레스', 'mammothcoffee', '메머드커피', '커피에반하다',
    '감성커피', '드롭탑', 'dalcomm', '달콤커피', '바나프레소', 'banapresso',
    '더리터', '하삼동커피', '텐퍼센트커피', '텐퍼센트스페셜티커피', '10percentcoffee',
    '카페봄봄', '카페051', '읍천리382', '블루샥', '블루보틀', 'bluebottle',
    '아티제', 'artisee', '공차', 'gongcha', '설빙', 'sulbing', '카페인중독', '카페게이트', 'cafegate',
    '랑데자뷰', '커피스미스', '커피명가', '뚜레쥬르', '파리바게뜨', '파리바게트',
)
CHAIN_CAFE_DESCRIPTION = re.compile(r'(?:프[랜렌]차이즈|체인)\s*(?:카페|커피\s*(?:전문점|매장))|'
                                    r'(?:카페|커피\s*전문점)\s*(?:프[랜렌]차이즈|체인점)')
NON_CHAIN_DESCRIPTION = re.compile(r'(?:비\s*프[랜렌]차이즈|프[랜렌]차이즈\s*(?:카페\s*)?[이가]?\s*아니)')
REGIONS = {
    '서울': ('11', None), '종로': ('11', '110'), '중구': ('11', '140'),
    '명동': ('11', '140'), '마포': ('11', '440'), '홍대': ('11', '440'),
    '성수': ('11', '200'), '강남': ('11', '680'), '송파': ('11', '710'),
    '김포': ('41', '570'),
    '동탄': ('41', '590'),  # TourAPI lists Dongtan venues under Hwaseong.
    '부산': ('26', None), '대구': ('27', None), '인천': ('28', None),
    '광주': ('29', None), '대전': ('30', None), '제주': ('50', None),
}
DISTRICT_NAMES = {
    ('11', '110'): ('종로구',), ('11', '140'): ('중구',),
    ('11', '200'): ('성동구',), ('11', '440'): ('마포구',),
    ('11', '680'): ('강남구',), ('11', '710'): ('송파구',),
    ('41', '570'): ('김포시',), ('41', '590'): ('화성시', '화성특례시'),
}
PROVINCE_NAMES = {codes[0]: label for label, codes in REGIONS.items() if codes[1] is None}
PROVINCE_NAMES['41'] = '경기'
LOCALITY_HINTS = {
    '성수': ('성수', '서울숲', '연무장', '성덕정', '뚝섬로'),
    '홍대': ('홍대', '서교동', '동교동', '와우산로', '어울마당로', '홍익로'),
    '명동': ('명동', '남대문로2가', '충무로1가', '충무로2가'),
    '동탄': ('동탄', '반송동', '석우동', '능동', '영천동', '청계동', '오산동', '산척동',
           '석정동', '목동', '송동', '신동', '장지동', '방교동', '지산', '노작로'),
}
WEATHER_FIELDS = ('temperature_2m', 'apparent_temperature', 'precipitation', 'wind_speed_10m')
MESSAGES = {
    'MISSING_API_KEY': '서버 환경변수에 공급자 API 키를 설정해 주세요.',
    'AUTH_FAILED': 'API 키와 서비스 사용 승인을 확인해 주세요.',
    'RATE_LIMITED': '외부 서비스 호출 한도에 도달했어요.',
    'TIMEOUT': '외부 서비스 응답 시간이 초과됐어요.',
    'INVALID_INPUT': '조회에 필요한 입력을 확인해 주세요.',
    'NO_RESULT': '조회 조건에 맞는 결과가 없어요.',
    'AMBIGUOUS_STATION': '같은 이름의 역이 여러 곳 있어요. 도시나 호선을 같이 알려 주세요.',
    'MISSING_REQUIRED_ATTRIBUTE': '제약 판단에 필요한 정보가 응답에 없어요.',
    'UPSTREAM_ERROR': '외부 서비스 응답을 처리할 수 없어요.',
}


class Failure(Exception):
    pass


class SearchArgs(BaseModel):
    region: str = Field(min_length=1, max_length=160)
    target_date: date | None = None
    keyword: str | None = Field(None, min_length=1, max_length=100)
    category: int | None = None
    center: Point | None = None
    radius_m: int = Field(1500, ge=100, le=20000)
    page: int = Field(1, ge=1, le=10)
    provider: Literal['tour', 'tmap_cafes', 'tmap_station', 'tmap_restaurants'] = 'tour'


class DetailArgs(BaseModel):
    content_id: str = Field(pattern=r'^[0-9]{1,18}$')
    content_type_id: int


class RouteArgs(BaseModel):
    start: Point
    end: Point
    start_name: str = Field(min_length=1, max_length=160)
    end_name: str = Field(min_length=1, max_length=160)


class WeatherArgs(BaseModel):
    point: Point
    target_date: date
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    years: int = Field(5, ge=5, le=10)


class Candidate(BaseModel):
    content_id: str
    content_type_id: int
    name: str
    address: str
    point: Point
    food_kind: Literal['cafe', 'restaurant'] | None = None
    provider: Literal['tour', 'tmap'] = 'tour'
    district_address: str | None = None
    cuisine: str | None = None


class SearchData(BaseModel):
    candidates: list[Candidate]
    requested_date: date | None
    consulted_on: date
    coverage: str


class DetailData(BaseModel):
    content_id: str
    content_type_id: int
    category: str
    description: str | None = None
    menu: str | None = None
    hours: str | None = None
    closure: str | None = None
    admission: int | None = None
    fee_note: str | None = None
    missing: list[str]
    source_url: str
    photo: PlacePhoto | None = None


class ToolError(BaseModel):
    code: str
    message: str


class ToolMeta(BaseModel):
    source: str
    fetched_at: str
    warnings: list[str]


class ToolResult(BaseModel):
    ok: bool
    data: SearchData | DetailData | Leg | Weather | None
    error: ToolError | None
    meta: ToolMeta


@dataclass(frozen=True)
class Tool:
    description: str
    args: type[BaseModel]
    output: type[BaseModel]
    source: str
    live: Callable
    kind: str = 'external'


def get_key(name):
    value = setting(name)
    if not value:
        raise Failure('MISSING_API_KEY')
    return value


def request(method, url, **kwargs):
    result = requests.request(method, url, timeout=(3, 7), allow_redirects=False, **kwargs)
    if not 200 <= result.status_code < 300:
        errors = {400: 'INVALID_INPUT', 401: 'AUTH_FAILED', 403: 'AUTH_FAILED', 429: 'RATE_LIMITED'}
        raise Failure(errors.get(result.status_code, 'UPSTREAM_ERROR'))
    return result


def tour_items(operation, **params):
    key = unquote(get_key('TOUR_API_KEY'))
    response = request('GET', f'{TOUR}/{operation}', params={
        'serviceKey': key, 'MobileOS': 'ETC', 'MobileApp': 'DearMe', '_type': 'json', **params,
    })
    try:
        data = response.json()
    except ValueError:
        code = ElementTree.fromstring(response.content).findtext('.//returnReasonCode')
        data = {'OpenAPI_ServiceResponse': {'cmmMsgHeader': {'returnReasonCode': code}}}
    payload = data.get('response') or {}
    gateway = data.get('OpenAPI_ServiceResponse') or {}
    code = payload.get('header', {}).get('resultCode')
    if code is None:
        code = gateway.get('cmmMsgHeader', {}).get('returnReasonCode')
    code = str(code).strip()
    if code.isdecimal():
        code = code.lstrip('0').zfill(2)
    if code != '00':
        errors = {'03': 'NO_RESULT', '10': 'INVALID_INPUT', '11': 'INVALID_INPUT',
                  '20': 'AUTH_FAILED', '22': 'RATE_LIMITED', '23': 'RATE_LIMITED',
                  '29': 'AUTH_FAILED', '30': 'AUTH_FAILED', '31': 'AUTH_FAILED'}
        raise Failure(errors.get(code, 'UPSTREAM_ERROR'))
    items = payload.get('body', {}).get('items') or {}
    rows = items.get('item') or []
    return [rows] if isinstance(rows, dict) else rows


def validate_point(point):
    lon, lat = point
    if not (math.isfinite(lon) and -180 <= lon <= 180 and math.isfinite(lat) and -90 <= lat <= 90):
        raise Failure('INVALID_INPUT')


def plain(raw):
    if raw is None:
        return None
    body = unescape(str(raw))
    body = re.sub(r'<br\s*/?>', '\n', body, flags=re.I)
    body = re.sub(r'<[^>]*>', '', body).strip()
    return body or None


def gap_m(a, b):
    lon_scale = math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * lon_scale, a[1] - b[1]) * 111_195


def is_chain_cafe(name, description=''):
    normalized = re.sub(r'[^가-힣a-z0-9]', '', name.casefold())
    if normalized.startswith(CHAIN_CAFE_PREFIXES):
        return True
    return bool(CHAIN_CAFE_DESCRIPTION.search(description) and not NON_CHAIN_DESCRIPTION.search(description))


def station_name(region):
    if not region:
        return None
    return next((match['station'] for match in STATION_TOKEN.finditer(region)
                 if not match['station'].endswith(('지역', '구역', '권역', '번역', '영역'))), None)


def resolve_region(region):
    matched = [(label, codes) for label, codes in REGIONS.items() if label in region]
    province = next((codes[0] for _, codes in matched if not codes[1]), None)
    return max((entry for entry in matched if not province or entry[1][0] == province),
               key=lambda entry: (bool(entry[1][1]), entry[0] in LOCALITY_HINTS, len(entry[0])),
               default=(None, None))


def address_matches_region(region, address, district_address=None):
    if not address:
        return False
    region_words = region.split()
    if not region_words:
        return False
    label, codes = resolve_region(region)
    area = address.split()
    if not area:
        return False
    if codes:
        if not area[0].startswith(PROVINCE_NAMES[codes[0]]):
            return False
        districts = DISTRICT_NAMES.get(codes)
        if districts and (len(area) < 2 or area[1] not in districts):
            return False
        reported = (district_address or '').split()
        if len(reported) >= 2 and (not reported[0].startswith(PROVINCE_NAMES[codes[0]])
                                  or districts and reported[1] not in districts):
            return False
        if not districts and region_words[-1].endswith(('구', '군', '동')) and region_words[-1] not in area[1:4]:
            return False
    else:
        return region_words[-1] in address or region_words[-1] in (district_address or '')
    locality = LOCALITY_HINTS.get(label, ())
    return not locality or any(hint in address or hint in (district_address or '') for hint in locality)


def search_live(args):
    if args.provider == 'tmap_station':
        return search_tmap_station(args)
    if args.provider == 'tmap_cafes':
        return search_tmap_food(args, cafes=True)
    if args.provider == 'tmap_restaurants':
        return search_tmap_food(args, cafes=False)
    params = {'numOfRows': 10, 'pageNo': args.page}
    if args.center:
        validate_point(args.center)
    if args.category:
        params['contentTypeId'] = args.category
    _, area = resolve_region(args.region)
    around_station = bool(station_name(args.region))
    if around_station and not args.center:
        raise Failure('INVALID_INPUT')
    festival = args.category == 15 and args.target_date is not None
    cafe = args.category == 39 and args.keyword == '카페' and bool(args.center or area)
    cuisine = CUISINE_CODES.get(args.keyword) if args.category == 39 and args.center else None
    if cafe:
        params.update(lclsSystm1='FD', lclsSystm2='FD05', lclsSystm3='FD050100', numOfRows=25)
    if cuisine:
        params.update(lclsSystm1='FD', lclsSystm2=cuisine[:4], lclsSystm3=cuisine, numOfRows=15)
    day = args.target_date.strftime('%Y%m%d') if args.target_date else ''
    if args.center and not festival and (not args.keyword or cafe or cuisine):
        lon, lat = args.center
        params.update(mapX=lon, mapY=lat, radius=args.radius_m, arrange='S')
        operation = 'locationBasedList2'
    else:
        if area:
            params['lDongRegnCd'] = area[0]
            if area[1] and not around_station:
                params['lDongSignguCd'] = area[1]
        if festival:
            del params['contentTypeId']
            params.update(eventStartDate=(args.target_date - timedelta(days=28)).strftime('%Y%m%d'),
                          eventEndDate=day, numOfRows=30)
            operation = 'searchFestival2'
        elif not cafe and (args.keyword or not area):
            params['keyword'] = args.keyword or re.sub(r'^(?:서울(?:특별시)?|부산(?:광역시)?)\s+', '', args.region)
            if args.keyword == '카페' and not area:
                params['keyword'] = f'{args.region} 카페'
            operation = 'searchKeyword2'
        else:
            operation = 'areaBasedList2'
    candidates = []
    for row in tour_items(operation, **params):
        try:
            name, address = plain(row.get('title')), plain(row.get('addr1'))
            if not name or not address or (not around_station and not address_matches_region(args.region, address)):
                continue
            point = float(row['mapx']), float(row['mapy'])
            validate_point(point)
            if args.center and gap_m(args.center, point) > args.radius_m:
                continue
            kind = int(row['contenttypeid'])
            if kind == 15:
                starts, ends = (str(row.get(field) or '') for field in ('eventstartdate', 'eventenddate'))
                if not day or not re.fullmatch(r'\d{8}', starts) or not re.fullmatch(r'\d{8}', ends) or not starts <= day <= ends:
                    continue
            if not re.fullmatch(r'[0-9]{1,18}', str(row.get('contentid'))):
                continue
            classification = row.get('lclsSystm3')
            food_kind = None
            if kind == 39:
                if is_chain_cafe(name):
                    continue
                if classification == 'FD050100' or row.get('cat3') == 'A05020900':
                    food_kind = 'cafe'
                elif classification:
                    food_kind = 'restaurant'
            candidates.append(Candidate(content_id=str(row['contentid']), content_type_id=kind,
                                        name=name, address=address, point=point, food_kind=food_kind,
                                        cuisine=next((label for label, code in CUISINE_CODES.items()
                                                      if code == classification), None)))
        except (ValueError, TypeError, KeyError, Failure):
            continue
    if not candidates:
        raise Failure('NO_RESULT')
    today = datetime.now(KST).date()
    return SearchData(candidates=candidates, requested_date=args.target_date, consulted_on=today,
                      coverage='현재 TourAPI 등록 정보로 조회했어요. 희망일 행사 일정과 특별 운영은 별도 확인이 필요해요.')


def tmap_pois(params):
    response = request('GET', TMAP_POI, params={'version': 1, 'reqCoordType': 'WGS84GEO',
                       'resCoordType': 'WGS84GEO', 'multiPoint': 'Y', **params},
                       headers={'appKey': get_key('TMAP_APP_KEY'), 'Accept': 'application/json'})
    rows = (response.json()['searchPoiInfo'].get('pois') or {}).get('poi') or []
    return [rows] if isinstance(rows, dict) else rows


def tmap_address(row):
    roads = (row.get('newAddressList') or {}).get('newAddress') or []
    if isinstance(roads, dict):
        roads = [roads]
    district = ' '.join(filter(None, (plain(row.get(key)) for key in
                        ('upperAddrName', 'middleAddrName', 'lowerAddrName'))))
    road = plain(roads[0].get('fullAddressRoad')) if roads else None
    return road or ' '.join(filter(None, (district, plain(row.get('firstNo'))))), district


def search_tmap_station(args):
    name = station_name(args.region)
    if not name:
        raise Failure('INVALID_INPUT')
    qualifier = re.search(STATION_LINE, args.region, re.I)
    province = next((label for label, codes in REGIONS.items()
                     if codes[1] is None and args.region.startswith(label + ' ')), None)
    keyword = f'{province} {name}' if province else name
    matches = []
    for row in tmap_pois({'searchKeyword': keyword, 'count': 24}):
        try:
            label = plain(row.get('name')) or ''
            kind = ' '.join(str(row.get(key) or '') for key in ('middleBizName', 'lowerBizName', 'detailBizName'))
            if re.split(r'\s*[\[(]', label, maxsplit=1)[0] != name:
                continue
            if not any(category in kind for category in ('지하철역', '철도역', '전철역', '기차역')):
                continue
            if qualifier and not re.search(r'(?<!\d)' + re.escape(qualifier[0]), label + ' ' + kind, re.I):
                continue
            address, district = tmap_address(row)
            if not address or province and not address_matches_region(province, address, district):
                continue
            point = float(row.get('noorLon') or row['frontLon']), float(row.get('noorLat') or row['frontLat'])
            validate_point(point)
            matches.append(Candidate(content_id='tmap:station', content_type_id=0, name=name, address=address,
                                     point=point, provider='tmap', district_address=district or None))
        except (ValueError, TypeError, KeyError, Failure):
            continue
    if not matches:
        raise Failure('NO_RESULT')
    if any(gap_m(matches[0].point, row.point) > 400 for row in matches[1:]):
        raise Failure('AMBIGUOUS_STATION')
    return SearchData(candidates=matches[:1], requested_date=args.target_date, consulted_on=datetime.now(KST).date(),
                      coverage=f'역을 기준으로 반경 {STATION_RADIUS_M / 1000:g}km 안에서 장소를 골랐어요.')


def search_tmap_food(args, cafes):
    region = args.region.strip()
    if not region:
        raise Failure('INVALID_INPUT')
    around_station = bool(station_name(region))
    if around_station and not args.center:
        raise Failure('INVALID_INPUT')
    keyword = '카페' if cafes else args.keyword
    if not keyword or not cafes and not args.center:
        raise Failure('INVALID_INPUT')
    params = {'searchKeyword': f'{region} {keyword}', 'count': 35 if cafes else 20}
    if args.center:
        validate_point(args.center)
        params.update(searchKeyword=keyword, centerLon=args.center[0], centerLat=args.center[1],
                      radius=math.ceil(args.radius_m / 1000), searchtypCd='R')
    candidates = []
    for row in tmap_pois(params):
        try:
            name = plain(row.get('name'))
            category = ' '.join(filter(None, (plain(row.get(key)) for key in
                                              ('middleBizName', 'lowerBizName', 'detailBizName'))))
            cafe_type = any(word in (category.strip() or name) for word in ('카페', '커피', '찻집'))
            restaurant_type = any(word in category for word in (*CUISINE_CODES, '음식점', '음식', '레스토랑'))
            matches_type = cafe_type if cafes else restaurant_type and not cafe_type
            if not name or not matches_type or is_chain_cafe(name, category if cafes else ''):
                continue
            address, district = tmap_address(row)
            point = float(row.get('pnsLon') or row['frontLon']), float(row.get('pnsLat') or row['frontLat'])
            validate_point(point)
            if not around_station and not address_matches_region(region, address, district):
                continue
            if args.center and gap_m(args.center, point) > args.radius_m:
                continue
            id = str(row.get('id') or '').strip()
            if not id or not address:
                continue
            candidates.append(Candidate(content_id=f'tmap:{id}', content_type_id=39, name=name[:160],
                                        address=address, point=point, food_kind='cafe' if cafes else 'restaurant',
                                        provider='tmap', district_address=district or None,
                                        cuisine=next((label for label in CUISINE_CODES if label in category), None)))
        except (ValueError, TypeError, KeyError, Failure):
            continue
    if not candidates:
        raise Failure('NO_RESULT')
    kind = '카페' if cafes else '식당'
    return SearchData(candidates=candidates, requested_date=args.target_date, consulted_on=datetime.now(KST).date(),
                      coverage=f'TMAP에서 {kind} 후보를 보충했어요. 운영 시간과 휴무는 방문 전에 확인해 주세요.')


def exact_fee(text):
    if not text:
        return None
    text = re.sub(r'\s+', '', text)
    if text in {'무료', '무료입장', '입장무료'}:
        return 0
    matched = re.fullmatch(r'(?:입장료[:：]?)?([0-9][0-9,]*)원', text)
    return int(matched[1].replace(',', '')) if matched else None


def details_live(args):
    with ThreadPoolExecutor(max_workers=2) as pool:
        common = pool.submit(tour_items, 'detailCommon2', contentId=args.content_id)
        intro = pool.submit(tour_items, 'detailIntro2', contentId=args.content_id,
                            contentTypeId=args.content_type_id)
        base_rows, intro_rows = common.result(), intro.result()
    if not base_rows or not intro_rows:
        raise Failure('NO_RESULT')
    base, intro = base_rows[0], intro_rows[0]
    if any(str(row.get('contentid')) != args.content_id for row in (base, intro)):
        raise Failure('MISSING_REQUIRED_ATTRIBUTE')
    keymap = {
        12: ('usetime', 'restdate', 'admissionfee'),
        14: ('usetimeculture', 'restdateculture', 'usefee'),
        15: ('playtime', '', 'usetimefestival'),
        38: ('opentime', 'restdateshopping', ''),
        39: ('opentimefood', 'restdatefood', ''),
    }
    hour_key, close_key, fee_key = keymap.get(args.content_type_id, ('', '', ''))
    hours, closure = plain(intro.get(hour_key)), plain(intro.get(close_key))
    fee = plain(intro.get(fee_key))
    admission = exact_fee(fee)
    missing = [name for name, value in [('hours', hours), ('closure', closure), ('admission', admission)] if value is None]
    return DetailData(content_id=args.content_id, content_type_id=args.content_type_id,
                      category=CATEGORIES.get(args.content_type_id, '기타'), description=plain(base.get('overview')),
                      menu=plain(intro.get('firstmenu')) if args.content_type_id == 39 else None,
                      hours=hours, closure=closure, admission=admission, fee_note=fee, missing=missing,
                      photo=tour_photo(base),
                      source_url=f'https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid={quote(str(base["cotid"]))}'
                      if base.get('cotid') else TOUR_SOURCE)


def tour_photo(base):
    license_type = {'Type1': 1, 'Type3': 3}.get(base.get('cpyrhtDivCd'))
    if not license_type:
        return None
    main = tour_image_url(base.get('firstimage'))
    thumbnail = tour_image_url(base.get('firstimage2'))
    if not (main or thumbnail):
        return None
    return PlacePhoto(url=main or thumbnail, thumbnail_url=thumbnail, license_type=license_type)


def tour_image_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        image = urlsplit(value.strip())
        host = image.hostname or ''
    except ValueError:
        return None
    if (image.scheme not in ('https', 'http') or not host.endswith('.visitkorea.or.kr')
            or image.netloc != host or not image.path):
        return None
    return urlunsplit(('https', host, image.path, image.query, ''))


def route_live(args):
    validate_point(args.start)
    validate_point(args.end)
    if args.start == args.end:
        raise Failure('INVALID_INPUT')
    response = request('POST', TMAP, params={'version': 1}, headers={'appKey': get_key('TMAP_APP_KEY')}, json={
        'startX': args.start[0], 'startY': args.start[1], 'endX': args.end[0], 'endY': args.end[1],
        'startName': args.start_name, 'endName': args.end_name,
        'reqCoordType': 'WGS84GEO', 'resCoordType': 'WGS84GEO',
    }).json()
    features = response.get('features') or []
    if not features:
        raise Failure('NO_RESULT')
    props = features[0].get('properties') or {}
    lines = [item['geometry']['coordinates'] for item in features
             if item.get('geometry', {}).get('type') == 'LineString'
             and len(item['geometry'].get('coordinates', [])) >= 2]
    seconds, distance = int(props.get('totalTime') or 0), int(props.get('totalDistance') or 0)
    if not lines or seconds <= 0 or distance <= 0:
        raise Failure('MISSING_REQUIRED_ATTRIBUTE')
    for line in lines:
        for point in line:
            validate_point(point)
    return Leg(origin=args.start_name, destination=args.end_name, distance_m=distance, seconds=seconds, lines=lines)


def year_weather(year, args):
    lon, lat = args.point
    hourly = request('GET', METEO, params={
        'latitude': lat, 'longitude': lon, 'start_date': f'{year}-12-20', 'end_date': f'{year}-12-26',
        'hourly': ','.join(WEATHER_FIELDS), 'timezone': 'Asia/Seoul',
    }).json().get('hourly') or {}
    offsets = {value: offset for offset, value in enumerate(hourly.get('time') or [])}
    sample = {}
    for field in WEATHER_FIELDS:
        series = hourly.get(field) or []
        readings = []
        for day in range(20, 27):
            for hour in range(args.start_hour, args.end_hour):
                index = offsets.get(f'{year}-12-{day}T{hour:02d}:00')
                if index is not None and index < len(series):
                    value = series[index]
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        readings.append(value)
        sample[field] = readings
    return sample


def weather_live(args):
    validate_point(args.point)
    if args.start_hour >= args.end_hour:
        raise Failure('INVALID_INPUT')
    today = datetime.now(KST).date()
    year = min(args.target_date.year, today.year)
    if year == today.year and today < date(year, 12, 26) + timedelta(days=7):
        year -= 1
    years = list(range(year - args.years + 1, year + 1))
    with ThreadPoolExecutor(max_workers=5) as pool:
        probes = list(pool.map(lambda item: safe_weather_year(item, args), years))
    samples = [sample for sample, _ in probes if sample is not None]
    if not samples:
        raise Failure(next((code for _, code in probes if code), 'NO_RESULT'))
    combined = {field: [value for sample in samples for value in sample[field]] for field in WEATHER_FIELDS}
    temp, apparent, precip, wind = (combined[field] for field in WEATHER_FIELDS)
    if not temp and not apparent:
        raise Failure('NO_RESULT')
    if not temp or not apparent:
        raise Failure('MISSING_REQUIRED_ATTRIBUTE')
    expected = args.years * 7 * (args.end_hour - args.start_hour)
    guide = '보온 이너, 두꺼운 외투, 장갑을 준비하고 실내에서 몸을 녹이는 시간을 넣어보세요.' if min(apparent) < 0 \
        else '겹쳐 입을 옷과 바람을 막을 외투를 준비해 보세요.'
    if precip and max(precip) > 0:
        guide += ' 접이식 우산과 미끄럼이 적은 신발도 챙겨보세요.'
    return Weather(temperature=(min(temp), max(temp)), apparent=(min(apparent), max(apparent)),
                   precipitation_max=max(precip) if precip else None, wind_max=max(wind) if wind else None,
                   years=[y for y, (sample, _) in zip(years, probes) if sample and any(sample.values())],
                   period=f'12월 20~26일 {args.start_hour:02d}:00~{args.end_hour:02d}:00 (KST)',
                   missing={field: expected - len(values) for field, values in combined.items()},
                   guide=guide, source_url=METEO_SOURCE)


def safe_weather_year(year, args):
    try:
        return year_weather(year, args), None
    except requests.Timeout:
        return None, 'TIMEOUT'
    except Failure as error:
        return None, str(error)
    except (requests.RequestException, TypeError, ValueError, AttributeError):
        return None, 'UPSTREAM_ERROR'


TOOLS = {
    'search_places': Tool('지역, 취향, 활동에 맞는 방문 후보가 필요할 때 먼저 조회하세요. 장소 식별자와 좌표를 반환합니다.',
                          SearchArgs, SearchData, TOUR_SOURCE, search_live),
    'get_place_details': Tool('후보 식별자를 확보한 뒤 방문 시간, 휴무, 요금 근거를 확인해야 할 때 선택하세요.',
                               DetailArgs, DetailData, TOUR_SOURCE, details_live),
    'get_walking_route': Tool('출발 및 도착 좌표가 정해진 구간의 실제 보행 시간과 경로가 필요할 때 선택하세요.',
                               RouteArgs, Leg, TMAP_SOURCE, route_live),
    'get_christmas_weather': Tool('장소 좌표와 활동 시간대를 확보한 뒤 과거 크리스마스 날씨로 준비물을 안내할 때 선택하세요.',
                                  WeatherArgs, Weather, METEO_SOURCE, weather_live),
}


def schema(name, description, args):
    return {'type': 'function', 'name': name, 'description': description,
            'parameters': args.model_json_schema(), 'strict': False}


def call_tool(name, arguments, demo=False):
    tool = TOOLS.get(name)
    if not tool:
        return failure('INVALID_INPUT', ToolMeta(source='Tool 등록부', fetched_at=timestamp(), warnings=[]))
    meta = ToolMeta(source='로컬 검증용 데이터' if demo else tool.source, fetched_at=timestamp(), warnings=[])
    try:
        args = tool.args.model_validate(arguments)
    except ValidationError:
        return failure('INVALID_INPUT', meta)
    if not demo and isinstance(args, SearchArgs) and args.provider != 'tour':
        meta.source = TMAP_SOURCE
    try:
        if demo:
            from .fixtures import DEMO_TOOLS
            raw = DEMO_TOOLS[name](args)
        else:
            raw = tool.live(args)
        data = tool.output.model_validate(raw)
        if isinstance(data, SearchData):
            meta.warnings.append(data.coverage)
        if isinstance(data, DetailData) and data.missing:
            meta.warnings.append('미확인 속성: ' + ', '.join(data.missing))
        if isinstance(data, Weather) and any(data.missing.values()):
            meta.warnings.append('일부 참고 연도 또는 시간대의 자료가 비어 있어요.')
        return ToolResult(ok=True, data=data, error=None, meta=meta)
    except Failure as exc:
        return failure(str(exc), meta)
    except requests.Timeout:
        return failure('TIMEOUT', meta)
    except (requests.RequestException, ElementTree.ParseError, AttributeError, KeyError, IndexError, TypeError, ValueError):
        return failure('UPSTREAM_ERROR', meta)


def failure(code, meta):
    return ToolResult(ok=False, data=None, error=ToolError(code=code, message=MESSAGES[code]), meta=meta)
