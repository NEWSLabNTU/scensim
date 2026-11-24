"""A DDS domain of this test process's own (issue 155).

``take()`` holds the first free domain in ``DOMAINS`` by an exclusive ``flock`` on
``LOCK_DIR/<domain>.lock``, kept until the process ends (the kernel releases it however the
process ends), and sets ``ROS_DOMAIN_ID`` to it with ``ROS_LOCALHOST_ONLY=1``. Two test runs on
one host, from any worktree or session, never share a domain, so neither receives the other's
messages; a test's subprocesses inherit the domain from the environment.

Why 60-99, above CLAUDE.md's 57: that limit is the Cyclone localhost profile's (DomainGain
1000). These tests never run under it: ``CYCLONEDDS_URI`` is removed, and the RMW must be Fast
DDS or Cyclone with its defaults, both on the RTPS port mapping (base 7400, domain gain 250,
participant gain 2). Domain d's ports are 7400 + 250 d (+1 user multicast) and
7410 + 250 d + 2 p, 7411 + 250 d + 2 p for participant p (unicast): 22400 at d = 60, and at
d = 99 32150 to 32161 + 2 p, below Linux's ephemeral range (32768) for p up to 303. The seats'
own domains (default base 1, stride 8, count 7: 1 to 56) stay clear of the tests.

The same file is in scensim_agent's and scensim_launch's tests: keep the two identical."""
import fcntl
import os

DOMAINS = range(60, 100)
LOCK_DIR = "/tmp/scensim-test-domains"
RMWS = (None, "", "rmw_fastrtps_cpp", "rmw_cyclonedds_cpp")   # RTPS's port mapping, gain 250

_held = None   # (domain, fd): held for the life of the process


def take() -> int:
    """This process's domain, taken on the first call; ``RuntimeError`` when none is free."""
    global _held
    if _held is not None:
        return _held[0]
    rmw = os.environ.get("RMW_IMPLEMENTATION")
    if rmw not in RMWS:
        raise RuntimeError(f"test DDS domains assume Fast DDS or Cyclone, not {rmw!r} "
                           "(issue 155)")
    os.environ.pop("CYCLONEDDS_URI", None)   # the localhost profile: domains <= 57 only
    os.makedirs(LOCK_DIR, exist_ok=True)
    try:
        os.chmod(LOCK_DIR, 0o1777)   # every user's tests share the host's domains
    except PermissionError:
        pass   # another user's directory, already shared
    for d in DOMAINS:
        fd = os.open(os.path.join(LOCK_DIR, f"{d}.lock"), os.O_RDONLY | os.O_CREAT, 0o444)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            continue
        _held = (d, fd)
        os.environ["ROS_DOMAIN_ID"] = str(d)
        os.environ["ROS_LOCALHOST_ONLY"] = "1"
        return d
    raise RuntimeError(f"no free test domain in {DOMAINS.start}-{DOMAINS.stop - 1}: every one "
                       f"is held by another test run ({LOCK_DIR}; issue 155)")
