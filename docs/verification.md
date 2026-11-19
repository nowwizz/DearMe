# 검증 및 제출 체크리스트

## 재현

~~~powershell
.venv/Scripts/python.exe -m scripts.verify_scenarios --export docs/evidence/scenarios
.venv/Scripts/python.exe -m pip install playwright
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m scripts.verify_browser
~~~

브라우저 검증은 설치된 Edge와 별도의 임시 SQLite를 사용합니다. 다섯 대표 요청은 외부 API 대신 테스트용 장소·경로·날씨로 실행합니다. 각 JSON에는 요청 문장, 최종 응답, 전체 이벤트, 재계획 횟수와 처리 시간이 들어 있습니다.

2026년 11월 19일 KST에 시연 시나리오를 다시 실행했습니다. 아래 처리 시간은 외부 API 통신을 포함하지 않은 단일 실행 결과입니다.

| 시나리오 | 기대 | 실제 | 시간 · 증빙 |
| --- | --- | --- | --- |
| 보행 30분 | 첫 계획이 조건에 맞음 | 눈꽃 다과점 등 4곳, 보행 21분 26초, 재계획 0회 | 687ms · [전체 로그](evidence/scenarios/normal.json) |
| 보행 10분 | 가까운 대안 순서 선택 | 겨울빛 전시관과 눈꽃 다과점, 5분 32초, 추가 후보 검토 포함 재계획 3회 | 1,281ms · [전체 로그](evidence/scenarios/replan.json) |
| 보행 1분 | 상한 후 이유와 조정 가능한 값 안내 | 재계획 3회에서 종료, 초대장 생성 보류 | 1,360ms · [전체 로그](evidence/scenarios/capped.json) |
| 날씨 Tool 실패 | 날씨 실패를 표시하고 가능한 일정 제공 | `TIMEOUT` 기록, 장소 4곳과 경로가 포함된 초대장 반환 | 703ms · [전체 로그](evidence/scenarios/tool_failure.json) |
| 인사 | 외부 Tool 호출 없음 | 분석과 응답 노드만 실행, Tool 호출 0건 | 172ms · [전체 로그](evidence/scenarios/no_tool.json) |

다섯 시나리오의 최종 응답은 기대와 일치했습니다. 보행 10분 사례에서는 적합한 2곳을 확보한 뒤 일정에 맞는 추가 장소를 검토했기 때문에 재계획을 3회 수행했습니다. 추가 후보가 없을 때 확보한 코스를 반환했습니다. 초기 지역 단위 조회가 너무 먼 동선을 포함하는 문제는 역 반경과 구간별 보행 상한을 도입해 수정했습니다. 자세한 변경 사유는 [기획 검증](domain-verification.md)에 정리했습니다.

추가 확인은 ID → 상세 입력, 미확인 입장료 처리, 필수 조건 질문, 후속 동행 변경, 로그 연결·저장 실패 격리, 로그 세션 분리와 수정 금지, 초대장 중복·수정·삭제, TMAP 경로·타임라인의 SQLite 저장 제외를 포함합니다.

## 실연동 결과

| 검증 | 결과 |
| --- | --- |
| 공급자 연결 | TourAPI 후보·상세, TMAP 거리·시간·선형 경로, Open-Meteo 5개 연도, GMS 응답과 Tool 선택 확인 |
| 강남역 17:30–21:30, 친구와 양식 저녁·카페 | 12.5초에 초대장 생성. 장소 3곳, 도보 2구간, 최장 10분 21초. 일부 조회의 `NO_RESULT`를 처리하고 코스 반환 |
| 카카오톡 공유 | 테스트용 SDK로 카드 이미지 URL·버튼 링크·받는 화면 확인. 실제 카카오톡 채팅방 발송 검증은 남아 있음 |

## 화면

- [대화](evidence/screens/01-chat.png) · [초대장](evidence/screens/02-invitation.png) · [보관함](evidence/screens/03-archive.png)
- [재계획](evidence/screens/04-replan.png) · [실행 기록](evidence/screens/05-logs.png) · [Swagger UI](evidence/screens/06-api.png)
- [모바일](evidence/screens/07-mobile.png) · [API 키 누락](evidence/screens/08-missing-key.png)
- [받은 초대장 모달](evidence/screens/09-received-invitation.png) · [받은 초대장 모바일](evidence/screens/10-received-mobile.png)

## PDF p.26 기준 제출 전 자체 점검

- [x] 요구사항 정의서, Agent 설계, Tool 정의서, API 명세, README, 백엔드·프론트엔드 소스
- [x] 대표 요청 5종의 결과, 정상과 재계획의 전체 로그, 확인 화면
- [x] 시연 환경에서 필수 흐름, 오류 처리, 계획·로그 관리 확인
- [x] Open-Meteo 실호출 및 출처 확인, 키 제외 규칙 설정
- [x] TourAPI·TMAP·LLM 실호출 및 대표 실연동 처리 시간 측정
- [ ] 별도로 제공되는 3일차 공식 셀프 체크리스트 작성. 원본 양식은 작업 폴더에 없음

상세 제출 상태는 [자체 체크리스트](self-checklist.md)에 정리했습니다. 외부 API 응답의 세부 항목은 [기획 검증](domain-verification.md)에 기록했습니다.
