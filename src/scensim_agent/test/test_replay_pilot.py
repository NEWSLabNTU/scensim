"""replay_pilot without ROS (092 K2.4): commands by world frame, held before the goal and past
the last, one per frame whatever the clock's rate, and the per-frame log."""

import json

import pytest

from scensim_agent.adapters import replay_pilot as R

CMDS = [{"accel": 1.0, "velocity": 2.0, "steer": 0.0},
        {"accel": 0.5, "velocity": 3.0, "steer": 0.1},
        {"accel": 0.0, "velocity": 3.0, "steer": -0.1}]


def write(tmp_path, doc, name="cmds.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return p


def test_world_frame_counts_from_the_clock_origin():
    assert R.world_frame(1000.0, 0.05) == 0
    assert R.world_frame(1000.0 + 0.05 * 37 + 1e-9, 0.05) == 37
    assert R.world_frame(1000.0 + 0.05 * 37 - 1e-6, 0.05) == 37


def test_holds_until_the_goal_then_one_command_per_frame():
    r = R.Replay(0.05, CMDS, hold_accel=-2.0)
    k, c = r.frame(10)
    assert k is None and c == {"accel": -2.0, "velocity": 0.0, "steer": 0.0}
    r.arm()
    assert r.frame(11) == (0, CMDS[0])
    assert r.frame(11) is None                # the same frame again: nothing (a faster clock)
    assert r.frame(10) is None                # nor an older one
    assert r.frame(12) == (1, CMDS[1])
    assert r.frame(14) == (3, CMDS[2])        # a skipped frame keeps the index by frame
    assert r.skipped == 1
    assert r.frame(20) == (9, CMDS[2])        # past the last: held
    assert r.f0 == 11


def test_stop_holds_and_a_new_goal_starts_again():
    r = R.Replay(0.05, CMDS)
    r.arm()
    r.frame(5)
    r.disarm()
    assert r.frame(6)[0] is None
    r.arm()
    assert r.frame(7) == (0, CMDS[0])


def test_load_commands(tmp_path):
    dt, cmds = R.load_commands(write(tmp_path, {"step_time": 0.05, "commands": CMDS}))
    assert dt == 0.05 and cmds == CMDS
    with pytest.raises(ValueError, match="needs step_time"):
        R.load_commands(write(tmp_path, {"commands": CMDS}))
    with pytest.raises(ValueError, match=r"commands\[1\] has no steer"):
        R.load_commands(write(tmp_path, {"step_time": 0.05, "commands": [
            CMDS[0], {"accel": 0.0, "velocity": 0.0}]}))
    with pytest.raises(ValueError, match="no commands"):
        R.load_commands(write(tmp_path, {"step_time": 0.05, "commands": []}))
    y = tmp_path / "cmds.yaml"
    y.write_text("step_time: 0.1\ncommands:\n  - {accel: 0, velocity: 1, steer: 0}\n")
    assert R.load_commands(y) == (0.1, [{"accel": 0.0, "velocity": 1.0, "steer": 0.0}])


class FakeVehicle:
    def __init__(self):
        self.sent = []

    def publish(self, cmd):
        self.sent.append(cmd)

    def close(self):
        pass


def test_the_agent_publishes_and_logs_each_frame(tmp_path):
    cmds = write(tmp_path, {"step_time": 0.05, "commands": CMDS})
    log = tmp_path / "replay.jsonl"
    v = FakeVehicle()
    a = R.ReplayPilotAgent({"commands": str(cmds), "log": str(log)}, vehicle=v)
    a.on_reset(None)
    a.on_frame(3, 1000.15, {"steering": 0.0, "velocity": 0.0})
    a.on_goal({}, [])
    a.on_frame(4, 1000.20, {"steering": 0.0, "velocity": 0.0})
    a.on_frame(4, 1000.20, {"steering": 0.0, "velocity": 0.0})
    a.on_frame(5, 1000.25, {"steering": 0.05, "velocity": 0.1})
    a.on_speed_limit(13.9)
    a.close()
    assert v.sent == [{"accel": -3.0, "velocity": 0.0, "steer": 0.0}, CMDS[0], CMDS[1]]
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[-1] == {"speed_limit": 13.9}
    rows = rows[:-1]
    assert rows[0] == {"reset": True}
    assert [(r["frame"], r["k"]) for r in rows[1:]] == [(3, None), (4, 0), (5, 1)]
    assert rows[3]["status"] == {"steering": 0.05, "velocity": 0.1}
    assert rows[3]["cmd"] == CMDS[1]
    assert rows[3]["clock_ns"] == 1_000_250_000_000 and rows[3]["skipped"] == 0


def test_no_commands_file_is_refused():
    with pytest.raises(ValueError, match="give commands"):
        R.ReplayPilotAgent({}, vehicle=FakeVehicle())
