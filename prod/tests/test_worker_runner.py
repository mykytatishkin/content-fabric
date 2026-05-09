"""Tests for shared.queue.worker_runner — Redis failover handling."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _install_redis_stub():
    """Install a minimal redis.exceptions stub if redis isn't importable."""
    if "redis" in sys.modules and hasattr(sys.modules["redis"], "exceptions"):
        return

    redis_mod = types.ModuleType("redis")
    exc_mod = types.ModuleType("redis.exceptions")

    class ReadOnlyError(Exception):
        pass

    class ResponseError(Exception):
        pass

    class ConnectionError(Exception):  # noqa: A001 — mirror redis name
        pass

    exc_mod.ReadOnlyError = ReadOnlyError
    exc_mod.ResponseError = ResponseError
    exc_mod.ConnectionError = ConnectionError
    redis_mod.exceptions = exc_mod
    sys.modules["redis"] = redis_mod
    sys.modules["redis.exceptions"] = exc_mod


def _make_worker_factory(side_effect):
    """Return a callable that mimics rq.Worker(...).work() raising `side_effect`."""
    worker_inst = MagicMock()
    worker_inst.work.side_effect = side_effect
    factory = MagicMock(return_value=worker_inst)
    return factory, worker_inst


@pytest.fixture(autouse=True)
def _stub_redis():
    _install_redis_stub()
    yield


def test_run_worker_clean_exit_returns_zero():
    """Normal `worker.work()` return -> exit code 0."""
    from shared.queue import worker_runner

    factory, _ = _make_worker_factory(side_effect=None)
    rq_mod = types.ModuleType("rq")
    rq_mod.Worker = factory
    with patch.dict(sys.modules, {"rq": rq_mod}):
        rc = worker_runner.run_worker(["q"], MagicMock(), "test-worker")
    assert rc == 0


def test_run_worker_swallows_readonly_error_during_failover():
    """ReadOnlyError on shutdown is treated as a clean failover restart."""
    from redis.exceptions import ReadOnlyError
    from shared.queue import worker_runner

    err = ReadOnlyError(
        "Command # 1 (SREM rq:workers ...) of pipeline caused error: "
        "You can't write against a read only replica."
    )
    factory, _ = _make_worker_factory(side_effect=err)
    rq_mod = types.ModuleType("rq")
    rq_mod.Worker = factory
    with patch.dict(sys.modules, {"rq": rq_mod}):
        rc = worker_runner.run_worker(["q"], MagicMock(), "test-worker")
    # Failover -> systemd should restart, but exit cleanly so the
    # restart counter doesn't escalate.
    assert rc == 0


def test_run_worker_swallows_unblocked_response_error():
    """`UNBLOCKED ... master -> replica?` ResponseError is treated as failover."""
    from redis.exceptions import ResponseError
    from shared.queue import worker_runner

    err = ResponseError(
        "UNBLOCKED force unblock from blocking operation, "
        "instance state changed (master -> replica?)"
    )
    factory, _ = _make_worker_factory(side_effect=err)
    rq_mod = types.ModuleType("rq")
    rq_mod.Worker = factory
    with patch.dict(sys.modules, {"rq": rq_mod}):
        rc = worker_runner.run_worker(["q"], MagicMock(), "test-worker")
    assert rc == 0


def test_run_worker_propagates_unexpected_response_error():
    """A ResponseError unrelated to failover should NOT be silently swallowed.

    We log + return non-zero so systemd flags the failure.
    """
    from redis.exceptions import ResponseError
    from shared.queue import worker_runner

    err = ResponseError("WRONGTYPE Operation against a key holding the wrong kind of value")
    factory, _ = _make_worker_factory(side_effect=err)
    rq_mod = types.ModuleType("rq")
    rq_mod.Worker = factory
    with patch.dict(sys.modules, {"rq": rq_mod}):
        rc = worker_runner.run_worker(["q"], MagicMock(), "test-worker")
    assert rc == 1
