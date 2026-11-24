"""scensim-agent supervise: a group of zombies is gone (issue 153)."""
from scensim_agent import supervise


def test_a_group_whose_only_member_left_is_a_zombie_is_gone_issue_153():
    """A zombie keeps its group, so ``killpg(pgid, 0)`` alone calls it alive; under a PID 1
    that never reaps, an orphaned one stays for good (issue 153)."""
    import os
    import subprocess
    import time
    p = subprocess.Popen(["true"], start_new_session=True)   # its own group; not reaped yet
    try:
        deadline = time.time() + 30
        while open(f"/proc/{p.pid}/stat").read().rsplit(")", 1)[1].split()[0] != "Z":
            assert time.time() < deadline, "the child never exited"
            time.sleep(0.05)
        os.killpg(p.pid, 0)   # the probe this replaces: the zombie still answers
        assert not supervise.group_alive(p.pid)
    finally:
        p.wait()
    assert not supervise.group_alive(p.pid)


def test_a_group_with_a_live_member_is_alive_issue_153():
    import subprocess
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        assert supervise.group_alive(p.pid)
    finally:
        p.kill()
        p.wait()
