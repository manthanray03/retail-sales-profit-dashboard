-- =============================================================================
-- 01_schema.sql
-- Star schema for the retail sales & profit dashboard (SQLite).
--
-- Four dimensions (date, store, department, channel) and four fact tables:
--   fact_sales         daily sales by store x department x channel
--   fact_store_day     daily customer transactions and labour hours by store
--   fact_service_desk  daily customer service desk contacts by store x channel x reason
--   fact_targets       monthly net sales target by store
--
-- Money is stored as REAL because SQLite has no DECIMAL type; in SQL Server or
-- PostgreSQL these columns would be DECIMAL(12,2).
-- =============================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_targets;
DROP TABLE IF EXISTS fact_service_desk;
DROP TABLE IF EXISTS fact_store_day;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_channel;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_date;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------
CREATE TABLE dim_date (
    date             TEXT    PRIMARY KEY,          -- YYYY-MM-DD
    year             INTEGER NOT NULL,
    quarter_num      INTEGER NOT NULL,
    quarter          TEXT    NOT NULL,             -- Q1..Q4
    month_num        INTEGER NOT NULL,
    month_name       TEXT    NOT NULL,             -- Jan..Dec
    month_year       TEXT    NOT NULL,             -- Jan 2025
    year_month       INTEGER NOT NULL,             -- 202501 (sort key for month_year)
    month_start      TEXT    NOT NULL,             -- first day of the month
    iso_week         INTEGER NOT NULL,
    day_of_week_num  INTEGER NOT NULL,             -- 1 = Monday
    day_name         TEXT    NOT NULL,             -- Mon..Sun
    is_weekend       INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    holiday_event    TEXT                          -- Black Friday, Boxing Day, ... (blank otherwise)
);

CREATE TABLE dim_store (
    store_id      INTEGER PRIMARY KEY,
    store_name    TEXT    NOT NULL UNIQUE,
    city          TEXT    NOT NULL,
    region        TEXT    NOT NULL,                -- South / Central / North Saskatchewan
    province      TEXT    NOT NULL,
    store_format  TEXT    NOT NULL,                -- Supercentre / Discount Store
    square_feet   INTEGER NOT NULL,
    open_year     INTEGER NOT NULL,
    latitude      REAL    NOT NULL,                -- approximate, city level
    longitude     REAL    NOT NULL
);

CREATE TABLE dim_department (
    department_id     INTEGER PRIMARY KEY,
    department_name   TEXT    NOT NULL UNIQUE,
    department_group  TEXT    NOT NULL             -- Food / Consumables & Health / General Merchandise
);

CREATE TABLE dim_channel (
    channel_id     INTEGER PRIMARY KEY,
    channel_name   TEXT    NOT NULL UNIQUE,        -- In-Store / Online Pickup / Online Delivery
    channel_group  TEXT    NOT NULL                -- In-Store / Online
);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------
CREATE TABLE fact_sales (
    date             TEXT    NOT NULL REFERENCES dim_date (date),
    store_id         INTEGER NOT NULL REFERENCES dim_store (store_id),
    department_id    INTEGER NOT NULL REFERENCES dim_department (department_id),
    channel_id       INTEGER NOT NULL REFERENCES dim_channel (channel_id),
    units_sold       INTEGER NOT NULL,
    gross_sales      REAL    NOT NULL,             -- ticket price before markdowns
    markdown_amount  REAL    NOT NULL,             -- clearance, promo and price-match discounts
    net_sales        REAL    NOT NULL,             -- gross_sales - markdown_amount
    cogs             REAL    NOT NULL,             -- cost of goods sold (incl. online fulfilment)
    gross_profit     REAL    NOT NULL,             -- net_sales - cogs
    return_units     INTEGER NOT NULL,
    return_amount    REAL    NOT NULL,
    PRIMARY KEY (date, store_id, department_id, channel_id)
);

CREATE TABLE fact_store_day (
    date                   TEXT    NOT NULL REFERENCES dim_date (date),
    store_id               INTEGER NOT NULL REFERENCES dim_store (store_id),
    customer_transactions  INTEGER NOT NULL,       -- in-store baskets + online orders
    labour_hours           REAL    NOT NULL,       -- scheduled associate hours
    PRIMARY KEY (date, store_id)
);

CREATE TABLE fact_service_desk (
    date                    TEXT    NOT NULL REFERENCES dim_date (date),
    store_id                INTEGER NOT NULL REFERENCES dim_store (store_id),
    contact_channel         TEXT    NOT NULL,      -- Phone / Chat / Email
    contact_reason          TEXT    NOT NULL,
    contacts                INTEGER NOT NULL,
    resolved_first_contact  INTEGER NOT NULL,
    total_handle_minutes    REAL    NOT NULL,
    PRIMARY KEY (date, store_id, contact_channel, contact_reason)
);

CREATE TABLE fact_targets (
    month_start   TEXT    NOT NULL REFERENCES dim_date (date),
    store_id      INTEGER NOT NULL REFERENCES dim_store (store_id),
    sales_target  REAL    NOT NULL,                -- monthly net sales plan
    PRIMARY KEY (month_start, store_id)
);

-- Indexes for the joins and filters the analysis uses most
CREATE INDEX ix_sales_store       ON fact_sales (store_id);
CREATE INDEX ix_sales_department  ON fact_sales (department_id);
CREATE INDEX ix_sales_channel     ON fact_sales (channel_id);
CREATE INDEX ix_desk_reason       ON fact_service_desk (contact_reason);
