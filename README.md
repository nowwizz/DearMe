# Dear. Me — 나에게 도착한 크리스마스

크리스마스 하루를 대화로 준비하고, 나에게 보내는 초대장으로 받는 Vue 3 · FastAPI 서비스입니다. 초대장에 방문 순서, 이동 시간, 날씨 기반 준비물, 음악을 담고 SQLite 보관함에서 다시 열 수 있습니다.

## 실행

Python 3.12와 Node.js 24에서 확인했습니다. 백엔드 최소 기준은 Python 3.10, 프론트엔드 빌드에는 Node.js 20.19+ 또는 22.12+가 필요합니다.

~~~powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
~~~

- 앱은 [http://127.0.0.1:8000](http://127.0.0.1:8000), API 문서는 [Swagger UI](http://127.0.0.1:8000/docs)에서 엽니다.
- 키 없이 전체 계획 흐름을 보려면 **예시 초대장 받아보기**를 누르세요. 서울 종로를 배경으로 한 가상 장소·경로·날씨를 사용합니다.
- 프론트엔드 개발 시 별도 터미널에서 `npm.cmd --prefix frontend run dev`를 실행합니다. Vite가 API 요청을 8000번 포트로 전달합니다.
- SQLite 기본 파일은 `data/dear-me.sqlite3`입니다. 폴링 실행과 경로 미리보기는 서버 메모리에 있으므로 Uvicorn 워커는 한 개로 실행합니다.
- `requirements.txt`는 필수 기능에 필요한 PDF 지정 버전을 설치합니다. 전체 명세 버전은 `requirements.pdf.txt`에 있습니다.

## 컨테이너 배포

```powershell
docker build -t dear-me .
docker run --rm --env-file .env --env DATABASE_PATH=/data/dear-me.sqlite3 --env PORT=8000 --publish 127.0.0.1:8000:8000 --mount source=dear-me-data,target=/data dear-me
```

호스팅 환경에서는 단일 인스턴스에 영구 디스크를 `/data`로 연결하고 상태 확인 경로를 `/healthz`로 설정합니다. API 키는 호스팅 서비스의 런타임 비밀 변수로 등록합니다. 보관함과 실행 기록은 인스턴스 전체에서 공유하므로 배포 시 신뢰할 수 있는 사용자만 접근하도록 호스팅 서비스에서 접근을 제한합니다.

### Render 무료 시연 배포

소스 저장소를 Render에 연결하고 루트의 `render.yaml`을 Blueprint로 사용합니다. 무료 Docker 웹 서비스가 열리면 **예시 초대장 받아보기**로 코스를 시연할 수 있습니다. 실연동이 필요하면 Render에서 아래 API 키를 비밀 변수로 등록합니다. 이 구성에는 영구 디스크가 없으므로 재시작 시 보관함이 초기화됩니다.

## 실연동 설정

`.env.example`을 `.env`로 복사한 뒤 다음 값을 입력하고 서버를 재시작합니다.

| 변수 | 설정 |
| --- | --- |
| `TOUR_API_KEY` | 한국관광공사 국문 관광정보 서비스 활용 신청 후 발급된 일반 인증키 |
| `TMAP_APP_KEY` | SK open API TMAP 프로젝트 App Key. 보행 경로와 부족한 카페 후보 검색에 사용해요. |
| `GMS_KEY` | SSAFY GMS에서 발급한 API 키 |
| `GMS_BASE_URL` | `https://gms.ssafy.io/gmsapi/api.openai.com/v1` |
| `GMS_MODEL` | `gpt-6.1-sol` |
| `MAX_REPLANS` | 기본 3회, 설정 범위 0~8 |
| `LOGGING_ENABLED` | 기본 true. false를 지정하면 장기 로그 저장 없이 진행 상태를 표시 |
| `DATABASE_PATH` | 선택 SQLite 파일 경로 |

LLM 요청은 `GMS_BASE_URL`에 `/responses`를 붙인 주소로 전송합니다.

`.venv/Scripts/python.exe scripts/verify_apis.py`로 실호출을 확인합니다. 이전 검증 결과와 공급자별 신청 절차는 [기획 검증](docs/domain-verification.md)에 있습니다. [공공데이터포털](https://www.data.go.kr/data/15101578/openapi.do) · [SK open API](https://openapi.sk.com/products/detail?linkMenuSeq=24) · [SSAFY GMS](https://gms.ssafy.io/web/)

## 제출 자료

- [요구사항 정의서](docs/requirements.md) · [Agent 설계](docs/agent.md) · [Tool 정의](docs/tools.md) · [API 명세](docs/api.md)
- [기획 검증](docs/domain-verification.md) · [대표 시나리오와 체크리스트](docs/verification.md)
- [정상 전체 실행 로그](docs/evidence/scenarios/normal.json) · [재계획 전체 실행 로그](docs/evidence/scenarios/replan.json) · [화면 증빙](docs/evidence/screens)
- F3020~F3023은 기본 MVP 완료와 실연동 확인 이후 선택할 심화 과제입니다.
- lab.ssafy.com 제출에는 README, 연결 문서, 소스 및 증빙을 포함합니다. 공식 3일차 셀프 체크리스트 양식은 제공받은 뒤 결과를 추가합니다.
