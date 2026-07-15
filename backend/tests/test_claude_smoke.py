"""Regression tests for the real-provider smoke command."""
import os
import subprocess
import sys
from pathlib import Path


def test_smoke_script_reports_missing_openrouter_key_from_any_working_directory(
    tmp_path: Path,
) -> None:
    """The command must find app imports before it validates provider credentials."""
    script = Path(__file__).resolve().parents[1] / "scripts" / "claude_smoke.py"
    env = os.environ.copy()
    env.update(
        {
            "USE_MOCK_CLAUDE": "false",
            "AI_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "",
        }
    )
    # pytest-cov propagates its bootstrap variables to child processes. This
    # command deliberately runs from a temporary directory, where it cannot
    # locate the repository coverage configuration and would corrupt totals.
    for key in list(env):
        if key.startswith("COV_CORE_") or key == "COVERAGE_PROCESS_START":
            env.pop(key)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "OPENROUTER_API_KEY is required" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
