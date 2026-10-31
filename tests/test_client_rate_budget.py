"""Offline admission and actual discovery-caller boundary tests. No live HTTP."""

from __future__ import annotations

import importlib
import io
import json
import math
import socket
import threading
import time
from email.message import Message
from email.utils import formatdate
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

OPS = Path(__file__).resolve().parents[1] / "ops"


class OfflineNetworkAttempt(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempted = []

    def deny(name):
        def blocked(*args, **kwargs):
            attempted.append(name)
            raise OfflineNetworkAttempt("Offline RATE test blocked " + name)

        return blocked

    for name in ("getaddrinfo", "create_connection"):
        monkeypatch.setattr(socket, name, deny(name))
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, deny(name))
    return attempted


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(OPS))
    return (
        importlib.import_module("client_rate_budget"),
        importlib.import_module("public_smoke"),
    )


class Clock:
    def __init__(self):
        self.now = 0.0
        self.wall = 1_000_000_000.0

    def sleep(self, duration):
        self.now += duration

    def budget(self, rate, **kwargs):
        return rate.RateBudget(
            clock=lambda: self.now,
            wall_clock=lambda: self.wall,
            sleep=self.sleep,
            **kwargs,
        )


def test_discovery_calls_are_spaced_and_attempts_are_finite(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate, max_attempts=4)
    starts = []
    for _ in range(4):
        budget.execute(lambda remaining: starts.append(clock.now), deadline=90)
    assert starts == pytest.approx([0, 10, 20, 30])
    with pytest.raises(rate.AttemptBudgetExceeded):
        budget.execute(lambda _: starts.append(clock.now), deadline=90)
    assert len(starts) == 4


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, 10),
        ("", 10),
        ("invalid", 10),
        ("-3", 10),
        ("1.5", 10),
        ("0", 0),
        ("25", 25),
    ],
)
def test_retry_after_delta_missing_and_malformed(modules, header, expected):
    rate, _ = modules
    assert rate.retry_after_seconds(header, wall_time=0) == expected


def test_http_date_and_excessive_retry_after_are_not_shortened(modules):
    rate, _ = modules
    now = 1_000_000_000
    assert (
        rate.retry_after_seconds(formatdate(now + 45, usegmt=True), wall_time=now) == 45
    )
    assert (
        rate.retry_after_seconds(formatdate(now - 45, usegmt=True), wall_time=now) == 0
    )
    assert math.isinf(rate.retry_after_seconds("9" * 400, wall_time=now))
    with pytest.raises(ValueError):
        rate.retry_after_seconds(None, wall_time=now, fallback_seconds=math.inf)


def test_429_latches_until_explicit_elapsed_resume_without_replay(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate)
    calls = []

    def limited(_):
        calls.append(clock.now)
        raise rate.RateLimited("30")

    with pytest.raises(rate.RateLimited):
        budget.execute(limited, deadline=100)
    with pytest.raises(rate.RateLimitHold):
        budget.execute(limited, deadline=100)
    clock.now = 29.9
    with pytest.raises(rate.RateLimitHold):
        budget.resume(deadline=100)
    clock.now = 30
    assert budget.resume(deadline=100) is True
    assert budget.resume(deadline=100) is False
    assert (
        budget.execute(lambda _: "unchanged payload", deadline=100)
        == "unchanged payload"
    )
    assert calls == [0]


def test_retry_after_longer_than_deadline_never_sends_another_request(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate)

    def limited(_):
        raise rate.RateLimited("3600")

    with pytest.raises(rate.RateLimited):
        budget.execute(limited, deadline=60)
    clock.now = 59
    with pytest.raises(rate.RateLimitHold):
        budget.resume(deadline=60)
    clock.now = 60
    with pytest.raises(rate.AdmissionDeadlineExceeded):
        budget.resume(deadline=60)


def test_remaining_timeout_and_exact_admission_deadline(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate)
    received = []
    budget.execute(lambda remaining: received.append(remaining), deadline=25)
    budget.execute(lambda remaining: received.append(remaining), deadline=25)
    assert received == pytest.approx([25, 15])
    with pytest.raises(rate.AdmissionDeadlineExceeded):
        budget.execute(lambda _: pytest.fail("No budget remained"), deadline=20)


def test_cancel_before_send_and_during_spacing_wait(modules):
    rate, _ = modules
    clock = Clock()
    cancelled = threading.Event()
    budget = clock.budget(rate)
    cancelled.set()
    with pytest.raises(rate.AdmissionCancelled):
        budget.execute(
            lambda _: pytest.fail("Cancelled request sent"),
            deadline=90,
            cancelled=cancelled.is_set,
        )
    cancelled.clear()
    budget.execute(lambda _: None, deadline=90)

    def cancel_on_sleep(duration):
        clock.sleep(duration)
        cancelled.set()

    budget._sleep = cancel_on_sleep
    with pytest.raises(rate.AdmissionCancelled):
        budget.execute(
            lambda _: pytest.fail("Cancelled request sent"),
            deadline=90,
            cancelled=cancelled.is_set,
        )


def test_late_cooperative_callback_return_is_not_success(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate)
    calls = []

    def late(remaining):
        calls.append(remaining)
        clock.now += remaining + 1
        return {"not_a_valid_timely_result": True}

    with pytest.raises(rate.AdmissionDeadlineExceeded):
        budget.execute(late, deadline=20)
    assert calls == [20]


def test_callback_exception_releases_lock_and_consumes_attempt(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate, max_attempts=2)

    def failed(_):
        raise OSError("controlled transport failure")

    with pytest.raises(OSError):
        budget.execute(failed, deadline=90)
    assert (
        budget.execute(lambda _: "recovered explicit operation", deadline=90)
        == "recovered explicit operation"
    )
    with pytest.raises(rate.AttemptBudgetExceeded):
        budget.execute(lambda _: pytest.fail("Budget reset unexpectedly"), deadline=90)


def test_already_queued_callback_stops_after_first_429(modules):
    rate, _ = modules
    budget = rate.RateBudget(max_attempts=2)
    entered, release, queued = threading.Event(), threading.Event(), threading.Event()
    calls, errors = [], []
    deadline = time.monotonic() + 3

    def first(_):
        calls.append("first")
        entered.set()
        assert release.wait(2)
        raise rate.RateLimited("10")

    def worker(operation, signal=None):
        if signal:
            signal.set()
        try:
            budget.execute(operation, deadline=deadline)
        except Exception as error:
            errors.append(error)

    one = threading.Thread(target=worker, args=(first,))
    two = threading.Thread(
        target=worker, args=(lambda _: calls.append("second"), queued)
    )
    try:
        one.start()
        assert entered.wait(1)
        two.start()
        assert queued.wait(1)
    finally:
        release.set()
        one.join(2)
        two.join(2)
    assert not one.is_alive() and not two.is_alive()
    assert calls == ["first"]
    assert len(errors) == 2
    assert any(isinstance(e, rate.RateLimitHold) for e in errors)


def test_lock_wait_cancellation_does_not_cancel_inflight_callback(modules):
    rate, _ = modules
    budget = rate.RateBudget(max_attempts=2)
    entered, release, cancelled, waiting = (threading.Event() for _ in range(4))
    calls, errors = [], []
    deadline = time.monotonic() + 3

    def first(_):
        calls.append("inflight")
        entered.set()
        assert release.wait(2)

    def queued():
        waiting.set()
        try:
            budget.execute(
                lambda _: calls.append("never"),
                deadline=deadline,
                cancelled=cancelled.is_set,
            )
        except Exception as error:
            errors.append(error)

    one = threading.Thread(target=lambda: budget.execute(first, deadline=deadline))
    two = threading.Thread(target=queued)
    try:
        one.start()
        assert entered.wait(1)
        two.start()
        assert waiting.wait(1)
        cancelled.set()
        two.join(1)
        assert not two.is_alive()
        assert one.is_alive()
    finally:
        release.set()
        one.join(2)
        two.join(2)
    assert calls == ["inflight"]
    assert len(errors) == 1 and isinstance(errors[0], rate.AdmissionCancelled)


def test_concurrent_resume_is_atomic_and_never_resets_attempt_budget(modules):
    rate, _ = modules
    clock = Clock()
    budget = clock.budget(rate, max_attempts=1)

    def limited(_):
        raise rate.RateLimited("10")

    with pytest.raises(rate.RateLimited):
        budget.execute(limited, deadline=100)
    clock.now = 10
    barrier = threading.Barrier(2)
    results = []

    def resume():
        barrier.wait(timeout=1)
        results.append(budget.resume(deadline=100))

    threads = [threading.Thread(target=resume) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert sorted(results) == [False, True]
    with pytest.raises(rate.AttemptBudgetExceeded):
        budget.execute(lambda _: pytest.fail("Attempt budget was reset"), deadline=100)


@pytest.mark.parametrize("deadline", [math.inf, math.nan])
def test_nonfinite_deadline_is_rejected_without_send(modules, deadline):
    rate, _ = modules
    with pytest.raises(ValueError):
        Clock().budget(rate).execute(
            lambda _: pytest.fail("Invalid deadline sent"), deadline=deadline
        )


@pytest.mark.parametrize("attempts", [0, -1, True])
def test_invalid_attempt_budget(modules, attempts):
    rate, _ = modules
    with pytest.raises(ValueError):
        rate.RateBudget(max_attempts=attempts)


@pytest.mark.parametrize("interval", [0, 9.9, math.inf, math.nan])
def test_invalid_admission_interval(modules, interval):
    rate, _ = modules
    with pytest.raises(ValueError):
        rate.RateBudget(minimum_interval=interval)


def response(document, media="application/json"):
    stream = io.BytesIO(json.dumps(document).encode())
    stream.headers = Message()
    stream.headers["Content-Type"] = media
    return stream


def test_actual_four_request_discovery_caller_uses_one_budget(
    modules, monkeypatch, capsys
):
    rate, smoke = modules
    clock = Clock()
    budget = clock.budget(rate)
    monkeypatch.setattr(smoke, "RateBudget", lambda **_: budget)
    monkeypatch.setattr(smoke, "time", SimpleNamespace(monotonic=lambda: clock.now))
    starts = []

    def opener(request, timeout):
        payload = json.loads(request.data)
        method = payload["method"]
        starts.append((clock.now, method, timeout))
        assert request.get_header("Accept") == "application/json, text/event-stream"
        assert request.get_header("Mcp-method") == method
        if method == "server/discover":
            result = {"supportedVersions": [smoke.CONTRACT["protocolVersion"]]}
        else:
            key = method.split("/")[0]
            field = "uri" if key == "resources" else "name"
            result = {key: [{field: value} for value in smoke.CONTRACT[key]]}
        return response({"jsonrpc": "2.0", "id": 1, "result": result})

    monkeypatch.setattr(smoke, "urlopen", opener)
    assert smoke.main() == 0
    assert [s[0] for s in starts] == pytest.approx([0, 10, 20, 30])
    assert len(starts) == 4 and all(0 < s[2] <= 20 for s in starts)
    assert json.loads(capsys.readouterr().out)["tools"] == smoke.CONTRACT["tools"]


def test_actual_http_429_is_preserved_without_second_send(modules, monkeypatch):
    rate, smoke = modules
    clock = Clock()
    budget = clock.budget(rate)
    requests = []

    def opener(request, timeout):
        requests.append(request)
        headers = Message()
        headers["Retry-After"] = "25"
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    monkeypatch.setattr(smoke, "urlopen", opener)
    with pytest.raises(rate.RateLimited):
        smoke.call("server/discover", budget=budget, deadline=90)
    with pytest.raises(rate.RateLimitHold):
        smoke.call("tools/list", budget=budget, deadline=90)
    assert len(requests) == 1


@pytest.mark.parametrize("media", ["text/event-stream", "text/html"])
def test_json_response_smoke_explicitly_rejects_other_media(
    modules, monkeypatch, media
):
    rate, smoke = modules
    monkeypatch.setattr(smoke, "urlopen", lambda *a, **k: response({}, media))
    with pytest.raises(ValueError, match="requires JSON"):
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)


def test_discovery_response_size_is_bounded(modules, monkeypatch):
    rate, smoke = modules
    value = io.BytesIO(b" " * 2_097_153)
    value.headers = Message()
    value.headers["Content-Type"] = "application/json"
    monkeypatch.setattr(smoke, "urlopen", lambda *a, **k: value)
    with pytest.raises(ValueError, match="2 MiB"):
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)


def test_clock_crossing_admission_between_reads_never_sleeps_negative(modules):
    rate, _ = modules

    class AdvancingClock:
        def __init__(self):
            self.now = 0.0

        def read(self):
            value = self.now
            self.now += 0.06
            return value

        def sleep(self, duration):
            assert duration >= 0, "Root regression: negative admission sleep"
            self.now += duration

    clock = AdvancingClock()
    budget = rate.RateBudget(clock=clock.read, wall_clock=lambda: 0, sleep=clock.sleep)
    calls = []
    budget.execute(lambda _: calls.append(clock.now), deadline=100)
    budget.execute(lambda _: calls.append(clock.now), deadline=100)
    assert len(calls) == 2
    assert calls[1] >= calls[0] + 10


def test_metadata_transport_never_follows_redirects(modules, monkeypatch, no_network):
    from urllib.request import BaseHandler, build_opener
    from urllib.response import addinfourl

    rate, smoke = modules
    sent = []

    class RedirectResponse(BaseHandler):
        handler_order = 100

        def https_open(self, request):
            sent.append(request.full_url)
            headers = Message()
            headers["Location"] = "https://example.com/unbudgeted"
            reply = addinfourl(io.BytesIO(b""), headers, request.full_url, 302)
            reply.msg = "Found"
            return reply

    opener = build_opener(smoke.NoRedirect(), RedirectResponse())
    monkeypatch.setattr(smoke, "urlopen", opener.open)
    with pytest.raises(HTTPError) as error:
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)
    assert error.value.code == 302
    assert sent == [smoke.CONTRACT["endpoint"]]
    assert no_network == []


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"jsonrpc": "2.0", "id": True, "result": {}},
        {"jsonrpc": "2.0", "id": 2, "result": {}},
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600}},
        {"jsonrpc": "1.0", "id": 1, "result": {}},
        {"jsonrpc": "2.0", "id": 1, "result": []},
    ],
)
def test_metadata_rpc_error_shape_and_identity_never_qualify_success(
    modules, monkeypatch, document
):
    rate, smoke = modules
    monkeypatch.setattr(smoke, "urlopen", lambda *a, **k: response(document))
    with pytest.raises(ValueError, match="discovery RPC"):
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)


def test_metadata_duplicate_json_keys_rejected(modules, monkeypatch):
    rate, smoke = modules
    reply = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":{},"result":{}}')
    reply.headers = Message()
    reply.headers["Content-Type"] = "application/json"
    monkeypatch.setattr(smoke, "urlopen", lambda *a, **k: reply)
    with pytest.raises(ValueError, match="Duplicate JSON"):
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)


def test_rate_guidance_relative_links_are_present(modules):
    import re

    document = OPS.parent / "docs" / "RATE_LIMITS.md"
    text = document.read_text()
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if not target.startswith("https://"):
            assert (document.parent / target).is_file(), target


def test_real_opener_is_blocked_before_dns_or_connect(modules, no_network):
    rate, smoke = modules
    with pytest.raises(OfflineNetworkAttempt, match="create_connection"):
        smoke.call("server/discover", budget=Clock().budget(rate), deadline=90)
    assert no_network == ["create_connection"]
