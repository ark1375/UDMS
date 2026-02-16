from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

import duckdb
import pandas as pd
import streamlit as st
import altair as alt

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# =========================
# 1) Settings via .env
# =========================
# We use pydantic-settings so you can keep configuration outside code (like your FastAPI setup).
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    duckdb_path: str = Field(..., alias="DUCKDB_PATH")


settings = Settings()


# =========================
# 2) Streamlit page config
# =========================
st.set_page_config(
    page_title="Trips Analytics Dashboard",
    layout="wide",
)


st.title("🚗 Trips Analytics Dashboard (DuckDB + dbt Medallion)")
st.caption("Data sources: silver.TransactionFact + gold.travels + gold.requests")


# =========================
# 3) Create DB connection ONCE
# =========================
# Streamlit reruns the script on every interaction, so we cache the connection.
# This prevents reconnecting on every filter change.
@st.cache_resource
def get_conn(path: str) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(path, read_only=True)
    # If you store local timestamps, you may want to set timezone policy. Adjust if needed.
    conn.execute("SET timezone='UTC';")
    return conn


conn = get_conn(settings.duckdb_path)


# =========================
# 4) Helper to run SQL -> DataFrame
# =========================
def qdf(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    if params is None:
        params = []
    return conn.execute(sql, params).fetchdf()


# =========================
# 5) Sidebar filters (interactive controls)
# =========================
# You asked:
# - filter by timestamps [Time delta]
# - filter by vehicle type
#
# Time delta approach: pick "Last N days/hours" -> we compute a cutoff timestamp and filter trip_ts >= cutoff
st.sidebar.header("Filters")

time_window = st.sidebar.selectbox(
    "Time window",
    options=[
        "Last 24 hours",
        "Last 7 days",
        "Last 30 days",
        "Last 90 days",
        "All time",
    ],
    index=1,
)

now = datetime.utcnow()

if time_window == "Last 24 hours":
    cutoff_ts = now - timedelta(hours=24)
elif time_window == "Last 7 days":
    cutoff_ts = now - timedelta(days=7)
elif time_window == "Last 30 days":
    cutoff_ts = now - timedelta(days=30)
elif time_window == "Last 90 days":
    cutoff_ts = now - timedelta(days=90)
else:
    cutoff_ts = None  # means "no time filter"

# Vehicle filter values come from silver (because it contains all records)
vehicle_options_df = qdf(
    """
    SELECT DISTINCT vehicle_type
    FROM silver.TransactionFact
    WHERE vehicle_type IS NOT NULL
    ORDER BY vehicle_type
    """
)
vehicle_options = vehicle_options_df["vehicle_type"].tolist()

selected_vehicles = st.sidebar.multiselect(
    "Vehicle types",
    options=vehicle_options,
    default=vehicle_options,  # default to all vehicles selected
)

# If user deselects all, it would filter everything out. Handle that gracefully:
if not selected_vehicles:
    st.sidebar.warning("No vehicle types selected — dashboard will show no data.")


# =========================
# 6) Build reusable WHERE clause
# =========================
# We need one consistent filter logic used across KPIs and charts.
# We'll filter by:
# - trip_ts >= cutoff_ts (if cutoff_ts is not None)
# - vehicle_type IN selected_vehicles
#
# NOTE: gold tables should also contain vehicle_type + trip_ts if built from silver.
# If your gold models did NOT include those columns, adjust queries to join back to silver by PK.
def build_filters(table_alias: str = ""):
    """
    Returns (where_sql, params) for consistent filters.
    table_alias: optional prefix like "s." or "t."
    """
    prefix = f"{table_alias}." if table_alias else ""
    clauses = []
    params: list = []

    if cutoff_ts is not None:
        clauses.append(f"{prefix}trip_ts >= ?")
        params.append(cutoff_ts)

    if selected_vehicles:
        # DuckDB supports = ANY(?) for list parameters
        clauses.append(f"{prefix}vehicle_type = ANY(?)")
        params.append(selected_vehicles)

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    return where_sql, params


# =========================
# 7) KPI queries
# =========================
# You asked:
# a) number of all the bookings --> count(*) on silver
# b) Successful trips --> gold.travels
# c) Total income --> gold.travels sum on pay (we’ll assume column is booking_value)
# d) success rate --> travels / (requests + travels)
#
# Important assumption:
# - gold.travels has booking_value, trip_ts, vehicle_type
# - gold.requests has trip_ts, vehicle_type, booking_status
#
# If your gold models don’t carry trip_ts/vehicle_type, tell me and we’ll join from silver using PK.
silver_where, silver_params = build_filters("")
travels_where, travels_params = build_filters("")
requests_where, requests_params = build_filters("")

# a) all bookings from silver
all_bookings = qdf(
    f"SELECT COUNT(*) AS n FROM silver.TransactionFact {silver_where}",
    silver_params,
)["n"].iloc[0]

# b) successful trips from gold.travels
successful_trips = qdf(
    f"SELECT COUNT(*) AS n FROM gold.travels {travels_where}",
    travels_params,
)["n"].iloc[0]

# c) total income from gold.travels (assuming booking_value is the pay)
total_income = qdf(
    f"SELECT COALESCE(SUM(booking_value), 0) AS total FROM gold.travels {travels_where}",
    travels_params,
)["total"].iloc[0]

# d) success rate = travels / (travels + requests)
requests_count = qdf(
    f"SELECT COUNT(*) AS n FROM gold.requests {requests_where}",
    requests_params,
)["n"].iloc[0]

denom = successful_trips + requests_count
success_rate = (successful_trips / denom) if denom > 0 else 0.0


# =========================
# 8) Render KPI cards
# =========================
k1, k2, k3, k4 = st.columns(4)
k1.metric("All bookings (Silver)", f"{all_bookings:,}")
k2.metric("Successful trips (Gold Travels)", f"{successful_trips:,}")
k3.metric("Total income (Gold Travels)", f"{total_income:,.2f}")
k4.metric("Success rate", f"{success_rate*100:.2f}%")


st.divider()


# =========================
# 9) Pie chart: distribution of unsuccessful trip types
# =========================
# “unsuccessful trip types” = booking_status in gold.requests
# We count by booking_status (Cancelled by Customer/Driver, Incomplete, No Driver Found, etc.)
requests_breakdown = qdf(
    f"""
    SELECT
      booking_status,
      COUNT(*) AS n
    FROM gold.requests
    {requests_where}
    GROUP BY 1
    ORDER BY n DESC
    """,
    requests_params,
)

left, right = st.columns([1, 1])

with left:
    st.subheader("Unsuccessful trip distribution (Requests)")
    if requests_breakdown.empty:
        st.info("No request records found for the selected filters.")
    else:
        pie = (
            alt.Chart(requests_breakdown)
            .mark_arc()
            .encode(
                theta=alt.Theta("n:Q"),
                color=alt.Color("booking_status:N", legend=alt.Legend(title="Type")),
                tooltip=["booking_status:N", "n:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(pie, use_container_width=True)

with right:
    st.subheader("Requests table (filtered)")
    st.dataframe(requests_breakdown, use_container_width=True)


# =========================
# 10) Bar chart: successful trips per vehicle + avg driver/customer rating
# =========================
# Using gold.travels (successful only)
travels_by_vehicle = qdf(
    f"""
    SELECT
      vehicle_type,
      COUNT(*) AS successful_trips,
      AVG(driver_rating) AS avg_driver_rating,
      AVG(customer_rating) AS avg_customer_rating
    FROM gold.travels
    {travels_where}
    GROUP BY 1
    ORDER BY successful_trips DESC
    """,
    travels_params,
)

st.subheader("Successful trips per vehicle + average ratings (Gold Travels)")

if travels_by_vehicle.empty:
    st.info("No successful trips found for the selected filters.")
else:
    # Trips bar
    trips_bar = (
        alt.Chart(travels_by_vehicle)
        .mark_bar()
        .encode(
            x=alt.X("vehicle_type:N", sort="-y", title="Vehicle type"),
            y=alt.Y("successful_trips:Q", title="Successful trips"),
            tooltip=["vehicle_type:N", "successful_trips:Q"],
        )
        .properties(height=300)
    )

    # Ratings as points/line (second chart, easier than dual-axis)
    ratings_long = travels_by_vehicle.melt(
        id_vars=["vehicle_type", "successful_trips"],
        value_vars=["avg_driver_rating", "avg_customer_rating"],
        var_name="rating_type",
        value_name="avg_rating",
    )

    ratings_chart = (
        alt.Chart(ratings_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("vehicle_type:N", title="Vehicle type"),
            y=alt.Y("avg_rating:Q", title="Average rating", scale=alt.Scale(domain=[0, 5])),
            color=alt.Color("rating_type:N", title="Rating"),
            tooltip=["vehicle_type:N", "rating_type:N", alt.Tooltip("avg_rating:Q", format=".2f")],
        )
        .properties(height=300)
    )

    c1, c2 = st.columns(2)
    c1.altair_chart(trips_bar, use_container_width=True)
    c2.altair_chart(ratings_chart, use_container_width=True)


st.divider()


# =========================
# 11) Line chart: trips per hour grouped by day (high traffic)
# =========================
# You said: "all requests. Use silver layer"
# I interpret that as NON-COMPLETED bookings, but we query from silver.
# (Equivalent to gold.requests, but using silver as requested.)
#
# We group by:
# - day (date(trip_ts))
# - hour (extract hour)
traffic_where, traffic_params = build_filters("s")

traffic = qdf(
    f"""
    SELECT
      CAST(date_trunc('day', s.trip_ts) AS DATE) AS trip_day,
      EXTRACT('hour' FROM s.trip_ts) AS trip_hour,
      COUNT(*) AS trips
    FROM silver.TransactionFact s
    {traffic_where}
      {"AND" if traffic_where else "WHERE"} s.booking_status != 'Completed'
    GROUP BY 1, 2
    ORDER BY 1, 2
    """,
    traffic_params,
)

st.subheader("High traffic hours (Requests only, Silver layer)")

if traffic.empty:
    st.info("No request trips found for the selected filters.")
else:
    # Make an x-axis timestamp for hour buckets (day + hour) for a clean line plot
    traffic["bucket_ts"] = pd.to_datetime(traffic["trip_day"]) + pd.to_timedelta(traffic["trip_hour"], unit="h")

    line = (
        alt.Chart(traffic)
        .mark_line()
        .encode(
            x=alt.X("bucket_ts:T", title="Day + Hour"),
            y=alt.Y("trips:Q", title="Trips (requests)"),
            tooltip=[
                alt.Tooltip("trip_day:T", title="Day"),
                alt.Tooltip("trip_hour:Q", title="Hour"),
                alt.Tooltip("trips:Q", title="Trips"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(line, use_container_width=True)


# =========================
# 12) Debug / transparency
# =========================
# Helps you verify filters are doing what you expect.
with st.expander("Show active filters"):
    st.write("Time window:", time_window)
    st.write("Cutoff timestamp (UTC):", cutoff_ts)
    st.write("Vehicles:", selected_vehicles)
