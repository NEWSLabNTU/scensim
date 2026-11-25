"""Zone-scoped surface knobs (roadmap 092 K9f-a): a knob value's `zones:`, its refusals by name
(one rule in testbench check and the run), the zones in the run's copy of the scenario (one copy
writer with the layouts, byte for byte the same), and the judgement from the truth's
road_condition record read back after a step."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scensim_sampler"))

from scensim import knobs as K, layouts as L, project, run, zones as Z  # noqa: E402

TABLE = {"reference": "asphalt", "classes": {
    "asphalt": {"mu": 1.12, "wet": {"moist": 0.9, "wetWithPuddles": 0.75}},
    "ice": {"mu": 0.265, "wet": {"moist": 0.47}},
    "dirt": {"mu": 0.68, "soil": {"n": 0.7}}}}
MAP = {"classes": "classes.yaml",
       "defaults": {"Road": "asphalt"},
       "zones": [
           {"id": "ice_at_goal", "class": "ice",
            "polygon": [[105, -134], [135, -134], [135, -126], [105, -126]]},
           {"id": "puddle_left", "water_depth": 0.006,
            "polygon": [[150, -134], [160, -134], [160, -130], [150, -130]]},
           {"id": "mud_pit", "class": "dirt", "soil": "grid",
            "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}
ROAD = """<GlobalAction><EnvironmentAction><Environment name="e">
          <RoadCondition frictionScaleFactor="1.0" wetness="dry"><Properties>
            <Property name="scensim.surface_map" value="town01_route"/>{extra}
          </Properties></RoadCondition></Environment></EnvironmentAction></GlobalAction>"""
SCEN = """<?xml version="1.0"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="2" date="2026-11-25T00:00:00" author="t" description="t">
    <Properties><Property name="scensim.knob.goal_surface" value="param:goal"/></Properties>
  </FileHeader>
  <ParameterDeclarations>
    <ParameterDeclaration name="goal" parameterType="string" value="ice"/>
  </ParameterDeclarations>
  <RoadNetwork><LogicFile filepath="$(env SCENSIM_MAPS)/Town01"/></RoadNetwork>
  <Entities><ScenarioObject name="ego"/></Entities>
  <Storyboard><Init><Actions>{road}<Private entityRef="ego"/></Actions></Init></Storyboard>
</OpenSCENARIO>
"""
WORLD = {"goal_surface": {"values": {"asphalt": {"zones": {"ice_at_goal": {"class": "asphalt"}}},
                                     "ice": None},
                          "default": "ice"}}


def scen(road=True, extra=""):
    return SCEN.format(road=ROAD.format(extra=extra) if road else "")


def _project(tmp_path, scenario=None, world=WORLD, simulator="isaac", zone_map=MAP):
    d = tmp_path / "proj"
    (d / "scenarios").mkdir(parents=True)
    (d / "ground").mkdir()
    (d / "ground" / "classes.yaml").write_text(yaml.safe_dump(TABLE))
    (d / "ground" / "town01_route.yaml").write_text(yaml.safe_dump(zone_map))
    (d / "testbench.yaml").write_text(yaml.safe_dump({
        "simulator": simulator, "maps": ["Town01"], "world": {"knobs": world},
        "ground": {"Town01": {"surface_maps": {"town01_route": "ground/town01_route.yaml"}}}}))
    (d / "scenarios" / "zones.xosc").write_text(scenario or scen())
    md = d / "assets" / "maps" / "Town01"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm town01/>")
    return d


def _runs(d, goal="asphalt", simulator="isaac", distribution=False):
    return Z.for_run(d, d / "scenarios" / "zones.xosc", {"goal": goal}, WORLD, "Town01",
                     simulator=simulator, distribution=distribution)


# --- the knob value's shape ----------------------------------------------------------------

def test_a_zones_value_is_checked_by_its_shape_and_wet_is_no_wetness():
    assert K.problems(WORLD) == []
    bad = {"k": {"values": {
        "a": {"zones": {"z": {"wetness": "wet"}}},
        "b": {"zones": {"z": {"colour": "red"}}},
        "c": {"zones": {"z": {"water_depth": -1}}},
        "d": {"zones": {"Bad-Id": {"class": "ice"}}},
        "e": {"zones": {"z": {"class": "ice"}}, "surface_map": "wet"}}}}
    text = " | ".join(f"{w}: {m}" for w, m in K.problems(bad))
    for want in ("k.values.a.zones.z.wetness: 'wet' is not an OpenSCENARIO wetness (one of dry, "
                 "moist, wetWithPuddles, lowFlooded, highFlooded)",
                 "k.values.b.zones.z.colour: a zone has class, wetness, water_depth",
                 "k.values.c.zones.z.water_depth: m, a number >= 0",
                 "k.values.d.zones.Bad-Id: a zone id is [a-z0-9_]+",
                 "k.values.e: names a surface map and sets zones"):
        assert want in text, want
    assert K.plan(WORLD, {"goal_surface": "asphalt"}, "isaac")["zones"] == {
        "goal_surface": {"ice_at_goal": {"class": "asphalt"}}}


def test_zones_on_carla_are_refused_naming_c7s_measured_limit():
    why = K.problems(WORLD, simulator="carla")
    assert why and "goal_surface.values.asphalt" in why[0][0]
    assert "zones: CARLA 0.9.16 cannot set a zone's ground" in why[0][1]
    assert "086 C7, measured" in why[0][1]
    with pytest.raises(K.KnobError, match="friction trigger sets all four wheels"):
        K.plan(WORLD, {"goal_surface": "asphalt"}, "carla")


# --- the rule ------------------------------------------------------------------------------

def test_the_runs_zones_name_their_map_and_properties(tmp_path):
    d = _project(tmp_path)
    zs = _runs(d)
    assert [(z["knob"], z["value"], z["properties"]) for z in zs] == [
        ("goal_surface", "asphalt", {"scensim.zone.ice_at_goal.class": "asphalt"})]
    assert zs[0]["surface_map"] == str(d / "ground" / "town01_route.yaml")
    assert _runs(d, goal="ice") == []


@pytest.mark.parametrize("zones,want", [
    ({"no_such": {"class": "ice"}}, "zone no_such is not in "),
    ({"ice_at_goal": {"class": "lava"}}, "class 'lava' is not in the surface class table "
                                         "(asphalt, dirt, ice)"),
    ({"mud_pit": {"class": "ice"}}, "zone mud_pit: a class on a soil zone (soil: grid)"),
])
def test_a_zone_the_map_cannot_take_is_refused_by_name_in_check_and_run(tmp_path, zones, want):
    world = {"goal_surface": {"values": {"asphalt": {"zones": zones}, "ice": None}}}
    d = _project(tmp_path, world=world)
    with pytest.raises(Z.ZoneError, match=want.replace("(", r"\(").replace(")", r"\)")):
        Z.for_run(d, d / "scenarios" / "zones.xosc", {"goal": "asphalt"}, world, "Town01",
                  simulator="isaac")
    found = [f.what for f in project.zone_problems(d, yaml.safe_load(
        (d / "testbench.yaml").read_text()))]
    assert any(want in m for m in found), found
    with pytest.raises(run.Refused, match="zones.xosc: "):
        run.expand(d / "scenarios" / "zones.xosc", d, params={"goal": ["asphalt"]})


def test_a_field_the_scenario_sets_too_is_two_writers(tmp_path):
    extra = '<Property name="scensim.zone.ice_at_goal.class" value="ice"/>'
    d = _project(tmp_path, scenario=scen(extra=extra))
    with pytest.raises(Z.ZoneError, match=r"zone ice_at_goal.class: the scenario sets "
                                          r"scensim.zone.ice_at_goal.class too: two writers"):
        _runs(d)
    found = [f.what for f in project.zone_problems(d, yaml.safe_load(
        (d / "testbench.yaml").read_text()))]
    assert any("two writers" in m for m in found), found


def test_one_zone_field_in_two_bound_knobs_is_two_writers(tmp_path):
    world = {"goal_surface": WORLD["goal_surface"],
             "goal_too": {"values": {"x": {"zones": {"ice_at_goal": {"class": "ice"}}}}}}
    scenario = scen().replace(
        '<Property name="scensim.knob.goal_surface" value="param:goal"/>',
        '<Property name="scensim.knob.goal_surface" value="param:goal"/>'
        '<Property name="scensim.knob.goal_too" value="param:too"/>').replace(
        '</ParameterDeclarations>',
        '<ParameterDeclaration name="too" parameterType="string" value="x"/>'
        '</ParameterDeclarations>')
    d = _project(tmp_path, scenario=scenario, world=world)
    with pytest.raises(Z.ZoneError, match="zone ice_at_goal.class: set by knob goal_surface and "
                                          "knob goal_too: two writers"):
        Z.for_run(d, d / "scenarios" / "zones.xosc", {"goal": "asphalt"}, world, "Town01",
                  simulator="isaac")


def test_zones_on_carla_or_ssv2s_distribution_are_refused_before_any_run(tmp_path):
    d = _project(tmp_path)
    with pytest.raises(Z.ZoneError, match="CARLA 0.9.16 cannot set a zone's ground"):
        _runs(d, simulator="carla")
    with pytest.raises(Z.ZoneError, match="SSv2's own distribution cannot add per run"):
        _runs(d, distribution=True)


def test_a_scenario_without_a_named_map_uses_the_maps_own(tmp_path):
    d = _project(tmp_path, scenario=scen(road=False))
    with pytest.raises(Z.ZoneError, match="map Town01 has no surface map"):
        _runs(d)
    own = d / "assets" / "maps" / "Town01" / "surfaces.yaml"
    own.write_text(yaml.safe_dump(dict(MAP, classes="../../../ground/classes.yaml")))
    assert _runs(d)[0]["surface_map"] == str(own)


# --- the copy ------------------------------------------------------------------------------

def test_zones_go_into_the_inits_road_condition_the_same_bytes_each_time(tmp_path):
    d = _project(tmp_path)
    src = d / "scenarios" / "zones.xosc"
    zs = _runs(d)
    one = L.inject(src, [], Z.properties(zs))
    assert one == L.inject(src, [], Z.properties(zs))
    root = ET.fromstring(one)
    rcs = root.findall(".//RoadCondition")
    assert len(rcs) == 1
    assert [(p.get("name"), p.get("value")) for p in rcs[0].iter("Property")] == [
        ("scensim.surface_map", "town01_route"), ("scensim.zone.ice_at_goal.class", "asphalt")]
    copy = L.write_copy(src, [], tmp_path, zs)
    assert copy["zones"] == [{"knob": "goal_surface", "value": "asphalt",
                              "surface_map": str(d / "ground" / "town01_route.yaml"),
                              "properties": {"scensim.zone.ice_at_goal.class": "asphalt"}}]
    assert Path(copy["path"]).read_bytes() == one
    assert "zones" not in L.write_copy(src, [], tmp_path)   # a layouts-only copy as before


def test_without_an_init_road_condition_the_copy_adds_one_before_the_private_actions(tmp_path):
    d = _project(tmp_path, scenario=scen(road=False))
    own = d / "assets" / "maps" / "Town01" / "surfaces.yaml"
    own.write_text(yaml.safe_dump(dict(MAP, classes="../../../ground/classes.yaml")))
    root = ET.fromstring(L.inject(d / "scenarios" / "zones.xosc", [], Z.properties(_runs(d))))
    actions = list(root.find("Storyboard/Init/Actions"))
    assert [a.tag for a in actions] == ["GlobalAction", "Private"]
    env = actions[0].find("EnvironmentAction/Environment")
    assert [c.tag for c in env] == ["RoadCondition"]
    rc = env.find("RoadCondition")
    assert (rc.get("frictionScaleFactor"), rc.get("wetness")) == ("1.0", "dry")
    assert [p.get("name") for p in rc.iter("Property")] == ["scensim.zone.ice_at_goal.class"]


# --- the judgement -------------------------------------------------------------------------

def _trace(records):
    from scensim import truth   # the reader scensim's run uses
    gt = truth._module("gap_trace")
    lines = [{"type": "episode", "schema": 4, "episode": 1, "start_unix": 0.0,
              "npc_motion": "tracked", "map": "Town01", "step_time": 0.05}]
    lines += records
    lines.append({"type": "end", "frame": 4, "sim_time": 0.2, "frames": 4, "dropped_frames": 0,
                  "complete": True})
    return gt.load_trace([json.dumps(x) for x in lines])


def _rc(frame, after_step, cls="asphalt", mu=1.12, wetness="dry", props=None):
    rec = {"type": "road_condition", "frame": frame, "sim_time_ns": 10**12 + frame,
           "sent": {"friction_scale_factor": 1.0, "wetness": "dry",
                    "properties": props if props is not None else {
                        "scensim.surface_map": "town01_route",
                        "scensim.zone.ice_at_goal.class": "asphalt"}},
           "applied": {"friction_scale_factor": 1.0, "wetness": "dry", "zones": {
               "ice_at_goal": {"surface_class": cls, "wetness": wetness, "water_depth": None,
                               "mu": mu}}}}
    if after_step:
        rec["after_step"] = True
    return rec


def test_a_zone_is_judged_from_the_first_record_read_back_after_a_step(tmp_path):
    d = _project(tmp_path)
    zs = _runs(d)
    # the reply's read-back (unmarked) is recorded, not judged: it may be wrong
    t = _trace([_rc(1, False, cls="ice", mu=0.265), _rc(2, True), _rc(3, True, mu=9.0)])
    blocks, why = Z.judge(zs, t.road_conditions)
    assert why == ""
    z = blocks["goal_surface"]["ice_at_goal"]
    assert z["ok"] and z["frame"] == 2
    assert z["expected"] == {"surface_class": "asphalt", "wetness": "dry", "water_depth": None,
                             "mu": pytest.approx(1.12)}
    assert z["read"]["surface_class"] == "asphalt"


def test_a_zone_whose_read_back_differs_or_is_missing_is_a_knob_mismatch(tmp_path):
    d = _project(tmp_path)
    zs = _runs(d)
    blocks, why = Z.judge(zs, _trace([_rc(2, True, mu=1.12 + 1e-5)]).road_conditions)
    assert not blocks["goal_surface"]["ice_at_goal"]["ok"]
    assert blocks["goal_surface"]["ice_at_goal"]["off"] == ["mu"]
    assert why == "knobs: zones read back differ from what was sent: goal_surface: zone " \
                  "ice_at_goal mu"
    blocks, why = Z.judge(zs, _trace([_rc(2, True, cls="ice", mu=0.265)]).road_conditions)
    assert blocks["goal_surface"]["ice_at_goal"]["off"] == ["surface_class", "mu"]
    blocks, why = Z.judge(zs, _trace([_rc(2, True, props={})]).road_conditions)
    assert blocks["goal_surface"]["ice_at_goal"]["off"][0] == "not sent"
    blocks, why = Z.judge(zs, _trace([_rc(1, False)]).road_conditions)
    assert blocks["goal_surface"]["ice_at_goal"] == {"sent": {"class": "asphalt"},
                                                     "read": "missing", "ok": False}
    assert "no road_condition record read back after a step" in why


def test_the_expected_mu_takes_the_zones_wetness_else_the_worlds(tmp_path):
    world = {"goal_surface": {"values": {"asphalt": {"zones": {
        "ice_at_goal": {"class": "asphalt", "wetness": "lowFlooded"},
        "puddle_left": {"water_depth": 0.01}}}, "ice": None}}}
    d = _project(tmp_path, world=world)
    zs = Z.for_run(d, d / "scenarios" / "zones.xosc", {"goal": "asphalt"}, world, "Town01",
                   simulator="isaac")
    want = Z.expected(zs, 0.5, "moist")["goal_surface"]
    # lowFlooded is missing from asphalt's row: it takes the next drier one's, wetWithPuddles
    assert want["ice_at_goal"] == {"surface_class": "asphalt", "wetness": "lowFlooded",
                                   "water_depth": None, "mu": pytest.approx(1.12 * 0.75 * 0.5)}
    # a zone with no class of its own reads class "" and mu 0, the world's wetness
    assert want["puddle_left"] == {"surface_class": "", "wetness": "moist",
                                   "water_depth": 0.01, "mu": 0.0}


def test_the_default_table_is_found_in_this_workspace():
    t = Z.load_table(Z.default_table())
    assert t["ice"]["mu"] == pytest.approx(0.265)
    assert t["asphalt"]["wet"][0] == 1.0


def test_the_run_writes_each_zones_judgement_into_its_knob_entry(tmp_path):
    d = _project(tmp_path)
    zs = _runs(d)
    rd = tmp_path / "run"
    (rd / "gap_trace").mkdir(parents=True)
    lines = [{"type": "episode", "schema": 4, "episode": 1, "start_unix": 0.0,
              "npc_motion": "tracked", "map": "Town01", "step_time": 0.05},
             _rc(1, False), _rc(2, True)]
    (rd / "gap_trace" / "episode_1.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines))
    block, events = {"ok": True, "knobs": {"goal_surface": {"value": "asphalt", "ok": True}}}, []
    assert run.judge_zones(zs, rd, block, events) == ""
    entry = block["knobs"]["goal_surface"]
    assert entry["ok"] and block["ok"] and entry["zones"]["ice_at_goal"]["frame"] == 2
    assert events[-1]["event"] == "knobs.zones" and events[-1]["ok"]
    # no record read back after a step: the knob and the block not ok, the run a mismatch
    (rd / "gap_trace" / "episode_1.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines[:2]))
    block = {"ok": True, "knobs": {"goal_surface": {"value": "asphalt", "ok": True}}}
    why = run.judge_zones(zs, rd, block, [])
    assert "no road_condition record read back after a step" in why
    assert not block["ok"] and not block["knobs"]["goal_surface"]["ok"]


def test_a_layout_prop_in_a_stretch_beside_a_zone_warns_at_run_and_is_refused_by_check(
        tmp_path, monkeypatch):
    """092 K9f-a with issue 174 (133's condition 2 on the rebase's resolution). One knob value
    names a layout and sets a zone; the layout's two props stand on lanelet 6583 at s 20, inside a
    stand-in reversed stretch [19.9, 20.1]. Predicted (written 2026-11-26 before the first run):
    at run time `check_layouts` refuses nothing, the copy carries the zone's property and both
    props, and two warnings name the props' stretch; `testbench check` refuses the two props with
    166's fix "move s outside the stretch" and finds nothing against the zone."""
    import io
    import test_layouts as TL
    from scensim import lane_positions as LP
    world = {"works": {"values": {"none": None,
                                  "closed": {"layout": "west_street_closed",
                                             "zones": {"ice_at_goal": {"class": "asphalt"}}}},
                       "default": "none"}}
    scen = TL.SCEN.replace('<Init><Actions>', '<Init><Actions>' + ROAD.format(extra=""))
    d = TL._project(tmp_path, scen=scen, world=world)
    tb = yaml.safe_load((d / "testbench.yaml").read_text())
    tb["simulator"] = "isaac"
    (d / "ground").mkdir()
    (d / "ground" / "classes.yaml").write_text(yaml.safe_dump(TABLE))
    (d / "ground" / "town01_route.yaml").write_text(yaml.safe_dump(MAP))
    tb["ground"] = {"Town01": {"surface_maps": {"town01_route": "ground/town01_route.yaml"}}}
    (d / "testbench.yaml").write_text(yaml.safe_dump(tb))
    monkeypatch.setattr(LP, "stretches", lambda md, lane: {6583: ((19.9, 20.1),)}.get(int(lane), ()))
    sc = d / "scenarios" / "cs3.xosc"
    spec = run.expand(sc, d, params={"closure": ["closed"]})[0][0]
    out = io.StringIO()
    run.check_layouts(spec, d, out)          # refuses nothing
    warned = out.getvalue().splitlines()
    assert len(warned) == 2 and all("inside a reversed stretch [19.900, 20.100]" in w
                                    for w in warned)
    assert "prop barrier_a" in warned[0] and "prop barrier_b" in warned[1]
    lays, zs = run.run_layouts(spec, d), run.run_zones(spec, d)
    root = ET.fromstring(L.inject(sc, [p for x in lays for p in x["props"]], Z.properties(zs)))
    assert [p.get("name") for p in root.find(Z.INIT_ROAD).iter("Property")] == [
        "scensim.surface_map", "scensim.zone.ice_at_goal.class"]
    assert {so.get("name") for so in root.find("Entities")} >= {"barrier_a", "barrier_b"}
    found = project.layout_problems(d, tb)
    assert len(found) == 2 and all(f.refused and f.fix == "move s outside the stretch"
                                   for f in found)
    assert project.zone_problems(d, tb) == []


REPO = Path(__file__).resolve().parents[3] / "scenarios" / "projects"


@pytest.mark.skipif(not (REPO / "k9f_zones" / "testbench.yaml").is_file(),
                    reason="the repository's scenarios/projects is not beside this package")
def test_k9f_zones_sets_ice_at_goal_either_way_and_passes_the_rule(tmp_path):
    """092 K9f-a's exit testbench: both goal_surface values set ice_at_goal's class on its own
    copy of town01_route, the check finds nothing, and CARLA would refuse it by name."""
    import shutil
    src = REPO / "k9f_zones"
    d = tmp_path / "k9f_zones"
    shutil.copytree(src, d, ignore=shutil.ignore_patterns("assets", "state", "runs"))
    md = d / "assets" / "maps" / "Town01"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm town01/>")
    settings = yaml.safe_load((d / "testbench.yaml").read_text())
    world = settings["world"]["knobs"]
    assert K.problems(world, simulator="isaac") == []
    assert "CARLA 0.9.16 cannot set a zone's ground" in K.problems(world, simulator="carla")[0][1]
    sc = d / "scenarios" / "goal_stop.xosc"
    for value, cls in (("asphalt", "asphalt"), ("ice", "ice")):
        zs = Z.for_run(d, sc, {"goal_surface": value}, world, "Town01", simulator="isaac")
        assert [z["properties"] for z in zs] == [{"scensim.zone.ice_at_goal.class": cls}]
        assert zs[0]["surface_map"] == str(d / "ground" / "town01_route.yaml")
        # the zone's expected read-back: dry, the table's mu (the workspace's class table)
        want = Z.expected(zs, 1.0, "dry")["goal_surface"]["ice_at_goal"]
        assert want["mu"] == pytest.approx({"asphalt": 1.12, "ice": 0.265}[cls])
    assert project.zone_problems(d, settings) == []
    root = ET.fromstring(L.inject(sc, [], Z.properties(zs)))
    assert [(p.get("name"), p.get("value")) for p in root.find(Z.INIT_ROAD).iter("Property")] \
        == [("scensim.surface_map", "town01_route"), ("scensim.zone.ice_at_goal.class", "ice")]
