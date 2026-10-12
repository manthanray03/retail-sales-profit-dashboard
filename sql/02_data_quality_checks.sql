-- =============================================================================
-- 02_data_quality_checks.sql
-- Every check returns one row: the check name and the number of failing rows.
-- build_database.py runs each block and stops if any check returns failures > 0.
-- Blocks are separated by "-- name:" lines so the script can run them one by one.
-- =============================================================================

-- name: no_negative_amounts
SELECT 'No negative amounts in fact_sales' AS check_name, COUNT(*) AS failures
FROM fact_sales
WHERE units_sold < 0 OR gross_sales < 0 OR markdown_amount < 0 OR net_sales < 0
   OR cogs < 0 OR return_units < 0 OR return_amount < 0;

-- name: net_equals_gross_minus_markdown
SELECT 'net_sales = gross_sales - markdown_amount' AS check_name, COUNT(*) AS failures
FROM fact_sales
WHERE ABS(gross_sales - markdown_amount - net_sales) > 0.011;

-- name: profit_equals_net_minus_cogs
SELECT 'gross_profit = net_sales - cogs' AS check_name, COUNT(*) AS failures
FROM fact_sales
WHERE ABS(net_sales - cogs - gross_profit) > 0.011;

-- name: returns_not_above_sales
SELECT 'Returns never exceed net sales on a row' AS check_name, COUNT(*) AS failures
FROM fact_sales
WHERE return_amount > net_sales;

-- name: no_sales_on_closed_day
SELECT 'No sales on Christmas Day (stores closed)' AS check_name, COUNT(*) AS failures
FROM fact_sales AS f
JOIN dim_date AS d ON d.date = f.date
WHERE COALESCE(d.holiday_event, '') = 'Christmas Day (store closed)';

-- name: complete_sales_grid
-- Every open day must have a row for every store x department x channel
SELECT 'Complete sales grid for every open day' AS check_name,
       (SELECT COUNT(*) FROM dim_date WHERE COALESCE(holiday_event, '') <> 'Christmas Day (store closed)')
       * (SELECT COUNT(*) FROM dim_store)
       * (SELECT COUNT(*) FROM dim_department)
       * (SELECT COUNT(*) FROM dim_channel)
       - (SELECT COUNT(*) FROM fact_sales) AS failures;

-- name: no_orphan_keys_in_sales
SELECT 'Every fact_sales key exists in its dimension' AS check_name, COUNT(*) AS failures
FROM fact_sales AS f
LEFT JOIN dim_date       AS d ON d.date = f.date
LEFT JOIN dim_store      AS s ON s.store_id = f.store_id
LEFT JOIN dim_department AS p ON p.department_id = f.department_id
LEFT JOIN dim_channel    AS c ON c.channel_id = f.channel_id
WHERE d.date IS NULL OR s.store_id IS NULL OR p.department_id IS NULL OR c.channel_id IS NULL;

-- name: store_day_matches_sales
SELECT 'Every store-day with sales has transactions and labour hours' AS check_name, COUNT(*) AS failures
FROM (SELECT DISTINCT date, store_id FROM fact_sales) AS f
LEFT JOIN fact_store_day AS sd ON sd.date = f.date AND sd.store_id = f.store_id
WHERE sd.store_id IS NULL OR sd.customer_transactions <= 0 OR sd.labour_hours <= 0;

-- name: resolved_not_above_contacts
SELECT 'Resolved-first-contact never exceeds contacts' AS check_name, COUNT(*) AS failures
FROM fact_service_desk
WHERE resolved_first_contact > contacts OR contacts < 0;

-- name: targets_complete
SELECT 'One target per store per month' AS check_name,
       (SELECT COUNT(DISTINCT month_start) FROM dim_date) * (SELECT COUNT(*) FROM dim_store)
       - (SELECT COUNT(*) FROM fact_targets) AS failures;
