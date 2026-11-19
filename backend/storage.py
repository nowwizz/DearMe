from contextlib import contextmanager
from pathlib import Path
import sqlite3
from uuid import uuid4

from .config import ROOT, setting, timestamp
from .models import Invitation, PlanSummary, SavedPlan, Stop, end_minutes


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, mode TEXT NOT NULL, conditions TEXT NOT NULL,
  last_request TEXT NOT NULL, last_response TEXT NOT NULL, plan_summary TEXT
);
CREATE TABLE IF NOT EXISTS plans (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL,
  start TEXT NOT NULL, end TEXT NOT NULL, mode TEXT NOT NULL,
  payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS plans_schedule ON plans(date, start, end);
CREATE TABLE IF NOT EXISTS events (
  ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
  timestamp TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(run_id, sequence)
);
CREATE INDEX IF NOT EXISTS events_session ON events(session_id, ordinal);
"""


class Store:
    def __init__(self, path=None):
        self.path = Path(path or setting('DATABASE_PATH') or ROOT / 'data' / 'dear-me.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode = WAL')
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def session(self, id):
        with self.connect() as db:
            return db.execute('SELECT * FROM sessions WHERE id = ?', (str(id),)).fetchone()

    def remember(self, id, mode, message, result):
        with self.connect() as db:
            db.execute("""
                INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET conditions=excluded.conditions,
                  last_request=excluded.last_request,last_response=excluded.last_response,
                  plan_summary=COALESCE(excluded.plan_summary,sessions.plan_summary)
                """, (str(id), mode, result.conditions.model_dump_json(), message,
                      result.message, result.plan.title if result.plan else None))

    def append(self, event):
        with self.connect() as db:
            db.execute('INSERT INTO events(session_id,run_id,sequence,timestamp,payload) VALUES (?,?,?,?,?)',
                       (str(event.session_id), str(event.run_id), event.sequence, event.timestamp, event.model_dump_json()))

    def sessions_with_logs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT session_id, COUNT(DISTINCT run_id) AS run_count,
                    COUNT(*) AS event_count, MAX(timestamp) AS last_at
                FROM events GROUP BY session_id ORDER BY MAX(ordinal) DESC
            """)]

    def events(self, id):
        with self.connect() as db:
            return [row['payload'] for row in db.execute(
                'SELECT payload FROM events WHERE session_id=? ORDER BY ordinal', (str(id),))]

    def delete_logs(self, id):
        with self.connect() as db:
            return db.execute('DELETE FROM events WHERE session_id=?', (str(id),)).rowcount

    def plans(self):
        with self.connect() as db:
            return [self.summary(row) for row in db.execute('SELECT * FROM plans ORDER BY updated_at DESC, id')]

    def get_plan(self, id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM plans WHERE id=?', (str(id),)).fetchone()
            return self.full(db, row) if row else None

    def save_plan(self, invitation):
        durable = durable_copy(invitation)
        date, start, end = schedule(durable)
        now = timestamp()
        id = str(uuid4())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO plans VALUES (?,?,?,?,?,?,?,?,?)',
                       (id, durable.title, date, start, end, durable.mode, durable.model_dump_json(), now, now))
            row = db.execute('SELECT * FROM plans WHERE id=?', (id,)).fetchone()
            return self.full(db, row)

    def edit_plan(self, id, edit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM plans WHERE id=?', (str(id),)).fetchone()
            if not row:
                return None
            current = Invitation.model_validate_json(row['payload'])
            if edit.title is not None:
                current.title = edit.title
            revalidate = False
            for key in ('date', 'start', 'end'):
                value = getattr(edit, key)
                if value is not None and value != getattr(current.conditions, key):
                    setattr(current.conditions, key, value)
                    revalidate = True
            date, start, end = schedule(current)
            if edit.stops is not None:
                stops = []
                for item in edit.stops:
                    same = next((stop for stop in current.stops if stop.name == item.name), None)
                    stop = same.model_copy(update={'stay_minutes': item.stay_minutes}) if same else Stop(
                        name=item.name, stay_minutes=item.stay_minutes, reason='직접 편집한 장소예요.')
                    stops.append(stop)
                if stops != current.stops:
                    revalidate = True
                    current.stops = stops
            if revalidate:
                invalidate(current)
            db.execute("""UPDATE plans SET title=?,date=?,start=?,end=?,payload=?,updated_at=? WHERE id=?""",
                       (current.title, date, start, end, current.model_dump_json(), timestamp(), str(id)))
            return self.full(db, db.execute('SELECT * FROM plans WHERE id=?', (str(id),)).fetchone())

    def delete_plan(self, id):
        with self.connect() as db:
            return db.execute('DELETE FROM plans WHERE id=?', (str(id),)).rowcount

    @staticmethod
    def summary(row, plan=None):
        payload = plan or Invitation.model_validate_json(row['payload'])
        return PlanSummary(id=row['id'], title=row['title'], start=row['start'], end=payload.conditions.end,
                           date=row['date'], mode=row['mode'], created_at=row['created_at'], updated_at=row['updated_at'],
                           revalidation_required=payload.revalidation_required, stops=[stop.name for stop in payload.stops])

    def full(self, db, row):
        plan = Invitation.model_validate_json(row['payload'])
        overlaps = db.execute("""
            SELECT * FROM plans WHERE date=? AND start<? AND end>? AND id<>?
            ORDER BY start, id
        """, (row['date'], row['end'], row['start'], row['id']))
        return SavedPlan(**self.summary(row, plan).model_dump(), plan=plan,
                         overlaps=[self.summary(other) for other in overlaps])


def schedule(plan):
    c = plan.conditions
    if not (c.date and c.start is not None and c.end is not None and
            end_minutes(c.end) > c.start.hour * 60 + c.start.minute):
        raise ValueError('같은 날의 시작 시각과 종료 시각을 확인해 주세요.')
    return c.date.isoformat(), c.start.strftime('%H:%M'), c.end.strftime('%H:%M') if c.end.hour or c.end.minute else '24:00'


def durable_copy(plan):
    copy = plan.model_copy(deep=True)
    has_tmap_place = any(stop.provider == 'tmap' for stop in copy.stops)
    if copy.mode == 'live' and (copy.legs or has_tmap_place):
        copy.warnings = [message for message in copy.warnings if not message.startswith('보행 경로 재확인')]
        invalidate(copy, route_only=True)
    if has_tmap_place:
        copy.origin_label = None
        copy.stops = [
            Stop(name='다시 찾아볼 카페' if stop.category == '카페' else '다시 찾아볼 식당',
                 category=stop.category, meal=stop.meal, stay_minutes=stop.stay_minutes, provider='tmap',
                 reason='보관한 일정의 활동 지역에서 이 장소를 다시 찾아봐 주세요.')
            if stop.provider == 'tmap' else stop for stop in copy.stops
        ]
    return copy


def invalidate(plan, route_only=False):
    plan.legs = []
    plan.walking_seconds = None
    plan.finishes = None
    plan.revalidation_required = True
    plan.exclusions = []
    if route_only:
        plan.warnings.append('보행 경로 재확인 · TMAP 경로는 임시로만 확인할 수 있어요.')
        for key in ('종료 시각', '보행', '이용 조건'):
            plan.checks.pop(key, None)
    else:
        plan.weather = None
        plan.origin_label = None
        plan.known_cost = 0
        plan.cost_basis = None
        plan.budget_remaining = None
        plan.checks = {}
        plan.warnings = ['편집한 일정은 경로와 이용 조건을 다시 확인해야 해요.']
    for stop in plan.stops:
        stop.arrives = None
        stop.leaves = None
        stop.access = 'unknown'
