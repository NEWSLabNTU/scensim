"""Prop layouts as a knob (roadmap 092 K9f-b): the layout file, where it is found, its check
against the world's anchors, the run's copy of the scenario (byte for byte the same for the
same inputs), and the refusals, one rule in testbench check and the run."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scensim_sampler"))

from scensim import knobs as K, layouts as L, project, run  # noqa: E402

PROP = {"category": "obstacle", "model": "static.prop.streetbarrier", "mass": 50,
        "box": {"center": [0, 0, 0.55], "dimensions": [0.4, 1.2, 1.1]},
        "at": {"lane": "west_street", "s": 20, "offset": -1.3}, "h": 1.5708}
LAYOUT = {"layout": 1, "props": {"barrier_b": dict(PROP, at={"lane": "west_street", "s": 20,
                                                              "offset": 0.0}),
                                 "barrier_a": PROP}}
SCEN = """<?xml version="1.0"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="2" date="2026-11-25T00:00:00" author="t" description="t">
    <Properties><Property name="scensim.knob.works" value="param:closure"/></Properties>
  </FileHeader>
  <ParameterDeclarations>
    <ParameterDeclaration name="closure" parameterType="string" value="closed"/>
  </ParameterDeclarations>
  <CatalogLocations><VehicleCatalog><Directory path="catalogs/vehicles"/></VehicleCatalog></CatalogLocations>
  <RoadNetwork><LogicFile filepath="$(env SCENSIM_MAPS)/Town01"/></RoadNetwork>
  <Entities><ScenarioObject name="ego"/></Entities>
  <Storyboard><Init><Actions><Private entityRef="ego"/></Actions></Init></Storyboard>
</OpenSCENARIO>
"""
WORLD = {"works": {"values": {"none": None, "closed": {"layout": "west_street_closed"}},
                   "default": "none"}}


def _project(tmp_path, layout=LAYOUT, where="testbench", scen=SCEN, world=WORLD):
    """A testbench on map Town01 whose west_street is resolved (one lanelet, 6583, 224.22 m)."""
    from scensim_sampler import anchors as A
    d = tmp_path / "proj"
    (d / "scenarios").mkdir(parents=True)
    (d / "testbench.yaml").write_text(yaml.safe_dump({"simulator": "carla", "maps": ["Town01"],
                                                      "world": {"knobs": world}}))
    (d / "scenarios" / "cs3.xosc").write_text(scen)
    md = d / "assets" / "maps" / "Town01"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm town01/>")
    lane = {"kind": "lane", "lanelets": [{"id": 6583, "from_s": 0.0, "to_s": 224.22}],
            "length": 224.22, "speed_limit": 11.17, "start_x": 325.64, "start_y": -129.52,
            "end_x": 101.42, "end_y": -129.41, "heading_s": [0.0, 224.22],
            "heading": [3.1412, 3.1412], "heading_max_error": 0.0,
            "x": [325.64, 101.42], "y": [-129.52, -129.41]}
    (md / A.RESOLVED).write_text(json.dumps({"format": A.FORMAT, "version": A.VERSION,
                                             "map": "Town01", "map_sha256": A.map_digest(md),
                                             "anchors": {"west_street": lane}}))
    if layout is not None:
        ld = (d / "layouts" / "Town01") if where == "testbench" else (md / "layouts")
        ld.mkdir(parents=True)
        (ld / "west_street_closed.yaml").write_text(yaml.safe_dump(layout))
    return d


def test_a_layout_is_found_in_the_testbench_or_beside_the_map_not_both(tmp_path):
    d = _project(tmp_path)
    assert L.find(d, "Town01", "west_street_closed") == \
        d / "layouts" / "Town01" / "west_street_closed.yaml"
    (d / "assets/maps/Town01/layouts").mkdir()
    (d / "assets/maps/Town01/layouts/west_street_closed.yaml").write_text("layout: 1\n")
    with pytest.raises(L.LayoutError, match="in the testbench .* and beside map Town01"):
        L.find(d, "Town01", "west_street_closed")
    with pytest.raises(L.LayoutError, match="no layouts/Town01/gone.yaml"):
        L.find(d, "Town01", "gone")


def test_a_layouts_props_are_placed_on_the_lane_in_name_order(tmp_path):
    from scensim import anchors as anchorsmod
    d = _project(tmp_path)
    props = L.place(L.read(L.find(d, "Town01", "west_street_closed")),
                    anchorsmod.for_map(d, "Town01"))
    assert [(p["name"], p["lanelet"], p["s"], p["offset"]) for p in props] == [
        ("barrier_a", 6583, 20.0, -1.3), ("barrier_b", 6583, 20.0, 0.0)]
    # the map-frame x, y of a lane resolved with its centreline: offset to the left (west-
    # bound, so -1.3 is north of the centreline)
    assert props[0]["x"] == pytest.approx(305.64, abs=0.01)
    assert props[0]["y"] == pytest.approx(-129.51 + 1.3, abs=0.01)


def test_a_layout_wrong_for_the_world_is_refused_by_name(tmp_path):
    from scensim import anchors as anchorsmod
    d = _project(tmp_path)
    anchors = anchorsmod.for_map(d, "Town01")
    bad = {"layout": 1, "props": {
        "a": dict(PROP, category="barrier"),
        "b": dict(PROP, at={"lane": "east_street", "s": 1}),
        "c": dict(PROP, at={"lane": "west_street", "s": 300}),
        "d": dict(PROP, box={"center": [0, 0]}),
        "e": dict(PROP, colour="red")}}
    text = " | ".join(L.problems(bad, anchors))
    for want in ("a: category 'barrier': SSv2 implements obstacle only",
                 "b: at.lane east_street: the world has no resolved lane east_street",
                 "c: anchor.west_street: s 300", "d: box:", "e: colour: a prop has"):
        assert want in text, want
    assert L.problems({"layout": 2}, anchors) == ["layout: `layout: 1` first"]


def test_the_runs_copy_is_the_source_with_the_props_the_same_bytes_each_time(tmp_path):
    from scensim import anchors as anchorsmod
    d = _project(tmp_path)
    src = d / "scenarios" / "cs3.xosc"
    props = L.place(L.read(L.find(d, "Town01", "west_street_closed")),
                    anchorsmod.for_map(d, "Town01"))
    one, two = L.inject(src, props), L.inject(src, props)
    assert one == two
    root = ET.fromstring(one)
    assert [so.get("name") for so in root.find("Entities")] == ["ego", "barrier_a", "barrier_b"]
    mo = root.find("Entities/ScenarioObject[@name='barrier_a']/MiscObject")
    assert (mo.get("name"), mo.get("miscObjectCategory")) == ("static.prop.streetbarrier",
                                                              "obstacle")
    lp = root.find("Storyboard/Init/Actions/Private[@entityRef='barrier_a']//LanePosition")
    assert (lp.get("laneId"), lp.get("s"), lp.get("offset")) == ("6583", "20.0", "-1.3")
    # a relative catalog path is absolute in the copy; $(env ...) is kept
    assert root.find(".//Directory").get("path") == str((src.parent / "catalogs/vehicles").resolve())
    assert root.find(".//LogicFile").get("filepath") == "$(env SCENSIM_MAPS)/Town01"
    # a prop that is already a scenario entity: two writers
    with pytest.raises(L.LayoutError, match="ego: a layout's prop and the scenario's entity"):
        L.inject(src, [dict(props[0], name="ego")])


def test_the_knob_names_a_layout_and_the_run_refuses_what_the_check_refuses(tmp_path):
    assert K.problems(WORLD) == []
    assert "a layout's name" in K.problems({"w": {"values": {"x": {"layout": 3}}}})[0][1]
    assert K.plan(WORLD, {"works": "closed"}, "isaac")["layouts"] == {"works": "west_street_closed"}
    d = _project(tmp_path)
    sc = d / "scenarios" / "cs3.xosc"
    specs, _ = run.expand(sc, d, params={"closure": ["closed", "none"]})
    lays = [run.run_layouts(s, d) for s in specs]
    assert [x["layout"] for x in lays[0]] == ["west_street_closed"] and lays[1] == []
    copy = L.write_copy(sc, lays[0], tmp_path)
    assert copy["path"] == str(tmp_path / "scenario.xosc")
    assert copy["sha256"] == L.sha256((tmp_path / "scenario.xosc").read_bytes())
    assert copy["layouts"][0]["sha256"] == L.sha256(
        (d / "layouts/Town01/west_street_closed.yaml").read_bytes())
    assert project.layout_problems(d, yaml.safe_load((d / "testbench.yaml").read_text())) == []
    # a category SSv2 does not take: refused before any run, and by the check, in one rule
    bad = _project(tmp_path / "b", layout={"layout": 1,
                                           "props": {"x": dict(PROP, category="barrier")}})
    with pytest.raises(run.Refused, match="category 'barrier'"):
        run.expand(bad / "scenarios" / "cs3.xosc", bad, params={"closure": ["closed"]})
    found = project.layout_problems(bad, yaml.safe_load((bad / "testbench.yaml").read_text()))
    assert len(found) == 1 and found[0].refused and "category 'barrier'" in found[0].what
    # a layout knob on SSv2's own distribution: refused
    with pytest.raises(L.LayoutError, match="SSv2's own distribution"):
        L.for_run(d, sc, {"closure": "closed"}, WORLD, "Town01", distribution=True)


def test_one_prop_in_two_bound_layouts_is_two_writers(tmp_path):
    world = dict(WORLD, again={"values": {"on": {"layout": "west_street_closed"}},
                               "default": "on"})
    scen = SCEN.replace('</Properties>', '<Property name="scensim.knob.again" value="param:x"/>'
                        '</Properties>').replace(
        '</ParameterDeclarations>', '<ParameterDeclaration name="x" parameterType="string" '
        'value="on"/></ParameterDeclarations>')
    d = _project(tmp_path, scen=scen, world=world)
    with pytest.raises(L.LayoutError, match="in layout west_street_closed and layout "
                                            "west_street_closed: two writers"):
        L.for_run(d, d / "scenarios" / "cs3.xosc", {"closure": "closed"}, world, "Town01")
