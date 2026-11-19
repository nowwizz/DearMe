# 검증 및 제출 체크리스트

## 재현

~~~powershell
.venv/Scripts/python.exe -m scripts.verify_scenarios --export docs/evidence/scenarios
.venv/Scripts/python.exe -m pip install playwright
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m scripts.verify_browser
~~~

브라우저 검증은 설치된 Edge와 별도의 임시 SQLite를 사용합니다. 다섯 대표 요청은 외부 API 대신 테스트용 장소·경로·날씨로 실행합니다. 각 JSON에는 요청 문장, 최종 응답, 전체 이벤트, 재계획 횟수와 처리 시간이 들어 있습니다.

최종 시연에서 정상 계획 469ms, 재계획 후 성공 594ms, 상한 도달 1,375ms, 날씨 실패 859ms, 인사 187ms로 측정했습니다. 실제 공급자와 통신하는 전체 요청의 처리 시간은 키 설정 후 확인합니다.

| 시나리오 | 기대 | 실제 | 증빙 |
| --- | --- | --- | --- |
| 보행 30분 | 첫 조합이 조건에 맞음 | 전시관과 찻집, 24분 34초, 재계획 0회 | [전체 로그](evidence/scenarios/normal.json) |
| 보행 10분 | 긴 구간 대신 가까운 대안을 선택 | 전시관과 다과점, 5분 32초, 재계획 1회 | [전체 로그](evidence/scenarios/replan.json) |
| 보행 1분 | 상한 후 이유와 조정 가능한 값 안내 | 재계획 3회에서 종료, 초대장 생성 보류 | [전체 로그](evidence/scenarios/capped.json) |
| 날씨 Tool 실패 | 날씨 실패 이유를 표시하고 계획 응답 | TIMEOUT 기록, 장소·도보·음악 포함 초대장 반환 | [전체 로그](evidence/scenarios/tool_failure.json) |
| 인사 | 외부 Tool 호출 없음 | 분석과 답변만 실행 | [전체 로그](evidence/scenarios/no_tool.json) |

예상과 최종 결과가 일치했습니다. 첫 통합 실행에서 계획 노드 이름과 내부 결과 속성 이름이 겹쳐 호출에 실패했습니다. 속성 이름을 바꾼 뒤 현재 증빙을 생성했습니다. 초기에 모바일 설명과 장식이 일부 겹치는 화면을 확인해 장식 크기와 위치를 조정했습니다.

추가 확인은 ID → 상세 입력, 미확인 입장료 처리, 필수 조건 질문, 후속 동행 변경, 로그 연결·저장 실패 격리, 로그 세션 분리와 수정 금지, 초대장 중복·수정·삭제, TMAP 경로·타임라인의 SQLite 저장 제외를 포함합니다.

## 화면

- [대화](evidence/screens/01-chat.png) · [초대장](evidence/screens/02-invitation.png) · [보관함](evidence/screens/03-archive.png)
- [재계획](evidence/screens/04-replan.png) · [실행 기록](evidence/screens/05-logs.png) · [Swagger UI](evidence/screens/06-api.png)
- [모바일](evidence/screens/07-mobile.png) · [API 키 누락](evidence/screens/08-missing-key.png)

## PDF p.26 기준 제출 전 자체 점검

- [x] 요구사항 정의서, Agent 설계, Tool 정의서, API 명세, README, 백엔드·프론트엔드 소스
- [x] 대표 요청 5종의 결과, 정상과 재계획의 전체 로그, 확인 화면
- [x] 시연 환경에서 필수 흐름, 오류 처리, 계획·로그 관리 확인
- [x] Open-Meteo 실호출 및 출처 확인, 키 제외 규칙 설정
- [ ] TourAPI·TMAP·LLM 실호출에 의한 F3002~F3006·NF3005 최종 확인
- [ ] 별도로 제공되는 3일차 공식 셀프 체크리스트 작성. 원본 양식은 작업 폴더에 없음

외부 API 실호출은 [기획 검증](domain-verification.md)에 기록했습니다.
