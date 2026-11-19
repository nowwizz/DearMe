from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import Planner
from .config import ROOT, setting
from .events import EventBus, LoggingAgent, RunEvents, elapsed
from .models import (ChatAccepted, ChatRequest, ChatResult, Conditions, Event, LogDetail,
                     LogSummary, PlanCreate, PlanEdit, PlanSummary, RunStatus, SavedPlan)
from .storage import Store, durable_copy
from .tools import TOOLS, call_tool


class ToolSpec(BaseModel):
    name: str
    description: str
    kind: str
    input: dict
    output: dict
    source: str


def create_app(db_path=None, tool_runner=call_tool, logging_enabled=None):
    store = Store(db_path)
    lock = Lock()
    active = set()
    runs = OrderedDict()
    previews = OrderedDict()
    log_agent = LoggingAgent(store)
    if logging_enabled is None:
        logging_enabled = setting('LOGGING_ENABLED', 'true').lower() in {'true', '1', 'yes'}

    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.shutdown(wait=True)

    jobs = ThreadPoolExecutor(max_workers=4, thread_name_prefix='dear-me')
    app = FastAPI(title='Dear. Me API', version='1.0.0', lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_, exc):
        # Pydantic's default payload may echo the input text.
        return JSONResponse(status_code=422, content={'detail': '입력 형식을 확인해 주세요.'})

    @app.exception_handler(Exception)
    async def unexpected_error(_, exc):
        return JSONResponse(status_code=500, content={'detail': '요청을 처리하지 못했어요.'})

    def remember_event(event):
        with lock:
            current = runs.get(event.run_id)
            if current:
                current.events.append(event)

    def prune():
        now = monotonic()
        for collection in (previews, runs):
            for id, value in list(collection.items()):
                if collection is runs and value.status == 'running':
                    continue
                cutoff = value[0] if collection is previews else run_expirations.get(id, 0)
                if cutoff < now or len(collection) > 128:
                    collection.pop(id)
                    if collection is runs:
                        run_expirations.pop(id, None)

    run_expirations = {}

    def execute(run, req, previous, last):
        subscribers = [remember_event]
        if logging_enabled:
            subscribers.append(log_agent)
        events = RunEvents(EventBus(subscribers), run.session_id, run.run_id)
        started = monotonic()
        try:
            result = Planner(events, demo=req.mode == 'demo', invoke=tool_runner).run(req.message, previous, last)
            store.remember(run.session_id, req.mode, req.message, result)
            events.emit('run_completed', duration_ms=elapsed(started), decision='invitation' if result.plan else 'message')
            status = 'complete'
        except Exception:
            result = ChatResult(message='요청을 완료하지 못했어. 잠시 후 다시 시도해 줘.', conditions=previous,
                                warnings=['실행 중 오류가 발생했어요.'])
            events.emit('run_failed', duration_ms=elapsed(started), error_code='RUN_ERROR')
            status = 'failed'
        with lock:
            run.result = result
            run.status = status
            run_expirations[run.run_id] = monotonic() + 3600
            active.discard(run.session_id)

    @app.post('/api/chat', response_model=ChatAccepted, status_code=202)
    def chat(req: ChatRequest):
        session_id = req.session_id or uuid4()
        with lock:
            prune()
            if session_id in active:
                raise HTTPException(409, '이 대화의 응답을 준비하고 있어요.')
            if len(active) >= 12:
                raise HTTPException(503, '요청이 많아요. 잠시 후 다시 시도해 주세요.')
            existing = store.session(session_id)
            if existing and existing['mode'] != req.mode:
                raise HTTPException(409, '모드를 바꾸려면 새 대화를 시작해 주세요.')
            previous = Conditions.model_validate_json(existing['conditions']) if existing else Conditions()
            last = f'{existing["last_request"]}\n{existing["last_response"]}\n{existing["plan_summary"]}' if existing else ''
            run = RunStatus(session_id=session_id, run_id=uuid4(), status='running', events=[])
            runs[run.run_id] = run
            active.add(session_id)
        jobs.submit(execute, run, req, previous, last)
        return ChatAccepted(session_id=session_id, run_id=run.run_id)

    @app.get('/api/chat/{run_id}', response_model=RunStatus)
    def run_status(run_id: UUID, after: int = Query(0, ge=0)):
        with lock:
            prune()
            run = runs.get(run_id)
            if not run:
                raise HTTPException(404, '실행을 찾을 수 없어요. 실행 기록을 확인해 주세요.')
            return run.model_copy(update={'events': [event for event in run.events if event.sequence > after]})

    @app.get('/api/tools', response_model=list[ToolSpec])
    def tools():
        return [{'name': name, 'description': tool.description, 'kind': tool.kind,
                 'input': tool.args.model_json_schema(), 'output': tool.output.model_json_schema(),
                 'source': tool.source} for name, tool in TOOLS.items()]

    @app.post('/api/plans', response_model=SavedPlan, status_code=201)
    def save(req: PlanCreate):
        with lock:
            prune()
            run = runs.get(req.run_id)
            if not run or not run.result or not run.result.plan:
                raise HTTPException(404, '저장할 초대장이 없어요. 대화에서 먼저 초대장을 만들어 주세요.')
            invitation = run.result.plan
            saved = store.save_plan(invitation)
            if invitation.mode == 'live' and (invitation.legs or any(
                stop.provider == 'tmap' for stop in invitation.stops
            )):
                previews[saved.id] = run_expirations[run.run_id], invitation
                return with_preview(saved, invitation)
            return saved

    def with_preview(row, invitation):
        data = {'stops': [stop.name for stop in invitation.stops],
                'revalidation_required': invitation.revalidation_required}
        if isinstance(row, SavedPlan):
            data['plan'] = invitation.model_copy(update={'title': row.title})
        return row.model_copy(update=data)

    @app.get('/api/plans', response_model=list[PlanSummary])
    def list_plans():
        with lock:
            prune()
            return [with_preview(row, previews[row.id][1]) if row.id in previews else row
                    for row in store.plans()]

    @app.get('/api/plans/{plan_id}', response_model=SavedPlan)
    def plan(plan_id: UUID):
        with lock:
            prune()
            row = store.get_plan(plan_id)
            if not row:
                raise HTTPException(404, '초대장을 찾을 수 없어요.')
            preview = previews.get(plan_id)
            if preview:
                return with_preview(row, preview[1])
            return row

    @app.patch('/api/plans/{plan_id}', response_model=SavedPlan)
    def edit(plan_id: UUID, req: PlanEdit):
        with lock:
            prune()
            old = store.get_plan(plan_id)
            preview = previews.get(plan_id)
            if old and preview and req.stops is not None:
                temporary_names = {live.name: saved.name for live, saved in zip(preview[1].stops, old.plan.stops)
                                   if live.provider == 'tmap'}
                req = req.model_copy(update={'stops': [
                    stop.model_copy(update={'name': temporary_names.get(stop.name, stop.name)}) for stop in req.stops
                ]})
            try:
                row = store.edit_plan(plan_id, req)
            except ValueError:
                raise HTTPException(422, '같은 날의 시작 시각과 종료 시각을 확인해 주세요.') from None
            if not row:
                raise HTTPException(404, '초대장을 찾을 수 없어요.')
            old_values = old.plan.conditions
            new_values = row.plan.conditions
            if (old_values.date, old_values.start, old_values.end, old.plan.stops) != (
                    new_values.date, new_values.start, new_values.end, row.plan.stops):
                previews.pop(plan_id, None)
            preview = previews.get(plan_id)
            if preview:
                return with_preview(row, preview[1])
            return row

    @app.delete('/api/plans/{plan_id}', status_code=204)
    def delete_plan(plan_id: UUID):
        with lock:
            if not store.delete_plan(plan_id):
                raise HTTPException(404, '초대장을 찾을 수 없어요.')
            previews.pop(plan_id, None)
        return Response(status_code=204)

    @app.get('/api/logs', response_model=list[LogSummary])
    def logs():
        return store.sessions_with_logs()

    @app.get('/api/logs/{session_id}', response_model=LogDetail)
    def detail_logs(session_id: UUID):
        return LogDetail(session_id=session_id, events=[Event.model_validate_json(item) for item in store.events(session_id)])

    @app.delete('/api/logs/{session_id}', status_code=204)
    def delete_logs(session_id: UUID):
        with lock:
            if session_id in active:
                raise HTTPException(409, '실행이 끝나면 기록을 삭제할 수 있어요.')
            store.delete_logs(session_id)
        return Response(status_code=204)

    @app.get('/healthz', include_in_schema=False)
    def health():
        return {'status': 'ok'}

    if (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        app.mount('/', StaticFiles(directory=ROOT / 'frontend' / 'dist', html=True), name='frontend')
    return app


app = create_app()
