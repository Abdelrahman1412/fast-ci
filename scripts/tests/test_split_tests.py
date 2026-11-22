import pytest
from split_tests import split


def test_balances_by_time_not_count():
    tests = ["a.py::slow"] + [f"b.py::fast{i}" for i in range(9)]
    durations = {"a.py::slow": 9.0, **{f"b.py::fast{i}": 1.0 for i in range(9)}}
    buckets, totals, _ = split(tests, durations, 2)
    assert sorted(totals) == [9.0, 9.0]
    assert ["a.py::slow"] in buckets


def test_every_test_lands_in_exactly_one_shard():
    tests = [f"t.py::case{i}" for i in range(101)]
    buckets, _, _ = split(tests, {}, 7)
    flat = [t for b in buckets for t in b]
    assert sorted(flat) == sorted(tests)
    assert len(flat) == len(set(flat))


def test_unknown_tests_get_the_median():
    tests = ["x.py::known1", "x.py::known2", "x.py::known3", "x.py::new"]
    _, totals, info = split(tests, {"x.py::known1": 1, "x.py::known2": 2, "x.py::known3": 3}, 1)
    assert info["unknown"] == 1
    assert info["default"] == 2
    assert totals == [8]


def test_group_by_file_keeps_files_together_and_reports_the_heaviest():
    tests = ["slow.py::a", "slow.py::b", "fast.py::a", "fast.py::b"]
    durations = {"slow.py::a": 5, "slow.py::b": 5, "fast.py::a": 1, "fast.py::b": 1}
    buckets, totals, info = split(tests, durations, 2, group_by="file")
    assert sorted(map(sorted, buckets)) == [["fast.py::a", "fast.py::b"], ["slow.py::a", "slow.py::b"]]
    assert info["heaviest_unit"] == "slow.py"
    assert info["heaviest_seconds"] > info["ideal"]


def test_split_is_deterministic():
    tests = [f"t.py::case{i}" for i in range(50)]
    durations = {t: (i % 7) / 10 for i, t in enumerate(tests)}
    assert split(tests, durations, 4) == split(list(tests), dict(durations), 4)


def test_more_shards_than_tests_leaves_empty_shards():
    buckets, _, _ = split(["a.py::x"], {}, 3)
    assert sum(1 for b in buckets if not b) == 2


def test_rejects_zero_shards():
    with pytest.raises(ValueError):
        split(["a.py::x"], {}, 0)
