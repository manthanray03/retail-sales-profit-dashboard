-- =============================================================================
-- 03_kpi_analysis.sql
-- Business questions answered in SQL. build_database.py runs each block and
-- saves the result to outputs/<name>.csv and outputs/analysis_results.md.
-- These numbers are also the "answer key" for checking the Power BI measures.
--
-- Year-over-year comparisons use 2023 (first year) and 2025 (latest full year).
-- =============================================================================

-- name: yearly_kpis
-- Q: How did sales, profit and margin change year over year, and did we hit plan?
WITH yearly AS (
    SELECT d.year,
           SUM(f.net_sales)       AS net_sales,
           SUM(f.gross_sales)     AS gross_sales,
           SUM(f.markdown_amount) AS markdowns,
           SUM(f.gross_profit)    AS gross_profit,
           SUM(f.return_amount)   AS returns,
           SUM(f.units_sold)      AS units
    FROM fact_sales AS f
    JOIN dim_date   AS d ON d.date = f.date
    GROUP BY d.year
),
targets AS (
    SELECT d.year, SUM(t.sales_target) AS sales_target
    FROM fact_targets AS t
    JOIN dim_date     AS d ON d.date = t.month_start
    GROUP BY d.year
)
SELECT y.year,
       ROUND(y.net_sales, 0)                                   AS net_sales,
       ROUND(y.gross_profit, 0)                                AS gross_profit,
       ROUND(100.0 * y.gross_profit / y.net_sales, 2)          AS gross_margin_pct,
       ROUND(100.0 * y.markdowns / y.gross_sales, 2)           AS markdown_rate_pct,
       ROUND(100.0 * y.returns / y.net_sales, 2)               AS return_rate_pct,
       y.units                                                 AS units_sold,
       ROUND(100.0 * (y.net_sales / LAG(y.net_sales) OVER (ORDER BY y.year) - 1), 2)       AS net_sales_yoy_pct,
       ROUND(100.0 * (y.gross_profit / LAG(y.gross_profit) OVER (ORDER BY y.year) - 1), 2) AS gross_profit_yoy_pct,
       ROUND(100.0 * y.gross_profit / y.net_sales
             - 100.0 * LAG(y.gross_profit) OVER (ORDER BY y.year) / LAG(y.net_sales) OVER (ORDER BY y.year), 2)
                                                               AS margin_change_pts,
       ROUND(t.sales_target, 0)                                AS sales_target,
       ROUND(100.0 * y.net_sales / t.sales_target, 2)          AS target_attainment_pct
FROM yearly  AS y
JOIN targets AS t ON t.year = y.year
ORDER BY y.year;

-- name: department_performance
-- Q: Which departments drive sales and profit, and where did margin move?
WITH dept_year AS (
    SELECT p.department_name,
           p.department_group,
           d.year,
           SUM(f.net_sales)       AS net_sales,
           SUM(f.gross_profit)    AS gross_profit,
           SUM(f.gross_sales)     AS gross_sales,
           SUM(f.markdown_amount) AS markdowns,
           SUM(f.return_amount)   AS returns
    FROM fact_sales     AS f
    JOIN dim_date       AS d ON d.date = f.date
    JOIN dim_department AS p ON p.department_id = f.department_id
    GROUP BY p.department_name, p.department_group, d.year
),
pivot AS (
    SELECT department_name,
           department_group,
           SUM(CASE WHEN year = 2023 THEN net_sales END)    AS sales_2023,
           SUM(CASE WHEN year = 2025 THEN net_sales END)    AS sales_2025,
           SUM(CASE WHEN year = 2023 THEN gross_profit END) AS gp_2023,
           SUM(CASE WHEN year = 2025 THEN gross_profit END) AS gp_2025,
           SUM(CASE WHEN year = 2025 THEN gross_sales END)  AS gross_2025,
           SUM(CASE WHEN year = 2025 THEN markdowns END)    AS md_2025,
           SUM(CASE WHEN year = 2025 THEN returns END)      AS ret_2025
    FROM dept_year
    GROUP BY department_name, department_group
)
SELECT department_name,
       department_group,
       ROUND(sales_2025, 0)                                               AS net_sales_2025,
       ROUND(100.0 * sales_2025 / SUM(sales_2025) OVER (), 1)             AS sales_share_2025_pct,
       ROUND(100.0 * (sales_2025 / sales_2023 - 1), 1)                    AS sales_growth_2023_2025_pct,
       ROUND(gp_2025, 0)                                                  AS gross_profit_2025,
       ROUND(100.0 * gp_2025 / SUM(gp_2025) OVER (), 1)                   AS profit_share_2025_pct,
       ROUND(100.0 * gp_2023 / sales_2023, 2)                             AS margin_2023_pct,
       ROUND(100.0 * gp_2025 / sales_2025, 2)                             AS margin_2025_pct,
       ROUND(100.0 * gp_2025 / sales_2025 - 100.0 * gp_2023 / sales_2023, 2) AS margin_change_pts,
       ROUND(100.0 * md_2025 / gross_2025, 2)                             AS markdown_rate_2025_pct,
       ROUND(100.0 * ret_2025 / sales_2025, 2)                            AS return_rate_2025_pct
FROM pivot
ORDER BY net_sales_2025 DESC;

-- name: channel_mix
-- Q: How fast is online pickup and delivery growing, and what does it do to margin?
SELECT d.year,
       c.channel_name,
       ROUND(SUM(f.net_sales), 0)                                                     AS net_sales,
       ROUND(100.0 * SUM(f.net_sales) / SUM(SUM(f.net_sales)) OVER (PARTITION BY d.year), 2) AS share_pct,
       ROUND(100.0 * SUM(f.gross_profit) / SUM(f.net_sales), 2)                       AS gross_margin_pct,
       ROUND(100.0 * SUM(f.return_amount) / SUM(f.net_sales), 2)                      AS return_rate_pct
FROM fact_sales  AS f
JOIN dim_date    AS d ON d.date = f.date
JOIN dim_channel AS c ON c.channel_id = f.channel_id
GROUP BY d.year, c.channel_id, c.channel_name
ORDER BY d.year, c.channel_id;

-- name: store_scorecard_2025
-- Q: Which stores beat plan in 2025, and how productive is each one?
WITH sales AS (
    SELECT f.store_id, d.year, SUM(f.net_sales) AS net_sales, SUM(f.gross_profit) AS gross_profit
    FROM fact_sales AS f
    JOIN dim_date   AS d ON d.date = f.date
    GROUP BY f.store_id, d.year
),
ops AS (
    SELECT sd.store_id, d.year,
           SUM(sd.customer_transactions) AS transactions,
           SUM(sd.labour_hours)          AS labour_hours
    FROM fact_store_day AS sd
    JOIN dim_date       AS d ON d.date = sd.date
    GROUP BY sd.store_id, d.year
),
tgt AS (
    SELECT t.store_id, d.year, SUM(t.sales_target) AS sales_target
    FROM fact_targets AS t
    JOIN dim_date     AS d ON d.date = t.month_start
    GROUP BY t.store_id, d.year
)
SELECT s.store_name,
       s.city,
       s.region,
       ROUND(cur.net_sales, 0)                                 AS net_sales_2025,
       ROUND(100.0 * (cur.net_sales / prev.net_sales - 1), 2)  AS net_sales_yoy_pct,
       ROUND(100.0 * cur.gross_profit / cur.net_sales, 2)      AS gross_margin_pct,
       ROUND(t.sales_target, 0)                                AS sales_target_2025,
       ROUND(100.0 * cur.net_sales / t.sales_target, 1)        AS target_attainment_pct,
       ROUND(cur.net_sales / o.transactions, 2)                AS avg_basket,
       ROUND(cur.net_sales / o.labour_hours, 2)                AS sales_per_labour_hour
FROM dim_store AS s
JOIN sales AS cur  ON cur.store_id  = s.store_id AND cur.year  = 2025
JOIN sales AS prev ON prev.store_id = s.store_id AND prev.year = 2024
JOIN ops   AS o    ON o.store_id    = s.store_id AND o.year    = 2025
JOIN tgt   AS t    ON t.store_id    = s.store_id AND t.year    = 2025
ORDER BY target_attainment_pct DESC;

-- name: target_attainment_by_year
-- Q: Is a store's miss a one-off or a trend?
WITH monthly AS (
    SELECT f.store_id, d.month_start, SUM(f.net_sales) AS net_sales
    FROM fact_sales AS f
    JOIN dim_date   AS d ON d.date = f.date
    GROUP BY f.store_id, d.month_start
),
joined AS (
    SELECT m.store_id, CAST(substr(m.month_start, 1, 4) AS INTEGER) AS year,
           m.net_sales, t.sales_target
    FROM monthly AS m
    JOIN fact_targets AS t ON t.store_id = m.store_id AND t.month_start = m.month_start
)
SELECT s.store_name,
       ROUND(100.0 * SUM(CASE WHEN j.year = 2023 THEN j.net_sales END)
                   / SUM(CASE WHEN j.year = 2023 THEN j.sales_target END), 1) AS attainment_2023_pct,
       ROUND(100.0 * SUM(CASE WHEN j.year = 2024 THEN j.net_sales END)
                   / SUM(CASE WHEN j.year = 2024 THEN j.sales_target END), 1) AS attainment_2024_pct,
       ROUND(100.0 * SUM(CASE WHEN j.year = 2025 THEN j.net_sales END)
                   / SUM(CASE WHEN j.year = 2025 THEN j.sales_target END), 1) AS attainment_2025_pct,
       SUM(CASE WHEN j.year = 2025 AND j.net_sales < j.sales_target THEN 1 ELSE 0 END) AS months_below_plan_2025
FROM joined AS j
JOIN dim_store AS s ON s.store_id = j.store_id
GROUP BY s.store_name
ORDER BY attainment_2025_pct DESC;

-- name: monthly_trend
-- Q: What does the year look like month by month? (feeds the trend chart)
WITH m AS (
    SELECT d.year, d.month_num, d.month_name, d.year_month,
           SUM(f.net_sales)       AS net_sales,
           SUM(f.gross_profit)    AS gross_profit,
           SUM(f.gross_sales)     AS gross_sales,
           SUM(f.markdown_amount) AS markdowns
    FROM fact_sales AS f
    JOIN dim_date   AS d ON d.date = f.date
    GROUP BY d.year, d.month_num, d.month_name, d.year_month
)
SELECT year, month_num, month_name, year_month,
       ROUND(net_sales, 0)                           AS net_sales,
       ROUND(gross_profit, 0)                        AS gross_profit,
       ROUND(100.0 * gross_profit / net_sales, 2)    AS gross_margin_pct,
       ROUND(100.0 * markdowns / gross_sales, 2)     AS markdown_rate_pct
FROM m
ORDER BY year_month;

-- name: january_clearance_effect
-- Q: How much do clearance markdowns and post-holiday returns cost in January?
SELECT d.month_num,
       d.month_name,
       ROUND(100.0 * SUM(CASE WHEN p.department_group = 'General Merchandise' THEN f.markdown_amount END)
                   / SUM(CASE WHEN p.department_group = 'General Merchandise' THEN f.gross_sales END), 2)
                                                                   AS gm_markdown_rate_pct,
       ROUND(100.0 * SUM(CASE WHEN p.department_group = 'General Merchandise' THEN f.return_amount END)
                   / SUM(CASE WHEN p.department_group = 'General Merchandise' THEN f.net_sales END), 2)
                                                                   AS gm_return_rate_pct,
       ROUND(100.0 * SUM(f.gross_profit) / SUM(f.net_sales), 2)    AS total_gross_margin_pct
FROM fact_sales     AS f
JOIN dim_date       AS d ON d.date = f.date
JOIN dim_department AS p ON p.department_id = f.department_id
GROUP BY d.month_num, d.month_name
ORDER BY d.month_num;

-- name: event_day_lift
-- Q: How much bigger are Black Friday, Christmas Eve and Boxing Day than a normal day?
-- Lift = chain net sales that day / average for the same weekday in the same month (non-event days).
WITH day_sales AS (
    SELECT date, SUM(net_sales) AS net_sales
    FROM fact_sales
    GROUP BY date
),
baseline AS (
    SELECT d.year, d.month_num, d.day_of_week_num, AVG(ds.net_sales) AS avg_net_sales
    FROM day_sales AS ds
    JOIN dim_date  AS d ON d.date = ds.date
    WHERE COALESCE(d.holiday_event, '') = ''
    GROUP BY d.year, d.month_num, d.day_of_week_num
)
SELECT d.holiday_event,
       d.year,
       d.date,
       d.day_name,
       ROUND(ds.net_sales, 0)                AS chain_net_sales,
       ROUND(b.avg_net_sales, 0)             AS normal_same_weekday,
       ROUND(ds.net_sales / b.avg_net_sales, 2) AS lift_x
FROM day_sales AS ds
JOIN dim_date  AS d ON d.date = ds.date
JOIN baseline  AS b ON b.year = d.year AND b.month_num = d.month_num AND b.day_of_week_num = d.day_of_week_num
WHERE d.holiday_event IN ('Black Friday', 'Christmas Eve', 'Boxing Day')
ORDER BY d.holiday_event, d.year;

-- name: weekday_productivity_2025
-- Q: Are we staffed for the days customers actually shop?
WITH store_day AS (
    SELECT date, store_id, SUM(net_sales) AS net_sales
    FROM fact_sales
    GROUP BY date, store_id
)
SELECT d.day_of_week_num,
       d.day_name,
       ROUND(AVG(sd.net_sales), 0)                                      AS avg_net_sales_per_store,
       ROUND(AVG(o.customer_transactions), 0)                           AS avg_transactions_per_store,
       ROUND(AVG(o.labour_hours), 1)                                    AS avg_labour_hours_per_store,
       ROUND(SUM(sd.net_sales) / SUM(o.labour_hours), 2)                AS sales_per_labour_hour,
       ROUND(1.0 * SUM(o.customer_transactions) / SUM(o.labour_hours), 2) AS transactions_per_labour_hour
FROM store_day      AS sd
JOIN fact_store_day AS o ON o.date = sd.date AND o.store_id = sd.store_id
JOIN dim_date       AS d ON d.date = sd.date
WHERE d.year = 2025
GROUP BY d.day_of_week_num, d.day_name
ORDER BY d.day_of_week_num;

-- name: service_desk_yearly
-- Q: How busy is the customer service desk and how well are contacts resolved?
WITH desk AS (
    SELECT d.year,
           SUM(sv.contacts)               AS contacts,
           SUM(sv.resolved_first_contact) AS resolved,
           SUM(sv.total_handle_minutes)   AS minutes
    FROM fact_service_desk AS sv
    JOIN dim_date          AS d ON d.date = sv.date
    GROUP BY d.year
),
txns AS (
    SELECT d.year, SUM(sd.customer_transactions) AS transactions
    FROM fact_store_day AS sd
    JOIN dim_date       AS d ON d.date = sd.date
    GROUP BY d.year
)
SELECT desk.year,
       desk.contacts,
       ROUND(100.0 * desk.resolved / desk.contacts, 2)       AS first_contact_resolution_pct,
       ROUND(desk.minutes / desk.contacts, 2)                AS avg_handle_minutes,
       ROUND(1000.0 * desk.contacts / txns.transactions, 2)  AS contacts_per_1000_transactions
FROM desk
JOIN txns ON txns.year = desk.year
ORDER BY desk.year;

-- name: service_desk_by_reason
-- Q: Why do customers contact the desk, and which reasons are hardest to resolve?
SELECT sv.contact_reason,
       SUM(CASE WHEN d.year = 2023 THEN sv.contacts END) AS contacts_2023,
       SUM(CASE WHEN d.year = 2025 THEN sv.contacts END) AS contacts_2025,
       ROUND(100.0 * (1.0 * SUM(CASE WHEN d.year = 2025 THEN sv.contacts END)
                          / SUM(CASE WHEN d.year = 2023 THEN sv.contacts END) - 1), 1) AS growth_pct,
       ROUND(100.0 * SUM(CASE WHEN d.year = 2025 THEN sv.resolved_first_contact END)
                   / SUM(CASE WHEN d.year = 2025 THEN sv.contacts END), 1)            AS fcr_2025_pct,
       ROUND(SUM(CASE WHEN d.year = 2025 THEN sv.total_handle_minutes END)
             / SUM(CASE WHEN d.year = 2025 THEN sv.contacts END), 2)                  AS avg_handle_minutes_2025
FROM fact_service_desk AS sv
JOIN dim_date          AS d ON d.date = sv.date
GROUP BY sv.contact_reason
ORDER BY contacts_2025 DESC;

-- name: service_desk_by_channel
-- Q: Is chat taking volume from the phone line?
SELECT d.year,
       sv.contact_channel,
       SUM(sv.contacts)                                                                  AS contacts,
       ROUND(100.0 * SUM(sv.contacts) / SUM(SUM(sv.contacts)) OVER (PARTITION BY d.year), 1) AS share_pct,
       ROUND(100.0 * SUM(sv.resolved_first_contact) / SUM(sv.contacts), 1)               AS fcr_pct,
       ROUND(SUM(sv.total_handle_minutes) / SUM(sv.contacts), 2)                          AS avg_handle_minutes
FROM fact_service_desk AS sv
JOIN dim_date          AS d ON d.date = sv.date
GROUP BY d.year, sv.contact_channel
ORDER BY d.year, contacts DESC;
