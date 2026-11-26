import json
import sys

from scensim import budget, judges


def judge(tmp_path, body, name="j", **kw):
    script = tmp_path / f"{name}.py"
    script.write_text(body)
    return {"name": name, "run": [sys.executable, str(script)], **kw}


def run_dir(tmp_path):
    d = tmp_path / "run"
    (d / "logs").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"verdict": "passed"}))
    (d / "timeline.jsonl").write_text("")
    return d


def test_problems():
    assert judges.problems(None) == []
    assert judges.problems({}) == [("judges", "is not a list")]
    bad = judges.problems([{"name": "a/b", "run": [], "on": ["maybe"], "timeout": 0, "x": 1},
                           {"name": "ok", "run": ["true"]}, {"name": "ok", "run": ["true"]}])
    msgs = " | ".join(m for _, m in bad)
    for part in ("unknown key x", "name: a plain", "run: a non-empty", "on: a list",
                 "timeout: a positive", "name: ok twice"):
        assert part in msgs


def test_reads_names_the_run_files_a_judge_reads():
    """Issue 080: `reads:` is a list of paths or globs relative to the run directory."""
    ok = [{"name": "s5", "run": ["true"], "reads": ["coop_a.jsonl", "out/*.csv"]},
          {"name": "g", "run": ["true"], "reads": ["coop_a.jsonl", "b.txt"]}]
    assert judges.problems(ok) == []
    assert judges.read_files(ok) == ["coop_a.jsonl", "out/*.csv", "b.txt"]
    for bad in ("coop_a.jsonl", ["/abs.jsonl"], ["../up.jsonl"], ["~/x"], [""], [3]):
        msgs = [m for _, m in judges.problems([{"name": "j", "run": ["true"], "reads": bad}])]
        assert msgs == ["reads: a list of paths or globs relative to the run directory"], bad
    assert judges.read_files(None) == [] and judges.read_files([{"name": "j"}]) == []


def test_judge_output_recorded(tmp_path):
    d = run_dir(tmp_path)
    j = judge(tmp_path, "import json, sys, os\n"
              "r = json.load(open(sys.argv[1] + '/result.json'))\n"
              "assert os.environ['SCENSIM_RUN_DIR'] == sys.argv[1]\n"
              "print(json.dumps({'jerk_max': 1.5, 'seen': r['verdict']}))\n", version=3)
    rec = judges.run_one(j, d, tmp_path)
    assert rec["verdict"] == "passed" and rec["version"] == "3" and rec["seen"] == "passed"
    assert json.loads((d / "judges" / "j.json").read_text())["jerk_max"] == 1.5


def test_judge_verdicts(tmp_path):
    d = run_dir(tmp_path)
    fail = judge(tmp_path, "import sys; print('{\"why\": 1}'); sys.exit(1)", "f")
    assert judges.run_one(fail, d, tmp_path)["verdict"] == "failed"
    own = judge(tmp_path, "print('{\"verdict\": \"failed\", \"message\": \"too fast\"}')", "o")
    r = judges.run_one(own, d, tmp_path)
    assert r["verdict"] == "failed" and r["message"] == "too fast"
    crash = judge(tmp_path, "import sys; sys.stderr.write('boom\\n'); sys.exit(4)", "c")
    r = judges.run_one(crash, d, tmp_path)
    assert r["verdict"] == "error" and "exit 4: boom" in r["message"]
    assert (d / "logs" / "judge" / "c.log").read_text() == "boom\n"
    plain = judge(tmp_path, "import sys; print('one contact'); sys.exit(1)", "s")
    r = judges.run_one(plain, d, tmp_path)
    assert r["verdict"] == "failed" and r["message"] == "one contact"
    (d / "resolved.yaml").write_text("scenario: {path: /p/s.xosc}\n")
    sub = judge(tmp_path, "import sys, json; print(json.dumps({'a': sys.argv[1:]}))", "u")
    sub["run"] += ["{run_dir}/junit.xml", "--scenario", "{scenario}"]
    assert judges.run_one(sub, d, tmp_path)["a"] == [f"{d}/junit.xml", "--scenario", "/p/s.xosc"]
    slow = judge(tmp_path, "import time; time.sleep(5)", "t", timeout=0.2)
    assert "did not end" in judges.run_one(slow, d, tmp_path)["message"]
    assert judges.summary(d) == {"c": "error", "f": "failed", "o": "failed", "s": "failed",
                                 "t": "error", "u": "passed"}


def test_run_all_filters_by_verdict_and_appends_timeline(tmp_path):
    d = run_dir(tmp_path)
    a = judge(tmp_path, "print('{}')", "a")
    b = judge(tmp_path, "print('{}')", "b", on=["error"])
    recs = judges.run_all([a, b], d, tmp_path, "passed")
    assert [r["name"] for r in recs] == ["a"]
    ev = [json.loads(x) for x in (d / "timeline.jsonl").read_text().splitlines()]
    assert ev[0]["group"] == "judge" and ev[0]["judge"] == "a"


def test_budget_sizes():
    assert budget.parse_size("2GB") == 2 * 1024 ** 3
    assert budget.parse_size("1.5 mb") == int(1.5 * 1024 ** 2)
    assert budget.parse_size(10) == 10
    for bad in ("lots", "-1", True, "2PB"):
        try:
            budget.parse_size(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert budget.problems({"per_run": "x", "max": 1}) == [
        "unknown key max (use only per_run, total)", "per_run: 'x' is not a size (e.g. 500MB, 2GB)"]


def test_budget_check(tmp_path):
    b = {"per_run": "1GB", "total": "10GB"}
    assert budget.check(None, 5, tmp_path) == ""
    assert budget.check(b, 5, tmp_path, free=100 * 1024 ** 3, used=0) == ""
    assert "is free under" in budget.check(b, 5, tmp_path, free=2 * 1024 ** 3, used=0)
    assert "of logging.budget.total" in budget.check(b, 5, tmp_path, free=10 ** 13,
                                                     used=6 * 1024 ** 3)
    (tmp_path / "r1").mkdir()
    (tmp_path / "r1" / "f").write_bytes(b"x" * 1000)
    (tmp_path / "link").symlink_to(tmp_path / "r1")
    assert budget.dir_size(tmp_path) == 1000


# --- issue 189: the contact judge, on by default and before the verdict -------------------

def test_the_contact_judge_is_off_only_by_name_and_with_a_reason():
    ok = [{"name": "physical_verdict", "off": True, "why": "drives over rocks on purpose"}]
    assert judges.problems(ok) == []
    assert judges.contact_judge(ok) == (None, "drives over rocks on purpose")
    for bad, part in (
            ([{"name": "physical_verdict", "off": True}], "needs a reason"),
            ([{"name": "physical_verdict", "off": True, "why": "  "}], "needs a reason"),
            ([{"name": "comfort", "off": True, "why": "x"}], "only the contact judge"),
            ([{"name": "comfort", "run": ["true"], "why": "x"}], "only the contact judge"),
            ([{"name": "physical_verdict", "off": "yes", "why": "x"}], "off: true"),
            ([{"name": "physical_verdict", "run": ["true"], "why": "x"}], "goes with off"),
            ([{"name": "physical_verdict", "off": True, "why": "x", "run": ["true"]}],
             "runs nothing")):
        msgs = " | ".join(m for _, m in judges.problems(bad))
        assert part in msgs, (bad, msgs)


def test_the_default_contact_judge_and_a_listed_one_replacing_it():
    j, why = judges.contact_judge(None)
    assert why == "" and j["name"] == "physical_verdict"
    assert j["run"][-2:] == ["--min-impulse", "10"]
    assert "{run_dir}/scenario.xosc" in j["run"]
    own = {"name": "physical_verdict", "run": ["true"]}
    other = {"name": "comfort", "run": ["true"]}
    assert judges.contact_judge([other, own]) == (own, "")
    assert judges.after_verdict([other, own]) == [other]   # it runs once, before the verdict


def contact_run(tmp_path, report=True):
    d = run_dir(tmp_path)
    (d / "junit.xml").write_text('<testsuites><testsuite name="s" tests="1"><testcase '
                                 'name="sc"/></testsuite></testsuites>')
    (d / "contacts").mkdir()
    if report:
        (d / "contacts" / "r_e1.json").write_text("{}")
    return d


FAILS_THE_JUNIT = """import sys, xml.etree.ElementTree as ET
p = sys.argv[1] + "/junit.xml"
t = ET.parse(p); s = t.getroot().find("testsuite")
c = ET.SubElement(s, "testcase", name="carla_contact")
ET.SubElement(c, "failure", type="UndeclaredContact",
              message="'ped' (pedestrian) 5470.5 N*s (floor 10 N*s): 1 contact(s)")
t.write(p)
print("[physical_verdict] carla_contact: FAILURE")
sys.exit(1)
"""


def test_an_undeclared_contact_fails_the_run_naming_it(tmp_path):
    from scensim import results  # noqa: PLC0415
    d = contact_run(tmp_path)
    pv = judge(tmp_path, FAILS_THE_JUNIT, name="physical_verdict")
    rec = judges.run_contact([pv], d, tmp_path)
    assert rec["verdict"] == "failed"
    assert json.loads((d / "judges" / "physical_verdict.json").read_text())["verdict"] == "failed"
    verdict, reason = results.verdict_from(d / "junit.xml")
    assert verdict == "failed"
    assert reason.startswith("UndeclaredContact: 'ped' (pedestrian) 5470.5 N*s (floor 10 N*s)")


def test_the_contact_judge_off_or_without_a_report_records_why(tmp_path):
    d = contact_run(tmp_path, report=False)
    pv = judge(tmp_path, FAILS_THE_JUNIT, name="physical_verdict")
    assert judges.run_contact([pv], d, tmp_path) is None
    rec = json.loads((d / "judges" / "physical_verdict.json").read_text())
    assert rec["verdict"] == "off" and "no contact report" in rec["message"]
    assert "carla_contact" not in (d / "junit.xml").read_text()
    d2 = contact_run(tmp_path / "b")
    off = [{"name": "physical_verdict", "off": True, "why": "its own oracle"}]
    assert judges.run_contact(off, d2, tmp_path) is None
    rec = json.loads((d2 / "judges" / "physical_verdict.json").read_text())
    assert rec == {"name": "physical_verdict", "version": "", "verdict": "off",
                   "message": "off in testbench.yaml: its own oracle"}
