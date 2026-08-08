# GNF CAP Board

A live corrective action plan board for the LRQA Technical Support Visit at
**Good & Fast Packaging Co., Ltd** — Fire Safety, Electrical Safety and Structural Safety,
report ref **LRQA-BD-NRP-353682**, factory **FFC-12103**, assessed 26–29 July 2026.

All **101 non-conformities** are built in, each with the code citation exactly as LRQA
issued it and a plain-language statement of what that clause requires. Management opens
one link and sees where the CAP stands.

---

## What is here

| File | What it does |
|---|---|
| `index.html` | The board. Eight views: Overview, Register, CAP Gates, ORSVAI, Evidence Pack, Roadmap, Code Library, Reports. |
| `assets/css/style.css` | All styling. No framework. |
| `assets/js/data.js` | The 101 findings, 19 deliverables, 28 standards, 10 gates, 6 waves. Generated — do not hand-edit. |
| `assets/js/store.js` | Saves progress. Browser storage by default; Google Sheets when connected. |
| `assets/js/app.js` | Views, charts, filtering, the gate model and the exports. |
| `seed_data.json` | The same data in plain JSON, for the Python engine and for any other tool you point at it. |
| `Code.gs` | Google Apps Script backend. Optional. |
| `cap_engine.py` | Analytics and reporting. Produces the Steering Committee status report. |
| `source/` | The Python generators that build `data.js` and `seed_data.json`. Edit here, never the generated files. |

No build step, no npm install, no dependencies. Open `index.html` and it runs.

---

## 1. Put it on GitHub Pages

```bash
git init
git add .
git commit -m "CAP board for LRQA-BD-NRP-353682"
git branch -M main
git remote add origin https://github.com/<your-account>/gnf-cap-board.git
git push -u origin main
```

Then on GitHub: **Settings ▸ Pages ▸ Source: Deploy from a branch ▸ main ▸ / (root) ▸ Save.**

A minute later the board is at `https://<your-account>.github.io/gnf-cap-board/`.
That is the one link management needs.

> Make the repository **private** if you would rather the findings were not public.
> Private repositories need a GitHub Team or Enterprise plan for Pages; on a free
> account, either keep the repository public or host the same folder on any static
> web space — it is plain HTML.

---

## 2. Use it

**Overview** opens on the signature grid: one cell per non-conformity, grouped by area.
Colour is severity, the cell fills green as its ten gates clear, and a red ring means the
target date has passed. Click any cell to open that finding.

**A finding opens in the side panel** with the assessor's observation, the LRQA code
citation, what the code requires in plain language, the evidence needed for closure, the
ten gates, and the fields your team fills in — root cause, corrective action, preventive
action, owner, budget, remarks. Press **Save**. Use **← Previous / Next →** to work
straight through a filtered list.

**CAP Gates** is the same ten-gate model as a matrix. Click a box to clear a gate;
hold **Alt** and click to mark it not applicable. A finding reads **Ready** only when
every applicable gate is cleared.

**ORSVAI** assigns Owner, Responsible, Support, Verify, Approve and Inform against each
of the 19 consolidated deliverables. Gate 4 asks for a person, not a department — this is
where those names live.

**Reports** exports the register as CSV, the progress as JSON, and prints a status report
for the fortnightly Steering Committee pack.

### Where progress is saved

By default, in the browser of whoever entered it. The badge at the top right reads
**This browser**. That is fine for one person, but for a management team everyone needs
to see the same numbers — connect the Google Sheet below.

---

## 3. Connect the Google Sheet (optional but recommended)

1. Create a Google Sheet. **Extensions ▸ Apps Script**. Delete the placeholder and paste
   in `Code.gs`.
2. Change `SHARED_KEY` at the top to something only your team knows.
3. Run `testSetup` once from the editor and accept the authorisation prompt.
4. **Deploy ▸ New deployment ▸ Web app.** Execute as **Me**, access **Anyone**. Copy the
   `/exec` URL.
5. On the board: **Reports ▸ Google Sheets sync**. Paste the URL and the same key, press
   **Connect & pull**. The badge turns green and reads **Sheet connected**.

Every save now writes to the Sheet, and the board pulls the latest on load. Three tabs
appear in your Sheet:

- **CAP_PROGRESS** — one row per finding, all ten gates, status, actions, owner, budget.
  Filter it, pivot it, chart it like any spreadsheet.
- **ORSVAI** — the accountability assignments.
- **CHANGE_LOG** — a timestamped record of every save.

After editing `Code.gs`, re-deploy: **Manage deployments ▸ edit ▸ Version: New version**.
The URL stays the same.

---

## 4. Python analytics and reporting

`cap_engine.py` needs Python 3.8 or later and no packages at all.

```bash
# quick console read
python3 cap_engine.py stats

# with the team's progress (Reports ▸ Download progress)
python3 cap_engine.py stats  --progress GNF_CAP_progress_2026-08-07.json

# standalone HTML status report for the Steering Committee pack
python3 cap_engine.py report --progress progress.json --out CAP_status.html

# flat register with progress merged in
python3 cap_engine.py csv    --progress progress.json --out register.csv

# short text digest to paste into an email
python3 cap_engine.py digest --progress progress.json
```

The report adds one thing the board does not: **where open findings are stuck** — the
first gate not yet cleared, counted across every open finding. That single table tells
you whether the CAP is blocked on analysis, on budget, on vendors or on verification.

### Scheduling the report

Add a GitHub Action, or run it from the plant server on a cron:

```bash
0 7 * * 1  cd /srv/gnf-cap-board && python3 cap_engine.py digest --progress progress.json --out weekly.txt
```

---

## 5. Changing the data

The 101 findings come from the three LRQA reports and should not drift. If LRQA issues a
revision, or the brand confirms a different deadline start date, regenerate rather than
hand-edit:

1. Edit `source/findings.py`, `source/codes.py` or `source/evidence.py`.
2. Run `cd source && python3 build_web_data.py`.
3. Commit the regenerated `seed_data.json` and `assets/js/data.js`.

Progress already recorded is keyed by finding ID, so it survives a data regeneration.

**The deadline clock.** LRQA states deadlines in weeks, not dates. Every target date here
is counted from **29 July 2026**, the final day of the visit. If LRQA or the brand
confirms a different start, change `BASE_DATE` in `source/findings.py` and regenerate — every
date and wave follows.

---

## Notes

Severities, suggested plans of action and suggested deadlines are carried forward from the
LRQA reports unchanged. Root-cause themes, priority waves, responsible functions, the
ten-gate model and the plain-language code explanations are a management overlay added to
make the register actionable — they are not LRQA determinations.

Credit Partner: **Industry Compliance & Sustainability Platform**
Technology Partner: **guulba** — technology for better performance
