"""The review rounds' numbers, rebuilt from their records.

docs/AI_WORKFLOW.md's table of findings was counted from the rounds' own
records, the workflow runs' result files, which stay outside the repository. `export` writes them, anonymised, to
docs/audit/findings.csv: for each finding its wave, app, round, key and
severity, whether a probe showed it, and the sceptic's verdict and severity,
and nothing a finding said. With no argument, the tool rebuilds the table from
that file and compares it with the document's, row by row.

    py tools/audit_numbers.py                          # rebuild and compare
    py tools/audit_numbers.py export <records folder>  # write the .csv
"""
import collections
import csv
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "docs", "audit", "findings.csv")
DOC = os.path.join(ROOT, "docs", "AI_WORKFLOW.md")
FIELDS = ["wave", "app", "round", "key", "severity", "shown_by_probe", "verdict", "verdict_severity"]
WAVES = ["1", "1's lows", "3", "2", "2's lows"]
RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def wave_of(name):
    for prefix, wave in (("final-audit-wave1-", "1"), ("final-audit-lows-verify", "1's lows"),
                         ("final-audit-wave2-lows", "2's lows"), ("final-audit-wave2-", "2"),
                         ("final-audit-wave3", "3")):
        if name.startswith(prefix):
            return wave
    return None


def sides(result, name):
    """(app, reports, verdicts) for each app a run's result holds; its shape changed as the audit went on."""
    def verdicts(side):
        return (side.get("verdicts") or {}).get("verdicts") or []
    if isinstance(result, list):  # the earliest runs: one entry per app
        for side in result:
            if isinstance(side, dict):
                yield ("Phone" if str(side.get("app")).lower() in ("android", "phone") else "Desktop",
                       side.get("reports") or [], verdicts(side))
    elif isinstance(result, dict) and ("android" in result or "desktop" in result):
        for key, app in (("desktop", "Desktop"), ("android", "Phone")):
            if isinstance(result.get(key), dict):
                yield app, result[key].get("reports") or [], verdicts(result[key])
    elif isinstance(result, dict) and "reports" in result:
        app = "Phone" if name.endswith("-android") else "Desktop" if name.endswith("-desktop") else None
        yield app, result.get("reports") or [], verdicts(result)


def truthy(value):
    return value is True or str(value).strip().lower() in ("true", "yes", "1")


def export(folder):
    rows = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        run = json.load(open(path, encoding="utf-8"))
        name = run.get("workflowName", "")
        wave = wave_of(name)
        if not wave:
            continue
        for app, reports, verdicts in sides(run.get("result"), name):
            by_key = {v.get("key"): v for v in verdicts if isinstance(v, dict)}
            for report in reports:
                if not isinstance(report, dict):
                    continue
                # Some runs held both apps; each report's area says which ("w3d..." or "w3a...").
                area = str(report.get("area", ""))
                where = app or ("Phone" if area.startswith("w3a") else "Desktop")
                for finding in report.get("findings") or []:
                    if not isinstance(finding, dict) or "severity" not in finding:
                        continue
                    verdict = by_key.get(finding.get("key")) or {}
                    rows.append({"wave": wave, "app": where, "round": name, "key": str(finding.get("key", "")),
                                 "severity": str(finding["severity"]).lower(),
                                 "shown_by_probe": "yes" if truthy(finding.get("reproduced"))
                                 or truthy(finding.get("proved")) else "no",
                                 "verdict": str(verdict.get("verdict", "")),
                                 "verdict_severity": str(verdict.get("severity", "")).lower()})
    text = "\n".join(",".join(r.values()) for r in rows)
    if re.search(r"adas9|@gmail|Users\\", text, re.I):
        sys.exit("audit_numbers: a private word would be written; nothing was")
    with open(CSV, "w", encoding="utf-8", newline="\n") as f:
        out = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        out.writeheader()
        out.writerows(rows)
    print("wrote", len(rows), "findings to", os.path.relpath(CSV, ROOT))


def rebuilt():
    table = collections.OrderedDict(((w, a), collections.Counter()) for w in WAVES for a in ("Desktop", "Phone"))
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        t = table[(r["wave"], r["app"])]
        sev = r["severity"]
        t["all"] += 1
        t["high"] += sev in ("high", "critical")
        t["medium"] += sev == "medium"
        t["low"] += sev == "low"
        t["probe"] += r["shown_by_probe"] == "yes"
        verdict = r["verdict"]
        if verdict:
            t["graded"] += 1
            kept = verdict in ("confirmed", "plausible")
            t["kept"] += kept
            t["twice"] += verdict == "duplicate"
            # "already-decided": refuted by one of the owner's decisions.
            t["refuted"] += verdict in ("refuted", "already-decided")
            # Lowered: kept, at a lower severity than the agent gave it.
            t["lowered"] += kept and RANK.get(r["verdict_severity"], 9) < RANK.get(sev, 0)
    return table


def main():
    if sys.argv[1:2] == ["export"] and len(sys.argv) == 3:
        return export(sys.argv[2])
    table = rebuilt()
    doc = open(DOC, encoding="utf-8").read()
    row = re.compile(r"^\| (1|1's lows|3|2|2's lows) \| (Desktop|Phone) \| (\d[\d,]*) \((\d+) / (\d+) / (\d+)\) \| "
                     r"(\d+) \| (\d+): (\d+) / (\d+) / (\d+) / (\d+) \|$", re.M)
    found = {(m[0], m[1]): [int(x.replace(",", "")) for x in m[2:]] for m in row.findall(doc)}
    bad = 0
    for (wave, app), t in table.items():
        ours = [t["all"], t["high"], t["medium"], t["low"], t["probe"], t["graded"], t["kept"], t["twice"],
                t["refuted"], t["lowered"]]
        theirs = found.get((wave, app))
        mark = "agrees" if theirs == ours else "DIFFERS"
        bad += theirs != ours
        print(f"{wave:9} {app:7} {ours[0]:4} ({ours[1]} / {ours[2]} / {ours[3]}) probe {ours[4]:4} "
              f"graded {ours[5]}: {ours[6]} / {ours[7]} / {ours[8]} / {ours[9]}   {mark}"
              + ("" if theirs == ours else f"  (the document: {theirs})"))
    total = sum(t["all"] for t in table.values())
    print(f"{total} findings rebuilt from {os.path.relpath(CSV, ROOT)};",
          "the document's table agrees" if not bad and len(found) == len(table) else
          f"{bad} row(s) differ, {len(table) - len(found)} not found in the document")
    sys.exit(1 if bad or len(found) != len(table) else 0)


main()
