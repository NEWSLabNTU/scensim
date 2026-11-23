"""Sampled runs (roadmap 092 K3): a suite's sample: expanded into one run per record, each run's
record bound to its world and car, --replay of a record, and replay fidelity. The stack is the
test_run harness's (a real keeper, a stub SSv2)."""
import io
import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scensim_sampler"))

from scensim import results, run, runs, sampled  # noqa: E402
from _ceiling import STOP_WAIT  # noqa: E402
from test_run import fake, make, start_stack, where  # noqa: E402,F401 - the fixture

import scensim_sampler  # noqa: E402

SEEDED = """simulator: carla
assets:
  - dataset: carla-town-autoware-maps
    take: [Town01]
pilots:
  ego: {kind: autoware, vehicle: tesla_model3}
  lead: {kind: carla_basic}
  follower: {kind: command, lifetime: run,
             run: [python3, pilots/follower.py, --seed, "{seed}"]}
"""

DIST = """<?xml version="1.0"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="2" date="2026-11-21T00:00:00" author="t" description="t"/>
  <ParameterValueDistribution>
    <ScenarioFile filepath="sampled.xosc"/>
    <Stochastic numberOfTestRuns="3" randomSeed="41">
      <StochasticDistribution parameterName="gap">
        <UniformDistribution><Range lowerLimit="5" upperLimit="15"/></UniformDistribution>
      </StochasticDistribution>
      <StochasticDistribution parameterName="outcome">
        <ProbabilityDistributionSet><Element value="{outcome}" weight="1"/></ProbabilityDistributionSet>
      </StochasticDistribution>
    </Stochastic>
  </ParameterValueDistribution>
</OpenSCENARIO>
"""


def sampled_project(where, outcome="passed", testbench=None):
    d = make(where, testbench)
    src = (d / "scenarios" / "three_pilots.xosc").read_text()
    src = src.replace(
        'revMajor="1" revMinor="2" />',
        'revMajor="1" revMinor="2"><Properties>'
        '<Property name="scensim.category" value="R1.car_following.lead_brakes"/>'
        '<Property name="scensim.cell_attributes" value="surface"/>'
        '<Property name="scensim.cell.surface" value="dry"/></Properties></FileHeader>', 1)
    src = src.replace(
        "<ParameterDeclarations />",
        '<ParameterDeclarations>'
        '<ParameterDeclaration name="gap" parameterType="double" value="10"/>'
        '<ParameterDeclaration name="outcome" parameterType="string" value="passed"/>'
        '<ParameterDeclaration name="scensim_seed" parameterType="unsignedInt" value="0"/>'
        '</ParameterDeclarations>', 1)
    assert "scensim.category" in src and "scensim_seed" in src
    (d / "scenarios" / "sampled.xosc").write_text(src)
    (d / "scenarios" / "sampled_dist.xosc").write_text(DIST.replace("{outcome}", outcome))
    (d / "suites").mkdir(exist_ok=True)
    return d


def suite(d, **sample):
    (d / "suites" / "s.yaml").write_text(yaml.safe_dump({
        "sample": {"distribution": "../scenarios/sampled_dist.xosc", **sample},
        "logging": {"keep": {}}}))
    return d / "suites" / "s.yaml"


# --- expansion ------------------------------------------------------------------------------

def test_a_sample_key_expands_to_one_run_per_record(where, maps_hub):
    d = sampled_project(where)
    specs, _ = run.expand(suite(d, n=4, seed=7), d)
    assert [s.key for s in specs] == [f"sampled_s{i}_r0" for i in range(4)]
    for i, s in enumerate(specs):
        assert s.sample["sampler"]["index"] == i and s.sample["sampler"]["run_seed"] == 7
        assert 5 <= s.parameters["gap"] <= 15 and s.parameters["outcome"] == "passed"
        # the scenario declares scensim_seed: SSv2 gets the record's scenario seed
        assert s.parameters["scensim_seed"] == s.sample["seeds"]["scenario"]
        assert s.scenario == (d / "scenarios" / "sampled.xosc").resolve()
    # drawn again, the same records
    again, _ = run.expand(suite(d, n=4, seed=7), d)
    assert [s.sample["id"] for s in again] == [s.sample["id"] for s in specs]


def test_sample_sits_beside_the_old_keys_and_they_are_unchanged(where, maps_hub):
    d = sampled_project(where)
    (d / "suites" / "both.yaml").write_text(yaml.safe_dump({
        "scenarios": ["../scenarios/three_pilots.xosc"],
        "parameters": {"outcome": ["passed", "failed"]}, "repetitions": 2, "seed": 1000,
        "sample": [{"distribution": "../scenarios/sampled_dist.xosc", "n": 2, "seed": 1},
                   {"distribution": "../scenarios/sampled_dist.xosc", "n": 1, "seed": 2}]}))
    specs, _ = run.expand(d / "suites" / "both.yaml", d)
    old = [s for s in specs if s.sample is None]
    assert [(s.key, s.seed) for s in old] == [
        ("three_pilots_outcome-passed_r0", 1000), ("three_pilots_outcome-passed_r1", 1001),
        ("three_pilots_outcome-failed_r0", 1000), ("three_pilots_outcome-failed_r1", 1001)]
    new = [s for s in specs if s.sample is not None]
    assert [(s.key, s.seed) for s in new] == [("sampled_s0_r0", 1), ("sampled_s1_r0", 1),
                                              ("sampled_s0_r0", 2)]


@pytest.mark.parametrize("sample, words", [
    ({"distribution": "../scenarios/sampled_dist.xosc", "n": 0}, "n: an integer >= 1"),
    ({"distribution": "../scenarios/sampled_dist.xosc", "count": 3}, "unknown key count"),
    ({"distribution": "../scenarios/nope.xosc"}, "distribution ../scenarios/nope.xosc: no such"),
    ("x.xosc", "a mapping {distribution, n, seed"),
])
def test_a_bad_sample_is_refused_by_name(where, maps_hub, sample, words):
    d = sampled_project(where)
    (d / "suites" / "s.yaml").write_text(yaml.safe_dump({"sample": sample}))
    with pytest.raises(run.Refused, match=words):
        run.expand(d / "suites" / "s.yaml", d)


def test_a_scenario_without_a_category_is_refused_by_the_sampler(where, maps_hub):
    d = sampled_project(where)
    p = d / "scenarios" / "sampled.xosc"
    p.write_text(p.read_text().replace("scensim.category", "other.category"))
    with pytest.raises(run.Refused, match="no scensim.category property"):
        run.expand(suite(d, n=1, seed=1), d)


def test_a_stack_pilots_seed_is_named_as_not_applied():
    rec = {"seeds": {"pilots": {"ego": 5, "follower": 6}}}
    pilots = [{"entity": "ego", "lifetime": "stack"}, {"entity": "follower", "lifetime": "run"}]
    applied, notes = sampled.applied_seeds(rec, pilots)
    assert applied == {"ego": 0, "follower": 6}
    assert notes == ["pilot ego: a stack pilot, its seed 5 not applied; it ran with the "
                     "stack's (0)"]


def test_pilot_seed_is_the_records_for_its_entity():
    rec = {"seeds": {"pilots": {"follower": 77}}}
    assert sampled.pilot_seed(rec, "follower", 5) == 77
    assert sampled.pilot_seed(rec, "lead", 5) == 5
    assert sampled.pilot_seed(None, "follower", 5) == 5


def test_world_of_a_carla_town_hashes_its_map_directory(tmp_path):
    (tmp_path / "lanelet2_map.osm").write_text("<osm/>")
    (tmp_path / "carla").mkdir()
    (tmp_path / "carla" / "traffic_lights.yaml").write_text("861: green\n")
    rec = {"simulator": "carla", "map": "Town01", "map_path": str(tmp_path)}
    w = sampled.world_of(rec, {"carla": {"version": "0.9.16"}})
    assert w["name"] == "Town01"
    assert w["hash"].startswith("carla-0.9.16:Town01:map:sha256:")
    # the carla/ part changes the world without touching the lanelet
    (tmp_path / "carla" / "traffic_lights.yaml").write_text("861: red\n")
    assert sampled.world_of(rec, {"carla": {"version": "0.9.16"}})["hash"] != w["hash"]
    w = sampled.world_of({"simulator": "isaac", "map": "haruna"},
                         {"stage": {"root": "haruna", "sha256": "ab" * 32}})
    assert w == {"name": "haruna", "hash": "stage:sha256:" + "ab" * 32}
    assert sampled.world_of({"simulator": "carla", "map": "Town01"}, {})["hash"].endswith(
        ":unhashed")


# --- runs, replay, fidelity -----------------------------------------------------------------

# The fake pilot stays up until the run stops it, as a real one does: a pilot whose process
# has ended before the run's first poll is not coming up (issue 089), so one that exits at once
# failed the run whenever load delayed that poll (issue 112).
FAKE_PILOT = [sys.executable, "-c",
              "import signal, sys\n"
              "for s in (signal.SIGINT, signal.SIGTERM):\n"
              "    signal.signal(s, lambda *_: sys.exit(0))\n"
              "signal.pause()"]


@pytest.fixture
def stack_up(where, maps_hub, monkeypatch):
    d = sampled_project(where, testbench=SEEDED)
    monkeypatch.setattr(run, "scenario_argv", fake(where))
    seen = where["tmp"] / "seeds.jsonl"

    real = run.pilot_argv

    def pilot_cmd(rec, pilot, entry, log_dir):
        # the pilot's run argument, recorded here as the command is built: a child that wrote
        # it could be killed by run.end's SIGTERM before it started, under load (issue 112)
        argv = real(rec, pilot, entry, log_dir)
        words = dict(w.split(":=", 1) for w in argv if ":=" in w)
        with open(seen, "a") as f:
            f.write(json.dumps(words.get("run", "")) + "\n")
        return FAKE_PILOT
    monkeypatch.setattr(run, "pilot_argv", pilot_cmd)
    p, proc = start_stack(d)
    yield d, seen
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=STOP_WAIT())


def runs_dir(where):
    return where["tmp"] / "logs" / "proj" / "runs"


def test_sampled_runs_carry_their_bound_record_and_replay_exactly(stack_up, where):
    d, seen = stack_up
    out = io.StringIO()
    assert run.main([str(suite(d, n=2, seed=7)), "--project", str(d)], out=out) == 0, \
        out.getvalue()
    dirs = sorted(runs_dir(where).iterdir())
    assert len(dirs) == 2
    for rd in dirs:
        r = results.RunResult.read(rd / "result.json")
        rec = json.loads((rd / "sample.json").read_text())
        assert r.sample["id"] == rec["id"] and r.sample["drawn_id"] != rec["id"]
        assert rec["world"]["name"] == "Town01"
        assert rec["world"]["hash"].startswith("carla")
        # bound (world, and car when the stack names a spec_hash) and valid
        bound = scensim_sampler.check(rec, bound="car" in rec)
        assert bound == [], bound
        if "car" not in rec:
            assert any(n.startswith("car:") for n in r.sample["unbound"])
        assert r.scenario["parameters"]["gap"] == rec["values"]["gap"]
    # the follower (lifetime: run) got each record's seed for it
    pilot_runs = [json.loads(line) for line in seen.read_text().splitlines()]
    recs = [json.loads((rd / "sample.json").read_text()) for rd in dirs]
    want = {str(x["seeds"]["pilots"]["follower"]) for x in recs}
    assert {w.split("--seed ")[1] for w in pilot_runs} == want

    # replay the first run: same values and seeds, the target recorded
    first = dirs[0]
    out = io.StringIO()
    assert run.main(["--replay", str(first), "--project", str(d)], out=out) == 0, out.getvalue()
    replay = [x for x in sorted(runs_dir(where).iterdir()) if x.name.endswith("_replay")]
    assert len(replay) == 1
    rr = results.RunResult.read(replay[0] / "result.json")
    orig = results.RunResult.read(first / "result.json")
    assert rr.replay["of"] == orig.sample["drawn_id"] and rr.replay["of_run"] == first.name
    assert rr.replay["target"]["simulator"] == "carla"
    assert rr.scenario["parameters"] == orig.scenario["parameters"]
    assert json.loads((replay[0] / "sample.json").read_text())["seeds"] == \
        json.loads((first / "sample.json").read_text())["seeds"]
    assert json.loads(seen.read_text().splitlines()[-1]).split("--seed ")[1] == \
        str(recs[0]["seeds"]["pilots"]["follower"])

    # fidelity: the replay reached the original's outcome
    out = io.StringIO()
    assert runs.main(["fidelity", str(runs_dir(where)), "--json",
                      str(where["tmp"] / "f.json")], out=out) == 0
    assert "fidelity: 1 of 1 replays reached the original's outcome (1.00)" in out.getvalue()
    rep = json.loads((where["tmp"] / "f.json").read_text())
    assert rep["pairs"][0]["differs"] == []


def test_the_fake_pilot_outlives_a_late_first_poll(stack_up, where, monkeypatch):
    """Issue 112: the run's first poll of its pilot made late, as load makes it, on purpose. A
    fake pilot that exits at once has ended by then and the run is an infra error; one that
    stays up until the run stops it, as a real pilot does, passes."""
    d, _ = stack_up
    real = run._start

    def start(argv, *args, **kwargs):
        proc = real(argv, *args, **kwargs)
        if argv == FAKE_PILOT:
            try:   # until a pilot that exits at once has exited; a live one is waited 5 s
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return proc
    monkeypatch.setattr(run, "_start", start)
    out = io.StringIO()
    assert run.main([str(suite(d, n=1, seed=11)), "--project", str(d)], out=out) == 0, \
        out.getvalue()


def test_a_replay_of_a_changed_scenario_is_refused(stack_up, where, capsys):
    d, _ = stack_up
    assert run.main([str(suite(d, n=1, seed=3)), "--project", str(d)], out=io.StringIO()) == 0
    first = next(runs_dir(where).iterdir())
    p = d / "scenarios" / "sampled.xosc"
    p.write_text(p.read_text() + "\n<!-- edited -->\n")
    assert run.main(["--replay", str(first), "--project", str(d)], out=io.StringIO()) == 3
    assert "has changed since the record was drawn" in capsys.readouterr().err


def test_replay_takes_a_record_file_and_refuses_extra_arguments(where, maps_hub, capsys):
    d = sampled_project(where)
    b = scensim_sampler.Sampler.from_file(d / "scenarios" / "sampled_dist.xosc").draw(n=3)
    f = where["tmp"] / "r.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in b.records))
    with pytest.raises(run.Refused, match="3 records; give --index"):
        run.replay_specs(str(f), None, d)
    (spec,) = run.replay_specs(str(f), 2, d)
    assert spec.key == "sampled_s2_replay" and spec.replay_of == ""
    assert spec.sample["id"] == b.records[2]["id"]
    assert run.main(["--replay", str(f), "x.xosc", "--project", str(d)]) == 3
    assert "--replay runs the record as it is; drop a target" in capsys.readouterr().err
    assert run.main(["--project", str(d)]) == 3
    assert "a target (or --replay)" in capsys.readouterr().err


def test_fidelity_names_what_differs(tmp_path):
    def write(name, verdict, sample=None, replay=None, failures=0):
        rd = tmp_path / name
        rd.mkdir()
        r = results.RunResult(run_id=name, verdict=verdict,
                              ssv2={"junit": None, "failures": failures, "errors": 0,
                                    "message": ""},
                              sample=sample, replay=replay)
        r.write(rd / "result.json")
    s = {"id": "b" * 64, "drawn_id": "a" * 64, "index": 0, "run_seed": 1, "category": "R1.a.b",
         "cell": {}, "base": None, "proposal": None, "weight": 1.0, "log_weight": 0.0,
         "file": "sample.json"}
    write("o", "passed", sample=s)
    write("r1", "passed", sample=s, replay={"of": "a" * 64, "of_run": "o", "target": {}})
    write("r2", "failed", sample=s, replay={"of": "a" * 64, "of_run": "o", "target": {}},
          failures=1)
    rep = sampled.fidelity(sorted(tmp_path.iterdir()))
    assert rep["total"] == 2 and rep["agree"] == 1 and rep["share"] == 0.5
    bad = next(p for p in rep["pairs"] if p["replay"] == "r2")
    assert bad["differs"] == ["verdict", "end"]
    assert bad["replay_outcome"]["end"] == "ssv2.failure"


def test_the_result_validator_takes_sample_and_replay():
    good = {"schema": "swb.result/1", "run_id": "x", "verdict": "passed",
            "sample": {"id": "a" * 64, "drawn_id": "b" * 64, "index": 0, "weight": 1.0,
                       "log_weight": 0.0},
            "replay": {"of": "b" * 64, "of_run": None, "target": {}}}
    assert results.problems(good) == []
    bad = json.loads(json.dumps(good))
    bad["sample"]["index"] = -1
    bad["replay"]["of"] = "short"
    assert results.problems(bad) == ["sample.index: expected an integer >= 0",
                                     "replay.of: expected the replayed record's id (64 hex "
                                     "digits)"]
    # a run without a sample has neither key
    assert "sample" not in results.RunResult("x", "passed").to_dict()


def test_a_suites_sample_reads_the_projects_world_anchors(tmp_path):
    """093 gap 7: testbench.yaml's world.anchors reach the sampler; CS7's cell reads its exit
    lane's heading from them, and the record keeps the values read."""
    import shutil
    cases = Path(scensim_sampler.__file__).resolve().parents[1] / "examples" / "cases"
    for f in ("cs7_cyclist_low_sun.xosc", "cs7_cyclist_low_sun_dist.xosc"):
        shutil.copy(cases / f, tmp_path)
    shutil.copytree(cases / "models", tmp_path / "models")
    (tmp_path / "testbench.yaml").write_text(
        "simulator: carla\nworld:\n  anchors:\n    exit_n: {kind: lane, heading: 0.5, lanelet: 102}\n"
        "    approach_n: {kind: lane, lanelet: 101}\n")
    anchors = run._world_anchors(tmp_path)
    assert anchors["exit_n"] == {"kind": "lane", "heading": 0.5, "lanelet": 102}
    drawn = sampled.draw([{"distribution": "cs7_cyclist_low_sun_dist.xosc", "n": 3, "seed": 2}],
                         lambda x: tmp_path / x, "suite", anchors=anchors)
    assert len(drawn) == 3
    for rec, _ in drawn:
        assert rec["anchors"]["exit_n"] == {"heading": 0.5, "lanelet": 102.0}
    with pytest.raises(sampled.SampleRefused, match="anchor.exit_n.heading"):
        sampled.draw([{"distribution": "cs7_cyclist_low_sun_dist.xosc", "n": 1, "seed": 2}],
                     lambda x: tmp_path / x, "suite")
    assert run._world_anchors(tmp_path / "nowhere") is None


def test_a_maps_resolved_anchors_reach_the_sampler(tmp_path):
    """092 K9a: the map's anchors.resolved.json (beside lanelet2_map.osm in the project's
    assets) is merged with testbench.yaml's world.anchors for a distribution on that map; one
    resolved on another map is refused, and so is a name in both."""
    import shutil
    from scensim_sampler import anchors as A
    cases = Path(scensim_sampler.__file__).resolve().parents[1] / "examples" / "cases"
    for f in ("cs7_cyclist_low_sun.xosc", "cs7_cyclist_low_sun_dist.xosc"):
        shutil.copy(cases / f, tmp_path)
    shutil.copytree(cases / "models", tmp_path / "models")
    sc = tmp_path / "cs7_cyclist_low_sun.xosc"              # a project scenario names its map so
    sc.write_text(sc.read_text().replace('filepath="maps/town_street"',
                                         'filepath="$(env SCENSIM_MAPS)/town_street"'))
    assert "$(env SCENSIM_MAPS)/town_street" in sc.read_text()
    md = tmp_path / "assets" / "maps" / "town_street"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm/>")
    doc = {"format": A.FORMAT, "version": A.VERSION, "map": "town_street",
           "map_sha256": A.map_digest(md), "heading_step": 0.5, "heading_max_error": 0.0,
           "anchors": {"exit_n": {"kind": "lane", "lanelets": [{"id": 7, "from_s": 0.0,
                                                                "to_s": 30.0}],
                                  "length": 30.0, "speed_limit": 13.9, "start_x": 0.0,
                                  "start_y": 0.0, "end_x": 0.0, "end_y": 30.0,
                                  "heading_s": [0.0, 30.0], "heading": [0.25, 0.25],
                                  "heading_max_error": 0.0}}}
    (md / A.RESOLVED).write_text(json.dumps(doc))
    (tmp_path / "testbench.yaml").write_text(
        "simulator: carla\nworld:\n  anchors:\n    approach_n: {kind: lane, lanelet: 101}\n")
    # a resolved lane's LanePosition: the lanelet holding cyclist_s (092 K9b)
    sc.write_text(sc.read_text().replace('value="exit_n.lanelet"',
                                         'value="exit_n.lanelet_at($cyclist_s)"'))
    dist = tmp_path / "cs7_cyclist_low_sun_dist.xosc"
    got = run._anchors_for(tmp_path, dist)
    assert got["exit_n"]["length"] == 30.0 and got["approach_n"]["lanelet"] == 101 and got["exit_n"]["source"]["map"] == "town_street"
    # CS7 reads the bare heading, a stated anchor's number; a resolved lane has heading(s)
    with pytest.raises(sampled.SampleRefused, match=r"anchor.exit_n.heading\(s\), not bare"):
        sampled.draw([{"distribution": dist.name, "n": 1, "seed": 2}], lambda x: tmp_path / x,
                     "suite", anchors=lambda d: run._anchors_for(tmp_path, d))
    model = tmp_path / "models" / "cs7_cyclist.yaml"
    model.write_text(model.read_text().replace("anchor.exit_n.heading", "anchor.exit_n.heading(12.0)"))
    drawn = sampled.draw([{"distribution": dist.name, "n": 4, "seed": 2}],
                         lambda x: tmp_path / x, "suite",
                         anchors=lambda d: run._anchors_for(tmp_path, d))
    for rec, _ in drawn:
        assert rec["anchors"] == {"approach_n": {"lanelet": 101.0}}   # the stated one
        assert rec["anchor_source"] == [got["exit_n"]["source"]]
        assert scensim_sampler.check(rec) == []
        assert abs(rec["values"]["sun_azimuth"] - (0.25 + rec["values"]["rel_azimuth"])) < 1e-9
    # a name in both
    (tmp_path / "testbench.yaml").write_text(
        "simulator: carla\nworld:\n  anchors:\n    exit_n: {kind: lane, heading: 1.0}\n"
        "    approach_n: {kind: lane, lanelet: 101}\n")
    with pytest.raises(A.AnchorError, match="exit_n: declared by the map"):
        run._anchors_for(tmp_path, dist)
    # resolved on another map's bytes
    (tmp_path / "testbench.yaml").write_text("simulator: carla\n")
    (md / "lanelet2_map.osm").write_text("<osm><!-- edited --></osm>")
    with pytest.raises(sampled.SampleRefused, match="not the map in use"):
        sampled.draw([{"distribution": dist.name, "n": 1, "seed": 2}], lambda x: tmp_path / x,
                     "suite", anchors=lambda d: run._anchors_for(tmp_path, d))


def _cs7_on_a_resolved_exit(tmp_path, length=30.0):
    """CS7 in a project on map town_street, its exit lane resolved (two lanelets, 7 then 8),
    bound by lane position: exit_lane = exit_n.lanelet_at($cyclist_s), exit_ls its local s."""
    import shutil
    from scensim_sampler import anchors as A
    cases = Path(scensim_sampler.__file__).resolve().parents[1] / "examples" / "cases"
    for f in ("cs7_cyclist_low_sun.xosc", "cs7_cyclist_low_sun_dist.xosc"):
        shutil.copy(cases / f, tmp_path)
    shutil.copytree(cases / "models", tmp_path / "models")
    m = tmp_path / "models" / "cs7_cyclist.yaml"
    m.write_text(m.read_text().replace("anchor.exit_n.heading", "anchor.exit_n.heading(cyclist_s)"))
    sc = tmp_path / "cs7_cyclist_low_sun.xosc"
    x = sc.read_text().replace('filepath="maps/town_street"',
                               'filepath="$(env SCENSIM_MAPS)/town_street"')
    x = x.replace('value="exit_n.lanelet"', 'value="exit_n.lanelet_at($cyclist_s)"')
    x = x.replace('<Property name="scensim.anchor.exit_lane"',
                  '<Property name="scensim.anchor.exit_ls" value="exit_n.local_s($cyclist_s)"/>'
                  '\n      <Property name="scensim.anchor.exit_lane"')
    x = x.replace('<ParameterDeclaration name="exit_lane" parameterType="string" value=""/>',
                  '<ParameterDeclaration name="exit_lane" parameterType="string" value=""/>\n'
                  '    <ParameterDeclaration name="exit_ls" parameterType="double" value="0"/>')
    x = x.replace('s="$cyclist_s" offset="$kerb_offset"', 's="$exit_ls" offset="$kerb_offset"')
    sc.write_text(x)
    md = tmp_path / "assets" / "maps" / "town_street"
    md.mkdir(parents=True)
    (md / "lanelet2_map.osm").write_text("<osm/>")
    half = length / 2
    doc = {"format": A.FORMAT, "version": A.VERSION, "map": "town_street",
           "map_sha256": A.map_digest(md), "heading_step": 0.5, "heading_max_error": 0.0,
           "anchors": {"exit_n": {"kind": "lane", "lanelets": [
               {"id": 7, "from_s": 0.0, "to_s": half}, {"id": 8, "from_s": half, "to_s": length}],
               "length": length, "speed_limit": 13.9, "start_x": 0.0, "start_y": 0.0,
               "end_x": 0.0, "end_y": length, "heading_s": [0.0, length],
               "heading": [0.25, 0.25], "heading_max_error": 0.0}}}
    (md / A.RESOLVED).write_text(json.dumps(doc))
    (tmp_path / "testbench.yaml").write_text(
        "simulator: carla\nworld:\n  anchors:\n    approach_n: {kind: lane, lanelet: 101}\n")
    return sc


def test_a_scenarios_anchor_bindings_are_set_before_ssv2_starts(tmp_path):
    """092 K9b: scensim run sets a scenario's anchor-bound parameters from the world's anchors,
    and result.json keeps them; a given value for one is refused."""
    sc = _cs7_on_a_resolved_exit(tmp_path)
    specs, _ = run.expand(sc, tmp_path, params={"cyclist_s": [20.0]})
    (s,) = specs
    assert (s.parameters["exit_lane"], s.parameters["exit_ls"]) == ("8", 5.0)
    assert s.parameters["approach_lane"] == "101"
    assert s.anchors["exit_lane"]["anchor"] == "exit_n.lanelet_at($cyclist_s)"
    assert s.anchors["exit_lane"]["source"]["map"] == "town_street"
    assert s.anchors["approach_lane"]["source"] is None             # a stated anchor
    r = results.RunResult("x", "passed", anchors=s.anchors).to_dict()
    assert results.problems(r) == []
    assert results.problems(dict(r, anchors={"exit_lane": 8})) == [
        "anchors: expected an object, {parameter: {value, anchor, source}}"]
    with pytest.raises(run.Refused, match="exit_lane is bound to the world's anchor"):
        run.expand(sc, tmp_path, params={"exit_lane": ["9"]})
    with pytest.raises(run.Refused, match=r"cs7_cyclist_low_sun.xosc: scensim.anchor.exit_l\w+: "
                                          r"anchor.exit_n: s 31.0 outside the lane"):
        run.expand(sc, tmp_path, params={"cyclist_s": [31.0]})


def test_a_record_off_its_lane_or_on_other_anchors_is_refused(tmp_path):
    """092 K9b: a sample record's bound values are checked against the world before SSv2
    starts, not replaced."""
    sc = _cs7_on_a_resolved_exit(tmp_path)
    dist = tmp_path / "cs7_cyclist_low_sun_dist.xosc"
    drawn = sampled.draw([{"distribution": dist.name, "n": 3, "seed": 2}],
                         lambda x: tmp_path / x, "suite",
                         anchors=lambda d: run._anchors_for(tmp_path, d))
    rec, scenario = drawn[0]
    good = run.sample_spec(rec, scenario)
    run.bind_anchors(good, tmp_path)
    assert good.anchors["exit_ls"]["value"] == good.parameters["exit_ls"]
    edited = json.loads(json.dumps(rec))
    edited["values"]["exit_lane"] = "99"
    with pytest.raises(run.Refused, match="the record's exit_lane is '99'"):
        run.bind_anchors(run.sample_spec(edited, scenario), tmp_path)
    off = json.loads(json.dumps(rec))
    off["values"]["cyclist_s"] = 45.0
    with pytest.raises(run.Refused, match="outside the lane"):
        run.bind_anchors(run.sample_spec(off, scenario), tmp_path)
    assert sc.is_file()


def test_ssv2s_own_distribution_of_a_bound_scenario_is_refused(tmp_path):
    _cs7_on_a_resolved_exit(tmp_path)
    dist = tmp_path / "cs7_cyclist_low_sun_dist.xosc"
    spec = run.RunSpec(dist, {}, distribution=True)
    with pytest.raises(run.Refused, match="draw it with a suite's sample: instead"):
        run.bind_anchors(spec, tmp_path)


def test_a_resolved_sources_names_the_locks_dataset_revision(tmp_path):
    """092 K9d: a record's anchor_source names the dataset and commit the map came from, when
    the project's scensim.lock holds the resolved file with the digest read; a host's own copy
    that differs names none."""
    from scensim_sampler import anchors as A
    from scensim import assets as assetsmod
    _cs7_on_a_resolved_exit(tmp_path)
    f = tmp_path / "assets" / "maps" / "town_street" / A.RESOLVED
    digest = assetsmod.sha256(f)
    commit = "c" * 40
    (tmp_path / "scensim.lock").write_text(yaml.safe_dump({"version": 1, "datasets": {
        "maps": {"repo": "someone/maps", "commit": commit, "take": ["town_street"],
                 "files": {f"town_street/{A.RESOLVED}": f"sha256:{digest}"}}}}))
    dist = tmp_path / "cs7_cyclist_low_sun_dist.xosc"
    got = run._anchors_for(tmp_path, dist)
    assert got["exit_n"]["source"]["dataset"] == "someone/maps"
    assert got["exit_n"]["source"]["commit"] == commit
    assert "source" not in got["approach_n"]                 # stated
    drawn = sampled.draw([{"distribution": dist.name, "n": 2, "seed": 2}],
                         lambda x: tmp_path / x, "suite",
                         anchors=lambda d: run._anchors_for(tmp_path, d))
    for rec, _ in drawn:
        assert rec["anchor_source"][0]["commit"] == commit
        assert scensim_sampler.check(rec) == []
        bad = dict(rec, anchor_source=[{k: v for k, v in rec["anchor_source"][0].items()
                                        if k != "commit"}])
        assert any(p.startswith("anchor_source:") for p in scensim_sampler.check(bad))
    # the host's copy differs from the lock's: no revision claimed
    (tmp_path / "scensim.lock").write_text(yaml.safe_dump({"version": 1, "datasets": {
        "maps": {"repo": "someone/maps", "commit": commit, "take": ["town_street"],
                 "files": {f"town_street/{A.RESOLVED}": "sha256:" + "0" * 64}}}}))
    assert "commit" not in run._anchors_for(tmp_path, dist)["exit_n"]["source"]


def test_testbench_check_refuses_a_binding_the_world_cannot_satisfy(tmp_path):
    """092 K9d: testbench check reads a scenario's anchor bindings against its map's resolved
    anchors and world.anchors, and refuses what no run could satisfy, naming scenario,
    binding and the world's anchors."""
    from scensim import anchors as anchorsmod
    sc = _cs7_on_a_resolved_exit(tmp_path)
    an = run._anchors_for(tmp_path, sc)
    assert anchorsmod.binding_problems(sc, an) == []
    for old, new, want in (
            ('value="exit_n.lanelet_at($cyclist_s)"', 'value="ghost.lanelet_at($cyclist_s)"',
             "the world has no such anchor (its anchors: approach_n, exit_n)"),
            ('value="approach_n.lanelet"', 'value="approach_n.lanelet_at(3)"',
             "a stated anchor has numbers only"),
            ('value="approach_n.lanelet"', 'value="exit_n.heading"',
             "is read at a lane position"),
            ('value="approach_n.lanelet"', 'value="exit_n.lanelet_at(40)"',
             "outside the lane"),
            ('value="approach_n.lanelet"', 'value="approach_n.length"',
             "no anchor attribute anchor.approach_n.length")):
        text = sc.read_text()
        sc.write_text(text.replace(old, new))
        got = anchorsmod.binding_problems(sc, an)
        assert len(got) == 1 and want in got[0][0], (new, got)
        sc.write_text(text)
    # through testbench check: a refusal on the scenario's file
    from scensim import project
    text = sc.read_text()
    sc.write_text(text.replace('value="approach_n.lanelet"', 'value="approach_n.length"'))
    s = project.read_scenario(sc)
    f = project.check_scenario(tmp_path, s, {"simulator": "carla"})
    hits = [x for x in f if "approach_n.length" in x.what]
    assert hits and hits[0].refused and hits[0].file.endswith("cs7_cyclist_low_sun.xosc")
    sc.write_text(text)
    # a resolved file of other map bytes is refused there too
    (tmp_path / "assets" / "maps" / "town_street" / "lanelet2_map.osm").write_text("<osm><x/></osm>")
    f = project.check_scenario(tmp_path, project.read_scenario(sc), {"simulator": "carla"})
    assert any("not the map in use" in x.what and x.refused for x in f)
