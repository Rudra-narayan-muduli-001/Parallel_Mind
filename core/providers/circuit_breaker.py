import time


class CircuitBreaker:
    """CLOSED -> OPEN (after N consecutive failures) -> HALF_OPEN (after cooldown,
    trial request allowed) -> CLOSED (on success) or back to OPEN (on failure)."""

    def __init__(self, fail_threshold: int = 5, reset_timeout: float = 60.0):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.state = "CLOSED"
        self.opened_at = None

    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if self.opened_at and (time.time() - self.opened_at) > self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            self.opened_at = time.time()
            return
        if self.failures >= self.fail_threshold:
            self.state = "OPEN"
            self.opened_at = time.time()