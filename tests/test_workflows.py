from pathlib import Path


def test_bootstrap_pipeline_propagates_python_failure_and_captures_stderr():
    workflow = Path(".github/workflows/bootstrap.yml").read_text(encoding="utf-8")

    assert "set -o pipefail" in workflow
    assert "python -u -m src.bootstrap 2>&1 | tee bootstrap-output.txt" in workflow
    assert "bootstrap_status=${PIPESTATUS[0]}" in workflow
    assert 'exit "$bootstrap_status"' in workflow


def test_daily_schedule_is_0910_kst_in_utc():
    workflow = Path(".github/workflows/daily-sync.yml").read_text(encoding="utf-8")

    assert 'cron: "10 0 * * *"' in workflow
    assert 'timezone: "Asia/Seoul"' not in workflow
