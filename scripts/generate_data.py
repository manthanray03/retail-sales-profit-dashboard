"""
generate_data.py
----------------
Builds the simulated retail dataset behind the dashboard.

The data is synthetic, but the rules that shape it come from how a big-box
store actually runs: department mix, seasonality, weekend traffic, Black Friday
and Boxing Day spikes, January clearance markdowns, post-holiday returns, the
growth of online pickup and delivery, and the calls that land on the customer
service desk.

A fixed random seed means every run produces exactly the same CSV files, so the
numbers in the README and in powerbi/expected_values.md always match.

Run:  python scripts/generate_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
START = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2025-12-31")
BASE_DAILY_NET_SALES = 155_000  # average daily net sales of a "size 1.0" store in Jan 2023

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
# store_id, store_name, city, region, format, square_feet, open_year, lat, lon,
# size factor (sales scale), extra yearly growth vs the chain
STORES = [
    (101, "Regina East", "Regina", "South", "Supercentre", 168000, 2006, 50.4470, -104.5330, 1.20, 0.000),
    (102, "Regina Northwest", "Regina", "South", "Supercentre", 152000, 2011, 50.4930, -104.6690, 1.05, 0.005),
    (103, "Saskatoon East", "Saskatoon", "Central", "Supercentre", 160000, 2008, 52.1270, -106.5770, 1.15, 0.010),
    (104, "Saskatoon South", "Saskatoon", "Central", "Supercentre", 145000, 2019, 52.0860, -106.6170, 0.95, 0.040),
    (105, "Moose Jaw", "Moose Jaw", "South", "Supercentre", 130000, 2007, 50.4170, -105.5040, 0.70, -0.005),
    (106, "Prince Albert", "Prince Albert", "North", "Supercentre", 135000, 2005, 53.1850, -105.7440, 0.75, -0.025),
    (107, "Swift Current", "Swift Current", "South", "Discount Store", 110000, 2004, 50.2900, -107.7700, 0.55, 0.000),
    (108, "Yorkton", "Yorkton", "Central", "Discount Store", 115000, 2009, 51.2240, -102.4400, 0.60, -0.010),
]

# department_id, name, group, sales share, cost ratio (COGS / gross sales),
# yearly cost-ratio drift, base markdown rate, base return rate,
# average unit price (Jan 2023), yearly price inflation, yearly volume growth,
# online propensity (multiplies pickup and delivery share)
DEPARTMENTS = [
    (1, "Grocery", "Food", 0.24, 0.765, 0.0010, 0.020, 0.004, 4.20, 0.030, 0.040, 1.20),
    (2, "Fresh Food", "Food", 0.16, 0.720, 0.0000, 0.040, 0.006, 5.60, 0.030, 0.045, 0.80),
    (3, "Consumables", "Consumables & Health", 0.15, 0.720, -0.0030, 0.025, 0.010, 7.50, 0.025, 0.035, 1.25),
    (4, "Health & Beauty", "Consumables & Health", 0.09, 0.640, -0.0040, 0.030, 0.015, 9.00, 0.020, 0.075, 0.90),
    (5, "Electronics", "General Merchandise", 0.12, 0.840, -0.0020, 0.035, 0.055, 62.00, 0.010, -0.005, 1.30),
    (6, "Home & Seasonal", "General Merchandise", 0.10, 0.600, -0.0030, 0.060, 0.035, 18.00, 0.010, 0.030, 0.90),
    (7, "Apparel", "General Merchandise", 0.08, 0.550, -0.0020, 0.080, 0.065, 16.00, 0.010, 0.020, 1.00),
    (8, "Toys & Sporting Goods", "General Merchandise", 0.06, 0.630, -0.0020, 0.050, 0.030, 21.00, 0.010, 0.010, 1.10),
]

CHANNELS = [
    (1, "In-Store", "In-Store"),
    (2, "Online Pickup", "Online"),
    (3, "Online Delivery", "Online"),
]

# Monthly seasonality (Jan..Dec) for each department, normalised to mean 1 below
SEASONALITY = np.array([
    [0.93, 0.90, 0.97, 0.98, 1.00, 1.01, 1.02, 1.01, 0.98, 1.02, 1.03, 1.14],  # Grocery
    [0.92, 0.90, 0.96, 0.99, 1.03, 1.06, 1.07, 1.06, 1.00, 1.02, 0.98, 1.10],  # Fresh Food
    [0.97, 0.94, 0.99, 0.99, 1.00, 1.00, 1.01, 1.03, 1.02, 1.00, 1.00, 1.05],  # Consumables
    [0.95, 0.93, 0.98, 0.98, 1.00, 1.00, 1.00, 1.01, 0.99, 0.99, 1.05, 1.17],  # Health & Beauty
    [0.80, 0.78, 0.86, 0.86, 0.90, 0.92, 0.94, 1.08, 1.04, 0.95, 1.35, 1.55],  # Electronics
    [0.68, 0.72, 0.92, 1.20, 1.45, 1.28, 1.02, 0.88, 0.84, 1.08, 1.12, 1.38],  # Home & Seasonal
    [0.76, 0.74, 0.92, 0.98, 1.02, 1.00, 0.98, 1.28, 1.08, 0.98, 1.06, 1.22],  # Apparel
    [0.62, 0.64, 0.80, 0.88, 1.02, 1.12, 1.10, 0.98, 0.84, 0.92, 1.38, 1.82],  # Toys & Sporting
])
SEASONALITY = SEASONALITY / SEASONALITY.mean(axis=1, keepdims=True)

# Day of week (Mon..Sun): Friday and Saturday are the busiest days
DOW = np.array([0.88, 0.85, 0.90, 0.97, 1.12, 1.25, 1.03])
DOW = DOW / DOW.mean()

GM = [4, 5, 6, 7]          # 0-based positions of the general merchandise departments
FOOD = [0, 1]
CONS_HEALTH = [2, 3]


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def nth_weekday(year: int, month: int, weekday: int, n: int) -> pd.Timestamp:
    """n-th given weekday (Mon=0) of a month."""
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 7 * (n - 1))


def holiday_events(years) -> dict:
    """Date -> event name for the retail events used in the data."""
    events = {}
    for y in years:
        black_friday = nth_weekday(y, 11, 3, 4) + pd.Timedelta(days=1)  # day after 4th Thursday
        thanksgiving = nth_weekday(y, 10, 0, 2)                           # Canadian Thanksgiving
        events[pd.Timestamp(y, 1, 1)] = "New Year's Day"
        events[pd.Timestamp(y, 7, 1)] = "Canada Day"
        events[thanksgiving - pd.Timedelta(days=2)] = "Thanksgiving Weekend"
        events[thanksgiving - pd.Timedelta(days=1)] = "Thanksgiving Weekend"
        events[thanksgiving] = "Thanksgiving Day"
        events[black_friday] = "Black Friday"
        events[pd.Timestamp(y, 12, 24)] = "Christmas Eve"
        events[pd.Timestamp(y, 12, 25)] = "Christmas Day (store closed)"
        events[pd.Timestamp(y, 12, 26)] = "Boxing Day"
        events[pd.Timestamp(y, 12, 31)] = "New Year's Eve"
    return events


def build_dim_date() -> pd.DataFrame:
    dates = pd.date_range(START, END, freq="D")
    events = holiday_events(range(START.year, END.year + 1))
    df = pd.DataFrame({"date": dates})
    df["year"] = df["date"].dt.year
    df["quarter_num"] = df["date"].dt.quarter
    df["quarter"] = "Q" + df["quarter_num"].astype(str)
    df["month_num"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.strftime("%b")
    df["month_year"] = df["date"].dt.strftime("%b %Y")
    df["year_month"] = df["year"] * 100 + df["month_num"]
    df["month_start"] = df["date"].dt.to_period("M").dt.start_time
    df["iso_week"] = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_week_num"] = df["date"].dt.dayofweek + 1  # 1 = Monday
    df["day_name"] = df["date"].dt.strftime("%a")
    df["is_weekend"] = (df["day_of_week_num"] >= 6).astype(int)
    df["holiday_event"] = df["date"].map(events).fillna("")
    return df


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
def event_multipliers(dates: pd.DatetimeIndex, n_dept: int) -> np.ndarray:
    """Sales multiplier for each (day, department) from retail events."""
    m = np.ones((len(dates), n_dept))
    idx = {d: i for i, d in enumerate(dates)}

    def apply(day, food, cons, hb, elec, home, app, toys):
        if day in idx:
            m[idx[day]] *= np.array([food, food, cons, hb, elec, home, app, toys])

    for y in range(START.year, END.year + 1):
        bf = nth_weekday(y, 11, 3, 4) + pd.Timedelta(days=1)
        tg = nth_weekday(y, 10, 0, 2)
        apply(bf, 1.15, 1.30, 1.30, 3.20, 2.00, 1.90, 2.60)                         # Black Friday
        apply(bf + pd.Timedelta(days=1), 1.05, 1.15, 1.15, 1.80, 1.40, 1.40, 1.60)  # Saturday after
        for k in range(1, 5):                                                       # Black Friday week
            apply(bf - pd.Timedelta(days=k), 1.00, 1.05, 1.05, 1.15, 1.10, 1.10, 1.15)
        for k in range(18, 24):                                                     # last week before Christmas
            apply(pd.Timestamp(y, 12, k), 1.15, 1.05, 1.15, 1.15, 1.05, 1.10, 1.30)
        apply(pd.Timestamp(y, 12, 24), 1.45, 1.10, 1.25, 1.10, 1.00, 1.10, 1.25)    # Christmas Eve
        apply(pd.Timestamp(y, 12, 26), 0.90, 1.10, 1.20, 2.40, 1.80, 1.90, 1.50)    # Boxing Day
        apply(pd.Timestamp(y, 12, 31), 1.25, 0.90, 0.90, 0.85, 0.85, 0.85, 0.85)    # New Year's Eve
        apply(pd.Timestamp(y, 1, 1), 0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55)      # New Year's Day
        apply(pd.Timestamp(y, 7, 1), 0.95, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85)      # Canada Day
        apply(tg - pd.Timedelta(days=2), 1.30, 1.05, 1.00, 1.00, 1.05, 1.00, 1.00)  # Thanksgiving Sat
        apply(tg - pd.Timedelta(days=1), 1.25, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00)  # Thanksgiving Sun
        apply(tg, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.85)                         # Thanksgiving Mon
        for d in pd.date_range(pd.Timestamp(y, 8, 15), pd.Timestamp(y, 9, 5)):      # back to school
            apply(d, 1.00, 1.05, 1.00, 1.12, 1.00, 1.18, 1.00)
    return m


def markdown_month_factor(month: np.ndarray) -> np.ndarray:
    """Markdown multiplier per (day, department). January clearance hits GM hardest."""
    gm = np.array([1.90, 1.40, 1.00, 0.90, 0.90, 1.00, 1.35, 1.10, 1.00, 0.95, 1.25, 0.95])
    other = np.array([1.15, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.05, 1.10])
    f = np.empty((len(month), 8))
    f[:, :4] = other[month - 1][:, None]
    f[:, 4:] = gm[month - 1][:, None]
    return f


def return_month_factor(month: np.ndarray) -> np.ndarray:
    """Return-rate multiplier per (day, department). Post-holiday returns land in January."""
    gm = np.array([1.90, 1.20, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.10])
    other = np.array([1.10, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00])
    f = np.empty((len(month), 8))
    f[:, :4] = other[month - 1][:, None]
    f[:, 4:] = gm[month - 1][:, None]
    return f


def build_sales(dim_date: pd.DataFrame):
    open_days = dim_date.loc[dim_date["holiday_event"] != "Christmas Day (store closed)", "date"]
    dates = pd.DatetimeIndex(open_days)
    n_d, n_s, n_p, n_c = len(dates), len(STORES), len(DEPARTMENTS), len(CHANNELS)

    month = dates.month.values
    dow = dates.dayofweek.values
    yrs = ((dates - START).days.values / 365.25)[:, None, None]       # years since start
    t = ((dates - START).days.values / (END - START).days)[:, None, None]

    size = np.array([s[9] for s in STORES])[None, :, None]
    store_growth = np.array([s[10] for s in STORES])[None, :, None]
    share = np.array([d[3] for d in DEPARTMENTS])[None, None, :]
    cost_ratio0 = np.array([d[4] for d in DEPARTMENTS])
    cost_drift = np.array([d[5] for d in DEPARTMENTS])
    md_base = np.array([d[6] for d in DEPARTMENTS])
    ret_base = np.array([d[7] for d in DEPARTMENTS])
    price0 = np.array([d[8] for d in DEPARTMENTS])
    inflation = np.array([d[9] for d in DEPARTMENTS])
    dept_growth = np.array([d[10] for d in DEPARTMENTS])[None, None, :]
    online_prop = np.array([d[11] for d in DEPARTMENTS])

    season = SEASONALITY.T[month - 1][:, None, :]                    # (d, 1, p)
    dow_f = DOW[dow][:, None, None]
    events = event_multipliers(dates, n_p)[:, None, :]
    growth = ((1 + 0.008) * (1 + dept_growth) * (1 + store_growth)) ** yrs

    # Store-day shock: local traffic swings plus the odd winter storm day
    store_day = rng.lognormal(0.0, 0.04, size=(n_d, n_s))
    winter = np.isin(month, [12, 1, 2, 3])[:, None]
    storm = (rng.random((n_d, n_s)) < 0.012) & winter
    store_day = np.where(storm, store_day * 0.65, store_day)[:, :, None]

    noise = rng.lognormal(0.0, 0.05, size=(n_d, n_s, n_p))
    expected = BASE_DAILY_NET_SALES * size * share * season * dow_f * events * growth
    dept_net = expected * store_day * noise                          # (d, s, p)

    # Channel split: online pickup and delivery grow steadily over the three years
    pickup = (0.065 + 0.050 * t) * online_prop[None, None, :] * rng.lognormal(0, 0.10, (n_d, n_s, n_p))
    delivery = (0.035 + 0.030 * t) * online_prop[None, None, :] * rng.lognormal(0, 0.12, (n_d, n_s, n_p))
    instore = 1.0 - pickup - delivery
    split = np.stack([instore, pickup, delivery], axis=-1)            # (d, s, p, c)
    net = dept_net[..., None] * split

    # Markdowns (incl. clearance and promo pricing) shrink ~7% a year as planning improves
    md_rate = md_base[None, :] * markdown_month_factor(month)
    black_fridays = [nth_weekday(y, 11, 3, 4) + pd.Timedelta(days=1) for y in range(START.year, END.year + 1)]
    bf_mask = np.asarray(dates.isin(black_fridays))
    bd_mask = (dates.month == 12) & (dates.day == 26)
    md_rate[np.ix_(bf_mask, GM)] *= 2.2
    md_rate[np.ix_(bd_mask, GM)] *= 2.0
    md_rate = md_rate[:, None, :, None] * (1 - 0.07 * yrs[..., None])
    md_rate = md_rate * rng.lognormal(0, 0.08, net.shape)
    md_rate = np.clip(md_rate, 0.0, 0.45)

    gross = net / (1 - md_rate)
    markdown = gross - net

    # Cost of goods: online orders carry picking/fulfilment cost
    channel_cost = np.array([0.0, 0.005, 0.015])[None, None, None, :]
    cost_ratio = (cost_ratio0[None, None, :, None] + cost_drift[None, None, :, None] * yrs[..., None]
                  + channel_cost)
    cost_ratio = cost_ratio * rng.lognormal(0, 0.006, net.shape)
    cogs = gross * cost_ratio

    # Units sold
    price = price0[None, None, :, None] * (1 + inflation[None, None, :, None]) ** yrs[..., None]
    units = net / (price * rng.lognormal(0, 0.03, net.shape))

    # Returns
    channel_ret = np.array([1.00, 1.10, 1.35])[None, None, None, :]
    ret_rate = ret_base[None, None, :, None] * return_month_factor(month)[:, None, :, None] * channel_ret
    ret_rate = ret_rate * rng.lognormal(0, 0.15, net.shape)

    # Flatten to a table
    d_idx, s_idx, p_idx, c_idx = np.meshgrid(
        np.arange(n_d), np.arange(n_s), np.arange(n_p), np.arange(n_c), indexing="ij"
    )
    net_r = np.round(net, 2).ravel()
    markdown_r = np.round(markdown, 2).ravel()
    cogs_r = np.round(cogs, 2).ravel()
    units_r = np.maximum(1, np.round(units)).astype(int).ravel()
    ret_units = np.round(units.ravel() * ret_rate.ravel()).astype(int)
    ret_amount = np.round(net.ravel() * ret_rate.ravel(), 2)

    fact = pd.DataFrame({
        "date": dates.values[d_idx.ravel()],
        "store_id": np.array([s[0] for s in STORES])[s_idx.ravel()],
        "department_id": np.array([d[0] for d in DEPARTMENTS])[p_idx.ravel()],
        "channel_id": np.array([c[0] for c in CHANNELS])[c_idx.ravel()],
        "units_sold": units_r,
        "gross_sales": np.round(net_r + markdown_r, 2),
        "markdown_amount": markdown_r,
        "net_sales": net_r,
        "cogs": cogs_r,
        "gross_profit": np.round(net_r - cogs_r, 2),
        "return_units": ret_units,
        "return_amount": ret_amount,
    })

    # Expected (noise-free) store-day sales, used to plan labour hours
    planned_sales = (BASE_DAILY_NET_SALES * size * share * season * events * growth).sum(axis=2)  # (d, s)
    return fact, dates, planned_sales


# ---------------------------------------------------------------------------
# Store-day operations: transactions and labour hours
# ---------------------------------------------------------------------------
def build_store_day(fact: pd.DataFrame, dates: pd.DatetimeIndex, planned_sales: np.ndarray) -> pd.DataFrame:
    totals = (fact.groupby(["date", "store_id"], sort=True)["net_sales"].sum()
              .unstack("store_id").reindex(dates))
    store_ids = [s[0] for s in STORES]
    totals = totals[store_ids].values                                   # (d, s)

    month = dates.month.values
    dow = dates.dayofweek.values
    yrs = ((dates - START).days.values / 365.25)[:, None]

    basket_month = np.array([0.96, 0.97, 0.99, 1.00, 1.01, 1.01, 1.01, 1.02, 1.00, 1.00, 1.05, 1.10])
    basket_dow = np.array([0.98, 0.96, 0.98, 0.99, 1.02, 1.06, 1.03])
    basket = (64.0 * (1.025 ** yrs) * basket_month[month - 1][:, None] * basket_dow[dow][:, None]
              * rng.lognormal(0, 0.03, totals.shape))
    transactions = np.round(totals / basket).astype(int)

    # Labour is scheduled ahead from planned sales and only partly follows the
    # weekday pattern, so busy days end up with thinner coverage per dollar of sales.
    size = np.array([s[9] for s in STORES])[None, :]
    base_hours = 1150.0 * size
    planned_ratio = planned_sales / planned_sales.mean(axis=0, keepdims=True)
    dow_cover = (0.70 + 0.30 * DOW[dow])[:, None]
    productivity = 1.0 / (1.0 + 0.025 * yrs)
    hours = base_hours * (0.55 + 0.45 * planned_ratio) * dow_cover * productivity
    hours = hours * rng.lognormal(0, 0.02, hours.shape)
    hours = np.round(hours * 2) / 2                                     # half-hour steps

    out = pd.DataFrame({
        "date": np.repeat(dates.values, len(store_ids)),
        "store_id": np.tile(store_ids, len(dates)),
        "customer_transactions": transactions.ravel(),
        "labour_hours": hours.ravel(),
    })
    return out


# ---------------------------------------------------------------------------
# Customer service desk contacts
# ---------------------------------------------------------------------------
def build_service_desk(dates: pd.DatetimeIndex) -> pd.DataFrame:
    store_ids = [s[0] for s in STORES]
    size = np.array([s[9] for s in STORES])
    channels = ["Phone", "Chat", "Email"]
    reasons = ["Product availability", "Online order & delivery", "Price questions",
               "Returns & exchanges", "Other"]

    n_d, n_s = len(dates), len(store_ids)
    month = dates.month.values
    dow = dates.dayofweek.values
    yrs = (dates - START).days.values / 365.25
    t = (dates - START).days.values / (END - START).days

    month_f = np.array([1.25, 1.00, 0.98, 0.97, 0.98, 0.98, 0.97, 1.00, 0.98, 1.00, 1.12, 1.35])
    dow_f = np.array([1.08, 1.00, 0.98, 0.98, 1.04, 1.02, 0.90])
    volume = (48.0 * size[None, :] ** 0.8 * month_f[month - 1][:, None] * dow_f[dow][:, None]
              * (1.03 ** yrs)[:, None])                                 # (d, s)

    # Chat takes share from phone over time
    phone = 0.66 - 0.08 * t
    chat = 0.16 + 0.08 * t
    email = np.full(n_d, 0.18)
    ch_share = np.stack([phone, chat, email], axis=1)                   # (d, 3)

    # Online-order contacts grow with online sales; returns spike after the holidays
    online_growth = (0.10 + 0.08 * t) / 0.10
    returns_f = np.where(month == 1, 1.8, np.where(month == 2, 1.2, 1.0))
    r_share = np.stack([
        np.full(n_d, 0.32), 0.20 * online_growth, np.full(n_d, 0.18), 0.18 * returns_f, np.full(n_d, 0.12)
    ], axis=1)
    r_share = r_share / r_share.sum(axis=1, keepdims=True)              # (d, 5)

    lam = volume[:, :, None, None] * ch_share[:, None, :, None] * r_share[:, None, None, :]
    contacts = rng.poisson(lam)

    fcr_channel = np.array([0.80, 0.74, 0.66])
    fcr_reason = np.array([0.06, -0.12, 0.04, -0.02, -0.04])
    fcr = (fcr_channel[None, None, :, None] + fcr_reason[None, None, None, :]
           + 0.015 * yrs[:, None, None, None])
    fcr = np.clip(fcr, 0.05, 0.98)
    resolved = rng.binomial(contacts, np.broadcast_to(fcr, contacts.shape))

    aht_channel = np.array([5.5, 8.0, 10.5])
    aht_reason = np.array([0.85, 1.40, 0.80, 1.20, 1.00])
    aht = (aht_channel[None, None, :, None] * aht_reason[None, None, None, :]
           * (1 - 0.02 * yrs)[:, None, None, None])
    minutes = np.round(contacts * aht * rng.lognormal(0, 0.08, contacts.shape), 1)

    d_idx, s_idx, c_idx, r_idx = np.meshgrid(
        np.arange(n_d), np.arange(n_s), np.arange(3), np.arange(5), indexing="ij"
    )
    return pd.DataFrame({
        "date": dates.values[d_idx.ravel()],
        "store_id": np.array(store_ids)[s_idx.ravel()],
        "contact_channel": np.array(channels)[c_idx.ravel()],
        "contact_reason": np.array(reasons)[r_idx.ravel()],
        "contacts": contacts.ravel(),
        "resolved_first_contact": resolved.ravel(),
        "total_handle_minutes": minutes.ravel(),
    })


# ---------------------------------------------------------------------------
# Monthly sales targets (plan = last year's actual + 4.5%)
# ---------------------------------------------------------------------------
def build_targets(fact: pd.DataFrame) -> pd.DataFrame:
    monthly = fact.assign(month_start=fact["date"].dt.to_period("M").dt.start_time)
    monthly = monthly.groupby(["month_start", "store_id"], as_index=False)["net_sales"].sum()
    monthly["year"] = monthly["month_start"].dt.year
    monthly["month"] = monthly["month_start"].dt.month

    rows = []
    lookup = monthly.set_index(["year", "month", "store_id"])["net_sales"]
    for _, r in monthly.iterrows():
        if r["year"] == START.year:
            # No 2022 actuals in this dataset, so the first year's plan sits close to actuals
            target = r["net_sales"] * rng.uniform(0.985, 1.035)
        else:
            target = lookup[(r["year"] - 1, r["month"], r["store_id"])] * 1.045
        rows.append((r["month_start"], r["store_id"], round(target, -3)))
    return pd.DataFrame(rows, columns=["month_start", "store_id", "sales_target"])


# ---------------------------------------------------------------------------
def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    dim_date = build_dim_date()
    dim_store = pd.DataFrame(
        [s[:9] for s in STORES],
        columns=["store_id", "store_name", "city", "region", "store_format", "square_feet",
                 "open_year", "latitude", "longitude"],
    )
    dim_store.insert(4, "province", "SK")
    dim_department = pd.DataFrame(
        [d[:3] for d in DEPARTMENTS], columns=["department_id", "department_name", "department_group"]
    )
    dim_channel = pd.DataFrame(CHANNELS, columns=["channel_id", "channel_name", "channel_group"])

    fact_sales, dates, planned = build_sales(dim_date)
    fact_store_day = build_store_day(fact_sales, dates, planned)
    fact_service_desk = build_service_desk(dates)
    fact_targets = build_targets(fact_sales)

    date_fmt = "%Y-%m-%d"
    tables = {
        "dim_date": dim_date,
        "dim_store": dim_store,
        "dim_department": dim_department,
        "dim_channel": dim_channel,
        "fact_sales": fact_sales,
        "fact_store_day": fact_store_day,
        "fact_service_desk": fact_service_desk,
        "fact_targets": fact_targets,
    }
    for name, df in tables.items():
        df.to_csv(DATA_DIR / f"{name}.csv", index=False, date_format=date_fmt)
        print(f"{name:<18} {len(df):>9,} rows")


if __name__ == "__main__":
    main()
