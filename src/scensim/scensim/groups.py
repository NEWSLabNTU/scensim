"""Process groups: whether anything of one is left (issue 153)."""
import os


def group_alive(pgid) -> bool:
    """Any process left in group ``pgid``, zombies excluded. A zombie keeps its group, so
    ``os.killpg(pgid, 0)`` alone counts it, and under a PID 1 that never reaps (a container
    without an init) an orphaned zombie stays for good (issue 153). The same function is in
    scripts/t3.py, scensim.groups and scensim_agent.supervise: keep the three identical."""
    try:
        os.killpg(pgid, 0)  # cheap: nothing of the group, not even a zombie
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
        except OSError:
            continue
        if fields[0] != "Z" and int(fields[2]) == pgid:
            return True
    return False
