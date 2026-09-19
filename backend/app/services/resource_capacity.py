"""Hold a slot in the executing thread until work ends, including after await cancellation."""
from contextlib import contextmanager
from functools import wraps
from threading import BoundedSemaphore
from app.services.ai.errors import AIError

_provider_slots = BoundedSemaphore(8)
_parser_slots = BoundedSemaphore(4)

@contextmanager
def provider_slot():
    if not _provider_slots.acquire(blocking=False):
        raise AIError('AI_CAPACITY_EXCEEDED', 429)
    try:
        yield
    finally:
        _provider_slots.release()

def bounded_parser(function):
    @wraps(function)
    def run(*args, **kwargs):
        if not _parser_slots.acquire(blocking=False):
            raise AIError('AI_CAPACITY_EXCEEDED', 429)
        try:
            return function(*args, **kwargs)
        finally:
            _parser_slots.release()
    return run
