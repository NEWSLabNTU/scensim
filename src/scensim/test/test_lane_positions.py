"""Issue 166: a LanePosition inside a reversed stretch of SSv2's spline is refused when written
into the scenario (scensim check) and warned of when a run's values put it there (scensim run)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scensim_batch"))

from scensim import lane_positions as L   # noqa: E402


def test_an_uneven_centreline_has_its_stretches_and_an_even_one_none():
    from scensim_batch.catmull import lanelet_stretches
    xs = [0.0, 0.015, 0.03, 0.045, 0.06] + [0.06 + 0.3 * k for k in range(1, 21)]
    st = lanelet_stretches([[x, 0.0, 0.0] for x in xs])
    assert st and all(b - a < 0.1 for a, b in st)
    assert lanelet_stretches([[0.3 * k, 0.0, 0.0] for k in range(30)]) == []
    assert lanelet_stretches([[0.0, 0.0], [1.0, 0.0]]) == []         # a line never reverses


XOSC = """<OpenSCENARIO><ParameterDeclarations>
  <ParameterDeclaration name="walk_s" parameterType="double" value="3.0"/>
</ParameterDeclarations><Storyboard><Init><Actions>
  <Private entityRef="a"><PrivateAction><TeleportAction><Position>
    <LanePosition roadId="" laneId="7" s="10.0" offset="0"/></Position></TeleportAction></PrivateAction></Private>
  <Private entityRef="b"><PrivateAction><TeleportAction><Position>
    <LanePosition roadId="" laneId="7" s="20.0" offset="0"/></Position></TeleportAction></PrivateAction></Private>
  <Private entityRef="w"><PrivateAction><TeleportAction><Position>
    <LanePosition roadId="" laneId="9" s="$walk_s" offset="0"/></Position></TeleportAction></PrivateAction></Private>
</Actions></Init></Storyboard></OpenSCENARIO>
"""


def test_check_refuses_a_written_s_in_a_stretch_and_run_warns_of_a_bound_one(tmp_path,
                                                                             monkeypatch):
    sc = tmp_path / "s.xosc"
    sc.write_text(XOSC)
    table = {7: ((9.98, 10.02),), 9: ((4.0, 4.5),)}
    monkeypatch.setattr(L, "stretches", lambda md, lane: table.get(int(lane), ()))
    assert L.positions(sc) == [("7", "10.0"), ("7", "20.0"), ("9", "$walk_s")]
    (msg,) = L.fixed_problems(sc, tmp_path)           # only the written one, at s 10
    assert "laneId 7 s 10" in msg and "[9.980, 10.020]" in msg and "issue 166" in msg
    assert L.run_warnings(sc, tmp_path, {"walk_s": 3.0}) == []           # outside
    (w,) = L.run_warnings(sc, tmp_path, {"walk_s": 4.2})                  # the run's value
    assert "laneId 9 s 4.2" in w and "[4.000, 4.500]" in w


def test_a_map_that_does_not_load_is_said_and_neither_refused_nor_fatal(tmp_path):
    """The gate's k9e test: a stand-in map file stopped `scensim run` in the run's warning.
    An unloadable map is a check not made: the run warns so and goes on, `check` says so."""
    import io
    from types import SimpleNamespace
    from scensim import run as R
    md = tmp_path / "assets" / "maps" / "Town01"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm town01/>")
    sc = tmp_path / "s.xosc"
    sc.write_text(XOSC.replace("<OpenSCENARIO>", "<OpenSCENARIO><RoadNetwork><LogicFile "
                               "filepath=\"$(env SCENSIM_MAPS)/Town01\"/></RoadNetwork>"))
    try:
        L.fixed_problems(sc, md)
        raise AssertionError("an unloadable map was read")
    except L.MapUnreadable as e:
        assert "map Town01 does not load" in str(e) and "issue 166" in str(e)
    out = io.StringIO()
    R.warn_lane_positions(SimpleNamespace(scenario=str(sc), parameters={}), tmp_path, out=out)
    assert "warning  s.xosc: map Town01 does not load" in out.getvalue()
