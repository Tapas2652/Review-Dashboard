"""
Data loading & aggregation layer for the CEO / BH Performance Dashboard.
Can read either a local Excel file or a hosted file (Google Drive,
SharePoint, S3, any direct-download URL). Either way, the cache key
is tied to a freshness signal (file mtime for local paths, a
periodic TTL for URLs) so the dashboard picks up new data without a
code change or redeploy.
"""
import io
import os
import re
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

BH_LIST = ["Sadhna Shukla", "Mehr Hashim", "Prathap Sagar", "Deepak Desai", "Anuradha Murthy"]
DOMAIN_LIST = ["Captive", "Services", "ITES"]
MONTHS = ["Apr'26", "May'26", "Jun'26", "Jul'26", "Aug'26"]
CURRENT_MONTH = "Aug'26"
HIST_MONTHS = ["Apr'26", "May'26", "Jun'26", "Jul'26"]  # months with a finalised Cost baseline
TODAY = datetime.now()

L = 100000.0  # 1 Lakh, for PO/Margin conversion

URL_CACHE_TTL_SECONDS = 300  # re-fetch a hosted file at most every 5 minutes


def _to_gdrive_direct(url: str) -> str:
    """Convert a normal Google Drive share link into a direct-download link."""
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        file_id = m.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url  # already a direct link (S3, SharePoint, Dropbox ?dl=1, etc.)


def is_url(source: str) -> bool:
    return isinstance(source, str) and source.strip().lower().startswith(("http://", "https://"))



def _norm_bh(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "Anuradha":
        return "Anuradha Murthy"
    return s


def _norm_month(x):
    if x is None:
        return None
    return str(x).strip()


def _clean_str(x):
    if x is None:
        return None
    return str(x).strip()


def _to_num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


@st.cache_data(show_spinner="Loading raw data from Excel...")
def load_all(_source, cache_key):
    """Load and lightly clean every sheet we need. `_source` is either a
    local file path or a file-like object (BytesIO) — prefixed with an
    underscore so Streamlit doesn't try to hash it. `cache_key` (mtime,
    content hash, or URL+time-bucket) is what Streamlit actually hashes
    to decide whether to reload."""
    xls = pd.ExcelFile(_source, engine="openpyxl")

    def rd(sheet, usecols, header=0, rename=None):
        df = pd.read_excel(xls, sheet_name=sheet, header=header, usecols=usecols)
        if rename:
            df = df.rename(columns=rename)
        return df

    demand = rd("Demand", ["company_name", "Month", "BH", "Domain2", "no_of_opening"])
    submissions = rd("Submissions", ["client", "Month", "BH", "Domain2"], rename={"client": "company_name"})
    interviews = rd("Interviews", ["company_name", "Month", "BH", "Domain2"])
    selections = rd("Selections", ["company_name", "Month", "BH", "Domain2", "po", "margin"])
    onboarding = rd("Onboarding", ["company_name", "Month", "BH", "Domain2", "p_o_value", "margin"])
    exit_ = rd("Exit", ["company_name", "Month", "BH", "Domain2", "p_o_value", "margin"])
    exit_prog = rd("Exit in Progress", ["company_name", "BH", "Domain2", "p_o_value", "margin"])
    ob_pipeline = rd("OB Pipeline", ["Company_name", "BH", "Domain2", "p_o_value", "margin", "display_date"],
                      rename={"Company_name": "company_name"})
    active_hc = rd("Active Head Count", ["company_name", "BH", "Domain2", "p_o_value", "margin", "designation"])
    cost = pd.read_excel(xls, sheet_name="Cost", header=None)
    closures = rd("Contract Closure Rawa Data",
                   ["Business Head", "Key Account names", "Impacted Headcount",
                    "PO Value(MRR Impact)", "Month End Date", "Final Status (As of today)", "Client Type"])
    org_map = rd("ORG Mapping", ["Client", "Domain", "Business Head"])

    signed = pd.read_excel(xls, sheet_name="Signed Clients Data", header=None)

    # ---- normalise ----
    for df in [demand, submissions, interviews, selections, onboarding, exit_, exit_prog, ob_pipeline, active_hc]:
        df["BH"] = df["BH"].apply(_norm_bh)
        df["Domain2"] = df["Domain2"].apply(_clean_str)
        df["company_name"] = df["company_name"].apply(_clean_str)
    for df in [demand, submissions, interviews, selections, onboarding, exit_]:
        df["Month"] = df["Month"].apply(_norm_month)

    closures["Business Head"] = closures["Business Head"].apply(_norm_bh)
    org_map["Business Head"] = org_map["Business Head"].apply(_norm_bh)
    org_map["Client"] = org_map["Client"].apply(_clean_str)
    org_map["Domain"] = org_map["Domain"].apply(_clean_str)

    # Signed Clients Data — wide table: row0 = month group labels (every 3rd col from col 7),
    # row1 = HC/PO/Margin sub-headers, data from row2. Build month->col-offset map dynamically.
    row0 = signed.iloc[0].tolist()
    month_starts = {}
    for c in range(7, len(row0), 3):
        label = row0[c]
        if label and "Total" not in str(label):
            month_starts[_norm_month(label)] = c
    body = signed.iloc[2:].reset_index(drop=True)

    def month_hc(month):
        c = month_starts.get(month)
        return body.iloc[:, c].apply(_to_num) if c is not None else pd.Series(0, index=body.index)

    chrono_months = [m for m in month_starts.keys()]  # sheet is already in chronological order
    hc_by_month = {m: month_hc(m) for m in chrono_months}
    hc_frame = pd.DataFrame(hc_by_month)

    def first_active_month(row):
        for m in chrono_months:
            if row[m] > 0:
                return m
        return None

    first_month = hc_frame.apply(first_active_month, axis=1)

    jul_col = month_starts.get("Jul'26")
    signed_clean = pd.DataFrame({
        "client": body.iloc[:, 0].apply(_clean_str),
        "bh": body.iloc[:, 6].apply(_norm_bh),
        "first_active_month": first_month,
        "jul_hc": body.iloc[:, jul_col].apply(_to_num) if jul_col is not None else 0,
        "jul_po": body.iloc[:, jul_col + 1].apply(_to_num) if jul_col is not None else 0,
        "jul_margin": body.iloc[:, jul_col + 2].apply(_to_num) if jul_col is not None else 0,
    })

    return {
        "demand": demand, "submissions": submissions, "interviews": interviews,
        "selections": selections, "onboarding": onboarding, "exit": exit_,
        "exit_prog": exit_prog, "ob_pipeline": ob_pipeline, "active_hc": active_hc,
        "cost": cost, "closures": closures, "org_map": org_map, "signed": signed_clean,
    }


def get_data(source="Review_Data.xlsx"):
    """
    source can be:
      - a local file path (str) -> cache busts on file mtime
      - a URL (str, http/https) -> cache busts every URL_CACHE_TTL_SECONDS
      - a file-like object (e.g. from st.file_uploader) -> cache busts on content hash
    """
    if hasattr(source, "read"):  # uploaded file object
        raw = source.getvalue() if hasattr(source, "getvalue") else source.read()
        return load_all(io.BytesIO(raw), hash(raw))

    if is_url(source):
        direct_url = _to_gdrive_direct(source)
        time_bucket = int(time.time() // URL_CACHE_TTL_SECONDS)
        resp = requests.get(direct_url, timeout=60)
        resp.raise_for_status()
        return load_all(io.BytesIO(resp.content), (direct_url, time_bucket))

    mtime = os.path.getmtime(source)
    return load_all(source, mtime)


def _f(df, bh, domains, month=None, month_col="Month"):
    m = (df["BH"] == bh) & (df["Domain2"].isin(domains))
    if month is not None:
        m &= (df[month_col] == month)
    return df[m]


def monthly_funnel(data, bh, domains, months=MONTHS):
    """One row per month: Demand, Submission, Interview, Selection, OB (HC/PO/Margin in L),
    Exit (HC/PO/Margin in L), Net (HC/PO/Margin in L)."""
    rows = []
    for month in months:
        d = _f(data["demand"], bh, domains, month)["no_of_opening"].sum()
        s = len(_f(data["submissions"], bh, domains, month))
        i = len(_f(data["interviews"], bh, domains, month))
        sel = len(_f(data["selections"], bh, domains, month))
        ob = _f(data["onboarding"], bh, domains, month)
        ob_hc, ob_po, ob_mg = len(ob), ob["p_o_value"].sum() / L, ob["margin"].sum() / L
        ex = _f(data["exit"], bh, domains, month)
        ex_hc, ex_po, ex_mg = len(ex), ex["p_o_value"].sum() / L, ex["margin"].sum() / L
        rows.append({
            "Month": month, "Demand": int(d), "Submission": s, "Interview": i, "Selection": sel,
            "OB_HC": ob_hc, "OB_PO_L": round(ob_po, 2), "OB_Margin_L": round(ob_mg, 2),
            "Exit_HC": ex_hc, "Exit_PO_L": round(ex_po, 2), "Exit_Margin_L": round(ex_mg, 2),
            "Net_HC": ob_hc - ex_hc, "Net_PO_L": round(ob_po - ex_po, 2), "Net_Margin_L": round(ob_mg - ex_mg, 2),
        })
    return pd.DataFrame(rows)


def current_month_pipeline(data, bh, domains):
    """Aug'26-only: OB pipeline, Exit pipeline, overdue, and projections."""
    ob = _f(data["onboarding"], bh, domains, CURRENT_MONTH)
    ob_hc, ob_po, ob_mg = len(ob), ob["p_o_value"].sum() / L, ob["margin"].sum() / L

    ex = _f(data["exit"], bh, domains, CURRENT_MONTH)
    ex_hc, ex_po, ex_mg = len(ex), ex["p_o_value"].sum() / L, ex["margin"].sum() / L

    obp = _f(data["ob_pipeline"], bh, domains)  # OB Pipeline sheet = current month only, no Month col
    obp_hc, obp_po, obp_mg = len(obp), obp["p_o_value"].sum() / L, obp["margin"].sum() / L

    exp = _f(data["exit_prog"], bh, domains)  # Exit in Progress = "Exit Pipeline", current month only
    exp_hc, exp_po, exp_mg = len(exp), exp["p_o_value"].sum() / L, exp["margin"].sum() / L

    # Overdue: display_date < today AND same month as today
    if "display_date" in obp.columns:
        dd = pd.to_datetime(obp["display_date"], errors="coerce")
        overdue_mask = (dd.dt.month == TODAY.month) & (dd.dt.year == TODAY.year) & (dd < TODAY)
        overdue = obp[overdue_mask]
    else:
        overdue = obp.iloc[0:0]
    overdue_hc, overdue_po, overdue_mg = len(overdue), overdue["p_o_value"].sum() / L, overdue["margin"].sum() / L

    ob_proj_hc, ob_proj_po, ob_proj_mg = ob_hc + obp_hc, ob_po + obp_po, ob_mg + obp_mg
    ex_proj_hc, ex_proj_po, ex_proj_mg = ex_hc + exp_hc, ex_po + exp_po, ex_mg + exp_mg
    net_proj_hc = ob_proj_hc - ex_proj_hc
    net_proj_po = ob_proj_po - ex_proj_po
    net_proj_mg = ob_proj_mg - ex_proj_mg

    return {
        "ob": (ob_hc, round(ob_po, 2), round(ob_mg, 2)),
        "exit": (ex_hc, round(ex_po, 2), round(ex_mg, 2)),
        "net": (ob_hc - ex_hc, round(ob_po - ex_po, 2), round(ob_mg - ex_mg, 2)),
        "ob_pipeline": (obp_hc, round(obp_po, 2), round(obp_mg, 2)),
        "exit_pipeline": (exp_hc, round(exp_po, 2), round(exp_mg, 2)),
        "overdue": (overdue_hc, round(overdue_po, 2), round(overdue_mg, 2)),
        "ob_projection": (ob_proj_hc, round(ob_proj_po, 2), round(ob_proj_mg, 2)),
        "exit_projection": (ex_proj_hc, round(ex_proj_po, 2), round(ex_proj_mg, 2)),
        "net_projection": (net_proj_hc, round(net_proj_po, 2), round(net_proj_mg, 2)),
    }


def cost_trend(data, bh):
    """GM% (Gross Margin / Delivery Cost) and Net Margin% (Net Margin / Total Cost),
    month on month, Apr'26-Jul'26 (the months the Cost sheet carries a finalised baseline)."""
    cost = data["cost"]
    # locate the two blocks: "Delivery Cost" header row and "Total Cost" header row
    header_rows = cost[cost[0].astype(str).str.strip().isin(["Delivery Cost", "Total Cost"])]
    dc_row = header_rows[header_rows[0].astype(str).str.strip() == "Delivery Cost"].index[0]
    tc_row = header_rows[header_rows[0].astype(str).str.strip() == "Total Cost"].index[0]
    month_cols = list(cost.iloc[dc_row, 1:5])  # Apr'26..Jul'26

    def bh_row(block_start):
        for r in range(block_start + 1, block_start + 6):
            name = _norm_bh(cost.iloc[r, 0])
            if name == bh:
                return cost.iloc[r, 1:5].astype(float).tolist()
        return [None, None, None, None]

    delivery_cost = bh_row(dc_row)
    total_cost = bh_row(tc_row)

    funnel = monthly_funnel(data, bh, DOMAIN_LIST, HIST_MONTHS)  # unfiltered by domain for cost-basis GM
    rows = []
    for i, month in enumerate(HIST_MONTHS):
        gm = funnel.loc[funnel["Month"] == month, "OB_Margin_L"].values[0]
        netm = funnel.loc[funnel["Month"] == month, "Net_Margin_L"].values[0]
        dc = delivery_cost[i]
        tc = total_cost[i]
        gm_pct = (gm / dc * 100) if dc else None
        netm_pct = (netm / tc * 100) if tc else None
        rows.append({
            "Month": month, "Gross_Margin_L": gm, "Delivery_Cost_L": dc,
            "GM_to_DeliveryCost_pct": round(gm_pct, 1) if gm_pct is not None else None,
            "Net_Margin_L": netm, "Total_Cost_L": tc,
            "NetMargin_to_TotalCost_pct": round(netm_pct, 1) if netm_pct is not None else None,
        })
    return pd.DataFrame(rows)


def client_level_funnel(data, bh, domains, months=MONTHS):
    """Client x Month grid across the funnel, for drill-down."""
    frames = []
    for name, df, cnt_col in [
        ("Demand", data["demand"], "no_of_opening"),
        ("Submission", data["submissions"], None),
        ("Interview", data["interviews"], None),
        ("Selection", data["selections"], None),
    ]:
        sub = _f(df, bh, domains)
        sub = sub[sub["Month"].isin(months)]
        if cnt_col:
            g = sub.groupby(["company_name", "Month"])[cnt_col].sum().reset_index(name="value")
        else:
            g = sub.groupby(["company_name", "Month"]).size().reset_index(name="value")
        g["Metric"] = name
        frames.append(g)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def client_level_margin(data, bh, domains, months=MONTHS):
    """Per-client, per-month Onboarding HC/PO/Margin, Exit HC/PO/Margin, Net, and Margin% (Margin/PO)."""
    ob = _f(data["onboarding"], bh, domains)
    ob = ob[ob["Month"].isin(months)]
    ob_g = ob.groupby(["company_name", "Month"]).agg(
        OB_HC=("p_o_value", "count"), OB_PO_L=("p_o_value", lambda s: s.sum() / L),
        OB_Margin_L=("margin", lambda s: s.sum() / L)).reset_index()

    ex = _f(data["exit"], bh, domains)
    ex = ex[ex["Month"].isin(months)]
    ex_g = ex.groupby(["company_name", "Month"]).agg(
        Exit_HC=("p_o_value", "count"), Exit_PO_L=("p_o_value", lambda s: s.sum() / L),
        Exit_Margin_L=("margin", lambda s: s.sum() / L)).reset_index()

    merged = pd.merge(ob_g, ex_g, on=["company_name", "Month"], how="outer").fillna(0)
    merged["Net_HC"] = merged["OB_HC"] - merged["Exit_HC"]
    merged["Net_PO_L"] = merged["OB_PO_L"] - merged["Exit_PO_L"]
    merged["Net_Margin_L"] = merged["OB_Margin_L"] - merged["Exit_Margin_L"]
    merged["Margin_pct"] = merged.apply(
        lambda r: round(r["OB_Margin_L"] / r["OB_PO_L"] * 100, 1) if r["OB_PO_L"] else None, axis=1)
    return merged.sort_values(["company_name", "Month"])


def active_headcount_summary(data, bh, domains):
    ahc = _f(data["active_hc"], bh, domains)
    total_hc = len(ahc)
    total_po = ahc["p_o_value"].sum() / L
    total_mg = ahc["margin"].sum() / L
    by_client = ahc.groupby("company_name").agg(
        HC=("p_o_value", "count"), PO_L=("p_o_value", lambda s: s.sum() / L),
        Margin_L=("margin", lambda s: s.sum() / L)).reset_index().sort_values("HC", ascending=False)
    return {"total_hc": total_hc, "total_po": round(total_po, 2), "total_mg": round(total_mg, 2)}, by_client


def contract_closures(data, bh):
    c = data["closures"]
    sub = c[c["Business Head"] == bh].copy()
    sub["PO_L"] = sub["PO Value(MRR Impact)"].apply(_to_num) / L
    return sub


def signed_clients(data, bh):
    s = data["signed"]
    sub = s[(s["bh"] == bh)].copy()
    # "1st time HC and PO in Jul'26" => this client's first non-zero month (across the whole
    # signed-clients history) is Jul'26 itself
    new_in_jul = sub[sub["first_active_month"] == "Jul'26"].copy()
    active_all = sub[sub["jul_hc"] > 0]  # total achieved from all active signed clients
    totals = {
        "total_hc": active_all["jul_hc"].sum(),
        "total_po_L": round(active_all["jul_po"].sum() / L, 2),
    }
    return new_in_jul, totals


def no_movement_accounts(data, bh, domains, months=MONTHS):
    org = data["org_map"]
    roster = org[(org["Business Head"] == bh) & (org["Domain"].isin(domains))]["Client"].dropna().unique()

    active_clients = set()
    for df in [data["demand"], data["submissions"], data["interviews"],
               data["selections"], data["onboarding"], data["exit"]]:
        sub = _f(df, bh, domains)
        sub = sub[sub["Month"].isin(months)]
        col = "company_name" if "company_name" in sub.columns else "client"
        active_clients.update(sub[col].dropna().unique())

    return sorted(set(roster) - active_clients)
