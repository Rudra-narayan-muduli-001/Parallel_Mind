import pytest

from core.providers.key_pool import APIKeyPool, NoAvailableKeyError


@pytest.mark.asyncio
async def test_get_key_round_robin():
    pool = APIKeyPool(["key1", "key2", "key3"])
    first = await pool.get_key()
    second = await pool.get_key()
    third = await pool.get_key()
    fourth = await pool.get_key()
    assert first == "key1"
    assert second == "key2"
    assert third == "key3"
    assert fourth == "key1"


@pytest.mark.asyncio
async def test_skip_unhealthy_key():
    pool = APIKeyPool(["key1", "key2"])
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=5)
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=5)
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=5)
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=5)
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=5)
    key = await pool.get_key()
    assert key == "key2"


@pytest.mark.asyncio
async def test_all_keys_exhausted():
    pool = APIKeyPool(["key1"])
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=1)
    with pytest.raises(NoAvailableKeyError):
        await pool.get_key()


@pytest.mark.asyncio
async def test_report_success_resets():
    pool = APIKeyPool(["key1"])
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=1)
    pool.report_success("key1")
    key = await pool.get_key()
    assert key == "key1"


def test_has_healthy_key():
    pool = APIKeyPool(["key1", "key2"])
    assert pool.has_healthy_key() is True
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=1)
    pool.report_failure("key2", cooldown_sec=9999, fail_threshold=1)
    assert pool.has_healthy_key() is False


def test_reset():
    pool = APIKeyPool(["key1"])
    pool.report_failure("key1", cooldown_sec=9999, fail_threshold=1)
    pool.reset()
    assert pool.has_healthy_key() is True
