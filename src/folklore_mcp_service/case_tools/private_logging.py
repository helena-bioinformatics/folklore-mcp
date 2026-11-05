# Private stdio transport records carry no request/response values (CR025).

import logging
from threading import RLock

_lock = RLock()
_users = 0
_factory = None
_previous = None


def protect_transport_logs():
    global _users, _factory, _previous
    with _lock:
        if _users == 0:
            _previous = logging.getLogRecordFactory()
            previous = _previous

            def factory(*args, **kwargs):
                record = previous(*args, **kwargs)
                if any(
                    record.name == name or record.name.startswith(name + ".")
                    for name in ("httpx", "httpcore", "mcp")
                ):
                    record.msg = "Private protocol transport event"
                    record.args = ()
                    record.exc_info = None
                    record.exc_text = None
                    record.stack_info = None
                return record

            _factory = factory
            logging.setLogRecordFactory(factory)
        _users += 1
    released = False

    def release():
        nonlocal released
        global _users, _factory, _previous
        with _lock:
            if released:
                return
            released = True
            _users -= 1
            if _users == 0:
                if logging.getLogRecordFactory() is _factory:
                    logging.setLogRecordFactory(_previous)
                _factory = None
                _previous = None

    return release
