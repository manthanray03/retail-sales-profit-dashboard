"""
make_charts.py
--------------
Draws the README charts from the SQL results in outputs/.
Run build_database.py first.

Run:  python scripts/make_charts.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from matplotlib.transforms import offset_copy  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
IMG_DIR = ROOT / "images"

# Colours (validated colour-blind-safe palette; same values as powerbi/theme.json)
SURFACE = "#FCFCFB"
INK = "#0B0B0B"
INK_2 = "#52514E"
MUTED = "#898781"
GRID = "#E1E0D9"
AXIS = "#C3C2B7"
BLUE_LIGHT = "#86B6EF"   # older year
BLUE_MID = "#2A78D6"
BLUE_DARK = "#104281"    # latest year
RED = "#D03B3B"
YEAR_COLOURS = {2023: BLUE_LIGHT, 2024: BLUE_MID, 2025: BLUE_DARK}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 10,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "legend.frameon": False,
    "legend.labelcolor": INK_2,
})


def millions(x, _=None):
    return f"${x / 1e6:,.0f}M"


def style_axis(ax, grid_axis="y"):
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    if grid_axis == "y":
        ax.spines["left"].set_visible(False)
    else:
        ax.spines["bottom"].set_visible(False)


def save(fig, name, title, subtitle):
    """Title and subtitle sit above the plot area at a fixed distance, whatever the figure height."""
    fig.text(0.012, 1.0, title, ha="left", va="bottom", fontsize=13, fontweight="bold", color=INK,
             transform=offset_copy(fig.transFigure, fig=fig, y=0.12, units="inches"))
    fig.text(0.012, 1.0, subtitle, ha="left", va="bottom", fontsize=9.5, color=INK_2,
             transform=offset_copy(fig.transFigure, fig=fig, y=-0.12, units="inches"))
    fig.savefig(IMG_DIR / name, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"  images/{name}")


def chart_yearly(yearly: pd.DataFrame):
    """Small multiples: net sales, gross profit, gross margin by year."""
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), gridspec_kw={"wspace": 0.35})
    fig.subplots_adjust(top=0.78)
    years = yearly["year"].astype(str)
    colours = [YEAR_COLOURS[y] for y in yearly["year"]]

    for ax, col, title in [(axes[0], "net_sales", "Net sales"), (axes[1], "gross_profit", "Gross profit")]:
        bars = ax.bar(years, yearly[col], width=0.5, color=colours)
        ax.set_title(title)
        ax.yaxis.set_major_formatter(FuncFormatter(millions))
        style_axis(ax)
        for bar, v in zip(bars, yearly[col]):
            ax.text(bar.get_x() + bar.get_width() / 2, v, f"${v / 1e6:,.1f}M", ha="center", va="bottom",
                    fontsize=9, color=INK, fontweight="bold")
        ax.set_ylim(0, yearly[col].max() * 1.15)

    ax = axes[2]
    ax.plot(years, yearly["gross_margin_pct"], color=BLUE_DARK, linewidth=2, marker="o", markersize=8,
            markeredgecolor=SURFACE, markeredgewidth=2, solid_capstyle="round")
    for x, v in zip(years, yearly["gross_margin_pct"]):
        ax.text(x, v + 0.09, f"{v:.1f}%", ha="center", va="bottom", fontsize=9, color=INK, fontweight="bold")
    ax.set_title("Gross margin")
    ax.set_ylim(yearly["gross_margin_pct"].min() - 0.6, yearly["gross_margin_pct"].max() + 0.6)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}%"))
    style_axis(ax)

    first, last = yearly.iloc[0], yearly.iloc[-1]
    save(fig, "sales_profit_by_year.png", "Sales and profit grew every year, and margin widened",
         f"Net sales +{100 * (last.net_sales / first.net_sales - 1):.1f}% and gross profit "
         f"+{100 * (last.gross_profit / first.gross_profit - 1):.1f}% from {int(first.year)} to {int(last.year)}; "
         f"margin up {last.gross_margin_pct - first.gross_margin_pct:.2f} pts")


def chart_monthly(monthly: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    fig.subplots_adjust(top=0.80)
    for year, grp in monthly.groupby("year"):
        ax.plot(grp["month_name"], grp["net_sales"], color=YEAR_COLOURS[year], linewidth=2,
                marker="o", markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.5,
                solid_capstyle="round", label=str(year))
    ax.yaxis.set_major_formatter(FuncFormatter(millions))
    ax.set_xlim(-0.3, 11.3)
    ax.set_ylim(20e6, monthly["net_sales"].max() * 1.08)
    style_axis(ax)
    ax.legend(loc="upper left", ncol=3, handlelength=1.6)
    peak = monthly.loc[monthly["net_sales"].idxmax()]
    by_month = monthly.pivot(index="month_num", columns="year", values="net_sales")
    every_month_up = bool((by_month.diff(axis=1).iloc[:, 1:] > 0).all().all())
    title = ("Each year beat the year before in every single month" if every_month_up
             else "Monthly net sales by year")
    save(fig, "monthly_sales_trend.png", title,
         f"Monthly net sales; December peaks at ${peak.net_sales / 1e6:,.1f}M ({int(peak.year)}), "
         "February is the low point every year")


def chart_department_margin(dept: pd.DataFrame):
    d = dept.sort_values("margin_2025_pct")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.subplots_adjust(top=0.82)
    y = range(len(d))
    ax.hlines(y, d["margin_2023_pct"], d["margin_2025_pct"], color=AXIS, linewidth=2)
    ax.scatter(d["margin_2023_pct"], y, s=70, color=BLUE_LIGHT, edgecolor=SURFACE, linewidth=2,
               zorder=3, label="2023")
    ax.scatter(d["margin_2025_pct"], y, s=70, color=BLUE_DARK, edgecolor=SURFACE, linewidth=2,
               zorder=3, label="2025")
    for yi, (_, r) in zip(y, d.iterrows()):
        ax.text(r["margin_2025_pct"] + 0.8, yi, f"{r['margin_2025_pct']:.1f}%  ({r['margin_change_pts']:+.2f} pts)",
                va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(list(y))
    ax.set_yticklabels(d["department_name"])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlim(10, d["margin_2025_pct"].max() + 9)
    style_axis(ax, grid_axis="x")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    save(fig, "department_margin_change.png", "Margin improved in seven of eight departments",
         "Gross margin % by department, 2023 vs 2025. Grocery held flat; Apparel and Home & Seasonal gained most")


def chart_store_vs_plan(stores: pd.DataFrame):
    s = stores.sort_values("target_attainment_pct")
    gap = s["target_attainment_pct"] - 100
    fig, ax = plt.subplots(figsize=(10, 4.4))
    fig.subplots_adjust(top=0.82)
    colours = [BLUE_MID if g >= 0 else RED for g in gap]
    ax.barh(s["store_name"], gap, height=0.5, color=colours)
    ax.axvline(0, color=INK_2, linewidth=1)
    for name, g, sales_gap in zip(s["store_name"], gap, s["net_sales_2025"] - s["sales_target_2025"]):
        label = f"{g:+.1f} pts  ({'+' if sales_gap >= 0 else '-'}${abs(sales_gap) / 1e6:,.2f}M)"
        ax.text(g + (0.12 if g >= 0 else -0.12), name, label, va="center",
                ha="left" if g >= 0 else "right", fontsize=8.5, color=INK_2)
    lim = max(abs(gap.min()), gap.max()) + 2.2
    ax.set_xlim(-lim, lim)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} pts"))
    style_axis(ax, grid_axis="x")
    best, worst = s.iloc[-1], s.iloc[0]
    save(fig, "store_target_attainment.png",
         f"{best.store_name} beat plan by {best.target_attainment_pct - 100:.1f} pts; "
         f"{worst.store_name} missed by {100 - worst.target_attainment_pct:.1f} pts",
         f"2025 net sales vs plan by store; {int((gap >= 0).sum())} of {len(s)} stores reached 100% of target")


def chart_weekday(week: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    fig.subplots_adjust(top=0.80)
    top = week["sales_per_labour_hour"].max()
    colours = [BLUE_DARK if v == top else BLUE_LIGHT for v in week["sales_per_labour_hour"]]
    bars = ax.bar(week["day_name"], week["sales_per_labour_hour"], width=0.5, color=colours)
    for bar, v in zip(bars, week["sales_per_labour_hour"]):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 2, f"${v:,.0f}", ha="center", va="bottom",
                fontsize=9, color=INK)
    ax.set_ylim(0, top * 1.15)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    style_axis(ax)
    low = week.loc[week["sales_per_labour_hour"].idxmin()]
    hi = week.loc[week["sales_per_labour_hour"].idxmax()]
    save(fig, "weekday_productivity.png", "Saturdays carry the most sales per labour hour",
         f"2025 sales per labour hour by weekday; {hi.day_name} runs "
         f"{100 * (hi.sales_per_labour_hour / low.sales_per_labour_hour - 1):.0f}% above {low.day_name}")


def chart_service_desk(reasons: pd.DataFrame):
    r = reasons.sort_values("contacts_2025")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.0), gridspec_kw={"wspace": 0.55})
    fig.subplots_adjust(top=0.78)
    y = range(len(r))
    h = 0.34
    ax1.barh([i + h / 2 for i in y], r["contacts_2023"], height=h, color=BLUE_LIGHT, label="2023")
    ax1.barh([i - h / 2 for i in y], r["contacts_2025"], height=h, color=BLUE_DARK, label="2025")
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(r["contact_reason"])
    ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    ax1.set_title("Contacts by reason")
    ax1.legend(loc="lower right")
    style_axis(ax1, grid_axis="x")
    online = r[r["contact_reason"] == "Online order & delivery"].iloc[0]
    ax1.text(online["contacts_2025"] + 600, list(r["contact_reason"]).index("Online order & delivery") - h / 2,
             f"+{online['growth_pct']:.0f}%", va="center", fontsize=9, color=INK, fontweight="bold")
    ax1.set_xlim(0, r["contacts_2025"].max() * 1.22)

    f = reasons.sort_values("fcr_2025_pct", ascending=False)
    colours = [RED if v == f["fcr_2025_pct"].min() else BLUE_LIGHT for v in f["fcr_2025_pct"]]
    ax2.barh(f["contact_reason"], f["fcr_2025_pct"], height=0.5, color=colours)
    for name, v in zip(f["contact_reason"], f["fcr_2025_pct"]):
        ax2.text(v + 1, name, f"{v:.1f}%", va="center", fontsize=9, color=INK)
    ax2.set_xlim(0, 100)
    ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.set_title("First contact resolution, 2025")
    style_axis(ax2, grid_axis="x")
    save(fig, "service_desk_reasons.png", "Online order contacts are growing fastest and are hardest to resolve",
         f"Online order & delivery contacts +{online['growth_pct']:.0f}% since 2023, with the lowest "
         f"first-contact resolution ({online['fcr_2025_pct']:.1f}%)")


def main():
    IMG_DIR.mkdir(exist_ok=True)
    print("Saving charts")
    chart_yearly(pd.read_csv(OUT_DIR / "yearly_kpis.csv"))
    chart_monthly(pd.read_csv(OUT_DIR / "monthly_trend.csv"))
    chart_department_margin(pd.read_csv(OUT_DIR / "department_performance.csv"))
    chart_store_vs_plan(pd.read_csv(OUT_DIR / "store_scorecard_2025.csv"))
    chart_weekday(pd.read_csv(OUT_DIR / "weekday_productivity_2025.csv"))
    chart_service_desk(pd.read_csv(OUT_DIR / "service_desk_by_reason.csv"))


if __name__ == "__main__":
    main()
