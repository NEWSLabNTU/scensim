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
