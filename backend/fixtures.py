"""Synthetic Seoul-like examples for offline use and deterministic verification."""

from datetime import datetime
from math import hypot

from .config import KST
from .models import Leg, Weather
from .tools import Candidate, DetailData, Failure, SearchData


PLACES = [
    ('101', 14, '겨울빛 전시관', (126.975, 37.578), '겨울 풍경을 담은 조용한 실내 전시 공간이에요.'),
    ('102', 39, '온기 찻집', (126.988, 37.575), '따뜻한 차와 디저트를 즐길 수 있는 실내 공간이에요.'),
    ('103', 39, '눈꽃 다과점', (126.978, 37.578), '전시관 근처에서 차와 작은 디저트로 쉬어가기 좋아요.'),
    ('104', 14, '작은 종이 도서관', (126.981, 37.578), '종이 작품을 만나는 실내 독립 전시 공간이에요.'),
    ('105', 12, '별빛 정원', (126.986, 37.574), '야외 산책로를 한 바퀴 둘러볼 수 있어요.'),
    ('106', 14, '종로역', (126.984, 37.571), '출발 지점으로만 사용하는 예시 역이에요.'),
    ('107', 39, '겨울 한상 식당', (126.976, 37.577), '따뜻한 한식 정식을 내는 예시 식당이에요.'),
    ('108', 39, '별빛 저녁 식당', (126.979, 37.577), '겨울 저녁에 수프와 요리를 즐길 수 있는 예시 음식점이에요.'),
    ('109', 15, '성탄 작은 마켓', (126.981, 37.577), '크리스마스 저녁에 열리는 예시 행사예요.'),
]


def search(args):
    if not any(token in args.region for token in ('종로', '서울')):
        raise Failure('NO_RESULT')
    rows = [Candidate(content_id=id, content_type_id=category, name=name, address='서울 종로구 (예시)',
                      point=point) for id, category, name, point, _ in PLACES
            if (args.category is None or category == args.category)
            and (not args.keyword or args.keyword in name)
            and (id != '109' or args.target_date and (args.target_date.month, args.target_date.day) == (12, 25))
            and (id != '106' or args.keyword)]
    if not rows or args.page > 1:
        raise Failure('NO_RESULT')
    return SearchData(candidates=rows, requested_date=args.target_date, consulted_on=datetime.now(KST).date(),
                      coverage='시연 데이터로 조회했어요. 예시 장소와 경로를 실제 방문에 사용하지 마세요.')


def details(args):
    row = next((item for item in PLACES if item[0] == args.content_id), None)
    if row is None:
        raise Failure('NO_RESULT')
    id, kind, _, _, description = row
    hours = '11:00~22:00' if kind == 39 else '18:30~22:00' if kind == 15 else '11:00~19:00'
    return DetailData(content_id=id, content_type_id=kind, category={14: '문화시설', 39: '음식점', 12: '관광지', 15: '행사'}[kind],
                      description=description, hours=hours, closure='연중무휴',
                      admission=0 if kind != 39 else None,
                      missing=['admission'] if kind == 39 else [], source_url='')


def route(args):
    dx, dy = abs(args.start[0] - args.end[0]), abs(args.start[1] - args.end[1])
    distance = max(30, round(130_000 * hypot(dx, dy)))
    seconds = round(distance * 0.85)
    middle = ((args.start[0] + args.end[0]) / 2, args.start[1])
    return Leg(origin=args.start_name, destination=args.end_name, distance_m=distance, seconds=seconds,
               lines=[[args.start, middle, args.end]])


def weather(args):
    year = args.target_date.year
    return Weather(temperature=(-8, 6), apparent=(-12, 3), precipitation_max=1.2, wind_max=19,
                   years=list(range(year - 5, year)), period='12월 20~26일 (시연 데이터)', missing={},
                   guide='두꺼운 외투와 장갑을 준비해 보세요. 실내에서 쉬어가는 시간도 좋아요.', source_url='')


DEMO_TOOLS = {'search_places': search, 'get_place_details': details,
              'get_walking_route': route, 'get_christmas_weather': weather}
