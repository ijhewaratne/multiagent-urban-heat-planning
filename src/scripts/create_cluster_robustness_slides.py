"""
Per-cluster robustness slide: for every street cluster, builds the real
KPI contract + decision (via decision.kpi_contract / decision.rules — the
actual production pipeline, not a hand-rolled approximation), renders four
supporting figures (LCOH violin, scenario-by-scenario scatter, parameter
tornado, decision-stability CDF), and composes them into a one-page summary
slide. Everything is written per cluster into its own folder:

    results/thesis/figures/per_cluster/{CLUSTER_ID}/
        fig_lcoh_violin.png
        fig_lcoh_scatter.png
        fig_tornado.png
        fig_decision_stability.png
        slide.png
"""
import sys
import json
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.gridspec as gridspec

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from branitz_heat_decision.decision.kpi_contract import build_kpi_contract
from branitz_heat_decision.decision.rules import decide_from_contract

RESULTS = Path("results")
OUT_ROOT = RESULTS / "thesis" / "figures" / "per_cluster"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

C_DH, C_HP = "#c0392b", "#1a5276"
C_DH_L, C_HP_L = "#e8a09a", "#7fb3d3"
C_GREY, C_GOLD = "#7f8c8d", "#d4ac0d"
C_ACCENT = "#1e5f4a"   # dark green accent (slide header/stat)
C_ORANGE = "#c0611f"   # header bullet

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 8.5,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

PARAM_LABELS = {
    "capex_mult": "CAPEX Multiplier",
    "elec_price_mult": "Electricity Price",
    "fuel_price_mult": "Fuel / Gas Price",
    "grid_co2_mult": "Grid CO₂ Factor",
    "hp_cop": "Heat Pump COP",
    "discount_rate": "Discount Rate",
}


def make_violin(mc, cid_short, label, out_path):
    dh = mc["lcoh_dh_eur_per_mwh"].dropna().values
    hp = mc["lcoh_hp_eur_per_mwh"].dropna().values

    fig, ax = plt.subplots(figsize=(6, 5))
    parts = ax.violinplot([dh, hp], positions=[1, 2], showmedians=True,
                           showextrema=False, widths=0.55)
    for i, (fc, ec) in enumerate([(C_DH_L, C_DH), (C_HP_L, C_HP)]):
        parts["bodies"][i].set_facecolor(fc)
        parts["bodies"][i].set_edgecolor(ec)
        parts["bodies"][i].set_linewidth(1.5)
        parts["bodies"][i].set_alpha(0.75)
    parts["cmedians"].set_color("black")
    parts["cmedians"].set_linewidth(2.5)

    for pos, vals, col in zip([1, 2], [dh, hp], [C_DH, C_HP]):
        p05, p95 = np.percentile(vals, 5), np.percentile(vals, 95)
        ax.plot([pos - 0.12, pos + 0.12], [p05, p05], color=col, lw=2)
        ax.plot([pos - 0.12, pos + 0.12], [p95, p95], color=col, lw=2)
        ax.plot([pos, pos], [p05, p95], color=col, lw=1, linestyle="--", alpha=0.5)
        med = np.median(vals)
        ax.text(pos, med + (max(dh.max(), hp.max()) * 0.02), f"{med:.0f}",
                ha="center", va="bottom", fontsize=9, fontweight="bold", color=col)

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["District Heating (DH)", "Heat Pumps (HP)"])
    ax.set_ylabel("Levelised Cost of Heat (EUR / MWh)")
    ax.set_title(f"LCOH Distribution — {len(dh)} Monte Carlo Scenarios\n{label}")
    legend_handles = [
        mpatches.Patch(facecolor=C_DH_L, edgecolor=C_DH, label="DH distribution"),
        mpatches.Patch(facecolor=C_HP_L, edgecolor=C_HP, label="HP distribution"),
        mlines.Line2D([], [], color="black", lw=2.5, label="Median"),
        mlines.Line2D([], [], color=C_GREY, lw=1.5, linestyle="--", label="P5 – P95 range"),
    ]
    ax.legend(handles=legend_handles, loc="best", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_scatter(mc, cid_short, label, out_path):
    dh = mc["lcoh_dh_eur_per_mwh"].values
    hp = mc["lcoh_hp_eur_per_mwh"].values
    hp_wins = dh > hp

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(hp[hp_wins], dh[hp_wins], alpha=0.35, s=14, color=C_HP,
               label=f"HP preferred ({hp_wins.sum()} / {len(hp_wins)} scenarios)")
    ax.scatter(hp[~hp_wins], dh[~hp_wins], alpha=0.35, s=14, color=C_DH,
               label=f"DH preferred ({(~hp_wins).sum()} / {len(hp_wins)} scenarios)")

    all_v = np.concatenate([dh, hp])
    vmin, vmax = all_v.min() * 0.95, all_v.max() * 1.05
    ax.plot([vmin, vmax], [vmin, vmax], "k--", linewidth=1.2, alpha=0.5, label="Break-even line")
    ax.fill_between([vmin, vmax], [vmin, vmin], [vmin, vmax], alpha=0.04, color=C_DH)
    ax.fill_between([vmin, vmax], [vmax, vmax], [vmin, vmax], alpha=0.04, color=C_HP)
    ax.text(vmax * 0.98, vmax * 0.97, "DH\ncheaper", ha="right", va="top", fontsize=8, color=C_DH, alpha=0.7)
    ax.text(vmin * 1.02, vmin * 1.03, "HP\ncheaper", ha="left", va="bottom", fontsize=8, color=C_HP, alpha=0.7)

    ax.set_xlim(vmin, vmax)
    ax.set_ylim(vmin, vmax)
    ax.set_xlabel("HP LCOH (EUR / MWh)")
    ax.set_ylabel("DH LCOH (EUR / MWh)")
    ax.set_title(f"Scenario-by-Scenario LCOH Comparison\n{label}")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_tornado(mc, cid_short, label, out_path):
    corr_dh, corr_hp = {}, {}
    for col, lab in PARAM_LABELS.items():
        if col in mc.columns:
            corr_dh[lab] = mc[col].corr(mc["lcoh_dh_eur_per_mwh"], method="spearman")
            corr_hp[lab] = mc[col].corr(mc["lcoh_hp_eur_per_mwh"], method="spearman")

    labels = list(corr_dh.keys())
    dh_vals = [corr_dh[l] for l in labels]
    hp_vals = [corr_hp[l] for l in labels]
    order = np.argsort([max(abs(d), abs(h)) for d, h in zip(dh_vals, hp_vals)])
    labels = [labels[i] for i in order]
    dh_vals = [dh_vals[i] for i in order]
    hp_vals = [hp_vals[i] for i in order]

    y = np.arange(len(labels))
    w = 0.32
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.barh(y + w / 2, dh_vals, height=w, color=C_DH, alpha=0.85, label="DH LCOH")
    ax.barh(y - w / 2, hp_vals, height=w, color=C_HP, alpha=0.85, label="HP LCOH")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Spearman Rank Correlation with LCOH")
    ax.set_title(f"Parameter Sensitivity — Influence on LCOH\n{label}")
    ax.set_xlim(-1.05, 1.05)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_decision_stability(mc, cid_short, label, choice, win_fraction, n, out_path):
    if choice == "DH":
        delta = mc["lcoh_hp_eur_per_mwh"].values - mc["lcoh_dh_eur_per_mwh"].values
        winner_region_label = "DH cheaper region"
    else:
        delta = mc["lcoh_dh_eur_per_mwh"].values - mc["lcoh_hp_eur_per_mwh"].values
        winner_region_label = "HP cheaper region"

    delta_sorted = np.sort(delta)
    p = np.linspace(0, 1, len(delta_sorted))
    p05, p50, p95 = np.percentile(delta, [5, 50, 95])

    fig, ax = plt.subplots(figsize=(7, 5.5))
    xmin, xmax = delta_sorted.min() * 1.1 if delta_sorted.min() < 0 else -5, delta_sorted.max() * 1.1

    fill_from = max(0, xmin)
    ax.axvspan(0, xmax, color="#2e7d5b", alpha=0.08, label=winner_region_label)
    ax.plot(delta_sorted, p, color="#2040c0", lw=2.2, label="ΔLCOH CDF")
    ax.fill_between(delta_sorted, 0, p, color="#4050c8", alpha=0.25)

    ax.axvline(0, color="#c0392b", linestyle="--", lw=2, label="Decision boundary (ΔLCOH = 0)")
    ax.axvline(p50, color="#2e7d5b", lw=1.5, label=f"Median = {p50:.2f} €/MWh")
    ax.axvline(p05, color=C_GREY, lw=1, linestyle=":")
    ax.axvline(p95, color=C_GREY, lw=1, linestyle=":")

    ax.annotate(f"P5 = {p05:.2f}", xy=(p05, 0.05), xytext=(p05 - (xmax - xmin) * 0.18, 0.15),
                fontsize=8.5, color=C_GREY, arrowprops=dict(arrowstyle="->", color=C_GREY, lw=0.9))
    ax.annotate(f"P95 = {p95:.2f}", xy=(p95, 0.92), xytext=(p95 - (xmax - xmin) * 0.28, 0.8),
                fontsize=8.5, color=C_GREY, arrowprops=dict(arrowstyle="->", color=C_GREY, lw=0.9))
    ax.annotate(f"P50 = {p50:.2f}", xy=(p50, 0.5), xytext=(p50 + (xmax - xmin) * 0.08, 0.6),
                fontsize=8.5, color="#2e7d5b", arrowprops=dict(arrowstyle="->", color="#2e7d5b", lw=0.9))

    box_txt = (f"$\\omega_{{{choice}}}$ = {win_fraction:.2f} "
               f"({choice} wins in {int(round(win_fraction * n))} of {n} samples)\n"
               f"Median advantage: {p50:.2f} €/MWh\n"
               f"Range: [{p05:.2f}, {p95:.2f}] €/MWh")
    ax.text(0.02, 0.97, box_txt, transform=ax.transAxes, ha="left", va="top",
            fontsize=8.5, bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5e8c8",
                                     edgecolor="#b8942f", alpha=0.95))

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel(f"ΔLCOH = LCOH$_{{other}}$ − LCOH$_{{{choice}}}$ (EUR/MWh)")
    ax.set_ylabel("Cumulative Probability")
    ax.set_title(f"Decision Stability Plot for {cid_short} (N={n})\nCumulative Distribution of ΔLCOH")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p05, p50, p95


def make_slide(cid, cid_short, label, contract, result, win_fraction, n,
                p05, p50, p95, hp_feas, dh_feas, img_paths, out_path):
    choice = result.choice
    winner_full = "District Heating" if choice == "DH" else ("Heat Pumps" if choice == "HP" else "Undecided")
    winner_block = contract["district_heating"] if choice == "DH" else contract["heat_pumps"]
    loser_feas = hp_feas if choice == "DH" else dh_feas

    robust_word = "robust" if result.robust else ("sensitive" if "SENSITIVE_DECISION" in result.reason_codes else "marginal")

    fig = plt.figure(figsize=(15, 9.2))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.0, 1.55], wspace=0.06,
                            left=0.045, right=0.98, top=0.90, bottom=0.06)

    # ── Header bar ──────────────────────────────────────────────────────────
    fig.text(0.045, 0.965, "■", fontsize=13, color=C_ORANGE, fontweight="bold")
    fig.text(0.065, 0.965, "RESULTS  ·  ROBUSTNESS", fontsize=11, color=C_ORANGE,
             fontweight="bold", va="center", family="DejaVu Sans")
    title = f"Economic sensitivity: {winner_full} wins {win_fraction:.0%} of {n} cost samples ({robust_word})"
    fig.text(0.045, 0.935, title, fontsize=17, fontweight="bold", color="#1a1a1a", va="center")
    fig.plot = None
    fig.add_artist(plt.Line2D([0.045, 0.12], [0.912, 0.912], color=C_ACCENT, lw=3, transform=fig.transFigure))

    # ── Left text column ─────────────────────────────────────────────────────
    ax_text = fig.add_subplot(gs[0, 0])
    ax_text.axis("off")

    y0 = 0.90
    ax_text.text(0, y0, f"ω = {win_fraction:.2f}", fontsize=44, color=C_ACCENT,
                 fontweight="bold", transform=ax_text.transAxes, va="top")
    feas_note = "HP baseline is technically infeasible" if (choice == "DH" and not loser_feas) else (
        "DH baseline is technically infeasible" if (choice == "HP" and not loser_feas) else "both options technically feasible")
    ax_text.text(0, y0 - 0.14, f"{n} sampled comparisons · {feas_note}", fontsize=10.5,
                 color="#444", transform=ax_text.transAxes, va="top")

    rows = [
        (f"{winner_block['lcoh']['median']:.2f} €/MWh", "median " + choice + " LCOH  ·  "
         f"{winner_block['co2']['median']:.2f} kg CO₂/MWh"),
        (f"{p50:.2f} €/MWh", f"median sampled {choice} cost advantage"),
        (f"{p05:.2f} – {p95:.2f} €/MWh", "P5–P95 of the cost advantage"),
    ]
    y = y0 - 0.26
    for val, lab in rows:
        ax_text.plot([0, 1], [y + 0.045, y + 0.045], color="#ddd6c4", lw=1, transform=ax_text.transAxes)
        ax_text.text(0, y, val, fontsize=14, fontweight="bold", color="#1a1a1a",
                     transform=ax_text.transAxes, va="top")
        ax_text.text(0, y - 0.045, lab, fontsize=9.5, color="#555",
                     transform=ax_text.transAxes, va="top")
        y -= 0.16

    ax_text.plot([0, 1], [y + 0.03, y + 0.03], color="#ddd6c4", lw=1, transform=ax_text.transAxes)
    reason_txt = ", ".join(result.reason_codes)
    if choice == "DH" and not hp_feas:
        footer = ("Economic sensitivity only. The infeasible HP baseline is not a deployable ranked\n"
                  "alternative; no reinforced-grid scenario was modeled.")
    elif choice == "HP" and not dh_feas:
        footer = ("Economic sensitivity only. The infeasible DH baseline is not a deployable ranked\n"
                  "alternative.")
    else:
        footer = f"Both technologies are technically feasible here; decision rule: {reason_txt.lower()}."
    footer = "\n".join(textwrap.wrap(footer, width=58))
    ax_text.text(0, y - 0.02, footer, fontsize=8.5, color="#777", style="italic",
                 transform=ax_text.transAxes, va="top")

    at_p5_text = f"At the fifth percentile, the sampled {winner_full.lower()} cost advantage is €{p05:.2f}/MWh."
    ax_text.text(0, 0.0, at_p5_text, fontsize=10, fontweight="bold", color="#1a1a1a",
                 transform=ax_text.transAxes, va="bottom")

    # ── Right 2x2 image grid ─────────────────────────────────────────────────
    gs_imgs = gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=gs[0, 1], wspace=0.03, hspace=0.15)
    panel_labels = ["(a) LCOH distributions", "(b) Scenario-by-scenario comparison",
                    "(c) Decision stability (ΔLCOH CDF)", "(d) Parameter sensitivity"]
    for i, img_path in enumerate(img_paths):
        ax_img = fig.add_subplot(gs_imgs[i // 2, i % 2])
        img = plt.imread(img_path)
        ax_img.imshow(img)
        ax_img.axis("off")
        ax_img.set_title(panel_labels[i], fontsize=8.5, color="#333", pad=3)

    fig.text(0.6, 0.025, f"{cid_short} — {label}: economic sensitivity, distributions, sample comparisons "
                          "and uncertainty analysis.", fontsize=8, color="#888", ha="center")
    fig.text(0.045, 0.025, "Branitz Heat Decision AI", fontsize=8.5, color="#1e5f4a",
             fontweight="bold", ha="left")

    fig.savefig(out_path, dpi=170, facecolor="white")
    plt.close(fig)


def main():
    saved_slides = []
    for d in sorted((RESULTS / "economics").glob("ST*")):
        cid = d.name
        cid_short = cid.split("_")[0]
        label = cid.split("_", 1)[1].replace("_", " ").title() + f" ({cid_short})"

        cha = json.load(open(RESULTS / "cha" / cid / "cha_kpis.json"))
        dha = json.load(open(RESULTS / "dha" / cid / "dha_kpis.json"))
        econ = json.load(open(RESULTS / "economics" / cid / "economics_monte_carlo.json"))
        mc = pd.read_csv(RESULTS / "economics" / cid / "economics_monte_carlo_samples.csv")

        contract = build_kpi_contract(cid, cha, dha, econ)
        result = decide_from_contract(contract)
        choice = result.choice
        dh_feas = contract["district_heating"]["feasible"]
        hp_feas = contract["heat_pumps"]["feasible"]
        mc_block = contract.get("monte_carlo") or {}
        n = mc_block.get("n_samples", len(mc))
        win_fraction = (mc_block.get("dh_wins_fraction") if choice == "DH"
                         else mc_block.get("hp_wins_fraction") if choice == "HP" else 0.5)

        out_dir = OUT_ROOT / cid
        out_dir.mkdir(parents=True, exist_ok=True)

        p_violin = out_dir / "fig_lcoh_violin.png"
        p_scatter = out_dir / "fig_lcoh_scatter.png"
        p_tornado = out_dir / "fig_tornado.png"
        p_stability = out_dir / "fig_decision_stability.png"

        make_violin(mc, cid_short, label, p_violin)
        make_scatter(mc, cid_short, label, p_scatter)
        make_tornado(mc, cid_short, label, p_tornado)
        p05, p50, p95 = make_decision_stability(mc, cid_short, label, choice, win_fraction, n, p_stability)

        slide_path = out_dir / "slide.png"
        make_slide(cid, cid_short, label, contract, result, win_fraction, n,
                   p05, p50, p95, hp_feas, dh_feas,
                   [p_violin, p_scatter, p_stability, p_tornado], slide_path)

        saved_slides.append(slide_path)
        print(f"Done: {cid}  choice={choice}  win_fraction={win_fraction:.2%}")

    print(f"\n{len(saved_slides)} slides written under {OUT_ROOT}")


if __name__ == "__main__":
    main()
