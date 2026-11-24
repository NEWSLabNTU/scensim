"""scensim.attachments (roadmap 092 K4): processes tied to a run, which read the truth stream."""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from _ceiling import ceiling

from scensim import attachments as at

WATCH = """import json, os, signal, sys, time
out = os.path.join(os.environ["SCENSIM_ATTACHMENT_DIR"], "env.json")
json.dump({k: v for k, v in os.environ.items() if k.startswith(("SCENSIM_", "ROS_"))}, open(out, "w"))
mode = sys.argv[1] if len(sys.argv) > 1 else "wait"
if mode == "die":
    sys.exit(3)
signal.signal(signal.SIGINT, lambda *a: sys.exit(0 if mode == "wait" else 5))
open(os.path.join(os.environ["SCENSIM_ATTACHMENT_DIR"], "ready"), "w").close()
while True:
    time.sleep(0.05)
"""


def ready(run_dir, name="netsim", timeout=None):
    """Wait until the watch script has its SIGINT handler (it writes `ready` after): a fixed
    sleep raced a loaded host, whose SIGINT then found the default action (exit -2)."""
    f = run_dir / "attachments" / name / "ready"
    deadline = time.time() + (timeout or ceiling())
    while not f.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert f.exists(), "the attachment never got ready"


def ended(r, timeout=None):
    """Wait until the attachment's process has exited on its own."""
    deadline = time.time() + (timeout or ceiling())
    while r.proc.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    assert r.proc.poll() is not None, "the attachment never ended"


def att(tmp_path, mode="wait", **kw):
    (tmp_path / "watch.py").write_text(WATCH)
    return {"name": "netsim", "run": [sys.executable, str(tmp_path / "watch.py"), mode], **kw}


def test_problems():
    assert at.problems(None) == []
    assert at.problems({"x": 1}) == [("attachments", "is not a list")]
    p = dict(at.problems([{"name": "a", "run": ["x"], "lockstep": "yes", "colour": 1},
                          {"name": "a", "run": []},
                          {"name": "b/c", "run": ["x"], "stop_timeout": 0},
                          {"name": "d", "run": ["x"], "lifetime": "lab"}]))
    msgs = " | ".join(m for _, m in at.problems([{"name": "a", "run": ["x"], "lockstep": "yes",
                                                  "colour": 1}]))
    assert "unknown key 'colour'" in msgs and "lockstep: 'yes' is not true or false" in msgs
    assert "given twice" in p["attachments[1]"] or "run:" in p["attachments[1]"]
    allm = " | ".join(m for _, m in at.problems([{"name": "a", "run": []}, {"name": "a", "run": ["x"]},
                                                 {"name": "b/c", "run": ["x"], "stop_timeout": 0},
                                                 {"name": "d", "run": ["x"], "lifetime": "lab"}]))
    for want in ("run: a command", "given twice", "a plain name", "stop_timeout", "question 6"):
        assert want in allm, want
    # lockstep follows CARLA's tick gate; Isaac has none yet
    assert at.problems([{"name": "a", "run": ["x"], "lockstep": True}], "carla") == []
    (w, m), = at.problems([{"name": "a", "run": ["x"], "lockstep": True}], "isaac")
    assert "no tick gate yet" in m
    assert at.lockstep([{"lockstep": True}]) and not at.lockstep([{"name": "a"}, None])


def test_an_attachment_gets_its_env_is_stopped_and_recorded(tmp_path):
    run_dir = tmp_path / "run"
    a = att(tmp_path, lockstep=True)
    roles = at.roles([SimpleNamespace(name="ego", ego=True), SimpleNamespace(name="npc", ego=False),
                      SimpleNamespace(name="lead", ego=False)], [{"entity": "lead", "kind": "carla_basic"}])
    assert roles == {"ego": "ego", "npc": "scenario", "lead": "carla_basic"}
    env = at.env_for(a, {"ROS_DOMAIN_ID": "9", "PATH": "/usr/bin:/bin"}, run_dir, 42, roles,
                     tick_gate="127.0.0.1:5561")
    r = at.start(a, env, run_dir, tmp_path)
    deadline = time.time() + ceiling()
    seen = run_dir / "attachments" / "netsim" / "env.json"
    while not seen.is_file() and time.time() < deadline:
        time.sleep(0.05)
    ready(run_dir)
    at.stop(r)
    e = json.loads(seen.read_text())
    assert e["SCENSIM_RUN_DIR"] == str(run_dir) and e["SCENSIM_RUN_SEED"] == "42"
    assert e["SCENSIM_ATTACHMENT_DIR"].endswith("attachments/netsim")
    assert json.loads(e["SCENSIM_ROLES"]) == roles
    assert e["SCENSIM_TRUTH_TOPIC"] == "/scensim/truth" and e["ROS_DOMAIN_ID"] == "9"
    assert e["SCENSIM_TICK_GATE"] == "127.0.0.1:5561"
    rec = r.record()
    assert rec["exit"] == 0 and not rec["ended_early"] and rec["stopped"] >= rec["started"]
    assert r.failed() == ""
    # without lockstep, no gate
    assert "SCENSIM_TICK_GATE" not in at.env_for(att(tmp_path), {}, run_dir, 1, {}, "127.0.0.1:1")


def test_an_early_exit_and_a_bad_exit_are_recorded_and_fail_only_if_required(tmp_path):
    run_dir = tmp_path / "run"
    r = at.start(att(tmp_path, "die"), at.env_for(att(tmp_path), {}, run_dir, None, {}), run_dir, tmp_path)
    ended(r)
    at.stop(r)
    assert r.early and r.code == 3 and "ended before the run did" in r.failed()
    assert r.record()["ended_early"] and not r.record()["required"]
    r = at.start(att(tmp_path, "bad"), at.env_for(att(tmp_path), {}, run_dir, None, {}), run_dir, tmp_path)
    ready(run_dir)
    at.stop(r)
    assert not r.early and r.code == 5 and "exited 5 when stopped" in r.failed()
    # a command that does not exist
    r = at.start({"name": "x", "run": [str(tmp_path / "nope")]}, {}, run_dir, tmp_path)
    assert "did not start" in r.failed() and at.stop(r).record()["error"]


def test_one_that_ignores_sigint_is_terminated(tmp_path):
    (tmp_path / "stubborn.py").write_text(
        "import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "open(__import__('os').environ['SCENSIM_ATTACHMENT_DIR'] + '/up', 'w')\n"
        "while True: time.sleep(0.05)\n")
    run_dir = tmp_path / "run"
    a = {"name": "s", "run": [sys.executable, str(tmp_path / "stubborn.py")], "stop_timeout": 0.5}
    r = at.start(a, at.env_for(a, {}, run_dir, None, {}), run_dir, tmp_path)
    deadline = time.time() + ceiling()
    while not (run_dir / "attachments" / "s" / "up").exists() and time.time() < deadline:
        time.sleep(0.05)
    t = time.time()
    at.stop(r)
    assert r.code == -15 and time.time() - t < 5


# --- commands (roadmap 092 K12) -----------------------------------------------------------

def ent(name, controller="", kind="pedestrian"):
    from scensim.project import Entity
    return Entity(name, controller=controller, kind=kind)


def test_commands_key_is_checked():
    ok = {"name": "walkers", "run": ["x"], "lockstep": True, "commands": ["walker"]}
    assert at.problems([ok], "carla") == []
    for bad, want in (([], "a list of entity names"), (["w", "w"], "named twice"),
                      ("walker", "a list of entity names")):
        (_, m), = at.problems([{**ok, "commands": bad}], "carla")
        assert want in m, (bad, m)
    msgs = " | ".join(m for _, m in at.problems([ok], "isaac"))
    assert "cannot move an entity on a model's commands" in msgs
    assert at.gate_wanted([{"name": "a", "run": ["x"], "commands": ["w"]}])
    assert not at.gate_wanted([{"name": "a", "run": ["x"]}])


def test_command_problems_name_each_refusal():
    walkers = {"name": "walkers", "run": ["x"], "commands": ["walker"]}
    scene = [ent("ego", "Autoware", "vehicle"), ent("walker", "model")]
    assert at.command_problems([walkers], scene) == []
    assert at.command_problems([], [ent("ego", "Autoware", "vehicle")]) == []
    # a commanded entity nobody claims
    (m,), = [at.command_problems([], scene)]
    assert "'walker' has controller 'model' and no attachment claims it" in m
    # claimed twice
    twice = at.command_problems([walkers, {**walkers, "name": "other"}], scene)
    assert any("claimed by 2 attachments (walkers, other)" in m for m in twice)
    # a claim on an entity without the model controller, or not in the scenario
    plain = at.command_problems([{**walkers, "commands": ["walker", "npc", "ghost"]}],
                                scene + [ent("npc", "", "vehicle")])
    assert any("'npc', whose controller is 'the default', not 'model'" in m for m in plain)
    assert any("'ghost', which the scenario does not have" in m for m in plain)
    # a commanded vehicle is allowed (092 K13); a commanded misc object is not
    assert at.command_problems([{**walkers, "commands": ["car"]}],
                               [ent("car", "model", "vehicle")]) == []
    cone = at.command_problems([{**walkers, "commands": ["cone"]}],
                               [ent("cone", "model", "misc_object")])
    assert any("'cone' is a misc object with controller 'model'" in m for m in cone)
    # a catalog reference's kind is not known here: the world server judges it at the spawn
    assert at.command_problems([{**walkers, "commands": ["cat"]}],
                               [ent("cat", "model", None)]) == []
    # the datagram's bounds: 10 entities, 64-byte names
    many = [ent(f"w{i}", "model") for i in range(11)]
    over = at.command_problems([{**walkers, "commands": [e.name for e in many]}], many)
    assert any("11 commanded entities: at most 10" in m for m in over)
    long = "w" * 65
    assert any("name of 65 bytes" in m for m in
               at.command_problems([{**walkers, "commands": [long]}], [ent(long, "model")]))
    assert at.command_problems([{**walkers, "commands": ["w" * 64]}],
                               [ent("w" * 64, "model")]) == []


def test_a_commanding_attachment_gets_the_gate_its_entities_and_the_scenario(tmp_path):
    run_dir = tmp_path / "run"
    a = att(tmp_path, commands=["walker"])   # free-running: CMD to the gate, still the gate
    roles = at.roles([ent("ego", "Autoware", "vehicle"), ent("walker", "model")], [])
    assert roles == {"ego": "ego", "walker": "model"}
    env = at.env_for(a, {}, run_dir, 7, roles, tick_gate="127.0.0.1:5561",
                     scenario=tmp_path / "cs1.xosc", parameters={"walk_speed": 1.4})
    assert env["SCENSIM_TICK_GATE"] == "127.0.0.1:5561"
    assert json.loads(env["SCENSIM_COMMANDS"]) == ["walker"]
    assert env["SCENSIM_SCENARIO"] == str(tmp_path / "cs1.xosc")
    assert json.loads(env["SCENSIM_PARAMETERS"]) == {"walk_speed": 1.4}


def _gate_socket():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(ceiling())
    return s, f"127.0.0.1:{s.getsockname()[1]}"


def test_command_gate_lockstep_says_hello_done_with_commands_and_bye():
    srv, addr = _gate_socket()
    with at.CommandGate(addr, entities=["walker"], lockstep=True) as gate:
        assert srv.recv(2048) == b"HELLO"
        gate.send(5021, {"walker": (1.4, 1.5707963267948966, 2.0)})
        assert srv.recv(2048) == b"DONE 5021 walker 1.4 1.5707963267948966 2.0"
        gate.send(5022, {})
        assert srv.recv(2048) == b"DONE 5022"
    assert srv.recv(2048) == b"BYE"


def test_command_gate_free_running_sends_cmd_and_reads_its_environment(monkeypatch):
    srv, addr = _gate_socket()
    monkeypatch.setenv("SCENSIM_TICK_GATE", addr)
    monkeypatch.setenv("SCENSIM_COMMANDS", '["walker"]')
    monkeypatch.setenv("SCENSIM_LOCKSTEP", "0")
    gate = at.CommandGate()
    gate.send(7, {"walker": (0, -3.0, 0.5)})
    assert srv.recv(2048) == b"CMD 7 walker 0.0 -3.0 0.5"
    gate.close()
    srv.settimeout(0.2)
    import socket
    try:
        srv.recv(2048)
        raise AssertionError("a free-running gate sends no BYE")
    except socket.timeout:
        pass


def test_command_gate_refuses_what_the_world_would_drop():
    _, addr = _gate_socket()
    gate = at.CommandGate(addr, entities=["walker"], lockstep=False)
    for frame, cmds, want in ((3, {"other": (1, 0, 1)}, "not an entity"),
                              (3, {"walker": (-1, 0, 1)}, "must not be negative"),
                              (3, {"walker": (1, 0, 0)}, "must be positive"),
                              (3, {"walker": (1, float("nan"), 1)}, "finite"),
                              (-1, {}, "non-negative integer")):
        try:
            gate.datagram(frame, cmds)
            raise AssertionError(cmds)
        except ValueError as e:
            assert want in str(e), (cmds, e)
    gate.close()


def test_ten_commands_at_the_bounds_fit_one_datagram():
    # as scensim_carla_world's tick gate test: 10 names of 64 bytes, numbers of 24 characters
    names = [f"{i:02d}" + "w" * 62 for i in range(10)]
    _, addr = _gate_socket()
    gate = at.CommandGate(addr, entities=names, lockstep=True)
    heading, positive = -1.2345678901234567e-300, 1.2345678901234567e+300
    assert (len(repr(heading)), len(repr(positive))) == (24, 23)   # the longest forms
    d = gate.datagram(2 ** 64 - 1, {n: (positive, heading, positive) for n in names})
    assert len(d) <= at.MAX_DATAGRAM
    try:
        at.CommandGate(addr, entities=names + ["x" * 64], lockstep=True).datagram(
            2 ** 64 - 1, {n: (positive, heading, positive) for n in names + ["x" * 64]})
        raise AssertionError("eleven fit")
    except ValueError as e:
        assert "over the gate's 1472" in str(e)
    gate.close()
