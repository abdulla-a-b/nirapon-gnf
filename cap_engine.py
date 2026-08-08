#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cap_engine.py — analytics and reporting for the GNF CAP Board
=============================================================================
Reads seed_data.json (the 101 findings) plus an optional progress export from
the board, and produces:

  stats     a console summary for a quick check
  report    a standalone HTML status report for the Steering Committee pack
  csv       a flat register with progress merged in
  digest    a short plain-text digest suitable for pasting into an email

Usage
-----
    python3 cap_engine.py stats
    python3 cap_engine.py report  --progress GNF_CAP_progress_2026-08-07.json
    python3 cap_engine.py csv     --progress progress.json --out register.csv
    python3 cap_engine.py digest  --progress progress.json

The progress file is what the board's "Download progress (JSON)" button gives
you. Without it the engine reports the opening position: nothing started.

No third-party packages required.
=============================================================================
"""

import argparse, csv, datetime, html, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, "seed_data.json")
GATES = ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g10"]
SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2}


# ----------------------------------------------------------------- loading
def load(seed_path=SEED, progress_path=None):
    with open(seed_path, encoding="utf-8") as f:
        data = json.load(f)
    progress = {"findings": {}, "roles": {}}
    if progress_path:
        with open(progress_path, encoding="utf-8") as f:
            progress = json.load(f)
    progress.setdefault("findings", {})
    progress.setdefault("roles", {})
    return data, progress


def record(progress, fid):
    return progress["findings"].get(fid, {})


def gate_score(rec):
    g = rec.get("gates", {}) or {}
    done = sum(1 for k in GATES if g.get(k) == "Y")
    na = sum(1 for k in GATES if g.get(k) == "NA")
    applicable = max(1, len(GATES) - na)
    return done, na, applicable, done / applicable


def is_closed(rec):
    return rec.get("status") == "Closed - Verified"


def days_to(iso, today):
    return (datetime.date.fromisoformat(iso) - today).days


# ----------------------------------------------------------------- analytics
def analyse(data, progress, today=None):
    today = today or datetime.date.today()
    findings = data["findings"]
    out = {
        "today": today,
        "total": len(findings),
        "closed": 0,
        "overdue": [],
        "due_soon": [],
        "open_high": 0,
        "completion": 0.0,
        "by_status": Counter(),
        "by_area": defaultdict(lambda: {"High": 0, "Medium": 0, "Low": 0, "total": 0, "closed": 0, "score": 0.0}),
        "by_wave": defaultdict(lambda: {"total": 0, "closed": 0, "score": 0.0}),
        "by_theme": defaultdict(lambda: {"total": 0, "high": 0, "closed": 0, "name": ""}),
        "by_owner": defaultdict(lambda: {"total": 0, "closed": 0}),
        "gate_block": Counter(),
        "deliverables": [],
    }
    running = 0.0
    for f in findings:
        rec = record(progress, f["id"])
        _, _, _, pct = gate_score(rec)
        closed = is_closed(rec)
        status = rec.get("status", "Not Started")
        out["by_status"][status] += 1
        running += 1.0 if closed else pct
        if closed:
            out["closed"] += 1
        if f["severity"] == "High" and not closed:
            out["open_high"] += 1

        d = days_to(f["target"], today)
        if not closed and status != "Deferred - Justified":
            if d < 0:
                out["overdue"].append((f, d))
            elif d <= 14:
                out["due_soon"].append((f, d))

        a = out["by_area"][f["area"]]
        a[f["severity"]] += 1
        a["total"] += 1
        a["score"] += 1.0 if closed else pct
        if closed:
            a["closed"] += 1

        w = out["by_wave"][f["wave"]]
        w["total"] += 1
        w["score"] += 1.0 if closed else pct
        if closed:
            w["closed"] += 1

        t = out["by_theme"][f["theme"]]
        t["total"] += 1
        t["name"] = f["themeName"]
        if f["severity"] == "High":
            t["high"] += 1
        if closed:
            t["closed"] += 1

        o = out["by_owner"][f["owner"]]
        o["total"] += 1
        if closed:
            o["closed"] += 1

        # which gate is the first one blocking, for open findings
        if not closed:
            g = rec.get("gates", {}) or {}
            for i, k in enumerate(GATES):
                if g.get(k) not in ("Y", "NA"):
                    out["gate_block"][data["gates"][i]["label"]] += 1
                    break

    out["completion"] = running / max(1, out["total"])
    out["overdue"].sort(key=lambda x: x[1])
    out["due_soon"].sort(key=lambda x: x[1])

    for d in data["deliverables"]:
        done = sum(1 for fid in d["closes"] if is_closed(record(progress, fid)))
        out["deliverables"].append({**d, "done": done, "pct": done / max(1, len(d["closes"]))})

    return out


# ----------------------------------------------------------------- console
def cmd_stats(data, progress, args):
    a = analyse(data, progress)
    m = data["meta"]
    line = "=" * 74
    print(line)
    print(f"  {m['factory']}")
    print(f"  {m['scope']}")
    print(f"  {m['reportRef']} · {m['factoryId']} · assessed {m['assessment']}")
    print(f"  Status as at {a['today'].strftime('%d %B %Y')}")
    print(line)
    print(f"  Non-conformities      {a['total']}")
    print(f"  Closed and verified   {a['closed']}  ({a['closed'] / a['total'] * 100:.0f}%)")
    print(f"  CAP completion        {a['completion'] * 100:.1f}%  (measured across the ten gates)")
    print(f"  High severity open    {a['open_high']}")
    print(f"  Past target date      {len(a['overdue'])}")
    print(f"  Due within 14 days    {len(a['due_soon'])}")
    print(line)
    print("  BY AREA")
    for area, x in sorted(a["by_area"].items(), key=lambda kv: -kv[1]["total"]):
        bar = "#" * int(x["score"] / x["total"] * 28)
        print(f"    {area:<20} {x['total']:>3}  H{x['High']:<3}M{x['Medium']:<3}L{x['Low']:<3}  "
              f"{x['score'] / x['total'] * 100:>5.1f}%  {bar}")
    print(line)
    print("  ROOT-CAUSE THEMES")
    for code, x in sorted(a["by_theme"].items(), key=lambda kv: -kv[1]["total"]):
        print(f"    {code:<4} {x['name'][:46]:<46} {x['total']:>3} findings  {x['high']:>2} high")
    print(line)
    if a["overdue"]:
        print("  PAST TARGET DATE")
        for f, d in a["overdue"][:15]:
            print(f"    {f['id']:<9} {f['severity']:<7} {abs(d):>4}d late  {f['requirement'][:44]}")
        if len(a["overdue"]) > 15:
            print(f"    … and {len(a['overdue']) - 15} more")
        print(line)
    if a["gate_block"]:
        print("  FIRST BLOCKING GATE (open findings)")
        for g, n in a["gate_block"].most_common():
            print(f"    {n:>4}  {g}")
        print(line)


# ----------------------------------------------------------------- html report
CSS = """
:root{--ink:#0E1D2E;--navy:#12324F;--green:#1B6B4A;--green2:#28936A;--sheet:#E4E9ED;
--rule:#C6D1DA;--muted:#5E7183;--high:#B3261E;--med:#B26A00}
*{box-sizing:border-box}
body{margin:0;font:14px/1.55 "IBM Plex Sans",system-ui,sans-serif;color:var(--ink);background:#fff}
.page{max-width:940px;margin:0 auto;padding:34px 30px 60px}
h1,h2,h3{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;margin:0}
.hd{background:var(--navy);color:#fff;padding:22px 30px;border-bottom:3px solid var(--green2)}
.hd .eyebrow{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.16em;
text-transform:uppercase;color:#8FC4AE}
.hd h1{font-size:24px;margin:5px 0 4px}
.hd p{margin:0;font-size:12.5px;color:#A8BECE}
h2{font-size:17px;margin:30px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--navy)}
h3{font-size:14px;margin:20px 0 8px;color:var(--green)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}
.kpi{border:1px solid var(--rule);border-left:3px solid var(--navy);padding:12px 14px;border-radius:3px}
.kpi.warn{border-left-color:var(--med)}.kpi.bad{border-left-color:var(--high)}.kpi.good{border-left-color:var(--green2)}
.kpi dt{font-family:"IBM Plex Mono",monospace;font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.kpi dd{margin:6px 0 0;font-family:"IBM Plex Sans Condensed",sans-serif;font-size:30px;font-weight:600;line-height:1}
.kpi small{display:block;margin-top:5px;font-size:11px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:12px;margin:10px 0 4px}
th{background:var(--navy);color:#fff;text-align:left;padding:7px 9px;font-size:11px;
font-family:"IBM Plex Sans Condensed",sans-serif;text-transform:uppercase;letter-spacing:.03em}
td{padding:7px 9px;border-bottom:1px solid #E4EAEF;vertical-align:top}
tr:nth-child(even) td{background:#F7FAFC}
.mono{font-family:"IBM Plex Mono",monospace;font-size:11px}
.pill{font-family:"IBM Plex Mono",monospace;font-size:9.5px;padding:2px 6px;border-radius:2px;text-transform:uppercase}
.p-High{background:#FBE9E7;color:var(--high)}.p-Medium{background:#FDF2E0;color:var(--med)}
.p-Low{background:#E4F1EA;color:var(--green)}
.bar{height:13px;background:var(--sheet);border-radius:2px;overflow:hidden;border:1px solid #DCE4EA}
.bar i{display:block;height:100%;background:var(--green2)}
.late{color:var(--high);font-weight:600}
.foot{margin-top:34px;padding-top:14px;border-top:1px solid var(--rule);font-size:11px;color:var(--muted)}
@media print{.page{padding:0 0 20px}h2{break-after:avoid}table{break-inside:auto}tr{break-inside:avoid}}
"""


def cmd_report(data, progress, args):
    a = analyse(data, progress)
    m = data["meta"]
    e = html.escape
    P = []
    P.append('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">')
    P.append(f"<title>CAP status — {e(m['factory'])}</title>")
    P.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    P.append('<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
             '&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">')
    P.append(f"<style>{CSS}</style></head><body>")
    P.append('<div class="hd"><p class="eyebrow">Corrective Action Plan · Status Report</p>'
             f"<h1>{e(m['scope'])}</h1>"
             f"<p>{e(m['factory'])} · {e(m['reportRef'])} · {e(m['factoryId'])} · "
             f"assessed {e(m['assessment'])} · report generated {a['today'].strftime('%d %B %Y')}</p></div>")
    P.append('<div class="page">')

    P.append("<h2>Position</h2>")
    P.append(f"<p>Of <b>{a['total']}</b> non-conformities raised, <b>{a['closed']}</b> are closed and verified. "
             f"CAP completion measured across the ten development gates stands at <b>{a['completion'] * 100:.0f}%</b>. "
             f"<b>{a['open_high']}</b> High-severity findings remain open, <b>{len(a['overdue'])}</b> findings are past "
             f"their target date and <b>{len(a['due_soon'])}</b> more fall due within fourteen days.</p>")

    kp = [("kpi", "Non-conformities", a["total"], f"{a['closed']} closed"),
          ("kpi good", "CAP completion", f"{a['completion'] * 100:.0f}%", "across ten gates"),
          ("kpi bad" if a["overdue"] else "kpi good", "Past target", len(a["overdue"]), "escalate to Steering Committee"),
          ("kpi warn" if a["open_high"] else "kpi good", "High open", a["open_high"], f"{len(a['due_soon'])} due in 14 days")]
    P.append('<div class="kpis">' + "".join(
        f'<div class="{c}"><dt>{t}</dt><dd>{v}</dd><small>{s}</small></div>' for c, t, v, s in kp) + "</div>")

    P.append("<h2>Progress by assessment area</h2><table><tr><th>Area</th><th>Assessor</th>"
             "<th>High</th><th>Medium</th><th>Low</th><th>Total</th><th>Closed</th><th>Completion</th></tr>")
    for area, x in sorted(a["by_area"].items(), key=lambda kv: -kv[1]["total"]):
        pct = x["score"] / x["total"]
        P.append(f"<tr><td><b>{e(area)}</b></td><td>{e(m['assessors'].get(area, ''))}</td>"
                 f"<td>{x['High']}</td><td>{x['Medium']}</td><td>{x['Low']}</td><td>{x['total']}</td>"
                 f"<td>{x['closed']}</td><td><div class='bar'><i style='width:{pct * 100:.0f}%'></i></div>"
                 f"<span class='mono'>{pct * 100:.0f}%</span></td></tr>")
    P.append("</table>")

    P.append("<h2>Delivery waves</h2><table><tr><th>Wave</th><th>Window</th><th>Findings</th>"
             "<th>Closed</th><th>Completion</th><th>Focus</th></tr>")
    for w in data["waves"]:
        x = a["by_wave"][w["key"]]
        pct = x["score"] / max(1, x["total"])
        P.append(f"<tr><td><b>{e(w['short'])}</b><br><span class='mono'>{e(w['label'])}</span></td>"
                 f"<td class='mono'>{e(w['window'])}</td><td>{x['total']}</td><td>{x['closed']}</td>"
                 f"<td><div class='bar'><i style='width:{pct * 100:.0f}%'></i></div></td>"
                 f"<td style='font-size:11.5px'>{e(w['focus'])}</td></tr>")
    P.append("</table>")

    if a["overdue"]:
        P.append("<h2>Past target date — for escalation</h2><table>"
                 "<tr><th>ID</th><th>Area</th><th>Requirement</th><th>Sev</th><th>Target</th><th>Days late</th></tr>")
        for f, d in a["overdue"]:
            P.append(f"<tr><td class='mono'>{e(f['id'])}</td><td>{e(f['area'].replace(' Safety', ''))}</td>"
                     f"<td>{e(f['requirement'])}</td><td><span class='pill p-{f['severity']}'>{f['severity']}</span></td>"
                     f"<td class='mono'>{e(f['target'])}</td><td class='late'>{abs(d)}</td></tr>")
        P.append("</table>")

    if a["due_soon"]:
        P.append("<h2>Due within fourteen days</h2><table>"
                 "<tr><th>ID</th><th>Area</th><th>Requirement</th><th>Sev</th><th>Target</th><th>Days</th></tr>")
        for f, d in a["due_soon"]:
            P.append(f"<tr><td class='mono'>{e(f['id'])}</td><td>{e(f['area'].replace(' Safety', ''))}</td>"
                     f"<td>{e(f['requirement'])}</td><td><span class='pill p-{f['severity']}'>{f['severity']}</span></td>"
                     f"<td class='mono'>{e(f['target'])}</td><td class='mono'>{d}</td></tr>")
        P.append("</table>")

    P.append("<h2>Root-cause themes</h2><table><tr><th>Code</th><th>Theme</th><th>Findings</th>"
             "<th>High</th><th>Closed</th></tr>")
    for code, x in sorted(a["by_theme"].items(), key=lambda kv: -kv[1]["total"]):
        P.append(f"<tr><td class='mono'><b>{code}</b></td><td>{e(x['name'])}</td><td>{x['total']}</td>"
                 f"<td>{x['high']}</td><td>{x['closed']}</td></tr>")
    P.append("</table>")

    P.append("<h2>Consolidated deliverables</h2><table><tr><th>#</th><th>Deliverable</th>"
             "<th>Prepared by</th><th>Target</th><th>Findings closed</th></tr>")
    for d in a["deliverables"]:
        P.append(f"<tr><td class='mono'>{d['no']:02d}</td><td>{e(d['title'])}<br>"
                 f"<span class='mono' style='color:#5E7183'>{e(d['standard'])}</span></td>"
                 f"<td style='font-size:11.5px'>{e(d['preparedBy'])}</td><td class='mono'>{e(d['target'])}</td>"
                 f"<td>{d['done']} / {len(d['closes'])}"
                 f"<div class='bar' style='margin-top:4px'><i style='width:{d['pct'] * 100:.0f}%'></i></div></td></tr>")
    P.append("</table>")

    if a["gate_block"]:
        P.append("<h2>Where open findings are stuck</h2><p>The first gate not yet cleared, "
                 "counted across every open finding. This is where management attention buys the most movement.</p>"
                 "<table><tr><th>Blocking gate</th><th>Open findings</th></tr>")
        for g, n in a["gate_block"].most_common():
            P.append(f"<tr><td>{e(g)}</td><td class='mono'>{n}</td></tr>")
        P.append("</table>")

    P.append(f"<div class='foot'><b>{e(m['factory'])}</b> — CAP board report generated by cap_engine.py. "
             f"Severities, plans of action and deadlines are carried forward from the LRQA reports unchanged. "
             f"Deadlines counted from {e(m['clockStart'])}, the final day of the visit.<br>"
             f"Credit Partner: {e(m['creditPartner'])} · Technology Partner: {e(m['techPartner'])}</div>")
    P.append("</div></body></html>")

    out = args.out or os.path.join(HERE, f"CAP_status_{a['today'].isoformat()}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    print(f"Report written: {out}")


# ----------------------------------------------------------------- csv
def cmd_csv(data, progress, args):
    out = args.out or os.path.join(HERE, "CAP_register.csv")
    head = ["ID", "Area", "Section", "Requirement", "Observation", "Severity",
            "Code reference", "What the code requires", "Target", "Wave", "Theme",
            "Responsible function", "Status", "Gates cleared", "Gate score",
            "Root cause", "Corrective action", "Preventive action", "Action owner",
            "Budget (BDT)", "Closed on", "Remarks"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        for x in data["findings"]:
            r = record(progress, x["id"])
            done, na, applicable, pct = gate_score(r)
            w.writerow([x["id"], x["area"], x["section"], x["requirement"], x["observation"],
                        x["severity"], x["code"], x["plain"], x["target"], x["wave"],
                        f"{x['theme']} {x['themeName']}", x["owner"],
                        r.get("status", "Not Started"), f"{done}/{applicable}", f"{pct:.2f}",
                        r.get("rootCause", ""), r.get("corrective", ""), r.get("preventive", ""),
                        r.get("owner", ""), r.get("budget", ""), r.get("closed", ""), r.get("remarks", "")])
    print(f"Register written: {out}  ({len(data['findings'])} rows)")


# ----------------------------------------------------------------- digest
def cmd_digest(data, progress, args):
    a = analyse(data, progress)
    m = data["meta"]
    L = []
    L.append(f"CAP STATUS — {m['factory']}")
    L.append(f"{m['reportRef']} · as at {a['today'].strftime('%d %B %Y')}")
    L.append("")
    L.append(f"{a['closed']} of {a['total']} findings closed and verified. "
             f"CAP completion {a['completion'] * 100:.0f}% across the ten gates.")
    L.append(f"{a['open_high']} High-severity findings open. "
             f"{len(a['overdue'])} past target date, {len(a['due_soon'])} due within 14 days.")
    L.append("")
    for area, x in sorted(a["by_area"].items(), key=lambda kv: -kv[1]["total"]):
        L.append(f"  {area}: {x['closed']}/{x['total']} closed ({x['score'] / x['total'] * 100:.0f}% complete)")
    if a["overdue"]:
        L.append("")
        L.append("Past target date:")
        for f, d in a["overdue"][:10]:
            L.append(f"  {f['id']} ({f['severity']}, {abs(d)}d late) — {f['requirement'][:66]}")
        if len(a["overdue"]) > 10:
            L.append(f"  … and {len(a['overdue']) - 10} more")
    if a["gate_block"]:
        L.append("")
        L.append("Open findings are stuck mostly at: " +
                 ", ".join(f"{g} ({n})" for g, n in a["gate_block"].most_common(3)))
    text = "\n".join(L)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\nDigest written: {args.out}")


# ----------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="Analytics and reporting for the GNF CAP Board.")
    ap.add_argument("command", choices=["stats", "report", "csv", "digest"])
    ap.add_argument("--seed", default=SEED, help="Path to seed_data.json")
    ap.add_argument("--progress", help="Progress JSON exported from the board")
    ap.add_argument("--out", help="Output file path")
    args = ap.parse_args()

    if not os.path.exists(args.seed):
        sys.exit(f"seed_data.json not found at {args.seed}")
    if args.progress and not os.path.exists(args.progress):
        sys.exit(f"Progress file not found at {args.progress}")

    data, progress = load(args.seed, args.progress)
    {"stats": cmd_stats, "report": cmd_report, "csv": cmd_csv, "digest": cmd_digest}[args.command](data, progress, args)


if __name__ == "__main__":
    main()
