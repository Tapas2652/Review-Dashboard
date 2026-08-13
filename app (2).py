import os
import pandas as pd
import streamlit as st
import data_loader as dl

st.set_page_config(page_title="BH Performance Dashboard", layout="wide")

# =========================================================
# THEME — matches the reference "Sadhna Shukla Performance
# Dashboard" HTML: navy header, blue table headers, soft
# green/amber/red status cards.
# =========================================================
NAVY = "#0d2f4f"
BLUE = "#173e69"
BG = "#f5f7fa"
GREEN = "#d9f2df"
AMBER = "#fff0c2"
RED = "#fad6d6"
LIGHT = "#edf3f8"
MUTED = "#6b7280"
LINE = "#d8dee6"
TEXT = "#1f2937"

st.markdown(f"""
<style>
.stApp {{ background-color: {BG}; color: {TEXT}; }}
h1, h2, h3 {{ color: {NAVY}; }}
div[data-testid="stMetric"] {{
    background: #fff; border: 1px solid {LINE}; border-radius: 13px; padding: 14px 16px;
}}
div[data-testid="stMetricLabel"] {{ color: {MUTED}; font-size: 11px; text-transform: uppercase; font-weight: 800; }}
div[data-testid="stMetricValue"] {{ color: {NAVY}; font-weight: 900; }}
.kpi-good {{ background: {GREEN} !important; }}
.kpi-warn {{ background: {AMBER} !important; }}
.kpi-risk {{ background: {RED} !important; }}
.section-title {{ font-size: 18px; font-weight: 850; color: {NAVY}; margin: 10px 0 6px; }}
.subsection {{ font-weight: 800; color: {NAVY}; font-size: 15px; margin: 18px 0 6px; }}
.callout {{ background: #fff; border-left: 5px solid {BLUE}; padding: 12px 15px; border-radius: 9px; font-size: 12.5px; }}
.badge {{ display:inline-block; background:{LIGHT}; border-radius:99px; padding:3px 10px; font-size:11px; font-weight:800; margin-right:6px;}}
</style>
""", unsafe_allow_html=True)


def kpi_card(label, value, sub, tone="good"):
    tone_bg = {"good": GREEN, "warn": AMBER, "risk": RED}[tone]
    st.markdown(f"""
    <div style="background:{tone_bg};border:1px solid {LINE};border-radius:13px;padding:14px 16px;min-height:96px;">
        <div style="font-size:11px;text-transform:uppercase;font-weight:800;color:{MUTED};">{label}</div>
        <div style="font-size:25px;font-weight:900;color:{NAVY};margin:5px 0;">{value}</div>
        <div style="font-size:12px;color:{TEXT};">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def fmtL(n):
    if n is None:
        return "—"
    return f"₹{n:,.2f}L"


def fmtHC(n):
    if n is None:
        return "—"
    return f"{int(n):,}"


# =========================================================
# SIDEBAR — data source + global filters
# =========================================================
st.sidebar.header("Data source")

DEFAULT_URL = ""
try:
    DEFAULT_URL = st.secrets.get("DATA_URL", "")
except Exception:
    pass
source_mode = st.sidebar.radio(
    "Load data from", ["Hosted URL (Drive / S3 / SharePoint)", "Local file", "Upload"],
    index=0 if DEFAULT_URL else 1,
)

data_source = None
if source_mode.startswith("Hosted"):
    url = st.sidebar.text_input("File URL", value=DEFAULT_URL, placeholder="https://drive.google.com/file/d/.../view")
    if st.sidebar.button("🔄 Refresh now"):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(f"Auto-refreshes at least every {dl.URL_CACHE_TTL_SECONDS // 60} min, or instantly with the button above.")
    if url:
        data_source = url
elif source_mode == "Local file":
    default_path = "Review_Data.xlsx"
    if os.path.exists(default_path):
        data_source = default_path
        st.sidebar.caption(f"Source: `{default_path}`  \nLast modified: {pd.Timestamp(os.path.getmtime(default_path), unit='s')}")
    else:
        st.sidebar.warning(f"`{default_path}` not found next to this script.")
else:
    uploaded = st.sidebar.file_uploader("Upload raw data workbook", type=["xlsx"])
    if uploaded:
        data_source = uploaded

if not data_source:
    st.error("Provide a data source in the sidebar: a hosted file URL, a local `Review_Data.xlsx`, or upload one.")
    st.stop()

data = dl.get_data(data_source)

st.sidebar.header("Filters")
bh = st.sidebar.selectbox("Business Head", dl.BH_LIST, index=0)
domains = st.sidebar.multiselect("Domain", dl.DOMAIN_LIST, default=dl.DOMAIN_LIST)
if not domains:
    domains = dl.DOMAIN_LIST

st.markdown(f"<h1 style='margin-bottom:0'>{bh}'s Performance Dashboard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='color:{MUTED};margin-top:2px;'>Executive view with drill-down across funnel, margins, PO economics and closures</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Executive & Baseline", "🔻 Funnel, Accounts & Margin", "💰 PO, Economics & Closures"])

# =========================================================
# TAB 1 — Executive Summary
# =========================================================
with tab1:
    st.markdown("<div class='section-title'>Executive Summary — Aug'26 MTD</div>", unsafe_allow_html=True)
    pipe = dl.current_month_pipeline(data, bh, domains)
    ahc_kpi, ahc_by_client = dl.active_headcount_summary(data, bh, domains)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Active Headcount", fmtHC(ahc_kpi["total_hc"]), f"{fmtL(ahc_kpi['total_po'])} PO", "good")
    with c2:
        ob_hc, ob_po, ob_mg = pipe["ob"]
        kpi_card("Aug OB (MTD)", f"{ob_hc} HC", f"{fmtL(ob_po)} | {fmtL(ob_mg)} margin", "good")
    with c3:
        np_hc, np_po, np_mg = pipe["net_projection"]
        tone = "good" if np_hc >= 0 else "risk"
        kpi_card("Aug Net Projection", f"{np_hc} HC", f"{fmtL(np_po)} | {fmtL(np_mg)} margin", tone)
    with c4:
        exp_hc, exp_po, exp_mg = pipe["exit_projection"]
        kpi_card("Aug Exit Projection", f"{exp_hc} HC", f"{fmtL(exp_po)} | {fmtL(exp_mg)} margin", "warn")
    with c5:
        ov_hc, ov_po, ov_mg = pipe["overdue"]
        kpi_card("Onboarding Overdue", f"{ov_hc} HC", f"{fmtL(ov_po)} PO", "risk" if ov_hc else "good")

    st.write("")
    st.markdown("<div class='subsection'>Aug'26 Pipeline & Projection detail</div>", unsafe_allow_html=True)
    proj_df = pd.DataFrame([
        {"Category": "Onboarding (MTD)", "HC": pipe["ob"][0], "PO (₹L)": pipe["ob"][1], "Margin (₹L)": pipe["ob"][2]},
        {"Category": "OB Pipeline", "HC": pipe["ob_pipeline"][0], "PO (₹L)": pipe["ob_pipeline"][1], "Margin (₹L)": pipe["ob_pipeline"][2]},
        {"Category": "OB Projection (MTD + Pipeline)", "HC": pipe["ob_projection"][0], "PO (₹L)": pipe["ob_projection"][1], "Margin (₹L)": pipe["ob_projection"][2]},
        {"Category": "Exit (MTD)", "HC": pipe["exit"][0], "PO (₹L)": pipe["exit"][1], "Margin (₹L)": pipe["exit"][2]},
        {"Category": "Exit Pipeline", "HC": pipe["exit_pipeline"][0], "PO (₹L)": pipe["exit_pipeline"][1], "Margin (₹L)": pipe["exit_pipeline"][2]},
        {"Category": "Exit Projection (MTD + Pipeline)", "HC": pipe["exit_projection"][0], "PO (₹L)": pipe["exit_projection"][1], "Margin (₹L)": pipe["exit_projection"][2]},
        {"Category": "Net (MTD)", "HC": pipe["net"][0], "PO (₹L)": pipe["net"][1], "Margin (₹L)": pipe["net"][2]},
        {"Category": "Net Projection", "HC": pipe["net_projection"][0], "PO (₹L)": pipe["net_projection"][1], "Margin (₹L)": pipe["net_projection"][2]},
        {"Category": "Onboarding Overdue", "HC": pipe["overdue"][0], "PO (₹L)": pipe["overdue"][1], "Margin (₹L)": pipe["overdue"][2]},
    ])
    st.dataframe(proj_df, use_container_width=True, hide_index=True)

    st.markdown("<div class='subsection'>Monthly Funnel Trend (Apr'26 – Aug'26)</div>", unsafe_allow_html=True)
    funnel = dl.monthly_funnel(data, bh, domains)
    st.dataframe(funnel, use_container_width=True, hide_index=True)

    st.markdown("<div class='subsection'>Gross Margin / Net Margin vs Cost — MoM %</div>", unsafe_allow_html=True)
    ct = dl.cost_trend(data, bh)
    st.dataframe(ct, use_container_width=True, hide_index=True)
    best = ct.loc[ct["GM_to_DeliveryCost_pct"].idxmax()] if ct["GM_to_DeliveryCost_pct"].notna().any() else None
    worst = ct.loc[ct["GM_to_DeliveryCost_pct"].idxmin()] if ct["GM_to_DeliveryCost_pct"].notna().any() else None
    if best is not None and worst is not None:
        st.markdown(f"""<div class="callout"><b>Read:</b> best month on GM-to-Delivery-Cost was
        <b>{best['Month']}</b> at <b>{best['GM_to_DeliveryCost_pct']}%</b>; weakest was
        <b>{worst['Month']}</b> at <b>{worst['GM_to_DeliveryCost_pct']}%</b>.</div>""", unsafe_allow_html=True)

# =========================================================
# TAB 2 — Funnel, Accounts & Margin (client drill-down)
# =========================================================
with tab2:
    st.markdown("<div class='section-title'>Client-Level Funnel & Margin</div>", unsafe_allow_html=True)
    cm = dl.client_level_margin(data, bh, domains)
    latest_month = st.selectbox("Month", dl.MONTHS, index=len(dl.MONTHS) - 1, key="cm_month")
    view = cm[cm["Month"] == latest_month].sort_values("OB_PO_L", ascending=False)
    view_display = view.rename(columns={"company_name": "Client"})

    st.caption("Click a row to see that client's full month-on-month margin trend below.")
    sel = st.dataframe(
        view_display, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="client_table",
    )

    st.markdown("<div class='subsection'>Client Margin Trend (Month on Month)</div>", unsafe_allow_html=True)
    selected_client = None
    if sel and sel.selection and sel.selection.get("rows"):
        selected_client = view_display.iloc[sel.selection["rows"][0]]["Client"]
    else:
        top_clients = view_display["Client"].tolist()
        if top_clients:
            selected_client = st.selectbox("...or pick a client", top_clients, key="fallback_client")

    if selected_client:
        trend = cm[cm["company_name"] == selected_client].sort_values("Month")
        st.markdown(f"**{selected_client}**")
        c1, c2 = st.columns([2, 1])
        with c1:
            chart_df = trend.set_index("Month")[["OB_Margin_L", "Exit_Margin_L", "Net_Margin_L"]]
            st.line_chart(chart_df)
        with c2:
            st.dataframe(trend[["Month", "OB_HC", "OB_PO_L", "OB_Margin_L", "Margin_pct"]], hide_index=True, use_container_width=True)

    st.markdown("<div class='subsection'>No-Movement Accounts (no activity Apr\u201926\u2013Aug\u201926)</div>", unsafe_allow_html=True)
    nomove = dl.no_movement_accounts(data, bh, domains)
    if nomove:
        cols = st.columns(4)
        for i, acct in enumerate(nomove):
            with cols[i % 4]:
                st.markdown(f"<div style='background:#fff7db;border:1px solid #ead59c;border-radius:9px;padding:11px;font-weight:700;font-size:12px;margin-bottom:8px;'>{acct}</div>", unsafe_allow_html=True)
        st.markdown("<div class='callout'><b>Action:</b> every no-movement account should carry last activity date, owner, next meeting/date and a revenue hypothesis — or be formally deprioritised.</div>", unsafe_allow_html=True)
    else:
        st.info("No accounts flagged — every mapped client has had activity in this window.")

# =========================================================
# TAB 3 — PO, Economics & Closures
# =========================================================
with tab3:
    st.markdown("<div class='section-title'>Contract Closures</div>", unsafe_allow_html=True)
    closures = dl.contract_closures(data, bh)
    if len(closures):
        c1, c2 = st.columns(2)
        with c1:
            kpi_card("Impacted Headcount", fmtHC(len(closures)), "closure events", "risk")
        with c2:
            kpi_card("PO Value (MRR Impact)", fmtL(closures["PO_L"].sum()), "total exposure", "risk")
        st.dataframe(
            closures[["Key Account names", "Impacted Headcount", "PO_L", "Final Status (As of today)", "Month End Date"]]
            .rename(columns={"PO_L": "PO (₹L)"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No contract closure records for this BH in the current scope.")

    st.markdown("<div class='subsection'>Signed Clients \u2014 Newly Active in Jul\u201926</div>", unsafe_allow_html=True)
    new_jul, totals = dl.signed_clients(data, bh)
    c1, c2 = st.columns(2)
    with c1:
        kpi_card("Total HC (all active signed clients)", fmtHC(totals["total_hc"]), "achieved to date", "good")
    with c2:
        kpi_card("Total PO (all active signed clients)", fmtL(totals["total_po_L"]), "achieved to date", "good")
    if len(new_jul):
        st.dataframe(
            new_jul[["client", "jul_hc", "jul_po"]].assign(**{"jul_po": lambda d: d["jul_po"] / dl.L}).rename(
                columns={"client": "Client", "jul_hc": "HC", "jul_po": "PO (₹L)"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No newly-activated signed clients in Jul'26 for this BH.")

    st.markdown("<div class='subsection'>Active Headcount \u2014 Client Breakdown</div>", unsafe_allow_html=True)
    _, ahc_by_client = dl.active_headcount_summary(data, bh, domains)
    st.dataframe(
        ahc_by_client.rename(columns={"company_name": "Client", "PO_L": "PO (₹L)", "Margin_L": "Margin (₹L)"}),
        use_container_width=True, hide_index=True,
    )
