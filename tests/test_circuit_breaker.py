import time
from core.providers.circuit_breaker import CircuitBreaker


def test_initial_state():
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=0.1)
    assert cb.allow_request() is True
    assert cb.state == "CLOSED"


def test_opens_after_threshold():
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=60)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False


def test_half_open_on_reset_timeout():
    cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "OPEN"
    time.sleep(0.06)
    assert cb.allow_request() is True
    assert cb.state == "HALF_OPEN"


def test_closes_on_success_in_half_open():
    cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    cb.allow_request()
    cb.record_success()
    assert cb.state == "CLOSED"


def test_opens_again_on_failure_in_half_open():
    cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    time.sleep(0.06)
    cb.allow_request()
    cb.record_failure()
    assert cb.state == "OPEN"


def test_record_success_resets_failures():
    cb = CircuitBreaker(fail_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.failures == 0
    assert cb.state == "CLOSED"
