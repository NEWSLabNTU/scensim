"""The pilot's map variants (roadmap 092 K9, scenario-description.md CS3): world.pilot_maps, a
scenario's scensim.pilot_map binding, the check, the run's refusal and record, and the stack's
switch that starts the pilots on a variant while the world keeps its map."""
import json
import shutil

import pytest
import yaml

from scensim import assets, pilot_maps, project, results, run, stack

TB = """simulator: carla
maps: [Town01, Town05]
assets:
  - dataset: carla-town-autoware-maps
    take: [Town01, Town05]
pilots:
  ego: {kind: autoware, vehicle: tesla_model3}
  lead: {kind: carla_basic}
  follower: {kind: command, run: [python3, pilots/follower.py]}
"""
VARIANTS = {"Town01": {"current": "Town01", "before_works": "Town01_v",
                       "edited": {"map": "Town01_e", "pointcloud": "edited"}}}


@pytest.fixture
def where(host):
    tmp = host["tmp"]
    (tmp / "system" / "host.yaml").write_text(yaml.safe_dump(
        {"seat_locks": str(tmp / "locks"), "logs": str(tmp / "logs"), "seat": 2}))
    return host


def proj(where, pilot_maps_decl=VARIANTS, binding="$pm", default="current", name="proj"):
    """A multi-pilot project on Town01 with Town01_v (a byte copy of Town01) and Town01_e (an
    edited point cloud), world.pilot_maps, and a scenario binding the variant."""
    d = where["tmp"] / name
    project.new_project(d, "multi-pilot")
    tb = yaml.safe_load(TB)
    if pilot_maps_decl is not None:
        tb["world"] = {"pilot_maps": pilot_maps_decl}
    (d / "testbench.yaml").write_text(yaml.safe_dump(tb))
    assets.fetch(d, out=lambda s: None)
    maps = d / "assets" / "maps"
    for v in ("Town01_v", "Town01_e"):   # fetched files are read-only: writable copies
        shutil.copytree(maps / "Town01", maps / v, copy_function=shutil.copyfile)
        for x in [maps / v, *(p for p in (maps / v).rglob("*") if p.is_dir())]:
            x.chmod(0o755)
    (maps / "Town01_e" / "pointcloud_map.pcd").write_text("pcd01 with the cones")
    sc = d / "scenarios" / "three_pilots.xosc"
    x = sc.read_text()
    if binding is not None:
        x = x.replace('revMinor="2" />', 'revMinor="2"><Properties><Property '
                      f'name="scensim.pilot_map" value="{binding}"/></Properties></FileHeader>')
        x = x.replace("<ParameterDeclarations />", "<ParameterDeclarations><ParameterDeclaration "
                      f'name="pm" parameterType="string" value="{default}"/>'
                      "</ParameterDeclarations>")
    sc.write_text(x)
    return d, sc


def test_the_declarations_shape():
    assert pilot_maps.problems(VARIANTS) == []
    assert pilot_maps.problems({"Town01": {"current": "Town02"}}) == [
        ("world.pilot_maps.Town01.current", "is the world's own map, Town01, not Town02: name "
         "the other map as a variant of its own")]
    assert pilot_maps.problems({"Town01": {"x": {"map": "T", "pointcloud": "new"}}})[0][0] == \
        "world.pilot_maps.Town01.x"
    assert pilot_maps.problems(["Town01"])[0][1].startswith("is not a mapping")
    assert pilot_maps.variants(VARIANTS, "Town05") == {"current": ("Town05", False)}


def test_a_binding_resolves_from_the_runs_parameter_its_default_or_a_name(where, maps_hub):
    _, sc = proj(where)
    r = pilot_maps.resolve(VARIANTS, "Town01", sc)
    assert r == {"world": "Town01", "pilot": "Town01", "variant": "current", "pointcloud": "same"}
    r = pilot_maps.resolve(VARIANTS, "Town01", sc, {"pm": "before_works"})
    assert (r["pilot"], r["variant"]) == ("Town01_v", "before_works")
    assert pilot_maps.resolve(VARIANTS, "Town01", sc, {"pm": "edited"})["pointcloud"] == "edited"
    with pytest.raises(pilot_maps.PilotMapError, match=r"three_pilots.xosc: scensim.pilot_map: "
                       r"pm = 'old' is not a pilot map variant of Town01 \(world.pilot_maps."
                       r"Town01: before_works, current, edited\)"):
        pilot_maps.resolve(VARIANTS, "Town01", sc, {"pm": "old"})


def test_a_scenario_binding_no_variant_resolves_to_none(where, maps_hub):
    _, sc = proj(where, binding=None)
    assert pilot_maps.resolve(VARIANTS, "Town01", sc) is None


def test_the_check_holds_a_variant_to_the_worlds_frame_and_point_cloud(where, maps_hub):
    d, _ = proj(where)
    maps = d / "assets" / "maps"
    assert pilot_maps.file_problems(VARIANTS, maps) == []
    # the copy's point cloud edited without saying so, and its projection changed
    (maps / "Town01_v" / "pointcloud_map.pcd").write_text("other")
    (maps / "Town01_v" / pilot_maps.PROJECTOR).write_text("projector_type: MGRS\n")
    got = pilot_maps.file_problems(VARIANTS, maps)
    assert ("world.pilot_maps.Town01.before_works", "Town01_v's point cloud is not Town01's, and "
            "the variant does not declare it an edit ({map: Town01_v, pointcloud: edited})") in got
    assert ("world.pilot_maps.Town01.before_works", "Town01_v's map_projector_info.yaml is not "
            "Town01's: the pilot would localise in another frame than the world's") in got
    assert not [w for w, _ in got if w.endswith(".edited")]   # its cloud is a declared edit
    shutil.rmtree(maps / "Town01_v")
    assert any("map Town01_v is not fetched" in m for _, m in pilot_maps.file_problems(
        VARIANTS, maps))


def test_testbench_check_refuses_a_variant_off_the_worlds_frame_and_an_undeclared_one(
        where, maps_hub):
    d, _ = proj(where, default="before_works")
    assert not [f for f in project.check_project(d) if "pilot_map" in f.what]
    (d / "assets" / "maps" / "Town01_e" / pilot_maps.PROJECTOR).write_text("x: 1\n")
    f = [x for x in project.check_project(d) if "world.pilot_maps" in x.what]
    assert len(f) == 1 and "world.pilot_maps.Town01.edited" in f[0].what, [x.what for x in f]
    assert "another frame" in f[0].what
    d, _ = proj(where, pilot_maps_decl=None, default="before_works", name="undeclared")
    f = [x for x in project.check_project(d) if "scensim.pilot_map" in x.what]
    assert len(f) == 1 and f[0].refused
    assert "pm = 'before_works' is not a pilot map variant of Town01 (world.pilot_maps.Town01: " \
           "current)" in f[0].what


def test_scensim_run_refuses_an_undeclared_variant_before_any_run(where, maps_hub):
    d, sc = proj(where)
    specs, _ = run.expand(sc, d, params={"pm": ["before_works", "current"]})
    assert len(specs) == 2
    with pytest.raises(run.Refused, match="pm = 'stale' is not a pilot map variant of Town01"):
        run.expand(sc, d, params={"pm": ["stale"]})


def test_result_json_records_the_maps(where):
    m = {"world": "Town01", "pilot": "Town01_v", "variant": "before_works", "pointcloud": "same"}
    r = results.RunResult("x", "passed", maps=m).to_dict()
    assert r["maps"] == m and results.problems(r) == []
    assert "maps" not in results.RunResult("x", "passed").to_dict()
    assert results.problems(dict(r, maps={"world": "Town01"})) == [
        "maps: expected an object, {world, pilot, variant, pointcloud: same|edited}"]


class Pilots:
    def __init__(self, log):
        self.log, self.procs = log, {"ego": object()}

    def stop_all(self, rec):
        self.log.append("stop")

    def start_all(self, rec):
        self.log.append(("start", rec["map"], rec["map_path"].rsplit("/", 1)[-1]))


def test_another_variant_on_the_same_world_restarts_the_pilots_only(where, maps_hub,
                                                                    monkeypatch):
    d, _ = proj(where)
    rec = stack.plan(project_arg=str(d), map_name="Town01").record
    rec["map"] = "Town01"
    log = []
    monkeypatch.setattr(stack, "preload_map", lambda r, name: log.append(("load", name)) or
                        {"state": stack.LOADED, "message": "loaded"})
    sd = where["tmp"] / "stackdir"
    sd.mkdir()
    stack.request_switch(sd, "Town01", request_id="r1", pilot_map="Town01_v")
    req = stack.read_request(sd)
    assert req["pilot_map"] == "Town01_v"
    assert stack.switch_map(sd, rec, req, Pilots(log))
    # no town load: the world keeps Town01; the pilots start on the variant
    assert log == ["stop", ("start", "Town01", "Town01_v")]
    assert (rec["map"], rec["pilot_map"], stack.pilot_map_of(rec)) == ("Town01", "Town01_v",
                                                                       "Town01_v")
    assert rec["pilot_contract"]["map_path"].endswith("assets/maps/Town01_v")
    tl = rec["pilot_contract"].get("traffic_light_state_path")
    assert tl is None or tl.endswith("state/Town01/carla/traffic_lights.yaml")
    sw = json.loads((sd / "stack.json").read_text())["switch"]
    assert (sw["state"], sw["pilot_map"]) == (stack.DONE, "Town01_v") and "preload" not in sw
    # the same variant again: nothing to do
    log.clear()
    assert stack.switch_map(sd, rec, {"id": "r2", "map": "Town01", "pilot_map": "Town01_v"},
                            Pilots(log))
    assert log == []
    # back to the world's own map: the pilots only again
    assert stack.switch_map(sd, rec, {"id": "r3", "map": "Town01"}, Pilots(log))
    assert log == ["stop", ("start", "Town01", "Town01")] and rec["pilot_map"] is None
    # another world with a variant of its own: the town loads, then the pilots
    log.clear()
    assert stack.switch_map(sd, rec, {"id": "r4", "map": "Town05"}, Pilots(log))
    assert log == ["stop", ("load", "Town05"), ("start", "Town05", "Town05")]


def test_a_variant_not_fetched_is_the_switchs_problem(where, maps_hub):
    d, _ = proj(where)
    rec = stack.plan(project_arg=str(d), map_name="Town01").record
    assert stack.switch_problem(rec, "Town01", "Town01_v") is None
    assert "the pilots' map Town01_x is not fetched" in stack.switch_problem(rec, "Town01",
                                                                            "Town01_x")


def _edit_cached(d, rel="Town01/lanelet2_map.osm", text="<osm edited/>"):
    """Edit a locked file in the test's own cache, through the project's link, as issue 129's
    incident did."""
    p = (d / "assets" / "maps" / rel).resolve()
    p.chmod(0o644)
    p.parent.chmod(0o755)
    p.write_text(text)
    return p


def test_issue_129_the_keeper_refuses_a_switch_onto_an_edited_cache(where, maps_hub):
    d, _ = proj(where)
    rec = stack.plan(project_arg=str(d), map_name="Town01").record
    assert stack.switch_problem(rec, "Town01") is None
    _edit_cached(d)
    why = stack.switch_problem(rec, "Town01")
    assert why.startswith("map Town01 is not the locked one: carla-town-autoware-maps: "
                          "Town01/lanelet2_map.osm differs from the lock (sha256 "), why
    sd = where["tmp"] / "stackdir"
    sd.mkdir()
    log = []
    assert not stack.switch_map(sd, rec, {"id": "r1", "map": "Town01",
                                          "pilot_map": "Town01_v"}, Pilots(log))
    assert log == []   # no pilot stopped or started on it
    sw = json.loads((sd / "stack.json").read_text())["switch"]
    assert sw["state"] == stack.FAILED and "Town01/lanelet2_map.osm differs" in sw["error"]


def test_issue_129_testbench_check_refuses_a_lock_mismatch(where, maps_hub):
    d, _ = proj(where)
    assert not [f for f in project.check_project(d) if "differs from the lock" in f.what]
    _edit_cached(d)
    f = [x for x in project.check_project(d) if "differs from the lock" in x.what]
    assert len(f) == 1 and f[0].refused and "Town01/lanelet2_map.osm" in f[0].what


def test_issue_129_the_run_records_the_verified_digests(where, maps_hub):
    import hashlib
    d, _ = proj(where)
    want = hashlib.sha256((d / "assets" / "maps" / "Town01" / "lanelet2_map.osm")
                          .resolve().read_bytes()).hexdigest()
    assert pilot_maps.lanelet2_digest(d, "Town01") == want          # the lock's, verified
    assert pilot_maps.lanelet2_digest(d, "Town01_v") == want        # a copy, hashed
    _edit_cached(d)
    assert pilot_maps.lanelet2_digest(d, "Town01") != want
