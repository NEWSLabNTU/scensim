"""Judges: named, versioned programs run over a finished run's directory.

docs/design/projects-and-pilots.md, "Results". A project lists them in ``testbench.yaml``::

    judges:
      - name: comfort                    # judges/comfort.json
        run: [python3, -m, my_judges.comfort]
        version: "1"                     # recorded with the output
        on: [passed, failed]             # verdicts it runs for (default: passed, failed)
        timeout: 120                     # s
        needs: [gap_trace]               # what the stack must record for it (below)
        reads: [coop_a.jsonl]            # the run's files it reads, kept with the logs (below)

A judge is given the run directory as its last argument, or where ``{run_dir}`` stands in
``run`` (``{scenario}``: the run's scenario file; either one means nothing is appended), and
as ``SCENSIM_RUN_DIR``. It runs in the project directory and prints one JSON object on stdout, or
nothing in particular: then its exit code (0 passed, 1 failed) is its verdict and its last
line the message. scensim writes the record, with the judge's name, version, exit code and
duration, to ``judges/<name>.json``. A ``verdict`` key in it
(``passed`` or ``failed``) is the judge's own verdict; it is recorded beside the run's, never in
place of it: scoring stays with the judges, and a third-party evaluator reads the same files.
``needs`` names what the judge reads that a stack records only on request: ``gap_trace``
turns the bridge's gap trace on for the project's stack (as ``logging.gap_trace: true``), each
run's in ``gap_trace/`` (scensim.episodes; ``python3 -m scensim.gap`` runs gap_oracle and
incident_judge as judges); ``context`` records SSv2's storyboard state changes for each run, in
``context.jsonl`` (scensim.context; incident_judge's ``--context``). ``reads`` names the files of the
run directory the judge reads that no level keeps by name (a pilot's own log, say): paths or globs
relative to the run directory. Wherever a run keeps its logs (``standard`` and up), it keeps them
too (issue 080: s5's judge read ``coop_a.jsonl``, which only ``debug`` kept).

A judge that exits other than 0 or 1, prints JSON that is not an object, or overruns records
``verdict: error`` with the reason; the run itself is unaffected.

**The contact judge is the exception** (issue 189). ``physical_verdict`` (roadmap 021) runs in
every project, unlisted, and **before** the verdict: wherever the run directory holds the
bridge's contact reports (``contacts/``), it adds its ``carla_contact`` testcase to the run's
``junit.xml``. An undeclared contact with an actor, at any impulse, or with the static world
above ``CONTACT_FLOOR`` (N*s), fails the run as any JUnit failure does, its first line the
reason: ``UndeclaredContact: 'ped' (pedestrian) 5470.5 N*s (static floor 10 N*s): ...``. A run
the stack collected no report for is an error (NoContactReport); a world that reports none
(``contact_report_dir`` off or the user's) leaves the run unjudged, with a WARN on its line. A scenario that means to touch declares it (``csbExpectedContacts``);
a project lists the judge only to change it::

    judges:
      - name: physical_verdict            # its own arguments in place of the default's
        run: [ros2, run, scensim_launch, physical_verdict, "{run_dir}/junit.xml",
              --scenario, "{run_dir}/scenario.xosc", --min-impulse, "50"]
      - name: physical_verdict            # or: off, by name, and only with a reason
        off: true
        why: "drives over rocks on purpose; judged by its own oracle"

Either way it runs once, before the verdict. ``off`` and ``why`` are refused on any other judge,
and ``on``, ``needs`` and ``timeout`` on this one.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import yaml

from scensim import results

DEFAULT_ON = (results.PASSED, results.FAILED)
DEFAULT_TIMEOUT = 120.0
KEYS = ("name", "run", "version", "on", "timeout", "needs", "reads", "off", "why")
CONTACT = "physical_verdict"
CONTACT_FLOOR = 10.0   # N*s, the static world's only; issue 189's calibration (Isaac, CARLA)
CONTACT_REFUSED = ("on", "needs", "timeout")   # it always runs, before the verdict
CONTACT_DEFAULT = {
    "name": CONTACT, "version": "default",
    "run": ["ros2", "run", "scensim_launch", "physical_verdict", "{run_dir}/junit.xml",
            "--scenario", "{run_dir}/scenario.xosc", "--min-impulse", f"{CONTACT_FLOOR:g}"],
}
NEEDS = ("gap_trace", "context")
JUDGE_VERDICTS = (results.PASSED, results.FAILED, results.ERROR)


def problems(judges) -> list:
    """Every way a project's ``judges:`` list is wrong, as ``(where, message)``."""
    if judges is None:
        return []
    if not isinstance(judges, list):
        return [("judges", "is not a list")]
    out, names = [], set()
    for i, j in enumerate(judges):
        w = f"judges[{i}]"
        if not isinstance(j, dict):
            out.append((w, "is not a mapping: {name: ..., run: [...]}"))
            continue
        for k in j:
            if k not in KEYS:
                out.append((w, f"unknown key {k} (use only {', '.join(KEYS)})"))
        name = j.get("name")
        if not (isinstance(name, str) and name and "/" not in name and not name.startswith(".")):
            out.append((w, "name: a plain file name is required"))
        elif name in names:
            out.append((w, f"name: {name} twice"))
        else:
            names.add(name)
        off, why = j.get("off"), j.get("why")
        if ("off" in j or "why" in j) and name != CONTACT:
            out.append((w, f"off/why: only the contact judge ({CONTACT}) is on by default "
                           "and can be turned off"))
        elif "off" in j and off is not True:
            out.append((w, "off: true, or leave it out"))
        elif off is True and not (isinstance(why, str) and why.strip()):
            out.append((w, f"why: turning {CONTACT} off needs a reason (issue 189)"))
        elif "why" in j and off is not True:
            out.append((w, "why: goes with off: true"))
        if name == CONTACT:
            # it runs before the verdict, on every run with a report: nothing to schedule
            for k in CONTACT_REFUSED:
                if k in j:
                    out.append((w, f"{k}: not for the contact judge, which always runs, before "
                                   "the verdict (issue 189)"))
        if off is True and name == CONTACT:
            for k in j:
                if k not in ("name", "off", "why") and k not in CONTACT_REFUSED:
                    out.append((w, f"{k}: an entry that turns the judge off takes only name, "
                                   "off and why"))
            continue
        run = j.get("run")
        if not (isinstance(run, list) and run and all(isinstance(a, (str, int, float))
                                                      for a in run)):
            out.append((w, "run: a non-empty list of arguments is required"))
        on = j.get("on")
        bad_on = on is not None and (not isinstance(on, list)
                                     or any(v not in results.VERDICTS for v in on))
        if bad_on:
            out.append((w, f"on: a list of verdicts ({', '.join(results.VERDICTS)})"))
        needs = j.get("needs")
        if needs is not None and (not isinstance(needs, list)
                                  or any(n not in NEEDS for n in needs)):
            out.append((w, f"needs: a list of {', '.join(NEEDS)}"))
        reads = j.get("reads")
        if reads is not None and (not isinstance(reads, list) or not all(_relative(r) for r in reads)):
            out.append((w, "reads: a list of paths or globs relative to the run directory"))
        t = j.get("timeout")
        if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float)) or t <= 0):
            out.append((w, "timeout: a positive number of seconds"))
    return out


def contact_judge(judges):
    """``(judge, why_off)``: the contact judge a project runs before the verdict, the
    default unless it lists its own; ``(None, why)`` when it turns it off."""
    for j in judges if isinstance(judges, list) else []:
        if isinstance(j, dict) and j.get("name") == CONTACT:
            if j.get("off") is True:
                return None, str(j.get("why") or "").strip()
            return j, ""
    return dict(CONTACT_DEFAULT), ""


def after_verdict(judges) -> list:
    """The project's judges that run after the verdict: every one but the contact judge."""
    return [j for j in judges if not (isinstance(j, dict) and j.get("name") == CONTACT)] \
        if isinstance(judges, list) else []


def run_contact(judges, run_dir: Path, project: Path, reporting: bool = True, env=None):
    """The contact judge over ``run_dir``, before the verdict (issue 189): its record, or
    None when it did not run. ``reporting``: the stack collects the bridge's contact reports
    for each run (the world's ``contact_report_dir`` unset). Then a run without a report is
    still judged, and physical_verdict's NoContactReport makes it an error: a bridge that
    failed to report cannot hide a hit. It does not run when the project turned it off by name,
    when the world reports nothing scensim can read (``contact_report_dir`` off or the user's;
    the record has ``warn: true``, and the run's line says so), or without a ``junit.xml``.
    Those are written to ``judges/<name>.json`` with ``verdict: off`` and why."""
    run_dir = Path(run_dir)
    j, why_off = contact_judge(judges)
    warn = j is not None and not reporting
    why = (f"off in testbench.yaml: {why_off}" if j is None else
           "not judged: the world's contact_report_dir is off or the user's, so scensim has "
           "no contact report for the run" if warn else
           "no junit.xml" if not (run_dir / "junit.xml").is_file() else "")
    if why:
        out = run_dir / "judges"
        out.mkdir(exist_ok=True)
        rec = {"name": CONTACT, "version": "", "verdict": "off", "message": why}
        if warn:
            rec["warn"] = True
        (out / f"{CONTACT}.json").write_text(json.dumps(rec, indent=2) + "\n")
        _timeline(run_dir, rec)
        return None
    rec = run_one(j, run_dir, project, env)
    _timeline(run_dir, rec)
    return rec


def needed(judges) -> set:
    """What the project's judges need recorded (``needs:``)."""
    out = set()
    for j in judges if isinstance(judges, list) else []:
        if isinstance(j, dict) and isinstance(j.get("needs"), list):
            out |= {n for n in j["needs"] if n in NEEDS}
    return out


def _relative(r) -> bool:
    return (isinstance(r, str) and bool(r.strip("/")) and not r.startswith(("/", "~"))
            and ".." not in Path(r).parts)


def read_files(judges) -> list:
    """The run directory's paths or globs the project's judges read (``reads:``)."""
    out = []
    for j in judges if isinstance(judges, list) else []:
        if isinstance(j, dict) and isinstance(j.get("reads"), list):
            out += [r for r in j["reads"] if _relative(r) and r not in out]
    return out


def _record(j, verdict, message="", code=None, started=None, data=None) -> dict:
    out = dict(data or {})
    out.update(name=j["name"], version=str(j.get("version") or ""), verdict=verdict,
               exit_code=code,
               duration_s=round(time.time() - started, 3) if started is not None else None)
    if message:
        out["message"] = message
    return out


def run_one(j: dict, run_dir: Path, project: Path, env=None) -> dict:
    """Run one judge over ``run_dir``; its record (also written to ``judges/<name>.json``)."""
    run_dir = Path(run_dir)
    sub = {"run_dir": str(run_dir), "scenario": _scenario_path(run_dir)}
    argv = [str(a) for a in j["run"]]
    if any("{run_dir}" in a or "{scenario}" in a for a in argv):
        argv = [_substitute(a, sub) for a in argv]
    else:
        argv.append(str(run_dir))
    e = dict(os.environ if env is None else env)
    e["SCENSIM_RUN_DIR"] = str(run_dir)
    started = time.time()
    try:
        p = subprocess.run(argv, cwd=str(project), env=e, capture_output=True, text=True,
                           timeout=float(j.get("timeout") or DEFAULT_TIMEOUT))
    except subprocess.TimeoutExpired:
        limit = j.get("timeout") or DEFAULT_TIMEOUT
        rec = _record(j, results.ERROR, f"did not end within {limit} s", started=started)
    except OSError as ex:
        rec = _record(j, results.ERROR, f"did not start: {ex}", started=started)
    else:
        data, message = None, ""
        try:
            data = json.loads(p.stdout)
            if not isinstance(data, dict):
                data, message = None, "printed JSON that is not an object"
        except json.JSONDecodeError:
            pass
        if p.returncode not in (0, 1):
            tail = (p.stderr or "").strip().splitlines()[-1:] or [""]
            rec = _record(j, results.ERROR, f"exit {p.returncode}: {tail[0][:200]}".rstrip(": "),
                          p.returncode, started, data)
        elif data is None:
            # a plain program (no JSON): its exit code is its verdict, its last line the message
            last = (p.stdout or "").strip().splitlines()[-1:] or [""]
            v = results.PASSED if p.returncode == 0 else results.FAILED
            if message:
                v = results.ERROR
            rec = _record(j, v, message or last[0][:300], p.returncode, started)
        else:
            v = data.get("verdict")
            if v is None:
                v = results.PASSED if p.returncode == 0 else results.FAILED
            elif v not in JUDGE_VERDICTS:
                v, message = results.ERROR, f"verdict {data.get('verdict')!r} is not a verdict"
            rec = _record(j, v, message or data.get("message", ""), p.returncode, started, data)
        if p.stderr:
            log = run_dir / "logs" / "judge"
            log.mkdir(parents=True, exist_ok=True)
            (log / f"{j['name']}.log").write_text(p.stderr)
    out = run_dir / "judges"
    out.mkdir(exist_ok=True)
    (out / f"{j['name']}.json").write_text(json.dumps(rec, indent=2) + "\n")
    return rec


def _scenario_path(run_dir: Path) -> str:
    """The run's scenario file, from its ``resolved.yaml``; empty when there is none."""
    try:
        r = yaml.safe_load((Path(run_dir) / "resolved.yaml").read_text()) or {}
        return str((r.get("scenario") or {}).get("path") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def _substitute(arg: str, sub: dict) -> str:
    for k, v in sub.items():
        arg = arg.replace("{" + k + "}", v)
    return arg


def run_all(judges, run_dir: Path, project: Path, verdict: str, env=None) -> list:
    """Every judge that runs for ``verdict``, in order; their records. Each also lands in the
    run's timeline as a ``judge`` event."""
    recs = []
    for j in judges or []:
        if verdict not in (j.get("on") or DEFAULT_ON):
            continue
        rec = run_one(j, run_dir, project, env)
        recs.append(rec)
        _timeline(run_dir, rec)
    return recs


def _timeline(run_dir: Path, rec: dict):
    tl = Path(run_dir) / "timeline.jsonl"
    ev = {"t_wall": time.time(), "t_sim": None, "group": "judge", "event": "judge.end",
          "judge": rec["name"], "verdict": rec["verdict"]}
    if rec.get("message"):
        ev["message"] = rec["message"]
    with tl.open("a") as f:
        f.write(json.dumps(ev) + "\n")


def contact_warning(run_dir: Path) -> str:
    """The run's line's WARN when the contact judge could not judge it (issue 189), else ""."""
    try:
        rec = json.loads((Path(run_dir) / "judges" / f"{CONTACT}.json").read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    return f"WARN {CONTACT}: {rec.get('message', '')}" if rec.get("warn") else ""


def summary(run_dir: Path) -> dict:
    """``{name: verdict}`` of the judges a run directory holds."""
    d = Path(run_dir) / "judges"
    out = {}
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                out[p.stem] = json.loads(p.read_text()).get("verdict")
            except (OSError, json.JSONDecodeError):
                out[p.stem] = results.ERROR
    return out
