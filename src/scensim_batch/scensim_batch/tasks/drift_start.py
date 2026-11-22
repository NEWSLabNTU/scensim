"""The drift run's start draw (094 P2), without Isaac Lab: stock's 20 reference points a run."""
import math

LINE_RADIUS, STRAIGHT = 0.8, 0.8                 # stock's oval (mushr_drift_env_cfg.py)
TRACK_LENGTH = 2 * math.pi * LINE_RADIUS + 4 * STRAIGHT
REFERENCE_POINTS = 20                            # stock's num_points


def reference_points(seed):
    """The run's 20 reference points (m along the oval), as stock's reset_root_state_along_track
    draws them once per run (torch.rand x the track's length), here from the run's seed: the
    start distribution's knobs ref_s_0 to ref_s_19."""
    import numpy as np
    s = np.random.default_rng(int(seed)).uniform(0.0, TRACK_LENGTH, REFERENCE_POINTS)
    return {f"ref_s_{i}": float(v) for i, v in enumerate(s)}
