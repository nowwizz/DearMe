# API 명세

날짜는 ISO YYYY-MM-DD, 시각은 한국 현지 HH:mm을 사용합니다. 응답 시각에는 초 단위가 포함될 수 있습니다. 요청 및 응답의 Pydantic 스키마는 /docs와 /openapi.json으로 제공합니다.

| 메서드·경로 | 입력 | 성공 응답 |
| --- | --- | --- |
| POST /api/chat | message, 선택 session_id, mode 기본 live | 202 session_id, run_id |
| GET /api/chat/{run_id}?after=0 | run_id, 선택 마지막 이벤트 sequence | 200 session_id, run_id, status, events, result. result에 조건·메시지·초대장·경고·재계획 횟수 포함 |
| POST /api/plans | run_id | 201 저장된 초대장 상세와 overlaps |
| GET /api/plans | 없음 | 200 핵심 값·생성 및 수정 시각·재검증 표시 목록 |
| GET /api/plans/{plan_id} | plan_id | 200 plan, overlaps를 포함한 상세 |
| PATCH /api/plans/{plan_id} | 선택 title, date, start, end, stops [{name, stay_minutes}] | 200 수정된 상세. 시각·장소 변경 시 파생 검증 무효화 |
| DELETE /api/plans/{plan_id} | plan_id | 204 |
| GET /api/logs | 없음 | 200 세션별 session_id, run_count, event_count, last_at |
| GET /api/logs/{session_id} | session_id | 200 session_id, events. 발생 순서로 반환 |
| DELETE /api/logs/{session_id} | session_id | 204 |
| GET /api/tools | 없음 | 200 등록 Tool 설명, 출처, 입출력 스키마 |

겹치는 시간은 예약한 사용자 입력 구간으로 판단합니다. 시작이 다른 계획의 종료와 정확히 일치하면 겹치지 않습니다. 겹쳐도 저장되며 응답에서 겹친 계획을 알 수 있습니다.

이벤트 필드는 event_id, session_id, run_id, sequence, timestamp, event_type, stage, tool_name, sanitized_input, sanitized_output, duration_ms, decision, reason, error_code입니다. 조회·삭제로 관리합니다.

오류 형식은 `{detail}`입니다. 404는 없는 리소스, 409는 실행 중인 세션 또는 모드 충돌, 422는 입력 오류, 503은 동시 처리 제한입니다.
