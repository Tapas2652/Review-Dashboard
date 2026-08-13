# BH Performance Dashboard — Setup

## Files
- `app.py` — the Streamlit dashboard (UI, KPI cards, drill-downs)
- `data_loader.py` — reads & aggregates directly from the raw Excel workbook
- `requirements.txt` — Python dependencies

## Run it
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Choose a data source in the sidebar (radio buttons):
   - **Hosted URL** (recommended for GitHub deploys — see below)
   - **Local file** — put `Review_Data.xlsx` next to `app.py`
   - **Upload** — pick the file from your browser each session
3. Launch:
   ```
   streamlit run app.py
   ```

## Hosting the Excel file outside GitHub
GitHub's file-size limit makes a large raw-data workbook awkward to
commit directly. Instead, host the file somewhere with a stable link
and point the dashboard at it — the repo then only holds code, and
the "live update" behaviour actually gets *better*, since replacing
the hosted file updates the dashboard on its own with no redeploy.

**Google Drive**
1. Upload `Review_Data.xlsx` to Drive, set sharing to "Anyone with the link."
2. Copy the share link (`https://drive.google.com/file/d/FILE_ID/view?usp=sharing`).
3. Paste that link straight into the sidebar's "File URL" box — the app
   converts it to a direct-download link automatically.

**S3 / SharePoint / Dropbox / any host**
Paste a direct-download URL the same way. For Dropbox, make sure the
link ends in `?dl=1` (not `?dl=0`).

**Setting a default URL (optional)**
So you don't have to paste the link every time, add it to
`.streamlit/secrets.toml` (don't commit this file — add it to
`.gitignore`):
```toml
DATA_URL = "https://drive.google.com/file/d/FILE_ID/view?usp=sharing"
```
The sidebar will pre-fill from this automatically. On Streamlit
Community Cloud, set the same key under your app's **Settings → Secrets**.

## Live-refresh behaviour
- **Local file**: cache keys off the file's last-modified timestamp —
  overwrite the file on disk and the next rerun picks up the change.
- **Hosted URL**: re-fetched automatically every 5 minutes, or
  instantly via the sidebar's **🔄 Refresh now** button.
- **Upload**: cache keys off the uploaded content itself.


## Scope built in
- BH filter locked to: Sadhna Shukla, Mehr Hashim, Prathap Sagar,
  Deepak Desai, Anuradha Murthy
- Domain filter locked to: Captive, Services, ITES
- Trend months: Apr'26–Jul'26 (historical, with finalised Cost baseline)
  plus Aug'26 (current MTD, with OB/Exit Pipeline + overdue + projections)

## What each tab shows
**Executive & Baseline** — Active Headcount, Aug OB (MTD), Aug Net
Projection, Aug Exit Projection, Onboarding Overdue KPI cards; full
Aug'26 pipeline/projection breakdown table; Apr–Aug monthly funnel
trend (Demand → Submission → Interview → Selection → OB → Exit →
Net); Gross Margin/Delivery Cost % and Net Margin/Total Cost % trend.

**Funnel, Accounts & Margin** — client-level funnel + margin table
per month, click any row (or use the fallback dropdown) to drill into
that client's month-on-month margin trend chart; No-Movement Accounts
(mapped clients with zero activity across all months).

**PO, Economics & Closures** — Contract Closures (impacted headcount,
PO/MRR impact, status), Signed Clients newly active in Jul'26 plus
total HC/PO achieved from all active signed clients, and an Active
Headcount client breakdown.
