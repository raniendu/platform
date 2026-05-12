import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


def test_cli_file_execution_shows_help():
    result = subprocess.run(
        [sys.executable, str(APP_ROOT / "vikram" / "cli.py"), "--help"],
        capture_output=True,
        check=False,
        cwd=APP_ROOT,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: vikram" in result.stdout
    assert "--agent" in result.stdout
