import logging
from time import monotonic
from uuid import uuid4

from .config import timestamp
from .models import Event

logger = logging.getLogger(__name__)


class EventBus:
    """Observers receive validated events independently of the Agent."""

    def __init__(self, subscribers):
        self.subscribers = tuple(subscribers)

    def publish(self, event):
        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception:
                logger.warning('An execution event could not be delivered to an observer.')


class RunEvents:
    def __init__(self, bus, session_id, run_id):
        self.bus = bus
        self.session_id = session_id
        self.run_id = run_id
        self.sequence = 0

    def emit(self, kind, stage=None, **details):
        self.sequence += 1
        event = Event(event_id=uuid4(), session_id=self.session_id, run_id=self.run_id,
                      sequence=self.sequence, timestamp=timestamp(), event_type=kind, stage=stage, **details)
        self.bus.publish(event)

    def stage(self, name, function):
        def run(state):
            self.emit('stage_started', name)
            started = monotonic()
            try:
                return function(state)
            finally:
                self.emit('stage_finished', name, duration_ms=elapsed(started))
        return run


class LoggingAgent:
    def __init__(self, store):
        self.store = store

    def __call__(self, event):
        self.store.append(event)


def elapsed(started):
    return round((monotonic() - started) * 1000)
