"""`scensim-agent check` passes a good agent, names the rule a bad one breaks; `new` passes it."""

import select
import socket
import sys
import time

import pytest

import scensim_agent
from scensim_agent import protocol as P
from scensim_agent import check
from scensim_agent.check import FakeRelay, load_class, run_check
from scensim_agent.cli import main as cli
from scensim_agent.skeleton import create


class Good(scensim_agent.Agent):
    def on_reset(self, ep):
        pass

    def on_goal(self, goal, waypoints):
        self.report(P.DRIVING)

    def on_speed_limit(self, mps):
        pass

    def on_stop(self):
        pass


class NeverReady(Good):
    def on_reset(self, ep):
        self.report(P.INITIALIZING, detail="localization never converges")


class SlowStop(Good):
    def on_stop(self):
        time.sleep(3.5)


class V1Style(scensim_agent.Agent):
    """No reset hook: the boundary is teleported, and the SDK answers it."""

    def on_goal(self, goal, waypoints):
        pass

    def on_speed_limit(self, mps):
        pass

    def on_stop(self):
        pass


def failed_rules(report):
    return [rule for ok, rule, _ in report.results if not ok]


def test_a_good_agent_passes():
    report = run_check(Good)
    assert report.passed, report.text()


def test_an_agent_that_never_gets_ready_fails_the_reset_rule():
    report = run_check(NeverReady)
    assert failed_rules(report) == ["reset: IDLE before the reply",
                                    "second reset: IDLE before the reply"], report.text()


def test_a_slow_stop_fails_its_window():
    report = run_check(SlowStop)
    assert "stop answered within 2.5 s" in failed_rules(report), report.text()


def test_an_agent_without_reset_is_checked_with_teleported():
    report = run_check(V1Style)
    assert report.passed, report.text()
    assert any("teleported answered OK" in rule for _, rule, _ in report.results)


def test_new_generates_a_project_that_passes_check(tmp_path, capsys):
    root, spec = create("road-runner", tmp_path)
    assert (root / "pyproject.toml").exists() and (root / "agent.yaml").exists()
    sys.path.insert(0, str(root))
    try:
        assert load_class(spec).__name__ == "RoadRunnerAgent"
        assert cli(["check", spec, "--config", str(root / "agent.yaml")]) == 0
    finally:
        sys.path.remove(str(root))
    assert "PASS: 16/16 rules" in capsys.readouterr().out


def test_new_project_checks_from_its_directory_as_printed(tmp_path, monkeypatch, capsys):
    """075 step 8 (G44): in the skeleton's directory, with nothing added to sys.path, the
    module forms its files print load (as under `ros2 run`, whose sys.path[0] is the entry
    point's directory, not the working one)."""
    root, spec = create("cut-in", tmp_path)
    assert cli(["new", "other", "--dir", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "ros2 run scensim_agent scensim-agent check other.agent:OtherAgent" in printed
    assert "ros2 run scensim_agent scensim-agent check cut_in:CutInAgent" in (root / "README.md").read_text()
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p not in ("", str(root))])
    try:
        assert load_class(spec).__name__ == "CutInAgent"
        assert load_class("cut_in:CutInAgent").__name__ == "CutInAgent"
    finally:
        for m in [m for m in sys.modules if m == "cut_in" or m.startswith("cut_in.")]:
            del sys.modules[m]


def test_check_loads_a_file_path(tmp_path):
    path = tmp_path / "solo.py"
    path.write_text("import scensim_agent\n\nclass Solo(scensim_agent.Agent):\n    pass\n")
    assert load_class(f"{path}:Solo").__name__ == "Solo"



def _reset_by_peer():
    """A relay-side socket whose peer (the agent) closed with a heartbeat still unread: the
    close sends an RST, and shutdown on this end then raises ENOTCONN (issue 114's teardown,
    made deterministic: select waits for the RST, no timing)."""
    with socket.create_server(("127.0.0.1", 0)) as listener:
        agent = socket.create_connection(listener.getsockname())
        relay_end, _ = listener.accept()
    relay_end.sendall(P.encode(P.heartbeat(), P.VERSION))
    assert select.select([agent], [], [], 5.0)[0]     # the heartbeat reached the agent, unread
    agent.close()                                     # unread data: RST, not FIN
    assert select.select([relay_end], [], [], 5.0)[0]  # the RST arrived
    return relay_end


def test_drop_after_the_agent_closed_first():
    """The agent's end went first, by RST: the drop takes ENOTCONN and closes (issue 114)."""
    relay = FakeRelay()
    gone = _reset_by_peer()
    relay.sock = gone
    try:
        relay.drop()
        assert gone.fileno() == -1
    finally:
        relay.close()


class Closing(Good):
    closed = 0

    def close(self):
        Closing.closed += 1


def test_check_reports_and_closes_the_agent_when_its_connection_was_reset(monkeypatch):
    """The relay's socket reset by the agent before the teardown: run_check returns its report,
    and the agent is closed (issue 114)."""
    original = check.FakeRelay.close

    def reset_then_close(self):
        self.sock = _reset_by_peer()
        original(self)

    monkeypatch.setattr(check.FakeRelay, "close", reset_then_close)
    Closing.closed = 0
    report = run_check(Closing)
    assert report.passed, report.text()
    assert Closing.closed == 1


def test_the_agent_is_closed_when_the_relay_teardown_raises(monkeypatch):
    """Any teardown step that raises still closes the agent, and the error is not swallowed."""
    def broken(self):
        self.listener.close()
        raise OSError(107, "Transport endpoint is not connected")

    monkeypatch.setattr(check.FakeRelay, "close", broken)
    Closing.closed = 0
    with pytest.raises(OSError):
        run_check(Closing)
    assert Closing.closed == 1
