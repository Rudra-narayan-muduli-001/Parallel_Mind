import pytest
from core.router.candidate_rotation import RotatingCandidatePool


@pytest.mark.asyncio
async def test_rotation_cycles():
    pool = RotatingCandidatePool([("a", "m1"), ("b", "m2"), ("c", "m3")])
    r1 = await pool.next_ordering()
    r2 = await pool.next_ordering()
    r3 = await pool.next_ordering()
    r4 = await pool.next_ordering()
    assert r1 == [("a", "m1"), ("b", "m2"), ("c", "m3")]
    assert r2 == [("b", "m2"), ("c", "m3"), ("a", "m1")]
    assert r3 == [("c", "m3"), ("a", "m1"), ("b", "m2")]
    assert r4 == [("a", "m1"), ("b", "m2"), ("c", "m3")]


@pytest.mark.asyncio
async def test_empty_candidates():
    pool = RotatingCandidatePool([])
    result = await pool.next_ordering()
    assert result == []


@pytest.mark.asyncio
async def test_single_candidate():
    pool = RotatingCandidatePool([("x", "y")])
    r1 = await pool.next_ordering()
    r2 = await pool.next_ordering()
    assert r1 == [("x", "y")]
    assert r2 == [("x", "y")]
