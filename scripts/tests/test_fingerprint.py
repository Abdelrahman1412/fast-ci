from fingerprint import fingerprint


def make(tmp_path):
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "0001.sql").write_text("CREATE TABLE a (id int);")
    (tmp_path / "migrate.py").write_text("print('migrate')")
    return tmp_path


def test_stable_for_the_same_inputs(tmp_path):
    root = make(tmp_path)
    forward = fingerprint(root, ["migrations/*.sql", "migrate.py"])[0]
    assert forward == fingerprint(root, ["migrate.py", "migrations/*.sql"])[0]


def test_changes_when_a_migration_changes(tmp_path):
    root = make(tmp_path)
    before = fingerprint(root, ["migrations/*.sql"])[0]
    (root / "migrations" / "0001.sql").write_text("CREATE TABLE a (id bigint);")
    assert fingerprint(root, ["migrations/*.sql"])[0] != before


def test_changes_when_a_migration_is_added(tmp_path):
    root = make(tmp_path)
    before = fingerprint(root, ["migrations/*.sql"])[0]
    (root / "migrations" / "0002.sql").write_text("CREATE TABLE b (id int);")
    assert fingerprint(root, ["migrations/*.sql"])[0] != before


def test_changes_with_the_postgres_major(tmp_path):
    root = make(tmp_path)
    assert fingerprint(root, ["migrations/*.sql"], "pg16")[0] != fingerprint(root, ["migrations/*.sql"], "pg17")[0]


def test_a_pattern_that_matches_nothing_is_an_error(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        fingerprint(make(tmp_path), ["migrations/*.py"])
