from datetime import date as Date, time as Time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Point = tuple[float, float]
Mode = Literal['live', 'demo']


def end_minutes(value: Time) -> int:
    return value.hour * 60 + value.minute or 24 * 60


class Conditions(BaseModel):
    name: Text | None = None
    date: Date | None = None
    start: Time | None = None
    end: Time | None = None
    region: Text | None = None
    origin: Text | None = None
    companion: Text | None = None
    mood: Text | None = None
    activities: list[Text] | None = Field(None, max_length=5)
    food: Text | None = None
    music: Text | None = None
    budget: int | None = Field(None, ge=0, le=100_000_000)
    budget_basis: Literal['total', 'person'] | None = None
    party_size: int | None = Field(None, ge=1, le=100)
    walking_limit: int | None = Field(None, ge=0, le=1440)
    avoids: list[Text] | None = Field(None, max_length=8)
    cold_sensitive: bool | None = None
    indoor: Literal['mostly_indoor', 'balanced', 'mostly_outdoor'] | None = None

    @field_validator('end', mode='before')
    @classmethod
    def midnight(cls, value):
        return Time() if value in ('24:00', '24:00:00') else value

    @field_validator('start', 'end')
    @classmethod
    def local_minute(cls, value):
        if value and (value.second or value.microsecond or value.tzinfo):
            raise ValueError('Use local hours and minutes')
        return value


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    session_id: UUID | None = None
    mode: Mode = 'live'


class ChatAccepted(BaseModel):
    session_id: UUID
    run_id: UUID


class PlacePhoto(BaseModel):
    url: str
    thumbnail_url: str | None = None
    license_type: Literal[1, 3]


class Stop(BaseModel):
    id: str | None = None
    name: Text
    address: str | None = None
    point: Point | None = None
    category: str | None = None
    description: str | None = None
    service_note: str | None = None
    source_url: str | None = None
    reason: str = ''
    meal: Literal['점심', '저녁', '식사'] | None = None
    stay_minutes: int = Field(ge=1, le=1440)
    arrives: str | None = None
    leaves: str | None = None
    hours: str | None = None
    closure: str | None = None
    access: Literal['verified', 'unknown', 'closed'] = 'unknown'
    admission: int | None = None
    provider: Literal['tour', 'tmap'] | None = None
    cuisine: str | None = None
    menu: str | None = None
    photo: PlacePhoto | None = None


class Leg(BaseModel):
    origin: str
    destination: str
    seconds: int
    distance_m: int
    lines: list[list[Point]]


class Song(BaseModel):
    title: str
    artist: str
    reason: str
    url: str


class Weather(BaseModel):
    temperature: tuple[float, float]
    apparent: tuple[float, float]
    precipitation_max: float | None
    wind_max: float | None
    years: list[int]
    period: str
    missing: dict[str, int]
    guide: str
    source_url: str


class Invitation(BaseModel):
    title: Text
    letter: str
    conditions: Conditions
    mode: Mode
    stops: list[Stop]
    legs: list[Leg] = Field(default_factory=list)
    walking_seconds: int | None = None
    finishes: str | None = None
    buffer_minutes: int = 0
    known_cost: int = 0
    cost_basis: str | None = None
    budget_remaining: int | None = None
    weather: Weather | None = None
    songs: list[Song] = Field(default_factory=list)
    checks: dict[str, str] = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    origin_label: str | None = None
    revalidation_required: bool = False


class ChatResult(BaseModel):
    message: str
    conditions: Conditions
    plan: Invitation | None = None
    warnings: list[str] = Field(default_factory=list)
    replans: int = 0


class Event(BaseModel):
    event_id: UUID
    session_id: UUID
    run_id: UUID
    sequence: int
    timestamp: str
    event_type: str
    stage: str | None = None
    tool_name: str | None = None
    sanitized_input: dict | None = None
    sanitized_output: dict | None = None
    duration_ms: int | None = None
    decision: str | None = None
    reason: str | None = None
    error_code: str | None = None


class RunStatus(BaseModel):
    session_id: UUID
    run_id: UUID
    status: Literal['running', 'complete', 'failed']
    events: list[Event]
    result: ChatResult | None = None


class PlanCreate(BaseModel):
    run_id: UUID


class EditedStop(BaseModel):
    name: Text
    stay_minutes: int = Field(ge=1, le=1440)


class PlanEdit(BaseModel):
    model_config = {'extra': 'forbid'}
    title: Text | None = None
    date: Date | None = None
    start: Time | None = None
    end: Time | None = None
    stops: list[EditedStop] | None = Field(None, min_length=1, max_length=5)

    @model_validator(mode='after')
    def no_null(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Specify at least one non-null value')
        return self


class PlanSummary(BaseModel):
    id: UUID
    title: str
    date: Date
    start: Time
    end: Time
    mode: Mode
    created_at: str
    updated_at: str
    revalidation_required: bool
    stops: list[str]


class SavedPlan(PlanSummary):
    plan: Invitation
    overlaps: list[PlanSummary] = Field(default_factory=list)


class LogSummary(BaseModel):
    session_id: UUID
    run_count: int
    event_count: int
    last_at: str


class LogDetail(BaseModel):
    session_id: UUID
    events: list[Event]
