# Data dictionary

All tables are CSV files in `data/`, loaded into SQLite by `scripts/build_database.py`
and into Power BI by following `powerbi/BUILD_GUIDE.md`. Dates are ISO format (YYYY-MM-DD).
Money is Canadian dollars.

The data is **simulated** by `scripts/generate_data.py` (fixed seed 2026). The rules used to
simulate it are listed at the end of this file.

---

## Dimensions

### dim_date (1,096 rows, one per day from 2023-01-01 to 2025-12-31)

| Column | Type | Description |
| --- | --- | --- |
| date | date | Primary key |
| year | int | Calendar year |
| quarter_num / quarter | int / text | 1-4 / Q1-Q4 |
| month_num / month_name | int / text | 1-12 / Jan-Dec |
| month_year | text | e.g. "Jan 2025"; sort by `year_month` |
| year_month | int | e.g. 202501 |
| month_start | date | First day of the month (joins to `fact_targets`) |
| iso_week | int | ISO week number |
| day_of_week_num / day_name | int / text | 1 = Monday ... 7 = Sunday / Mon-Sun |
| is_weekend | int | 1 for Saturday and Sunday |
| holiday_event | text | Black Friday, Boxing Day, Christmas Eve, Christmas Day (store closed), Canada Day, Thanksgiving Weekend, Thanksgiving Day, New Year's Day, New Year's Eve; blank otherwise |

### dim_store (8 rows)

| Column | Type | Description |
| --- | --- | --- |
| store_id | int | Primary key (101-108) |
| store_name | text | Generic location name, e.g. "Regina East" |
| city / region / province | text | City; South, Central or North Saskatchewan; SK |
| store_format | text | Supercentre or Discount Store |
| square_feet | int | Sales floor size |
| open_year | int | Year the store opened |
| latitude / longitude | decimal | Approximate, city level (for the map visual) |

### dim_department (8 rows)

| department_id | department_name | department_group |
| --- | --- | --- |
| 1 | Grocery | Food |
| 2 | Fresh Food | Food |
| 3 | Consumables | Consumables & Health |
| 4 | Health & Beauty | Consumables & Health |
| 5 | Electronics | General Merchandise |
| 6 | Home & Seasonal | General Merchandise |
| 7 | Apparel | General Merchandise |
| 8 | Toys & Sporting Goods | General Merchandise |

### dim_channel (3 rows)

| channel_id | channel_name | channel_group |
| --- | --- | --- |
| 1 | In-Store | In-Store |
| 2 | Online Pickup | Online |
| 3 | Online Delivery | Online |

---

## Facts

### fact_sales (209,856 rows)

Grain: one row per **day x store x department x channel**. Stores are closed on Christmas
Day, so that date has no rows.

| Column | Type | Description |
| --- | --- | --- |
| date, store_id, department_id, channel_id | keys | Composite primary key |
| units_sold | int | Units sold |
| gross_sales | money | Sales at ticket price, before markdowns |
| markdown_amount | money | Clearance, promotional and price-match discounts |
| net_sales | money | `gross_sales - markdown_amount` (what the customer paid) |
| cogs | money | Cost of goods sold, including picking and delivery cost on online orders |
| gross_profit | money | `net_sales - cogs` |
| return_units | int | Units returned |
| return_amount | money | Value of returns |

### fact_store_day (8,744 rows)

Grain: one row per **day x store**.

| Column | Type | Description |
| --- | --- | --- |
| date, store_id | keys | Composite primary key |
| customer_transactions | int | In-store baskets plus online orders |
| labour_hours | decimal | Scheduled associate hours (half-hour steps) |

### fact_service_desk (131,160 rows)

Grain: one row per **day x store x contact channel x contact reason**.

| Column | Type | Description |
| --- | --- | --- |
| date, store_id | keys | |
| contact_channel | text | Phone, Chat or Email |
| contact_reason | text | Product availability, Online order & delivery, Price questions, Returns & exchanges, Other |
| contacts | int | Number of customer contacts |
| resolved_first_contact | int | Contacts resolved without a follow-up |
| total_handle_minutes | decimal | Total time spent on those contacts |

### fact_targets (288 rows)

Grain: one row per **month x store**.

| Column | Type | Description |
| --- | --- | --- |
| month_start | date | First day of the month |
| store_id | int | Store |
| sales_target | money | Net sales plan, rounded to the nearest $1,000 |

---

## KPI definitions

| KPI | Formula |
| --- | --- |
| Gross margin % | gross_profit / net_sales |
| Markdown rate % | markdown_amount / gross_sales |
| Return rate % | return_amount / net_sales |
| YoY % | (this period - same period last year) / same period last year |
| Margin change (pts) | this year's gross margin % - last year's, in percentage points |
| Target attainment % | net_sales (all departments and channels) / sales_target |
| Average basket | net_sales (all departments and channels) / customer_transactions |
| Sales per labour hour | net_sales (all departments and channels) / labour_hours |
| First contact resolution % | resolved_first_contact / contacts |
| Average handle time | total_handle_minutes / contacts |

---

## How the data was simulated

These are the rules in `scripts/generate_data.py`. They are assumptions based on how a
big-box store operates, not measurements from a real retailer.

| Area | Rule |
| --- | --- |
| Store size | Each store has a size factor; the chain does about $406M in net sales in 2023 |
| Growth | About 0.8% chain growth plus department growth (Health & Beauty +7.5% a year, Electronics -0.5%) plus store growth (Saskatoon South +4%, Prince Albert -2.5%) |
| Seasonality | Monthly pattern per department: Toys and Electronics peak in Nov-Dec, Home & Seasonal in spring (garden) and December, Apparel in back-to-school |
| Weekday | Friday and Saturday are busiest; Tuesday is slowest |
| Events | Black Friday, the week before Christmas, Christmas Eve, Boxing Day, Thanksgiving weekend, Canada Day, New Year's Day; stores closed Christmas Day |
| Weather | Occasional winter storm days (Dec-Mar) cut a store's sales by about a third |
| Markdowns | Base rate per department; January clearance, July summer clearance, Black Friday and Boxing Day promotions; markdowns shrink about 7% a year |
| Costs | Cost ratio per department with a small yearly drift; online pickup +0.5 pts and delivery +1.5 pts fulfilment cost |
| Returns | Base rate per department (Apparel and Electronics highest); about double in January for general merchandise; higher for online orders |
| Online | Pickup grows from about 6.5% to 11.5% of a department's sales and delivery from 3.5% to 6.5%, adjusted by how "online" each department is |
| Labour | Hours are scheduled from planned sales but only partly follow the weekday pattern, so busy days get thinner coverage |
| Service desk | About 47 contacts per store per day; chat takes share from phone; online order contacts grow with online sales; returns contacts spike in January |
| Targets | 2023 plan is close to actuals; 2024 and 2025 plans are the prior year's monthly actuals + 4.5% |
