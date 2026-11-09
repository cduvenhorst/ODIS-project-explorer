"""Strict reading: turn unread object content into errors instead of console messages."""
import contextlib
import contextvars

_strict = contextvars.ContextVar('strict_reading', default=False)


class UnreadContentError(RuntimeError):
    """Content was recognised but not read."""


class UnreadBytesError(UnreadContentError):
    """Bytes were left over after an object was loaded."""

    def __init__(self, object_type, remaining):
        super().__init__('{} bytes left unread in object {}'.format(remaining, object_type))
        self.object_type = object_type
        self.remaining = remaining


@contextlib.contextmanager
def strict_reading():
    token = _strict.set(True)
    try:
        yield
    finally:
        _strict.reset(token)


def is_strict():
    return _strict.get()


def report_unread(message):
    if is_strict():
        raise UnreadContentError(message)
    print(message)
