"""Static report figures (PNG) shared by the reports, notebooks, brief and deck."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.ticker import NullFormatter
from .common import ROOT, read_json, write_json
from .business import STRATEGY_LABELS

# Validated categorical order (dataviz reference palette, light mode); colour follows the entity.
COLORS = {"ev": "#2a78d6", "risk": "#eb6834", "segment_offers": "#1baf7a", "risk_positive_ev": "#eda100", "value": "#e87ba4"}
INK, SECONDARY, MUTED, GRID, AXIS, SURFACE, GREY = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#b9b8b2"
DIVERGING = LinearSegmentedColormap.from_list("net", ["#d03b3b", "#f0efec", "#2a78d6"])
FIGURES = ["eda_drivers", "calibration", "discrimination", "gains", "risk_value", "quadrant_selection", "strategy_comparison",
           "profit_curve", "tornado", "sensitivity_heatmap", "fairness", "model_drivers", "shap_challenger", "churn_reasons", "stress_test", "monte_carlo", "target_profile"]


def pretty_feature(name):
    if name.startswith("tenure_band_"):
        return "Tenure segment: " + name.removeprefix("tenure_band_")
    if "_" in name and not name.startswith(("tenure_band", "addon_count", "monthly_contract")):
        column, level = name.split("_", 1)
        return f"{column}: {level}"
    return {"tenure": "Tenure (months)", "MonthlyCharges": "Monthly charges", "TotalCharges": "Total charges", "addon_count": "Number of add-on services",
            "monthly_contract": "Month-to-month contract", "autopay": "Automatic payment"}.get(name, name.replace("_", " "))


def style():
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.edgecolor": AXIS, "axes.labelcolor": SECONDARY, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-", "axes.axisbelow": True,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "legend.frameon": False, "lines.linewidth": 2, "lines.solid_capstyle": "round"})


def money(x, _=None):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def figures(run):
    style()
    cfg = read_json(run / "manifest.json")["config"]
    decisions = read_json(run / "validation_decisions.json")
    strategy = decisions["strategy_selection"]["strategy"]
    dest = ROOT / "reports/figures"
    dest.mkdir(parents=True, exist_ok=True)
    for stale in dest.glob("*.png"):
        if stale.stem not in FIGURES:
            stale.unlink()
    catalog = []

    def finish(fig, name, title, caption, population="1,409 test customers, held out from every choice"):
        # The run ID is recorded in catalog.json rather than printed on charts meant for managers.
        fig.text(0.01, 0.005, f"{caption}\nPopulation: {population}.", fontsize=7.5, color=MUTED, va="bottom")
        fig.tight_layout(rect=(0, 0.07, 1, 1))
        fig.savefig(dest / f"{name}.png", dpi=160)
        plt.close(fig)
        catalog.append({"file": name + ".png", "title": title, "caption": caption, "population": population, "run_id": run.name})

    # 1. Churn drivers on train (small multiples, one hue).
    eda = pd.read_csv(run / "eda_segments.csv")
    base = pd.read_csv(run / "customers.csv").query("split == 'train'").churn.mean()
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5))
    order = {"tenure_segment": ["loyal", "developing", "new"]}  # barh draws bottom-up: new on top
    for ax, (column, title) in zip(axes.flat, [("Contract", "Contract type"), ("tenure_segment", "Tenure segment (<=12, 13-24, >24 months)"), ("InternetService", "Internet service"), ("PaymentMethod", "Payment method")]):
        part = eda.loc[eda.attribute.eq(column)].copy()
        part = part.set_index("group").loc[order[column]].reset_index() if column in order else part.sort_values("churn_rate")
        ax.barh(part.group.astype(str), part.churn_rate, height=0.5, color=COLORS["ev"])
        ax.axvline(base, color=SECONDARY, linewidth=1, linestyle=(0, (4, 3)))
        for y, (rate, n) in enumerate(zip(part.churn_rate, part.n)):
            ax.text(rate + 0.01, y, f"{rate:.0%}  (n={n:,})", va="center", fontsize=8.5, color=SECONDARY, bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1})
        ax.set_title(title, fontsize=10.5)
        ax.set_xlim(0, max(0.62, part.churn_rate.max() + 0.18))
        ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
        ax.grid(axis="y", visible=False)
    axes[0, 0].text(base + 0.005, 2.45, f"average {base:.0%}", fontsize=8, color=SECONDARY)
    fig.suptitle("Observed churn rate by customer segment", x=0.01, ha="left", fontweight="bold")
    finish(fig, "eda_drivers", "Observed churn rate by segment", "Descriptive association only; it does not show that changing a segment would change churn.", "train split (4,225 customers)")

    # 2. Calibration of the deployed model vs the challenger.
    calibration = pd.read_csv(run / "calibration.csv")
    metrics = pd.read_csv(run / "test_metrics.csv").set_index("model")
    selected = read_json(run / "manifest.json")["selected_model"]
    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.plot([0, 1], [0, 1], color=GREY, linewidth=1, label="Perfect calibration")
    for name, color, label in [(f"{selected}_calibrated", COLORS["ev"], "Deployed: calibrated " + selected.replace("_", " ")), ("xgboost_calibrated", COLORS["risk"], "Challenger: calibrated XGBoost")]:
        part = calibration.loc[calibration.model.eq(name)]
        ax.plot(part.predicted, part.observed, color=color, marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5,
                label=f"{label} (ECE {metrics.loc[name, 'ece']:.3f})")
    ax.set_xlabel("Predicted churn probability (decile mean)"); ax.set_ylabel("Observed churn rate")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Calibration: predicted vs observed churn")
    finish(fig, "calibration", "Calibration (reliability) curve", "Ten equal-size bins of predicted probability. ECE = expected calibration error.")

    # 3. ROC and PR for the deployed model.
    roc, pr = pd.read_csv(run / "roc_curve.csv"), pd.read_csv(run / "pr_curve.csv")
    row = metrics.loc[f"{selected}_calibrated"]
    prevalence = pd.read_csv(run / "scorecard.csv").query("split == 'test'").churn.mean()
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.8))
    a.plot(roc.fpr, roc.tpr, color=COLORS["ev"]); a.plot([0, 1], [0, 1], color=GREY, linewidth=1)
    a.set_title(f"ROC curve (AUC {row.roc_auc:.3f})", fontsize=11); a.set_xlabel("False positive rate"); a.set_ylabel("True positive rate (recall)")
    b.plot(pr.recall, pr.precision, color=COLORS["ev"]); b.axhline(prevalence, color=GREY, linewidth=1)
    b.text(0.02, prevalence + 0.02, f"random contact = {prevalence:.0%}", fontsize=8.5, color=SECONDARY)
    b.set_title(f"Precision-recall curve (AP {row.average_precision:.3f})", fontsize=11); b.set_xlabel("Recall"); b.set_ylabel("Precision"); b.set_ylim(0, 1.02)
    fig.suptitle("Discrimination of the deployed model", x=0.01, ha="left", fontweight="bold")
    finish(fig, "discrimination", "Discrimination of the deployed model", "AP (average precision) is the area under the precision-recall curve; it is the primary metric because churners are 27% of customers.")

    # 4. Cumulative gains.
    gains = pd.read_csv(run / "gains_test.csv")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    x = np.r_[0, gains.cumulative_customer_share]; y = np.r_[0, gains.cumulative_churner_capture]
    ax.plot([0, 1], [0, 1], color=GREY, linewidth=1, label="Random contact")
    ax.plot(x, y, color=COLORS["ev"], marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5, label="Contact by predicted risk")
    for i in [0, 2]:
        ax.annotate(f"top {x[i + 1]:.0%} of customers\ncontains {y[i + 1]:.0%} of churners", (x[i + 1], y[i + 1]), xytext=(x[i + 1] + 0.08, y[i + 1] - 0.12), fontsize=8.5, color=SECONDARY,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8})
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Share of customers contacted (highest risk first)"); ax.set_ylabel("Share of all churners reached"); ax.legend(loc="lower right")
    ax.set_title(f"Top-decile lift {gains.lift.iloc[0]:.1f}x")
    finish(fig, "gains", "Cumulative gains", "Ranking quality only. Whom to contact is decided by expected value, not by risk alone.")

    # 5. Risk x value map with frozen validation thresholds.
    thresholds = read_json(run / "targeting_thresholds.json")
    target = pd.read_csv(run / f"targeting_{strategy}.csv")
    fig, ax = plt.subplots(figsize=(9, 6.2))
    rest, chosen = target.loc[~target.selected], target.loc[target.selected]
    ax.scatter(rest.churn_probability, rest.customer_value, s=12, color=GREY, alpha=0.6, linewidths=0, label=f"Not contacted ({len(rest):,})")
    ax.scatter(chosen.churn_probability, chosen.customer_value, s=22, color=COLORS[strategy], edgecolors=SURFACE, linewidths=0.6, label=f"Contacted by {STRATEGY_LABELS[strategy].lower()} ({len(chosen):,})")
    ax.axvline(thresholds["risk"], color=SECONDARY, linewidth=1, linestyle=(0, (4, 3))); ax.axhline(thresholds["value"], color=SECONDARY, linewidth=1, linestyle=(0, (4, 3)))
    for text, xy, ha, va in [("High risk / High value", (0.99, 0.98), "right", "top"), ("Low risk / High value", (0.01, 0.98), "left", "top"),
                             ("High risk / Low value", (0.99, 0.02), "right", "bottom"), ("Low risk / Low value", (0.01, 0.02), "left", "bottom")]:
        ax.text(*xy, text, ha=ha, va=va, fontsize=9, color=SECONDARY, fontweight="bold", transform=ax.transAxes)
    ax.set_xlim(0, 1); ax.set_xlabel("Predicted churn probability"); ax.set_ylabel(f"Customer value proxy ({cfg['currency']})")
    ax.yaxis.set_major_formatter(money); ax.legend(loc="upper center", fontsize=9, bbox_to_anchor=(0.5, -0.12), ncol=2)
    ax.set_title("The campaign targets risk and value together, not risk alone")
    finish(fig, "risk_value", "Risk x value map", "Dashed lines: 75th percentiles of risk and value, fitted on validation and frozen. Value = margin x discounted remaining months.")

    # 6. Selection by quadrant: risk-only vs chosen strategy.
    matrix = pd.read_csv(run / "risk_value_matrix.csv")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(matrix))
    ax.barh(y - 0.17, matrix.selected_risk, height=0.3, color=COLORS["risk"], label="Highest churn risk")
    ax.barh(y + 0.17, matrix[f"selected_{strategy}"], height=0.3, color=COLORS[strategy], label=STRATEGY_LABELS[strategy])
    for i, r in matrix.iterrows():
        ax.text(max(r.selected_risk, r[f"selected_{strategy}"]) + 3, i, f"{r.customers:,} customers, {r.value_at_risk_share:.0%} of value at risk", va="center", fontsize=8.5, color=SECONDARY)
    ax.set_yticks(y, matrix.quadrant); ax.invert_yaxis(); ax.set_xlabel("Customers contacted within the same budget")
    ax.set_xlim(0, max(matrix.selected_risk.max(), matrix[f"selected_{strategy}"].max()) * 1.9); ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right"); ax.set_title("Customers contacted per risk x value quadrant")
    finish(fig, "quadrant_selection", "Who each rule contacts", "Value at risk = sum of churn probability x customer value in the quadrant.")

    # 7. Strategy comparison (one measure; the chosen rule is emphasised).
    comparison = pd.read_csv(run / "strategy_comparison.csv")
    comparison = comparison.loc[comparison.strategy.ne("none")].sort_values("expected_net_value")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    colors = [COLORS["ev"] if s == strategy else GREY for s in comparison.strategy]
    ax.barh([STRATEGY_LABELS.get(s, s) for s in comparison.strategy], comparison.expected_net_value, height=0.5, color=colors)
    ax.axvline(0, color=AXIS, linewidth=1)
    for i, (value, roi) in enumerate(zip(comparison.expected_net_value, comparison.roi)):
        ax.text(value + (60 if value >= 0 else -60), i, f"{money(value)}  (ROI {roi:.0%})", va="center", ha="left" if value >= 0 else "right", fontsize=8.5, color=SECONDARY)
    span = comparison.expected_net_value.abs().max()
    ax.set_xlim(min(0, comparison.expected_net_value.min()) - span * 0.45, comparison.expected_net_value.max() + span * 0.5)
    ax.xaxis.set_major_formatter(money); ax.set_xlabel(f"Expected net retention value ({cfg['currency']})"); ax.grid(axis="y", visible=False)
    ax.set_title("Same budget, different rules: expected net value")
    finish(fig, "strategy_comparison", "Strategy comparison at the fixed budget", "Expected value under the stated save-rate and cost assumptions; not realised profit.")

    # 8. Profit curve with marginal ROI panel (two panels, never two y-scales).
    curve = pd.read_csv(run / "budget_curve.csv").query("population == 'test'")
    reco = read_json(run / "recommended_campaign.json")
    base_share = cfg["campaign"]["budget_share"]
    fig, (top_ax, bottom) = plt.subplots(2, 1, figsize=(9.5, 7.2), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    for key in [strategy, "risk", "segment_offers" if strategy != "segment_offers" else "ev"]:
        part = curve.loc[curve.strategy.eq(key)]
        top_ax.plot(part.budget_share, part.expected_net_value, color=COLORS[key], label=STRATEGY_LABELS[key])
    for share, text in [(base_share, "base budget"), (reco["budget_share"], "recommended")]:
        for ax in (top_ax, bottom):
            ax.axvline(share, color=SECONDARY, linewidth=1, linestyle=(0, (4, 3)))
        top_ax.text(share + 0.004, curve.expected_net_value.max() * 1.02, text, fontsize=8.5, color=SECONDARY)
    top_ax.axhline(0, color=AXIS, linewidth=1); top_ax.yaxis.set_major_formatter(money); top_ax.set_ylabel("Expected net value"); top_ax.legend(loc="lower right", fontsize=9)
    top_ax.set_title("Expected net value by budget size")
    part = curve.loc[curve.strategy.eq(strategy)]
    bottom.bar(part.budget_share, part.marginal_roi.fillna(0), width=0.012, color=COLORS[strategy])
    bottom.axhline(cfg["campaign"]["recommendation"]["min_marginal_roi"], color=COLORS["risk"], linewidth=1.2)
    bottom.text(part.budget_share.max(), cfg["campaign"]["recommendation"]["min_marginal_roi"] + 0.05, f"hurdle {cfg['campaign']['recommendation']['min_marginal_roi']:.0%}", fontsize=8.5, color=SECONDARY, ha="right")
    bottom.set_ylabel("Marginal ROI\nof each step"); bottom.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    bottom.set_xlabel("Budget as share of customers that could be offered the standard offer"); bottom.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    finish(fig, "profit_curve", "Profit curve and marginal ROI", "Recommendation chosen on validation (largest budget whose last step still clears the hurdle) and shown here on test.")

    # 9. Tornado of one-way assumption changes.
    tornado = pd.read_csv(run / "tornado.csv").iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    base_net = tornado.base_net.iloc[0]
    y = np.arange(len(tornado))
    ax.barh(y, tornado.net_low_retarget - base_net, left=base_net, height=0.45, color=COLORS["risk"], label="Low end of the range")
    ax.barh(y, tornado.net_high_retarget - base_net, left=base_net, height=0.45, color=COLORS["ev"], label="High end of the range")
    ax.axvline(base_net, color=INK, linewidth=1)
    for i, r in enumerate(tornado.itertuples()):
        lo, hi = r.net_low_retarget, r.net_high_retarget
        ax.text(min(lo, hi) - 80, i, money(min(lo, hi)), ha="right", va="center", fontsize=8, color=SECONDARY)
        ax.text(max(lo, hi) + 80, i, money(max(lo, hi)), ha="left", va="center", fontsize=8, color=SECONDARY)
    ax.set_yticks(y, [f"{r.label}\n{r.low:g} to {r.high:g} (base {r.base:g})" for r in tornado.itertuples()], fontsize=8.5)
    span = max(abs(tornado.net_low_retarget - base_net).max(), abs(tornado.net_high_retarget - base_net).max())
    ax.set_xlim(base_net - span * 1.4, base_net + span * 1.4); ax.xaxis.set_major_formatter(money); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Expected net value when the list is re-optimised"); ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title(f"{tornado.label.iloc[-1]} moves the result most (base {money(base_net)})")
    finish(fig, "tornado", "One-way sensitivity (tornado)", "Each bar changes one assumption to the low/high end of its register range and re-selects customers within the same budget.")

    # 10. Save rate x offer cost heatmaps: frozen list vs re-optimised list.
    sens = pd.read_csv(run / "sensitivity.csv").query("axis == 'save_rate x offer_cost'")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.86, bottom=0.2, top=0.84, wspace=0.08)
    values = sens.expected_net_value
    norm = TwoSlopeNorm(vmin=min(values.min(), -1), vcenter=0, vmax=max(values.max(), 1))
    for ax, mode, title in zip(axes, ["fixed", "retarget"], ["Frozen list (plan already approved)", "Re-optimised list (plan adapts)"]):
        grid = sens.loc[sens["mode"].eq(mode)].pivot(index="parameter", columns="cost_multiplier", values="expected_net_value")
        image = ax.imshow(grid, aspect="auto", cmap=DIVERGING, norm=norm, origin="lower")
        ax.set_xticks(range(len(grid.columns)), [f"{c:g}x" for c in grid.columns]); ax.set_yticks(range(len(grid.index)), [f"{v:.0%}" for v in grid.index])
        for i in range(len(grid.index)):
            for j in range(len(grid.columns)):
                v = grid.iloc[i, j]
                label = f"{v / 1000:,.1f}k".replace("-0.0k", "0.0k")
                ax.text(j, i, label, ha="center", va="center", fontsize=8, color="white" if abs(norm(v) - 0.5) > 0.32 else INK)
        ax.set_title(title, fontsize=10.5); ax.set_xlabel("Offer cost multiplier"); ax.grid(False)
    axes[0].set_ylabel("Assumed save rate (standard offer)")
    fig.colorbar(image, cax=fig.add_axes([0.885, 0.2, 0.015, 0.64]), label=f"Expected net value ({cfg['currency']}); red = loss", format=money)
    fig.suptitle("Save rate x offer cost: frozen list vs re-optimised list", x=0.01, ha="left", fontweight="bold")
    fig.text(0.01, 0.005, f"Base case: save rate {cfg['offers'][[o['offer_id'] for o in cfg['offers']].index(cfg['campaign']['default_offer'])]['save_rate']:.0%}, cost 1x. Values in thousands.\nPopulation: test split. Run {run.name}.", fontsize=7.5, color=MUTED)
    fig.savefig(dest / "sensitivity_heatmap.png", dpi=160); plt.close(fig)
    catalog.append({"file": "sensitivity_heatmap.png", "title": "Save rate x offer cost sensitivity", "caption": "Frozen vs re-optimised list.", "population": "test", "run_id": run.name})

    # 11. Fairness: selection ratio with bootstrap CI.
    fair = pd.read_csv(run / "fairness.csv")
    rows = fair.loc[fair.attribute.isin(["gender", "SeniorCitizen"]) & fair.strategy.isin(["risk", strategy]) & (fair.group.astype(str) != fair.reference_group.astype(str))]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    low, high = cfg["guardrails"]["selection_ratio_alert"]
    ax.axvspan(low, high, color=GRID, alpha=0.6, linewidth=0); ax.axvline(1, color=AXIS, linewidth=1)
    labels = {"gender": {"Female": "Female vs male"}, "SeniorCitizen": {"1": "Senior vs non-senior"}}
    for k, (key, offset) in enumerate([("risk", -0.12), (strategy, 0.12)]):
        part = rows.loc[rows.strategy.eq(key)]
        ys = np.arange(len(part)) + offset
        ax.errorbar(part.ratio_to_reference, ys, xerr=[part.ratio_to_reference - part.ratio_lower_95, part.ratio_upper_95 - part.ratio_to_reference],
                    fmt="o", color=COLORS[key], markersize=7, markeredgecolor=SURFACE, elinewidth=1.5, capsize=0, label=STRATEGY_LABELS[key])
        ax.scatter(part.risk_adjusted_ratio, ys, marker="|", s=160, color=COLORS[key], linewidths=2)
    names = rows.loc[rows.strategy.eq(strategy)]
    ax.set_yticks(range(len(names)), [labels[a].get(str(g), f"{a}={g}") for a, g in zip(names.attribute, names.group.astype(str))])
    ax.set_xlabel("Selection-rate ratio (dot, 95% CI); tick = ratio after adjusting for risk decile"); ax.grid(axis="y", visible=False)
    ax.text((low + high) / 2, 0.97, f"no-review\nband {low}-{high}", fontsize=7.5, color=SECONDARY, ha="center", va="top", transform=ax.get_xaxis_transform())
    ax.legend(loc="lower right", fontsize=8.5); ax.set_title("Selection-rate ratio by protected attribute")
    finish(fig, "fairness", "Allocation audit by protected attribute", "Gender and SeniorCitizen are not model inputs; they are used only for this audit.")

    # 12. Drivers of the deployed (logistic) model as odds ratios against stated references.
    ratios = pd.read_csv(run / "odds_ratios.csv") if (run / "odds_ratios.csv").stat().st_size > 10 else pd.DataFrame()
    fig, ax = plt.subplots(figsize=(9, 5.6))
    if len(ratios):
        picks = pd.concat([ratios.nlargest(7, "odds_ratio"), ratios.nsmallest(5, "odds_ratio")]).drop_duplicates().sort_values("odds_ratio")
        names = [f"{r.variable}: {r.comparison}" for r in picks.itertuples()]
        colors = [COLORS["risk"] if v > 1 else COLORS["ev"] for v in picks.odds_ratio]
        ax.hlines(range(len(picks)), 1, picks.odds_ratio, color=colors, linewidth=2)
        ax.scatter(picks.odds_ratio, range(len(picks)), s=60, color=colors, zorder=3, edgecolor=SURFACE, linewidth=2)
        for y, v in enumerate(picks.odds_ratio):
            ax.text(v * (1.06 if v > 1 else 0.94), y, f"{v:.2f}", va="center", ha="left" if v > 1 else "right", fontsize=8.5, color=SECONDARY)
        ax.set_xscale("log"); ax.set_yticks(range(len(picks)), names)
        ticks = [0.25, 0.5, 1, 2, 4]
        ax.set_xticks(ticks, [f"{t:g}" for t in ticks]); ax.xaxis.set_minor_formatter(NullFormatter()); ax.set_xlim(0.3, 6)
        ax.axvline(1, color=AXIS, linewidth=1); ax.grid(axis="y", visible=False)
        ax.set_xlabel("Odds ratio of churning (log scale): 2 = twice the odds, 0.5 = half")
    ax.set_title("What moves the deployed model's churn odds")
    finish(fig, "model_drivers", "Deployed model drivers", "Calibrated logistic model. Categories vs their lowest-churn level, flags vs not having the service,\n"
           "tenure per 12 months. Associations, not causes.", "train split")

    # 13. Challenger SHAP (clearly labelled as not deployed).
    shap = pd.read_csv(run / "shap_global.csv").head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh([pretty_feature(f) for f in shap.feature], shap.mean_abs_shap, height=0.5, color=COLORS["risk"])
    ax.grid(axis="y", visible=False); ax.set_xlabel("Mean |SHAP value| (log-odds)")
    ax.set_title("Challenger XGBoost (not deployed): SHAP feature attribution")
    finish(fig, "shap_challenger", "Challenger model SHAP", "TreeSHAP on 200 validation customers; explains the raw XGBoost challenger, not the deployed calibrated logistic model.", "validation sample")

    # 14. Why churners left (IBM extended sample), all churners vs churners on the recommended list.
    summary = read_json(run / "churn_reasons_summary.json")
    categories = list(summary["category_share"])[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(categories))
    ax.barh(y + 0.2, [summary["category_share"][c] for c in categories], height=0.36, color=GREY, label="All churners")
    ax.barh(y - 0.2, [summary["category_share_on_list"].get(c, 0) for c in categories], height=0.36, color=COLORS["ev"], label="Churners on the recommended list (test)")
    for i, c in enumerate(categories):
        ax.text(summary["category_share"][c] + 0.006, i + 0.2, f"{summary['category_share'][c]:.0%}", va="center", fontsize=8.5, color=SECONDARY)
    ax.set_yticks(y, [f"{c}\n(offer can address)" if c in summary["addressable_categories"] else c for c in categories])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of churners"); ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title(f"Only {summary['addressable_share']:.0%} of churners left for price or a competitor's offer")
    finish(fig, "churn_reasons", "Why churners left", "Reason categories as grouped by IBM; recorded after customers left, so descriptive only, never a model input.",
           f"all {summary['churners']:,} churners in the IBM extended sample; list churners from the test split")

    # 15. Outside the sample: lower churn and Vietnamese prices (two panels, one measure each).
    stress = pd.read_csv(run / "stress_test.csv")
    stress["churn_label"] = [f"{p:.0%}" + (" (sample)" if pd.isna(t) else "") for p, t in zip(stress.mean_probability, stress.target_churn)]
    stress["offer_room"] = stress.affordable_offer_cost_top10 / stress.mean_monthly_bill
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))
    palette = {"Sample company (USD)": COLORS["ev"], "Vietnam-like prices": COLORS["segment_offers"]}
    for economy, part in stress.groupby("economy", sort=False):
        x = np.arange(len(part))
        left.plot(x, part.positive_ev_share, marker="o", markersize=7, color=palette[economy], label=economy)
        right.plot(x, part.offer_room, marker="o", markersize=7, color=palette[economy], label=economy)
        left.set_xticks(x, part.churn_label); right.set_xticks(x, part.churn_label)
    offer_share = float((stress.standard_offer_cost / stress.mean_monthly_bill).iloc[0])
    right.axhline(offer_share, color=MUTED, linestyle="--", linewidth=1)
    right.text(len(x) - 1, offer_share, f"standard offer = {offer_share:.0%} of a bill", fontsize=8, color=SECONDARY, ha="right", va="bottom")
    left.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); right.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    left.set_title("Customers worth an offer"); right.set_title("Affordable offer for the best 10%, as share of a bill")
    left.set_xlabel("Average churn probability"); right.set_xlabel("Average churn probability")
    left.legend(fontsize=8.5); left.set_ylim(bottom=0); right.set_ylim(bottom=0)
    finish(fig, "stress_test", "Outside the sample", "Probabilities shifted to lower average churn with ranks unchanged; Vietnam-like prices scale bills and offers to a "
           f"{cfg['vietnam_scenario']['monthly_bill_vnd']:,} VND bill\nand contact by SMS. Value horizon held fixed. Contact cap applies.")

    # 16. Joint uncertainty: net value of frozen lists across assumption draws.
    draws = pd.read_csv(run / "monte_carlo_draws.csv")
    summary = pd.read_csv(run / "monte_carlo_summary.csv").set_index("plan")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    values = np.concatenate([draws.net_recommended, draws.net_base_budget])
    bins = np.linspace(np.quantile(values, 0.002), np.quantile(values, 0.998), 60)
    ax.axvspan(bins[0], 0, color="#d03b3b", alpha=0.06, linewidth=0)
    for column, label, color in [("net_base_budget", "Base-budget list", COLORS["segment_offers"]), ("net_recommended", "Recommended list", COLORS["ev"])]:
        plan = "base budget" if column == "net_base_budget" else "recommended"
        ax.hist(draws[column], bins=bins, histtype="step", linewidth=2, color=color,
                label=f"{label}: loses money in {summary.loc[plan, 'prob_loss']:.0%} of draws")
    ax.axvline(0, color=INK, linewidth=1)
    ax.xaxis.set_major_formatter(money); ax.set_yticks([]); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Expected net value of the frozen list (test customers)"); ax.legend(loc="upper right", fontsize=8.5)
    ax.set_title("How often the lists lose money when every assumption is uncertain")
    finish(fig, "monte_carlo", "Joint uncertainty of the assumptions", f"{len(draws):,} draws; every register assumption drawn at once from a triangular distribution (low, base, high).\n"
           "Lists and offers are frozen, as they would be in a pilot; shaded area = loss; the most extreme 0.2% at each end are not drawn.")

    # 17. Who the recommended list contacts.
    profile = pd.read_csv(run / "target_profile.csv")
    picks = [("InternetService", "Fiber optic", "Fibre internet"), ("Contract", "Month-to-month", "Month-to-month contract"),
             ("PaymentMethod", "Electronic check", "Pays by electronic check"), ("tenure_segment", "new", "Tenure 12 months or less"), ("SeniorCitizen", "1", "Senior")]
    rows = [profile.loc[profile.attribute.eq(a) & profile.group.astype(str).eq(g)].iloc[0] for a, g, _ in picks]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    y = np.arange(len(picks))[::-1]
    ax.barh(y + 0.2, [r.all_share for r in rows], height=0.36, color=GREY, label="All test customers")
    ax.barh(y - 0.2, [r.list_share for r in rows], height=0.36, color=COLORS["ev"], label="Recommended list")
    for yi, r in zip(y, rows):
        ax.text(r.list_share + 0.01, yi - 0.2, f"{r.list_share:.0%}", va="center", fontsize=8.5, color=SECONDARY)
        ax.text(r.all_share + 0.01, yi + 0.2, f"{r.all_share:.0%}", va="center", fontsize=8.5, color=MUTED)
    ax.set_yticks(y, [label for _, _, label in picks]); ax.set_xlim(0, 1.12)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.grid(axis="y", visible=False); ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("Who the recommended list contacts")
    finish(fig, "target_profile", "Target profile", "Share of customers with each attribute, on the recommended list and among all test customers.")

    write_json(dest / "catalog.json", catalog)
    return catalog
