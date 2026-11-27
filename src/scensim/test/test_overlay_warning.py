"""Issue 195 (133's note): without the Autoware overlay, a reset that initializes localization
more than once can kill stock pose_instability_detector (docs/issues/027); the warning at an
Autoware start says so by name, with the command that builds the overlay."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "autoware_overlay.bash"


@pytest.mark.skipif(not SCRIPT.is_file(), reason="the workspace's scripts/ is not here")
def test_a_missing_overlay_warns_of_the_reset_crash(tmp_path):
    out = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; scensim_autoware_overlay_source "{tmp_path}/none" true'],
        capture_output=True, text=True, check=True)
    err = out.stderr
    assert "WARNING: Autoware overlay not built" in err
    assert "pose_instability_detector" in err and "reset" in err and "027" in err
    assert "build-autoware-overlay" in err
