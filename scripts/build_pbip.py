"""
build_pbip.py
-------------
Generates the Power BI Project (PBIP) for the dashboard:

  powerbi/Retail_Sales_Profit_Dashboard.pbip                 open this in Power BI Desktop
  powerbi/Retail_Sales_Profit_Dashboard.SemanticModel/       data model in TMDL
  powerbi/Retail_Sales_Profit_Dashboard.Report/              4 report pages in PBIR

The model is built from the CSV headers in data/ and the measures in
powerbi/measures.dax, so the DAX lives in one place. Re-run this script after
changing measures.dax or the report layout below.

PBIP is Microsoft's text format for Power BI files. Power BI Desktop opens it
like a .pbix, and File > Save As turns it into a .pbix.

Run:  python scripts/build_pbip.py
"""

import json
import re
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PBI_DIR = ROOT / "powerbi"
NAME = "Retail_Sales_Profit_Dashboard"
SM_DIR = PBI_DIR / f"{NAME}.SemanticModel"
RP_DIR = PBI_DIR / f"{NAME}.Report"

# Default location of the CSV files on the Windows machine running Power BI.
# Change it in Power BI with Home > Transform data > Edit parameters.
DEFAULT_DATA_FOLDER = "C:\\retail-sales-profit-dashboard\\data\\"

MEASURE_TABLE = "_Measures"
THEME_FILE = "RetailPerformance-7c41d2e9.json"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
UUID_NS = uuid.UUID("6f1c2b8e-3d4a-4e5f-9a7b-1c2d3e4f5a6b")  # deterministic ids between runs

TABLES = ["dim_date", "dim_store", "dim_department", "dim_channel",
          "fact_sales", "fact_store_day", "fact_service_desk", "fact_targets"]

# ---------------------------------------------------------------------------
# Column typing rules
# ---------------------------------------------------------------------------
DATE_COLUMNS = {"date", "month_start"}
INT_COLUMNS = {"year", "quarter_num", "month_num", "year_month", "iso_week", "day_of_week_num",
               "is_weekend", "store_id", "square_feet", "open_year", "department_id", "channel_id",
               "units_sold", "return_units", "customer_transactions", "contacts",
               "resolved_first_contact"}
MONEY_COLUMNS = {"gross_sales", "markdown_amount", "net_sales", "cogs", "gross_profit",
                 "return_amount", "sales_target"}
DOUBLE_COLUMNS = {"labour_hours", "total_handle_minutes", "latitude", "longitude"}
KEY_COLUMNS = {"store_id", "department_id", "channel_id", "date", "month_start"}

SORT_BY = {"month_name": "month_num", "month_year": "year_month",
           "day_name": "day_of_week_num", "quarter": "quarter_num"}
DATA_CATEGORY = {"latitude": "Latitude", "longitude": "Longitude", "city": "City",
                 "province": "StateOrProvince"}
HIDDEN_DIM_COLUMNS = {"store_id", "department_id", "channel_id", "quarter_num", "month_num",
                      "year_month", "day_of_week_num"}

FORMATS = {
    "Currency, 0 decimals": r"\$#,0;(\$#,0);\$#,0",
    "Currency, 2 decimals": r"\$#,0.00;(\$#,0.00);\$#,0.00",
    "Percentage, 1 decimal": "0.0%;-0.0%;0.0%",
    "Whole number, thousands separator": "#,0",
    "Whole number": "0",
    "Decimal number, 0 decimals, thousands separator": "#,0",
    "Decimal number, 1 decimal": "0.0",
    "Decimal number, 2 decimals": "0.00",
}


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(UUID_NS, "|".join(parts)))


def quote_name(name: str) -> str:
    """TMDL object name, quoted when it has spaces or special characters."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    return "'" + name.replace("'", "''") + "'"


def quote_value(value: str) -> str:
    """TMDL text property value; quoted (with doubled quotes) when it contains quotes."""
    if '"' in value or value != value.strip():
        return '"' + value.replace('"', '""') + '"'
    return value


# ---------------------------------------------------------------------------
# Measures from measures.dax
# ---------------------------------------------------------------------------
def parse_measures(path: Path) -> list[dict]:
    measures, folder, fmt = [], "", None
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        folder_match = re.match(r"//\s*Display folder:\s*(.+)$", line)
        format_match = re.match(r"//\s*\[Format:\s*(.+)\]\s*$", line)
        start = re.match(r"^([A-Za-z][^=/]*?)\s=\s?(.*)$", line)
        if folder_match:
            folder = folder_match.group(1).strip()
        elif format_match:
            fmt = format_match.group(1).strip()
        elif start and not line.startswith((" ", "\t")):
            name, first = start.group(1).strip(), start.group(2)
            body = [first] if first.strip() else []
            i += 1
            while i < len(lines) and lines[i].strip():
                body.append(lines[i])
                i += 1
            measures.append({"name": name, "expression": body, "format": fmt, "folder": folder})
            fmt = None
            continue
        i += 1
    return measures


def format_string(fmt: str | None) -> str | None:
    if fmt is None:
        return None
    if fmt.startswith("Custom"):
        return fmt[len("Custom"):].strip()
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format in measures.dax: {fmt}")
    return FORMATS[fmt]


# ---------------------------------------------------------------------------
# Semantic model (TMDL)
# ---------------------------------------------------------------------------
def column_spec(table: str, column: str) -> dict:
    is_fact = table.startswith("fact_")
    if column in DATE_COLUMNS:
        spec = {"dataType": "dateTime", "m": "type date", "formatString": "yyyy-mm-dd",
                "summarizeBy": "none", "annotation": "UnderlyingDateTimeDataType = Date"}
    elif column in INT_COLUMNS:
        spec = {"dataType": "int64", "m": "Int64.Type", "formatString": "0",
                "summarizeBy": "none" if (column in KEY_COLUMNS or not is_fact) else "sum"}
    elif column in MONEY_COLUMNS:
        spec = {"dataType": "decimal", "m": "Currency.Type",
                "formatString": r"\$#,0.00;(\$#,0.00);\$#,0.00", "summarizeBy": "sum"}
    elif column in DOUBLE_COLUMNS:
        spec = {"dataType": "double", "m": "type number",
                "summarizeBy": "none" if column in ("latitude", "longitude") else "sum"}
    else:
        spec = {"dataType": "string", "m": "type text", "summarizeBy": "none"}

    spec["isHidden"] = (is_fact and column not in ("contact_channel", "contact_reason")) or \
                       (not is_fact and column in HIDDEN_DIM_COLUMNS)
    spec["isKey"] = table == "dim_date" and column == "date"
    spec["sortByColumn"] = SORT_BY.get(column) if table == "dim_date" else None
    spec["dataCategory"] = DATA_CATEGORY.get(column) if table == "dim_store" else None
    return spec


def csv_columns(table: str) -> list[str]:
    with open(DATA_DIR / f"{table}.csv", encoding="utf-8") as f:
        return f.readline().strip().split(",")


def m_partition(table: str, columns: list[str], specs: dict) -> list[str]:
    types = ", ".join(f'{{"{c}", {specs[c]["m"]}}}' for c in columns)
    return [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        '    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),',
        f'    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{{types}}}, "en-US")',
        "in",
        '    #"Changed Type"',
    ]


def table_tmdl(table: str) -> str:
    columns = csv_columns(table)
    specs = {c: column_spec(table, c) for c in columns}
    out = [f"table {table}"]
    if table == "dim_date":
        out.append("\tdataCategory: Time")
    out.append("")
    for c in columns:
        s = specs[c]
        out.append(f"\tcolumn {quote_name(c)}")
        out.append(f"\t\tdataType: {s['dataType']}")
        if s["isHidden"]:
            out.append("\t\tisHidden")
        if s["isKey"]:
            out.append("\t\tisKey")
        if s.get("formatString"):
            out.append(f"\t\tformatString: {quote_value(s['formatString'])}")
        if s["dataCategory"]:
            out.append(f"\t\tdataCategory: {s['dataCategory']}")
        out.append(f"\t\tsummarizeBy: {s['summarizeBy']}")
        out.append(f"\t\tsourceColumn: {c}")
        if s["sortByColumn"]:
            out.append(f"\t\tsortByColumn: {quote_name(s['sortByColumn'])}")
        if s.get("annotation"):
            out += ["", f"\t\tannotation {s['annotation']}"]
        out.append("")
    out.append(f"\tpartition {table} = m")
    out.append("\t\tmode: import")
    out.append("\t\tsource =")
    out += ["\t\t\t" + line for line in m_partition(table, columns, specs)]
    out.append("")
    return "\n".join(out) + "\n"


def measures_table_tmdl(measures: list[dict]) -> str:
    out = [f"table {MEASURE_TABLE}", ""]
    for m in measures:
        expr = m["expression"]
        if len(expr) == 1:
            out.append(f"\tmeasure {quote_name(m['name'])} = {expr[0].strip()}")
        else:
            out.append(f"\tmeasure {quote_name(m['name'])} = ```")
            out += ["\t\t\t" + line.rstrip() for line in expr]
            out.append("\t\t\t```")
        fs = format_string(m["format"])
        if fs:
            out.append(f"\t\tformatString: {quote_value(fs)}")
        if m["folder"]:
            out.append(f'\t\tdisplayFolder: "{m["folder"]}"')
        out.append("")
    out += [
        "\tcolumn Value",
        "\t\tdataType: string",
        "\t\tisHidden",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: Value",
        "",
        f"\tpartition {MEASURE_TABLE} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\tlet",
        "\t\t\t    Source = #table(type table [Value = text], {})",
        "\t\t\tin",
        "\t\t\t    Source",
        "",
    ]
    return "\n".join(out) + "\n"


RELATIONSHIPS = [
    ("fact_sales", "date", "dim_date", "date"),
    ("fact_store_day", "date", "dim_date", "date"),
    ("fact_service_desk", "date", "dim_date", "date"),
    ("fact_targets", "month_start", "dim_date", "date"),
    ("fact_sales", "store_id", "dim_store", "store_id"),
    ("fact_store_day", "store_id", "dim_store", "store_id"),
    ("fact_service_desk", "store_id", "dim_store", "store_id"),
    ("fact_targets", "store_id", "dim_store", "store_id"),
    ("fact_sales", "department_id", "dim_department", "department_id"),
    ("fact_sales", "channel_id", "dim_channel", "channel_id"),
]


def write_semantic_model(measures: list[dict]) -> None:
    definition = SM_DIR / "definition"
    (definition / "tables").mkdir(parents=True)

    write_json(SM_DIR / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {"qnaEnabled": False},
    })
    write_text(definition / "database.tmdl", "database\n\tcompatibilityLevel: 1702\n")

    all_tables = TABLES + [MEASURE_TABLE]
    query_order = json.dumps(["DataFolder"] + all_tables)
    model = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        f"annotation PBI_QueryOrder = {query_order}",
        "",
        *[f"ref table {quote_name(t)}" for t in all_tables],
        "",
    ]
    write_text(definition / "model.tmdl", "\n".join(model))

    write_text(definition / "expressions.tmdl",
               f'expression DataFolder = "{DEFAULT_DATA_FOLDER}" '
               'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
               "\tannotation PBI_ResultType = Text\n")

    rels = []
    for from_t, from_c, to_t, to_c in RELATIONSHIPS:
        rels += [f"relationship {stable_id(from_t, from_c, to_t, to_c)}",
                 f"\tfromColumn: {from_t}.{quote_name(from_c)}",
                 f"\ttoColumn: {to_t}.{quote_name(to_c)}", ""]
    write_text(definition / "relationships.tmdl", "\n".join(rels))

    for t in TABLES:
        write_text(definition / "tables" / f"{t}.tmdl", table_tmdl(t))
    write_text(definition / "tables" / f"{MEASURE_TABLE}.tmdl", measures_table_tmdl(measures))


# ---------------------------------------------------------------------------
# Report (PBIR)
# ---------------------------------------------------------------------------
def lit(value) -> dict:
    """PBIR literal expression: strings in single quotes, numbers as D (double)."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, (int, float)):
        v = f"{value}D"
    else:
        v = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def column_field(table: str, column: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def measure_field(measure: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": measure}}


def col(table: str, column: str, display: str | None = None, category: bool = False) -> dict:
    p = {"field": column_field(table, column), "queryRef": f"{table}.{column}", "nativeQueryRef": column}
    if display:
        p["displayName"] = display
    if category:
        p["active"] = True  # only on cartesian Category roles
    return p


def mea(measure: str, display: str | None = None) -> dict:
    p = {"field": measure_field(measure), "queryRef": f"{MEASURE_TABLE}.{measure}", "nativeQueryRef": measure}
    if display:
        p["displayName"] = display
    return p


class Page:
    def __init__(self, name: str, display: str, subtitle: str):
        self.name, self.display, self.subtitle = name, display, subtitle
        self.visuals: list[dict] = []
        self.interactions: list[dict] = []
        self._z = 0

    def add(self, name: str, x, y, w, h, visual: dict, title: str | None = None) -> str:
        self._z += 1000
        visual.setdefault("drillFilterOtherVisuals", True)
        vco = visual.setdefault("visualContainerObjects", {})
        if title:
            vco["title"] = [{"properties": {"show": lit(True), "text": lit(title)}}]
        if not vco:
            del visual["visualContainerObjects"]
        self.visuals.append({
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/2.1.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "z": self._z, "height": h, "width": w, "tabOrder": self._z},
            "visual": visual,
        })
        return name

    def no_filter(self, source: str, *targets: str) -> None:
        self.interactions += [{"source": source, "target": t, "type": "NoFilter"} for t in targets]


def textbox(text: str, size: int, color: str, bold: bool = False) -> dict:
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [{
        "textRuns": [{"value": text, "textStyle": {
            "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI",
            "fontSize": f"{size}pt", "color": color}}]}]}}]}}


def slicer(table: str, column: str, display: str, sync: str | None, default: int | None = None) -> dict:
    v = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [col(table, column, display)]}}},
        "objects": {
            "data": [{"properties": {"mode": lit("Dropdown")}}],
            "header": [{"properties": {"show": lit(True), "text": lit(display)}}],
        },
        "visualContainerObjects": {"padding": [{"properties": {
            "top": lit(8), "bottom": lit(8), "left": lit(8), "right": lit(8)}}]},
    }
    if default is not None:
        # Pre-select one value (the latest year) and allow a single selection,
        # so year-over-year measures compare one year with the one before it
        v["objects"]["selection"] = [{"properties": {"singleSelect": lit(True)}}]
        v["objects"]["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "d", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": column}}],
                "Values": [[{"Literal": {"Value": f"{default}L"}}]],
            }}}],
        }}}}]
    if sync:
        v["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    return v


def kpi_card(measures: list[str]) -> dict:
    return {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [mea(m) for m in measures]}}},
        "objects": {
            "layout": [{"properties": {"columnCount": {"expr": {"Literal": {"Value": f"{len(measures)}L"}}},
                                       "style": lit("Cards"), "alignment": lit("middle")}}],
            "value": [{"properties": {"fontSize": lit(22)}, "selector": {"id": "default"}}],
            "label": [{"properties": {"fontSize": lit(10)}, "selector": {"id": "default"}}],
        },
    }


def chart(visual_type: str, category: dict, y: list[dict], series: dict | None = None,
          sort: tuple | None = None, labels: bool = False, categorical_axis: bool = False) -> dict:
    query_state = {"Category": {"projections": [category]}, "Y": {"projections": y}}
    if series:
        query_state["Series"] = {"projections": [series]}
    query = {"queryState": query_state}
    if sort:
        field, direction = sort
        query["sortDefinition"] = {"sort": [{"field": field, "direction": direction}], "isDefaultSort": False}
    objects = {}
    if labels:
        objects["labels"] = [{"properties": {"show": lit(True)}}]
    if categorical_axis:
        objects["categoryAxis"] = [{"properties": {"axisType": lit("Categorical")}}]
    v = {"visualType": visual_type, "query": query}
    if objects:
        v["objects"] = objects
    return v


def table_visual(visual_type: str, roles: dict, sort: tuple | None = None) -> dict:
    query = {"queryState": {role: {"projections": p} for role, p in roles.items()}}
    if sort:
        field, direction = sort
        query["sortDefinition"] = {"sort": [{"field": field, "direction": direction}], "isDefaultSort": False}
    return {"visualType": visual_type, "query": query, "objects": {"columnHeaders": [{"properties": {
        "columnAdjustment": lit("growToFit"), "autoSizeColumnWidth": lit(True)}}]}}


SUBTITLE = "Simulated data for 8 Saskatchewan stores, 2023 to 2025"
LATEST_YEAR = 2025
INK, INK_2 = "#0B0B0B", "#52514E"


def header(page: Page, slicers: list[tuple]) -> dict:
    """Title, subtitle and up to three slicers along the top. Returns slicer names by label."""
    page.add(f"{page.name}_title", 16, 10, 600, 40, textbox(page.display, 20, INK, bold=True))
    page.add(f"{page.name}_subtitle", 16, 50, 600, 28, textbox(page.subtitle, 11, INK_2))
    names = {}
    x = 1264 - 200 * len(slicers) - 8 * (len(slicers) - 1)
    for label, table, column, sync in slicers:
        key = re.sub(r"\W+", "_", label.lower())
        default = LATEST_YEAR if (table, column) == ("dim_date", "year") else None
        names[label] = page.add(f"{page.name}_slicer_{key}", x, 8, 200, 80,
                                slicer(table, column, label, sync, default))
        x += 208
    return names


def build_pages() -> list[Page]:
    year = ("Year", "dim_date", "year", "year")
    store = ("Store", "dim_store", "store_name", "store")
    channel = ("Channel", "dim_channel", "channel_name", "channel")
    month = col("dim_date", "month_name", "Month", category=True)
    month_sort = (column_field("dim_date", "month_name"), "Ascending")
    year_axis = col("dim_date", "year", "Year", category=True)
    year_sort = (column_field("dim_date", "year"), "Ascending")
    pages = []

    # Page 1 -----------------------------------------------------------------
    p = Page("executive_overview", "Executive Overview", SUBTITLE)
    s = header(p, [year, store, channel])
    p.add("p1_kpis", 16, 100, 1248, 104, kpi_card([
        "Net Sales", "Net Sales YoY %", "Gross Profit", "Gross Margin %",
        "Gross Margin Change (pts)", "Target Attainment %", "Online Share %"]))
    p.add("p1_sales_vs_ly", 16, 216, 820, 240,
          chart("lineChart", month, [mea("Net Sales", "Net sales"), mea("Net Sales PY", "Net sales last year")],
                sort=month_sort), "Net sales vs last year by month")
    p.add("p1_sales_vs_plan", 852, 216, 412, 240,
          chart("clusteredColumnChart", month,
                [mea("Net Sales (All Depts & Channels)", "Net sales"), mea("Sales Target", "Plan")],
                sort=month_sort), "Sales vs plan by month")
    by_year = p.add("p1_sales_by_year", 16, 468, 404, 240,
                    chart("clusteredColumnChart", year_axis, [mea("Net Sales", "Net sales")], sort=year_sort,
                          labels=True, categorical_axis=True), "Net sales by year")
    margin_year = p.add("p1_margin_by_year", 436, 468, 404, 240,
                        chart("lineChart", year_axis, [mea("Gross Margin %", "Gross margin")], sort=year_sort,
                              labels=True, categorical_axis=True), "Gross margin by year")
    mix_year = p.add("p1_channel_mix", 856, 468, 408, 240,
                     chart("hundredPercentStackedColumnChart", year_axis, [mea("Net Sales", "Net sales")],
                           series=col("dim_channel", "channel_name", "Channel"), sort=year_sort,
                           categorical_axis=True), "Channel mix by year")
    p.no_filter(s["Year"], by_year, margin_year, mix_year)
    pages.append(p)

    # Page 2 -----------------------------------------------------------------
    p = Page("departments", "Department Performance", SUBTITLE)
    s = header(p, [year, store, channel])
    p.add("p2_matrix", 16, 100, 1248, 296, table_visual("pivotTable", {
        "Rows": [col("dim_department", "department_name", "Department")],
        "Values": [mea(m) for m in ["Net Sales", "Net Sales YoY %", "Department Share %", "Gross Profit",
                                    "Gross Margin %", "Gross Margin Change (pts)", "Markdown Rate %",
                                    "Return Rate %"]],
    }, sort=(measure_field("Net Sales"), "Descending")), "Department scorecard")
    dept = col("dim_department", "department_name", "Department", category=True)
    p.add("p2_margin_by_dept", 16, 408, 404, 300,
          chart("clusteredBarChart", dept, [mea("Gross Margin %", "Gross margin")],
                sort=(measure_field("Gross Margin %"), "Descending"), labels=True),
          "Gross margin by department")
    md_month = p.add("p2_markdown_by_month", 436, 408, 404, 300,
                     chart("lineChart", month, [mea("Markdown Rate %", "Markdown rate")],
                           series=col("dim_date", "year", "Year"), sort=month_sort),
                     "Markdown rate by month: January clearance spike")
    p.add("p2_channel_mix", 856, 408, 408, 300,
          chart("hundredPercentStackedBarChart", dept, [mea("Net Sales", "Net sales")],
                series=col("dim_channel", "channel_name", "Channel")), "Channel mix by department")
    p.no_filter(s["Year"], md_month)
    pages.append(p)

    # Page 3 -----------------------------------------------------------------
    p = Page("stores", "Store Performance", SUBTITLE)
    header(p, [year, ("Region", "dim_store", "region", None)])
    p.add("p3_scorecard", 16, 100, 1248, 296, table_visual("tableEx", {
        "Values": [col("dim_store", "store_name", "Store"), col("dim_store", "city", "City")] +
                  [mea(m) for m in ["Net Sales", "Net Sales YoY %", "Gross Margin %", "Sales Target",
                                    "Target Attainment %", "Average Basket", "Sales per Labour Hour"]],
    }, sort=(measure_field("Target Attainment %"), "Descending")), "Store scorecard")
    p.add("p3_attainment", 16, 408, 620, 300,
          chart("clusteredBarChart", col("dim_store", "store_name", "Store", category=True),
                [mea("Target Attainment %", "Target attainment")],
                sort=(measure_field("Target Attainment %"), "Descending"), labels=True),
          "Sales vs plan by store")
    p.add("p3_splh_weekday", 652, 408, 612, 300,
          chart("clusteredColumnChart", col("dim_date", "day_name", "Weekday", category=True),
                [mea("Sales per Labour Hour", "Sales per labour hour")],
                sort=(column_field("dim_date", "day_name"), "Ascending"), labels=True),
          "Sales per labour hour by weekday")
    pages.append(p)

    # Page 4 -----------------------------------------------------------------
    p = Page("service_desk", "Customer Service Desk", SUBTITLE)
    s = header(p, [year, store, ("Contact channel", "fact_service_desk", "contact_channel", None)])
    p.add("p4_kpis", 16, 100, 1248, 104, kpi_card([
        "Desk Contacts", "Desk Contacts YoY %", "First Contact Resolution %", "Avg Handle Time (min)",
        "Contacts per 1K Transactions"]))
    reason = col("fact_service_desk", "contact_reason", "Reason")
    by_reason = p.add("p4_contacts_by_reason", 16, 216, 620, 240,
                      chart("columnChart", year_axis, [mea("Desk Contacts", "Contacts")], series=reason,
                            sort=year_sort, categorical_axis=True), "Contacts by reason")
    p.add("p4_fcr_by_reason", 652, 216, 612, 240,
          chart("clusteredBarChart", col("fact_service_desk", "contact_reason", "Reason", category=True),
                [mea("First Contact Resolution %", "First contact resolution")],
                sort=(measure_field("First Contact Resolution %"), "Ascending"), labels=True),
          "First contact resolution by reason")
    online = p.add("p4_online_trend", 16, 468, 620, 240,
                   chart("lineChart", col("dim_date", "month_year", "Month", category=True),
                         [mea("Online Order Contacts", "Online order contacts")],
                         sort=(column_field("dim_date", "month_year"), "Ascending")),
                   "Online order & delivery contacts by month")
    channel_mix = p.add("p4_channel_mix", 652, 468, 612, 240,
                        chart("hundredPercentStackedColumnChart", year_axis, [mea("Desk Contacts", "Contacts")],
                              series=col("fact_service_desk", "contact_channel", "Channel"), sort=year_sort,
                              categorical_axis=True), "Contact channel mix by year")
    p.no_filter(s["Year"], by_reason, online, channel_mix)
    pages.append(p)
    return pages


def write_report(pages: list[Page]) -> None:
    definition = RP_DIR / "definition"
    (definition / "pages").mkdir(parents=True)

    write_json(RP_DIR / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    write_json(definition / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    version_at_import = {"visual": "1.8.97", "report": "2.0.97", "page": "1.3.97"}
    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": version_at_import,
                          "type": "SharedResources"},
            "customTheme": {"name": THEME_FILE, "reportVersionAtImport": version_at_import,
                            "type": "RegisteredResources"},
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultFilterActionIsDataFilter": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "allowInlineExploration": True,
            "useEnhancedTooltips": True,
        },
    })

    theme = json.loads((PBI_DIR / "theme.json").read_text(encoding="utf-8"))
    theme["name"] = THEME_FILE  # must match the registered file name
    write_json(RP_DIR / "StaticResources" / "RegisteredResources" / THEME_FILE, theme)

    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages],
        "activePageName": pages[0].name,
    })
    for p in pages:
        page_dir = definition / "pages" / p.name
        page_json = {
            "$schema": f"{SCHEMA}/item/report/definition/page/2.0.0/schema.json",
            "name": p.name,
            "displayName": p.display,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        }
        if p.interactions:
            page_json["visualInteractions"] = p.interactions
        write_json(page_dir / "page.json", page_json)
        for v in p.visuals:
            write_json(page_dir / "visuals" / v["name"] / "visual.json", v)


# ---------------------------------------------------------------------------
def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    for d in (SM_DIR, RP_DIR):
        if d.exists():
            shutil.rmtree(d)
    measures = parse_measures(PBI_DIR / "measures.dax")
    write_semantic_model(measures)
    pages = build_pages()
    write_report(pages)
    write_json(PBI_DIR / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    n_visuals = sum(len(p.visuals) for p in pages)
    print(f"Semantic model: {len(TABLES) + 1} tables, {len(measures)} measures, {len(RELATIONSHIPS)} relationships")
    print(f"Report: {len(pages)} pages, {n_visuals} visuals")
    print(f"Open powerbi/{NAME}.pbip in Power BI Desktop")


if __name__ == "__main__":
    main()
