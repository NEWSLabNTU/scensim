"""World knobs per run (093 D7 gap 1): a scenario's bound knobs with the run's values, the
world's declarations, what a run sends (baseline merged, absolute), CARLA's refusals of
friction and surface maps, the read-back compared, and get_weather's answer parsed."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scensim_sampler"))

from scensim import knobs as K  # noqa: E402

WORLD = {
    "illumination": {"values": {"day": {"weather": {"sun_altitude_angle": 60}},
                                "night": {"weather": {"sun_altitude_angle": -30,
                                                      "street_lights": 100}}},
                     "default": "day"},
    "surface": {"values": {"dry": {"surface_map": "dry", "mu": 1.0},
                           "wet": {"surface_map": "wet", "mu": 0.7},
                           "wet_look": {"weather": {"wetness": 80}, "physics": "none"}}},
}
SCEN = """<?xml version="1.0"?><OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="3" date="2026-11-21T00:00:00" author="t" description="t">
    <Properties>
      <Property name="scensim.knob.illumination" value="$light"/>
      <Property name="scensim.knob.surface" value="$road"/>
    </Properties></FileHeader>
  <ParameterDeclarations>
    <ParameterDeclaration name="light" parameterType="string" value="day"/>
    <ParameterDeclaration name="road" parameterType="string" value="dry"/>
  </ParameterDeclarations><Entities/><Storyboard/></OpenSCENARIO>"""


def test_the_bound_knobs_take_the_runs_values_else_the_defaults(tmp_path):
    p = tmp_path / "s.xosc"
    p.write_text(SCEN)
    assert K.bound(p, {"light": "night"}) == {"illumination": "night", "surface": "dry"}


def test_the_declarations_are_checked():
    assert K.problems(WORLD) == []
    bad = {"illumination": {"values": {"night": {"weather": {"sun": "low"}}}, "default": "dusk"},
           "fog": {"values": {}}}
    msgs = [m for _, m in K.problems(bad)]
    assert any("parameter: number" in m for m in msgs)
    assert any("'dusk' is not one of its values" in m for m in msgs)
    assert any("needs values" in m for m in msgs)


def test_a_run_sends_the_baseline_merged_with_its_knobs():
    p = K.plan(WORLD, {"illumination": "night", "surface": "wet_look"}, "carla",
               baseline={"cloudiness": 10.0, "sun_altitude_angle": 45.0})
    assert p["weather"] == {"cloudiness": 10.0, "sun_altitude_angle": -30.0,
                            "street_lights": 100.0, "wetness": 80.0}


def test_isaac_takes_surface_maps_and_refuses_weather():
    p = K.plan(WORLD, {"surface": "wet"}, "isaac")
    assert p["surface_maps"] == {"surface": "wet"} and p["weather"] == {}
    with pytest.raises(K.KnobError, match="Isaac has no weather service"):
        K.plan(WORLD, {"illumination": "night"}, "isaac")


def test_carla_refuses_friction_and_surface_maps_but_runs_a_look():
    with pytest.raises(K.KnobError, match="a surface map, which CARLA cannot apply"):
        K.plan(WORLD, {"surface": "wet"}, "carla")
    world = {"surface": {"values": {"wet": {"mu": 0.7, "weather": {"wetness": 80}}}}}
    with pytest.raises(K.KnobError, match="weather does not change"):
        K.plan(world, {"surface": "wet"}, "carla")
    p = K.plan(WORLD, {"surface": "wet_look"}, "carla")
    assert p["weather"] == {"wetness": 80.0}
    assert p["notes"] == {"surface": "visual only: the friction was not applied"}


def test_a_knob_or_value_the_world_lacks_is_refused():
    with pytest.raises(K.KnobError, match="declares no such knob"):
        K.plan(WORLD, {"fog": "thick"}, "carla")
    with pytest.raises(K.KnobError, match="not a value the world declares"):
        K.plan(WORLD, {"illumination": "dusk"}, "carla")


def test_the_read_back_decides():
    knobs = {"illumination": "night", "surface": "wet"}
    p = {"weather": {"sun_altitude_angle": -30.0, "street_lights": 100.0}}   # as on a world
                                                                              # with both
    good = K.compare(knobs, WORLD, p["weather"],
                     {"sun_altitude_angle": -30.0004, "street_lights": 100.0})
    assert good["ok"] and good["knobs"]["illumination"]["ok"]
    assert good["knobs"]["surface"]["surface_map"] == {"sent": "wet", "read": "unverified"}
    bad = K.compare(knobs, WORLD, p["weather"], {"sun_altitude_angle": 60.0,
                                                 "street_lights": 100.0})
    assert not bad["ok"] and bad["knobs"]["illumination"]["applied"]["sun_altitude_angle"] == 60.0
    missing = K.compare({"illumination": "night"}, WORLD, p["weather"], None)
    assert not missing["ok"]


def test_get_weathers_answer_is_parsed():
    text = ("response:\nscensim_interfaces.srv.GetWeather_Response(success=True, message='', "
            "preset='', names=['cloudiness', 'sun_altitude_angle'], values=[10.0, -30.0])")
    assert K.weather_read(text) == {"cloudiness": 10.0, "sun_altitude_angle": -30.0}
    assert K.weather_read("waiting for service") is None


# --- through the runner ---------------------------------------------------------------------

import io  # noqa: E402
import json  # noqa: E402
import signal  # noqa: E402

import yaml  # noqa: E402

from scensim import results, run  # noqa: E402
from _ceiling import STOP_WAIT  # noqa: E402
from test_run import fake, start_stack, where  # noqa: E402,F401 - the fixture
from test_sampled import SEEDED, runs_dir, sampled_project  # noqa: E402

KNOBBED = SEEDED + """world:
  knobs:
    illumination:
      values:
        day: {weather: {sun_altitude_angle: 60}}
        night: {weather: {sun_altitude_angle: -30, street_lights: 100}}
      default: day
    surface:
      values:
        dry: {weather: {wetness: 0}, physics: none}
        wet_look: {weather: {wetness: 80}, physics: none}
"""
LIGHTS = """
      <StochasticDistribution parameterName="light">
        <ProbabilityDistributionSet><Element value="day" weight="1"/><Element value="night" weight="1"/></ProbabilityDistributionSet>
      </StochasticDistribution>
      <StochasticDistribution parameterName="road">
        <ProbabilityDistributionSet><Element value="dry" weight="1"/><Element value="wet_look" weight="1"/></ProbabilityDistributionSet>
      </StochasticDistribution>"""


def knobbed_project(where):
    d = sampled_project(where, testbench=KNOBBED)
    s = (d / "scenarios" / "sampled.xosc").read_text()
    s = s.replace('<Property name="scensim.cell_attributes" value="surface"/>'
                  '<Property name="scensim.cell.surface" value="dry"/>',
                  '<Property name="scensim.cell_attributes" value="illumination,surface"/>'
                  '<Property name="scensim.knob.illumination" value="$light"/>'
                  '<Property name="scensim.knob.surface" value="$road"/>', 1)
    s = s.replace('<ParameterDeclaration name="gap"',
                  '<ParameterDeclaration name="light" parameterType="string" value="day"/>'
                  '<ParameterDeclaration name="road" parameterType="string" value="dry"/>'
                  '<ParameterDeclaration name="gap"', 1)
    assert "scensim.knob.surface" in s
    (d / "scenarios" / "sampled.xosc").write_text(s)
    dist = (d / "scenarios" / "sampled_dist.xosc").read_text()
    (d / "scenarios" / "sampled_dist.xosc").write_text(
        dist.replace("</Stochastic>", LIGHTS + "\n    </Stochastic>", 1))
    return d


class Bridge:
    """The bridge's set_weather and get_weather: it keeps what it is sent, and `drop` names a
    parameter it then reports wrong (a world that did not apply it)."""

    def __init__(self, drop=None):
        self.weather, self.sent, self.drop = {}, [], drop

    def __call__(self, rec, argv):
        if "set_weather" in argv[3]:
            req = argv[-1]
            names = [n.strip() for n in req.split("names: [")[1].split("]")[0].split(",")]
            values = [float(v) for v in req.split("values: [")[1].split("]")[0].split(",")]
            self.sent.append(dict(zip(names, values)))
            self.weather.update(zip(names, values))
            return "response:\nSetWeather_Response(success=True, message='')", ""
        w = dict(self.weather)
        if self.drop in w:
            w[self.drop] = 12.5
        return ("response:\nGetWeather_Response(success=True, message='', preset='', names=["
                + ", ".join(f"'{k}'" for k in w) + "], values=["
                + ", ".join(repr(v) for v in w.values()) + "])"), ""


@pytest.fixture
def knob_stack(where, maps_hub, monkeypatch):
    d = knobbed_project(where)
    monkeypatch.setattr(run, "scenario_argv", fake(where))
    # a run pilot that stays up until the run stops it, as a real one does: one that exited at
    # once raced the run's readiness wait, which checks a pilot's exit before its readiness, and
    # a loaded host (load 66, 2026-11-22) let it exit first ("its launch exited (code 0)
    # before it was ready"); the run stops it with SIGINT at its end
    monkeypatch.setattr(run, "pilot_argv", lambda *a: [
        sys.executable, "-c", "import time\ntry:\n    time.sleep(600)\nexcept KeyboardInterrupt:\n    pass"])
    p, proc = start_stack(d)
    yield d, monkeypatch
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=STOP_WAIT())


def _use(monkeypatch, bridge):
    real = run.apply_knobs
    monkeypatch.setattr(run, "apply_knobs",
                        lambda rec, spec, ps, call=None, project=None:
                        real(rec, spec, ps, call=bridge, project=project))


def _suite(d, n):
    (d / "suites" / "k.yaml").write_text(yaml.safe_dump({
        "sample": {"distribution": "../scenarios/sampled_dist.xosc", "n": n, "seed": 5},
        "logging": {"keep": {}}}))
    return d / "suites" / "k.yaml"


def test_sampled_night_and_wet_reach_the_world_and_the_record(knob_stack, where):
    d, mp = knob_stack
    bridge = Bridge()
    _use(mp, bridge)
    out = io.StringIO()
    assert run.main([str(_suite(d, 6)), "--project", str(d)], out=out) == 0, out.getvalue()
    seen = set()
    for rd in sorted(runs_dir(where).iterdir()):
        r = results.RunResult.read(rd / "result.json")
        rec = json.loads((rd / "sample.json").read_text())
        light, road = rec["values"]["light"], rec["values"]["road"]
        assert rec["cell"] == {"illumination": light, "surface": road}
        assert r.knobs["ok"] and r.knobs["knobs"]["illumination"]["value"] == light
        want = -30.0 if light == "night" else 60.0
        assert r.knobs["knobs"]["illumination"]["applied"]["sun_altitude_angle"] == want
        assert r.knobs["sent"]["wetness"] == (80.0 if road == "wet_look" else 0.0)
        assert r.knobs["knobs"]["surface"]["physics"].startswith("none")
        seen.add((light, road))
    assert ("night", "wet_look") in seen or len(seen) >= 2
    # absolute: every run sent every knob's parameters, so none inherits another's weather
    assert all({"sun_altitude_angle", "wetness"} <= set(s) for s in bridge.sent)
    # K7 groups the runs by the knobs the world applied
    from scensim_sampler import coverage
    rep = coverage.report(coverage.outcomes_from_runs([runs_dir(where)]))
    cells = {tuple(sorted(c["cell"].items())) for c in rep["layer3"]}
    assert cells == {(("illumination", l), ("surface", r)) for l, r in seen}


def test_a_world_that_did_not_apply_a_knob_gives_an_error_run(knob_stack, where):
    d, mp = knob_stack
    _use(mp, Bridge(drop="sun_altitude_angle"))
    out = io.StringIO()
    run.main([str(_suite(d, 1)), "--project", str(d)], out=out)
    rd = sorted(runs_dir(where).iterdir())[-1]
    r = results.RunResult.read(rd / "result.json")
    assert r.verdict == "error", (r.verdict, r.reason)
    assert "knobs: the world did not apply illumination" in r.reason
    assert r.knobs["ok"] is False
    assert r.knobs["knobs"]["illumination"]["applied"]["sun_altitude_angle"] == 12.5
    assert r.error["kind"] == "knob_mismatch", r.error   # counted by kind (092 K4)


# --- 243's review: the baseline every run, EnvironmentAction overlap, unverified cells ------

class _Spec:
    def __init__(self, scenario, parameters=None):
        self.scenario, self.parameters = scenario, parameters or {}


PLAIN = """<?xml version="1.0"?><OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="3" date="2026-11-21T00:00:00" author="t" description="t"/>
  <ParameterDeclarations/><Entities/><Storyboard/></OpenSCENARIO>"""


def test_a_run_without_knobs_still_sends_and_checks_the_baseline(tmp_path):
    knobbed, plain = tmp_path / "k.xosc", tmp_path / "p.xosc"
    knobbed.write_text(SCEN)
    plain.write_text(PLAIN)
    rec = {"simulator": "carla", "weather": {"parameters": {"sun_altitude_angle": 45.0,
                                                            "wetness": 0.0}}}
    ps = {"world": {"knobs": {k: v for k, v in WORLD.items() if k == "illumination"}}}
    ps["world"]["knobs"]["surface"] = {"values": {"dry": {"physics": "none"}}}
    bridge = Bridge()
    a, why = run.apply_knobs(rec, _Spec(knobbed, {"light": "night"}), ps, call=bridge)
    assert a["ok"] and not why and bridge.weather["sun_altitude_angle"] == -30.0
    b, why = run.apply_knobs(rec, _Spec(plain), ps, call=bridge)
    assert b["ok"] and not why and b["knobs"] == {}
    assert bridge.sent[-1] == {"sun_altitude_angle": 45.0, "wetness": 0.0}   # back to the day
    # a world that keeps the night anyway fails the plain run
    stuck = Bridge(drop="sun_altitude_angle")
    b, why = run.apply_knobs(rec, _Spec(plain), ps, call=stuck)
    assert not b["ok"] and b["baseline_not_applied"] == ["sun_altitude_angle"] and why
    # no knobs declared and none bound: nothing is sent
    assert run.apply_knobs(rec, _Spec(plain), {"world": {}}, call=bridge) == (None, "")


def test_a_weather_knob_and_an_environment_action_setting_weather_are_refused(tmp_path):
    p = tmp_path / "s.xosc"
    p.write_text(SCEN.replace("<Entities/><Storyboard/>", "<Entities/><Storyboard><Init><Actions>"
                              "<GlobalAction><EnvironmentAction><Environment name='e'>"
                              "<TimeOfDay animation='false' dateTime='2026-11-21T07:00:00'/>"
                              "</Environment></EnvironmentAction></GlobalAction></Actions></Init>"
                              "</Storyboard>"))
    ps = {"world": {"knobs": WORLD}}
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(p, {"light": "night", "road": "wet_look"}),
                               ps, call=Bridge())
    assert not blk["ok"] and "EnvironmentAction sets TimeOfDay" in why


def test_an_unverified_surface_is_its_own_cell_in_the_coverage(tmp_path):
    from scensim_sampler import coverage
    rd = tmp_path / "r1"
    rd.mkdir()
    rec = {"cell": {"surface": "wet"}, "category": "c", "values": {}}
    (rd / "sample.json").write_text(json.dumps(rec))
    (rd / "result.json").write_text(json.dumps({
        "verdict": "passed", "knobs": {"ok": True, "knobs": {"surface": {
            "value": "wet", "ok": True, "surface_map": {"sent": "wet", "read": "unverified"}}}}}))
    [(r, o)] = coverage.outcomes_from_runs([tmp_path])
    assert r["cell"] == {"surface": "wet (unverified)"}


def test_world_anchors_are_checked():
    from scensim import world as W
    assert W.anchor_problems({"exit_n": {"kind": "lane", "heading": 1.57, "length": 40},
                              "conflict": {"kind": "point", "x": 1.0, "y": -2.0}}) == []
    bad = W.anchor_problems({"a": {"kind": "ramp", "heading": 1.0},
                             "b": {"kind": "lane", "x": 1.0},
                             "c": {"kind": "lane", "heading": "north"},
                             "d": {"kind": "point"}, "e-f": {"kind": "lane", "heading": 0}})
    text = " ".join(m for _, m in bad)
    for want in ("kind: one of lane, point",
                 "x: a lane anchor has heading, length, speed_limit, lanelet",
                 "a number, not 'north'", "no attributes", "an anchor's name is an identifier"):
        assert want in text, want
    assert W.anchor_problems([1]) and W.anchor_problems("x")
    # a stated lane's lanelet (092 K9b), which a LanePosition binds: an id
    assert W.anchor_problems({"exit_n": {"kind": "lane", "lanelet": 102}}) == []
    assert "a lanelet's id, an integer" in " ".join(
        m for _, m in W.anchor_problems({"exit_n": {"kind": "lane", "lanelet": 1.5}}))


# --- knob profiles (092 K9) -----------------------------------------------------------------

PROFILE_WORLD = {"visibility": {"profile": True, "sets": "fog_visual_range", "range": [50, 1000],
                                "default": 1000}}
PROFILED = """<?xml version="1.0"?><OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="3" date="2026-11-21T00:00:00" author="t" description="t">
    <Properties>
      <Property name="scensim.knob.visibility" value="BINDING"/>
    </Properties></FileHeader>
  <ParameterDeclarations>
    <ParameterDeclaration name="fog_start" parameterType="double" value="10"/>
    <ParameterDeclaration name="vmin" parameterType="double" value="80"/>
  </ParameterDeclarations>
  <RoadNetwork><LogicFile filepath="$(env SCENSIM_MAPS)/town_street"/></RoadNetwork>
  <Entities/><Storyboard/></OpenSCENARIO>"""


class ProfileBridge(Bridge):
    """Bridge, with set_knob_profiles: it keeps the JSON it is sent."""

    def __init__(self, refuse=None):
        super().__init__()
        self.profiles, self.refuse = [], refuse

    def __call__(self, rec, argv):
        if argv[3] == K.SET_KNOB_PROFILES:
            self.profiles.append(json.loads(yaml.safe_load(argv[-1])["profiles"])["profiles"])
            if self.refuse:
                return (f"response:\nSetKnobProfiles_Response(success=False, "
                        f"message='{self.refuse}')"), ""
            return "response:\nSetKnobProfiles_Response(success=True, message='1')", ""
        return super().__call__(rec, argv)


def _profiled(tmp_path, binding="time: 0 1000; $fog_start 1000; 20 $vmin"):
    p = tmp_path / "f.xosc"
    p.write_text(PROFILED.replace("BINDING", binding))
    return p


def test_a_profile_knob_is_declared_with_a_range_and_a_field():
    assert K.problems(PROFILE_WORLD) == []
    bad = K.problems({"a": {"profile": True, "sets": "fog", "range": [5, 1], "default": 9,
                            "values": {}},
                      "b": {"profile": True, "sets": "sun_elevation", "range": [0, 1],
                            "default": 2, "step": 0}})
    text = " ".join(m for _, m in bad)
    for want in ("values: a profile knob has", "one of fog_visual_range", "low below high",
                 "a number in its range", "a positive number"):
        assert want in text, want


def test_a_runs_profiles_go_to_the_bridge_with_the_runs_values(tmp_path):
    ps = {"world": {"knobs": PROFILE_WORLD}}
    b = ProfileBridge()
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(_profiled(tmp_path),
                                                              {"fog_start": 12.0}), ps, call=b)
    assert not why and blk["ok"]
    (p,) = b.profiles[-1]
    assert (p["knob"], p["field"], p["coordinate"]) == ("visibility", "fog_visual_range", "time")
    assert p["points"] == [[0.0, 1000.0], [12.0, 1000.0], [20.0, 80.0]]
    assert p["step"] == pytest.approx(9.5)                 # 1 % of the range
    assert p["min_interval"] == K.PROFILE_MIN_INTERVAL      # a send a second, at most
    assert blk["_profile_plan"][0]["knob"] == "visibility"
    # a run of the same testbench binding none still sends: an empty list
    (tmp_path / "p.xosc").write_text(PLAIN)
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(tmp_path / "p.xosc"), ps, call=b)
    assert not why and b.profiles[-1] == []


def test_profiles_the_world_cannot_take_are_refused_before_the_run(tmp_path):
    ps = {"world": {"knobs": PROFILE_WORLD}}
    cases = (
        ("time: 0 1000; 20 10", "carla", "outside its range [50, 1000]"),
        ("s(exit_n): 0 1000; 20 80", "carla", "no resolved lane exit_n"),
        ("time: 0 1000; 20 80", "nowhere", "cannot apply and read back"),
    )
    for binding, sim, why_want in cases:
        blk, why = run.apply_knobs({"simulator": sim}, _Spec(_profiled(tmp_path, binding)), ps,
                                   call=ProfileBridge(), project=tmp_path)
        assert why_want in why and not blk["ok"], (binding, why)
    # Isaac has no cloud read-back
    clouds = {"overcast": {"profile": True, "sets": "cloud_cover_oktas", "range": [0, 8]}}
    p = _profiled(tmp_path, "time: 0 0; 20 8").read_text().replace("visibility", "overcast")
    (tmp_path / "c.xosc").write_text(p)
    blk, why = run.apply_knobs({"simulator": "isaac"}, _Spec(tmp_path / "c.xosc"),
                               {"world": {"knobs": clouds}}, call=ProfileBridge())
    assert "carla only" in why
    # a fixed binding on a profile knob, and a bridge that refuses
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(_profiled(tmp_path, "$vmin")), ps,
                               call=ProfileBridge())
    assert "bound to a profile" in why
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(_profiled(tmp_path)), ps,
                               call=ProfileBridge(refuse="no ENVIRONMENT_APPLIED"))
    assert "set_knob_profiles refused" in why and "no ENVIRONMENT_APPLIED" in why


def test_a_profile_and_an_environment_action_on_the_same_part_are_refused(tmp_path):
    p = _profiled(tmp_path)
    p.write_text(p.read_text().replace("<Storyboard/>", "<Storyboard><Init><Actions>"
                 "<GlobalAction><EnvironmentAction><Environment name='e'><Weather>"
                 "<Fog visualRange='100'/></Weather></Environment></EnvironmentAction>"
                 "</GlobalAction></Actions></Init></Storyboard>"))
    blk, why = run.apply_knobs({"simulator": "carla"}, _Spec(p), {"world": {"knobs": PROFILE_WORLD}},
                               call=ProfileBridge())
    assert "EnvironmentAction sets Fog too" in why


def test_a_lane_profile_carries_the_lanes_centreline(tmp_path):
    from scensim_sampler import anchors as A
    md = tmp_path / "assets" / "maps" / "town_street"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm/>")
    lane = {"kind": "lane", "lanelets": [{"id": 7, "from_s": 0.0, "to_s": 30.0}], "length": 30.0,
            "speed_limit": 13.9, "start_x": 0.0, "start_y": 0.0, "end_x": 30.0, "end_y": 0.0,
            "heading_s": [0.0, 30.0], "heading": [0.0, 0.0], "heading_max_error": 0.0,
            "x": [0.0, 30.0], "y": [0.0, 0.0]}
    doc = {"format": A.FORMAT, "version": A.VERSION, "map": "town_street",
           "map_sha256": A.map_digest(md), "anchors": {"exit_n": lane}}
    (md / A.RESOLVED).write_text(json.dumps(doc))
    b = ProfileBridge()
    blk, why = run.apply_knobs({"simulator": "carla"},
                               _Spec(_profiled(tmp_path, "s(exit_n): 0 1000; 20 80")),
                               {"world": {"knobs": PROFILE_WORLD}}, call=b, project=tmp_path)
    assert not why, why
    c = b.profiles[-1][0]["coordinate"]
    assert (c["lane"], c["s"], c["x"], c["y"]) == ("exit_n", [0.0, 30.0], [0.0, 30.0], [0.0, 0.0])
    # resolved before the centreline was added: refused, naming the fix
    del lane["x"], lane["y"]
    (md / A.RESOLVED).write_text(json.dumps(doc))
    blk, why = run.apply_knobs({"simulator": "carla"},
                               _Spec(_profiled(tmp_path, "s(exit_n): 0 1000; 20 80")),
                               {"world": {"knobs": PROFILE_WORLD}}, call=ProfileBridge(),
                               project=tmp_path)
    assert "without the lane's centreline" in why


def test_the_summary_reads_the_trace_and_judges_the_read_back():
    class L:
        def __init__(self, f, c, a, s):
            self.knob, self.frame, self.commanded, self.applied, self.sent = "visibility", f, c, a, s
    plan = [{"knob": "visibility", "field": "fog_visual_range", "step": 9.5, "min_interval": 1.0,
             "coordinate": "time", "points": [[0, 1000], [20, 80]]}]
    # the first read-back is the world's weather before (not judged); a later one may show the
    # send before it (lagged: CARLA applies at its next tick)
    good = [L(1, 1000.0, 950.0, True), L(2, 995.0, 1000.0, False), L(3, 990.0, 990.0004, True),
            L(4, 980.0, 990.0, True)]
    s = K.profile_summary(PROFILE_WORLD, plan, good)["visibility"]
    assert (s["frames"], s["sent"], s["unread"], s["lagged"], s["ok"]) == (4, 3, 0, 1, True)
    assert s["max_deviation"] == pytest.approx(0.0004)
    assert s["max_lag"] == pytest.approx(10.0)      # frame 4: 980 commanded, 990 shown
    assert (s["first_read_back"], s["commanded"], s["min_interval"]) == (950.0, [980.0, 1000.0],
                                                                         1.0)
    off = good + [L(5, 970.0, 900.0, True)]
    s = K.profile_summary(PROFILE_WORLD, plan, off)["visibility"]
    assert not s["ok"] and s["off_frames"] == [5]
    unread = [L(1, 1000.0, None, True)]
    assert not K.profile_summary(PROFILE_WORLD, plan, unread)["visibility"]["ok"]
    assert not K.profile_summary(PROFILE_WORLD, plan, [])["visibility"]["ok"]


def test_a_ramp_the_world_trails_by_much_warns_naming_the_interval_that_fits():
    world = {"visibility": {"profile": True, "sets": "fog_visual_range", "range": [50, 1000],
                            "default": 1000},
             "quick": {"profile": True, "sets": "fog_visual_range", "range": [50, 1000],
                       "default": 1000, "min_interval": 0.25}}
    ramp = ("time", None, [(0.0, 1000.0), (60.0, 50.0)])     # 15.8 m/s
    notes = K.lag_notes(world, {"visibility": ramp})
    assert len(notes) == 1 and "knob visibility" in notes[0]
    assert "by up to 31.7" in notes[0] and "min_interval: 0.39" in notes[0]
    # 2 x 0.25 x 15.8 = 7.9 m, within 25 % of 50 m
    assert K.lag_notes(world, {"quick": ramp}) == []
    # a held value and a short segment (its change bounds the lag) do not warn
    assert K.lag_notes(world, {"visibility": ("time", None, [(0.0, 1000.0), (10.0, 1000.0)])}) == []
    assert K.lag_notes(world, {"visibility": ("time", None, [(0.0, 100.0), (0.1, 90.0)])}) == []
    # along a lane: per metre times the lane's speed; without a speed it is not judged
    lane = ("s", "route_n", [(0.0, 1000.0), (100.0, 50.0)])  # 9.5 per m
    assert K.lag_notes(world, {"visibility": lane}) == []
    n = K.lag_notes(world, {"visibility": lane}, {"route_n": 10.0})
    assert len(n) == 1 and "at 10 m/s" in n[0] and "0 -> 100 m" in n[0]
