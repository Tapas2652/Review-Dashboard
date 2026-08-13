# BH Performance Dashboard — Setup

## Files
- `app.py` — the Streamlit dashboard (UI, KPI cards, drill-downs)
- `data_loader.py` — reads & aggregates directly from the raw Excel workbook
- `requirements.txt` — Python dependencies

## Run it
1. Put all three files **and** `Review_Data.xlsx` in the same folder
   (or use the "Upload / replace raw data workbook" control in the
   sidebar once the app is running).
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Launch:
   ```
   streamlit run app.py
   ```

## Live-refresh behaviour
`data_loader.get_data()` keys its cache off the Excel file's last-modified
timestamp. Whenever `Review_Data.xlsx` is overwritten/updated on disk,
the next dashboard rerun (or a manual refresh) picks up the new numbers
automatically — no code changes needed.

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
