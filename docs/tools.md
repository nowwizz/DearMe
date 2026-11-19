# Tool 정의서

네 Tool은 외부 API용입니다. SQLite 저장, 중복 검사, 시간 계산은 서버 로직이 수행합니다. 등록 Tool의 Pydantic 입력·출력 JSON Schema를 `GET /api/tools`에서 확인할 수 있습니다.

| 이름 | 선택 시점 | 입력 | 결과 |
| --- | --- | --- | --- |
| search_places | 지역·활동의 방문 후보 필요 | region, 선택 target_date·keyword·category·center·radius_m·page | TourAPI content_id, content_type_id, 이름, 주소, 경위도, 요청일과 조회 기준 |
| get_place_details | 후보의 이용 조건 검증 필요 | content_id, content_type_id | 공통·소개 조회의 분류, 설명, 공개 이용·휴무 시간, 해석 가능한 단일 입장료, 요금 안내, 누락 필드, 출처 |
| get_walking_route | 출발과 도착 좌표 확보 | WGS84 start·end와 출발·도착 이름 | TMAP 합산 거리 m·시간 초, LineString 좌표 목록, 구간명 |
| get_christmas_weather | 좌표와 시간대 확보 및 겨울 준비 | WGS84 point, target_date, start_hour, end_hour, years 5~10 | Open-Meteo 기온·체감 범위, 강수·풍속 최대, 기간, 결측, 준비 가이드, 출처 |

날짜가 없으면 조회일 기준의 TourAPI 등록 데이터를 반환합니다. 희망일 운영을 확인할 수 없다는 안내를 포함합니다. 목록 ID와 분류 → 상세, 후보 좌표 → 경로·날씨로 전달합니다.

성공은 `{ok: true, data, error: null, meta}`, 실패는 `{ok: false, data: null, error: {code, message}, meta}`를 반환합니다. `meta`는 `source, fetched_at, warnings`를 포함합니다. 실패 코드는 MISSING_API_KEY, AUTH_FAILED, RATE_LIMITED, TIMEOUT, INVALID_INPUT, NO_RESULT, MISSING_REQUIRED_ATTRIBUTE, UPSTREAM_ERROR입니다.

Tool 추가 시 입력·출력 모델과 공급자 호출 함수를 정의한 뒤 `backend/tools.py`의 `TOOLS` 레지스트리에 설명과 함께 등록합니다. Agent 실행 노드에서 앞 Tool의 출력과 새로운 입력을 연결합니다.
