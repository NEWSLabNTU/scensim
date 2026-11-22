"""A wait ceiling for a child's readiness that grows with the host's load."""
import os


def ceiling(base=120.0):
    """How long to wait for a child to get ready: at least `base` s, longer on a loaded host
    (by the load per core, above 1). A fixed 20-30 s lost to gates at load 105 on 32 cores; it
    costs nothing when the child is ready sooner."""
    try:
        per_core = os.getloadavg()[0] / (os.cpu_count() or 1)
    except OSError:
        per_core = 1.0
    return base * max(1.0, per_core)


def STOP_WAIT():  # noqa: N802 - read as a constant at the call
    """How long to wait for a stack keeper (start_stack's) to stop after SIGTERM: its children's
    stop ladder (scensim.stack.stop_processes: SIGINT, 20 s, SIGTERM, 10 s, SIGKILL, 5 s) plus
    room, longer on a loaded host. A fixed 10 s timed out at load ~30 (issue 112)."""
    return ceiling(base=60.0)
