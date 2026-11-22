from pathlib import Path

import pytest
from ci_config import ConfigError, load, render, resolve_lanes

REPO = Path(__file__).resolve().parent.parent.parent


def write(tmp_path, text):
    path = tmp_path / "fast-ci.toml"
    path.write_text(text)
    return path


def test_the_shipped_example_is_valid():
    backend = load(REPO / "fast-ci.toml", "backend")
    frontend = load(REPO / "fast-ci.toml", "frontend")
    assert backend["shard_list"] == list(range(1, backend["shards"] + 1))
    assert frontend["playwright_shard_list"]


def test_defaults_fill_missing_keys(tmp_path):
    cfg = load(write(tmp_path, "[backend]\nshards = 2\n"), "backend", with_fingerprint=False)
    assert cfg["shard_list"] == [1, 2]
    assert cfg["rerun_policy"] == "fail"


@pytest.mark.parametrize(
    "text",
    [
        "[backend]\nshard = 2\n",
        "[backend]\nshards = 0\n",
        "[backend]\ngroup_by = 'dir'\n",
        "[backend]\nrerun_policy = 'ignore'\n",
        "[frontend]\n[frontend.lanes]\npull_request = ['smoke']\n",
    ],
)
def test_typos_and_bad_values_are_errors(tmp_path, text):
    section = "frontend" if "frontend" in text else "backend"
    with pytest.raises(ConfigError):
        load(write(tmp_path, text), section, with_fingerprint=False)


@pytest.mark.parametrize(
    ("event", "lanes"),
    [("pull_request", ["mock"]), ("push", ["mock", "full"]), ("schedule", ["mock", "full"]), ("merge_group", ["mock"])],
)
def test_lanes_follow_the_event(event, lanes):
    cfg = load(REPO / "fast-ci.toml", "frontend")
    assert resolve_lanes(cfg, event) == lanes


def test_manual_lane_override():
    cfg = load(REPO / "fast-ci.toml", "frontend")
    assert resolve_lanes(cfg, "pull_request", "full") == ["full"]
    with pytest.raises(ConfigError):
        resolve_lanes(cfg, "pull_request", "everything")


def test_render_writes_json_for_lists_and_heredoc_for_filters(tmp_path):
    path = write(tmp_path, "[backend]\nshards = 2\npaths = ['api/**']\n")
    lines = render(load(path, "backend", with_fingerprint=False))
    assert "shard_list=[1,2]" in lines
    assert "paths_filter<<EOF_FASTCI\nchanged:\n  - 'api/**'\nEOF_FASTCI" in lines


def test_fingerprint_inputs_that_match_nothing_are_an_error(tmp_path):
    (tmp_path / "backend").mkdir()
    with pytest.raises(ConfigError, match="migration_inputs"):
        load(write(tmp_path, "[backend]\nmigration_inputs = ['migrations/*.sql']\n"), "backend")


def test_shipped_example_fingerprint_is_stable():
    first = load(REPO / "fast-ci.toml", "backend")["migration_fingerprint"]
    assert first == load(REPO / "fast-ci.toml", "backend")["migration_fingerprint"]
    assert len(first) == 20
