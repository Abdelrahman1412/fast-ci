import pytest
from ci_result import judge


def needs(plan_result="success", run="true", **jobs):
    out = {"plan": {"result": plan_result, "outputs": {"run": run}}}
    out.update({name: {"result": result, "outputs": {}} for name, result in jobs.items()})
    return out


def test_all_green():
    assert judge(needs(test="success", gate="success"), "plan", set())[0]


@pytest.mark.parametrize("result", ["failure", "cancelled"])
def test_a_failed_or_cancelled_job_fails(result):
    assert not judge(needs(test=result, gate="success"), "plan", set())[0]


def test_skipped_because_upstream_failed_is_not_green():
    # test failed, so gate was skipped: GitHub would count the skip as a pass.
    ok, lines = judge(needs(test="failure", gate="skipped"), "plan", set())
    assert not ok
    assert any("gate: skipped, but the plan said it should run" in line for line in lines)


def test_skips_are_fine_when_nothing_relevant_changed():
    assert judge(needs(run="false", test="skipped", gate="skipped"), "plan", set())[0]


def test_allowed_skips():
    assert judge(needs(test="success", e2e_full="skipped"), "plan", {"e2e_full"})[0]


def test_plan_failure_fails():
    assert not judge(needs(plan_result="failure", test="skipped"), "plan", set())[0]


def test_missing_plan_job_fails():
    assert not judge({"test": {"result": "success"}}, "plan", set())[0]
