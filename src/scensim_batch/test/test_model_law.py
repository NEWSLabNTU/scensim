"""The batch's model law against the CARLA world server's COMMANDED integrator (roadmap 092 K12,
exit check 1): both read one fixture, scensim_carla_world's src/commanded_law.json, which this
test writes from scensim_batch.core.model_law (SCENSIM_WRITE_LAW_FIXTURE=1) and otherwise
checks; commanded.rs's test steps its Body through the same commands and compares."""
import json
import math
import os
import unittest
from pathlib import Path

try:
    import torch
    from scensim_batch.core import model_law
except ImportError:
    torch = None

FIXTURE = (Path(__file__).resolve().parents[2] / "scensim_carla_world" / "scensim_carla_world"
           / "src" / "commanded_law.json")
DT = 0.05
START = (10.0, -3.0)
# (speed, heading, accel_limit): speed up, hold, brake hard, turn, a reversal of heading, a slow
# creep, and commands above and below the reachable change, so the clamp acts both ways
COMMANDS = [(1.4, 0.3, 1.0)] * 4 + [(0.0, 0.3, 2.5)] * 3 + [(1.4, -1.2, 0.8)] * 5 + \
    [(2.9, math.pi - 0.01, 3.0)] * 4 + [(0.1, 2.0, 0.05)] * 3 + [(1.0, -2.5, 10.0)] * 2


def law_states():
    x, y, v = (torch.tensor([a], dtype=torch.float64) for a in (*START, 0.0))
    out = []
    for speed, heading, limit in COMMANDS:
        t = lambda a: torch.tensor([a], dtype=torch.float64)   # noqa: E731
        x, y, v = model_law(x, y, v, t(speed), t(heading), t(limit), DT)
        out.append([float(x), float(y), float(v), heading])
    return out


@unittest.skipIf(torch is None, "torch is not importable here")
class ModelLaw(unittest.TestCase):
    def test_the_fixture_is_the_batchs_law(self):
        fixture = {"dt": DT, "start": list(START), "commands": [list(c) for c in COMMANDS],
                   "states": law_states()}
        if os.environ.get("SCENSIM_WRITE_LAW_FIXTURE") == "1":
            FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")
        self.assertTrue(FIXTURE.is_file(), f"{FIXTURE} missing: SCENSIM_WRITE_LAW_FIXTURE=1")
        got = json.loads(FIXTURE.read_text())
        self.assertEqual((got["dt"], got["start"], got["commands"]),
                         (fixture["dt"], fixture["start"], fixture["commands"]))
        for k, (a, b) in enumerate(zip(got["states"], fixture["states"])):
            for u, w in zip(a, b):
                self.assertTrue(math.isclose(u, w, rel_tol=1e-12, abs_tol=1e-12), (k, a, b))


if __name__ == "__main__":
    unittest.main()
