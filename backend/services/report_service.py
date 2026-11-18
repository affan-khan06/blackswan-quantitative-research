from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.database.models import BacktestRecord, ExperimentRecord, StressTestRecord


def _render_fan_chart_png(fan_chart: dict, initial_capital: float) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=160)
    fig.patch.set_facecolor("#0E141B")
    ax.set_facecolor("#111820")

    days = np.array(fan_chart["days"])
    p05 = np.array(fan_chart["p05"]) / 1e5
    p25 = np.array(fan_chart["p25"]) / 1e5
    p50 = np.array(fan_chart["p50"]) / 1e5
    p75 = np.array(fan_chart["p75"]) / 1e5
    p95 = np.array(fan_chart["p95"]) / 1e5

    ax.fill_between(days, p05, p95, color="#00D6A0", alpha=0.14, label="5th-95th Percentile")
    ax.fill_between(days, p25, p75, color="#00D6A0", alpha=0.28, label="25th-75th Percentile")
    ax.plot(days, p50, color="#00D6A0", linewidth=2.0, label="Median Trajectory (P50)")
    ax.axhline(initial_capital / 1e5, color="#91A1B0", linestyle="--", linewidth=1.0, label="Initial Capital")

    ax.set_title("Simulated Portfolio Value Fan Chart (INR Lakhs)", color="#F1F5F9", fontsize=10, pad=8)
    ax.set_xlabel("Forecast Horizon (Trading Days)", color="#91A1B0", fontsize=8)
    ax.set_ylabel("Portfolio Value (INR Lakhs)", color="#91A1B0", fontsize=8)
    ax.tick_params(colors="#91A1B0", labelsize=8)
    ax.grid(color="#1F2B37", linestyle=":", linewidth=0.7)
    ax.legend(facecolor="#17212A", edgecolor="#253342", labelcolor="#F1F5F9", fontsize=7.5, loc="upper left")

    for spine in ax.spines.values():
        spine.set_color("#253342")

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def _render_loss_hist_png(loss_hist: dict, var_95: float, cvar_95: float) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=160)
    fig.patch.set_facecolor("#0E141B")
    ax.set_facecolor("#111820")

    centers = np.array(loss_hist["bin_centers"]) / 1e5
    counts = np.array(loss_hist["counts"])
    width = (centers[1] - centers[0]) * 0.9 if len(centers) > 1 else 0.1

    bar_colors = ["#FF5364" if c >= (var_95 / 1e5) else "#3B82F6" for c in centers]
    ax.bar(centers, counts, width=width, color=bar_colors, alpha=0.85)
    ax.axvline(var_95 / 1e5, color="#F59E0B", linestyle="--", linewidth=1.6, label=f"95% VaR: ₹{var_95:,.0f}")
    ax.axvline(cvar_95 / 1e5, color="#FF5364", linestyle="-", linewidth=1.8, label=f"95% CVaR: ₹{cvar_95:,.0f}")

    ax.set_title("Simulated Terminal Loss Distribution (Positive = Loss)", color="#F1F5F9", fontsize=10, pad=8)
    ax.set_xlabel("Terminal Portfolio Loss (INR Lakhs)", color="#91A1B0", fontsize=8)
    ax.set_ylabel("Path Frequency", color="#91A1B0", fontsize=8)
    ax.tick_params(colors="#91A1B0", labelsize=8)
    ax.grid(color="#1F2B37", linestyle=":", linewidth=0.7)
    ax.legend(facecolor="#17212A", edgecolor="#253342", labelcolor="#F1F5F9", fontsize=7.5)

    for spine in ax.spines.values():
        spine.set_color("#253342")

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_experiment_pdf_report(
    experiment: ExperimentRecord,
    recent_backtest: Optional[BacktestRecord] = None,
    recent_stress_tests: Optional[list[StressTestRecord]] = None,
) -> bytes:
    """
    Generate an institutional-grade quantitative research PDF report for a persisted experiment.
    Includes charts, reproducibility metadata, assumptions, VaR/CVaR, risk attribution,
    stress tests, backtesting validation, and explicit limitations.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"BLACKSWAN Research Report - {experiment.id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BSTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    h2_style = ParagraphStyle(
        "BSH2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BSBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )
    mono_style = ParagraphStyle(
        "BSMono",
        parent=styles["Code"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    res = experiment.results or {}
    hist = res.get("historical_analytics", {})
    garch = res.get("garch", {})
    regimes = res.get("regimes", {})
    sim = res.get("simulation", {})
    risk = res.get("risk_metrics", {})
    mc_risk = risk.get("monte_carlo", {})
    summary = risk.get("summary", {})
    attribution = risk.get("euler_risk_attribution", {})
    method_comp = res.get("method_comparison", [])
    provenance = experiment.data_provenance or {}

    story = []

    # Header
    story.append(Paragraph("BLACKSWAN — Quantitative Portfolio Risk Research Report", title_style))
    story.append(
        Paragraph(
            f"Experiment: <b>{experiment.name}</b> | ID: <font face='Courier'>{experiment.id}</font> | "
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            body_style,
        )
    )
    story.append(Spacer(1, 6))

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary & Reproducibility Metadata", h2_style))
    meta_rows = [
        ["Simulation Method", experiment.simulation_method, "Random Seed", str(experiment.random_seed)],
        ["Simulation Paths", f"{experiment.n_paths:,}", "Horizon (Trading Days)", str(experiment.horizon_days)],
        ["Initial Capital", f"INR {experiment.initial_capital:,.2f}", "Confidence Level", f"{experiment.confidence_level*100:.0f}%"],
        ["Data Coverage", f"{experiment.data_start_date} to {experiment.data_end_date}", "Model Version", experiment.model_version],
        ["Detected Regime", str(regimes.get("current_regime", "N/A")), "GARCH Cond. Vol (Ann.)", f"{(garch.get('current_conditional_vol_annualized') or 0)*100:.2f}%"],
    ]
    meta_tbl = Table(meta_rows, colWidths=[38 * mm, 52 * mm, 42 * mm, 46 * mm])
    meta_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_tbl)
    story.append(Spacer(1, 6))

    var95_amt = mc_risk.get("var_95", {}).get("var_amount", 0.0)
    cvar95_amt = mc_risk.get("cvar_95", {}).get("cvar_amount", 0.0)
    var99_amt = mc_risk.get("var_99", {}).get("var_amount", 0.0)
    cvar99_amt = mc_risk.get("cvar_99", {}).get("cvar_amount", 0.0)

    story.append(
        Paragraph(
            f"Over a {experiment.horizon_days}-trading-day horizon across {experiment.n_paths:,} simulated paths "
            f"using <b>{experiment.simulation_method}</b>, the portfolio exhibits a 95% Value at Risk of "
            f"<b>INR {var95_amt:,.2f}</b> and 95% Conditional Value at Risk (Expected Shortfall) of "
            f"<b>INR {cvar95_amt:,.2f}</b>. At 99% confidence, VaR is <b>INR {var99_amt:,.2f}</b> and "
            f"CVaR is <b>INR {cvar99_amt:,.2f}</b>. Probability of negative return is "
            f"{summary.get('probability_negative_return', 0)*100:.1f}%.",
            body_style,
        )
    )

    # 2. Portfolio Composition & Euler Risk Attribution
    story.append(Paragraph("2. Portfolio Composition & Euler Volatility Attribution", h2_style))
    attr_rows = [["Symbol", "Weight (%)", "Standalone Vol", "Marginal Vol", "Component Vol", "Risk Share (%)"]]
    for a in attribution.get("assets", []):
        attr_rows.append(
            [
                a["symbol"],
                f"{a['weight']*100:.2f}%",
                f"{a['standalone_annualized_vol']*100:.2f}%",
                f"{a['marginal_contribution_to_vol']*100:.2f}%",
                f"{a['component_contribution_to_vol']*100:.2f}%",
                f"{a['pct_risk_contribution']:.2f}%",
            ]
        )
    attr_tbl = Table(attr_rows, colWidths=[28 * mm, 26 * mm, 30 * mm, 30 * mm, 32 * mm, 32 * mm])
    attr_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(attr_tbl)
    story.append(
        Paragraph(
            f"Euler Reconciliation Check: Sum of component contributions = "
            f"{attribution.get('sum_component_contributions', 0)*100:.4f}% vs Portfolio Vol = "
            f"{attribution.get('portfolio_annualized_volatility', 0)*100:.4f}% "
            f"(Residual error: {attribution.get('reconciliation_error', 0):.2e}).",
            mono_style,
        )
    )

    # 3. Charts
    if sim.get("fan_chart"):
        story.append(Paragraph("3. Stochastic Trajectory & Loss Distribution", h2_style))
        fan_buf = _render_fan_chart_png(sim["fan_chart"], experiment.initial_capital)
        story.append(Image(fan_buf, width=172 * mm, height=76 * mm))
        story.append(Spacer(1, 4))

    if sim.get("terminal_loss_histogram"):
        hist_buf = _render_loss_hist_png(sim["terminal_loss_histogram"], var95_amt, cvar95_amt)
        story.append(Image(hist_buf, width=172 * mm, height=72 * mm))

    story.append(PageBreak())

    # 4. Data Provenance & Quality Audit
    story.append(Paragraph("4. Data Provenance & Quality Audit", h2_style))
    prov_rows = [["Symbol", "Source", "Start Date", "End Date", "Observations", "Missing %", "Status"]]
    for asset_entry in provenance.get("assets", [])[:12]:
        prov_rows.append(
            [
                asset_entry.get("symbol", ""),
                asset_entry.get("data_source", "")[:22],
                str(asset_entry.get("start_date", "")),
                str(asset_entry.get("end_date", "")),
                str(asset_entry.get("observation_count", 0)),
                f"{asset_entry.get('missing_observation_pct', 0):.2f}%",
                asset_entry.get("validation_status", ""),
            ]
        )
    prov_tbl = Table(prov_rows, colWidths=[24 * mm, 38 * mm, 24 * mm, 24 * mm, 22 * mm, 20 * mm, 26 * mm])
    prov_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("PADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    story.append(prov_tbl)

    # 5. Method Comparison
    if method_comp:
        story.append(Paragraph("5. Stochastic Methodology Comparison", h2_style))
        comp_rows = [["Methodology", "Expected Terminal", "95% VaR", "95% CVaR", "99% VaR", "P95 Max DD"]]
        for mc in method_comp:
            comp_rows.append(
                [
                    mc["method"],
                    f"INR {mc['expected_terminal_value']:,.0f}",
                    f"INR {mc['var_95_inr']:,.0f}",
                    f"INR {mc['cvar_95_inr']:,.0f}",
                    f"INR {mc['var_99_inr']:,.0f}",
                    f"{mc['p95_worst_max_drawdown']*100:.2f}%",
                ]
            )
        comp_tbl = Table(comp_rows, colWidths=[42 * mm, 30 * mm, 26 * mm, 26 * mm, 26 * mm, 24 * mm])
        comp_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("PADDING", (0, 0), (-1, -1), 3.5),
                ]
            )
        )
        story.append(comp_tbl)

    # 6. Out-of-Sample Model Validation (if recorded)
    story.append(Paragraph("6. Out-of-Sample Model Validation", h2_style))
    if recent_backtest and recent_backtest.results:
        bt = recent_backtest.results
        bt_rows = [["Model", "OOS Days", "Expected Viol.", "Actual Viol.", "Kupiec p-val", "Christoffersen p-val", "Verdict"]]
        for m_name, m_data in bt.get("models", {}).items():
            bt_rows.append(
                [
                    m_name,
                    str(m_data.get("observations", 0)),
                    str(m_data.get("expected_violations", 0)),
                    str(m_data.get("actual_violations", 0)),
                    f"{m_data.get('kupiec_p_value', 0):.4f}",
                    f"{m_data.get('christoffersen_p_value', 0):.4f}",
                    m_data.get("calibration_verdict", ""),
                ]
            )
        bt_tbl = Table(bt_rows, colWidths=[34 * mm, 16 * mm, 22 * mm, 20 * mm, 22 * mm, 26 * mm, 38 * mm])
        bt_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("PADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(bt_tbl)
    else:
        story.append(
            Paragraph(
                "No out-of-sample backtest run was persisted yet for this workspace. Execute a rolling "
                "VaR backtest in the Model Validation lab to attach Kupiec and Christoffersen coverage metrics.",
                body_style,
            )
        )

    # 7. Stress Test Outcomes
    if recent_stress_tests:
        story.append(Paragraph("7. Stress Testing Summary", h2_style))
        for st in recent_stress_tests[:4]:
            st_res = st.results or {}
            story.append(
                Paragraph(
                    f"<b>[{st.scenario_type}] {st.scenario_name}</b>: "
                    f"{st_res.get('narrative_analysis') or st_res.get('description', '')}",
                    body_style,
                )
            )
            story.append(Spacer(1, 3))

    # 8. Assumptions, Limitations & Non-Advisory Notice
    story.append(Paragraph("8. Statistical Assumptions, Limitations & Research Disclaimer", h2_style))
    for assumption in sim.get("assumptions", []):
        story.append(Paragraph(f"- {assumption}", body_style))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "<b>Limitations & Non-Advisory Disclaimer:</b> All risk measures, GARCH(1,1) volatility forecasts, "
            "HMM regime classifications, and Monte Carlo percentiles are conditioned on historical NSE observations "
            "and parametric/resampling assumptions. Simulated tail metrics do not constitute investment advice or "
            "a guarantee of future capital preservation. Unprecedented structural breaks may exceed historical bounds.",
            body_style,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
