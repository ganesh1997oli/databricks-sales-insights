import logging
import os
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config


st.set_page_config(
    page_title="Sales Insights",
    page_icon="📊",
    layout="wide",
)

st.title("Sales Insights")
st.caption("Explore sales performance • Fictional sample data • All prices in GBP")


@st.cache_data(ttl=60)
def load_sales():
    # Databricks supplies the app's authentication credentials.
    config = Config(auth_type="oauth-m2m")
    warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]

    with sql.connect(
        server_hostname=urlparse(config.host).hostname,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        credentials_provider=lambda: config.authenticate,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    order_id,
                    line_id,
                    order_date,
                    product,
                    category,
                    quantity,
                    unit_price,
                    line_revenue
                FROM workspace.portfolio_gold.sales_details
                ORDER BY order_date, order_id, line_id
            """)

            columns = [column[0] for column in cursor.description]
            rows = [tuple(row) for row in cursor.fetchall()]

    data = pd.DataFrame(rows, columns=columns)
    data["order_date"] = pd.to_datetime(data["order_date"])

    # Convert decimal values for charts and display.
    for column in ["unit_price", "line_revenue"]:
        data[column] = data[column].astype(float)

    return data


if st.sidebar.button("Refresh data"):
    load_sales.clear()

try:
    with st.spinner("Loading sales…"):
        sales = load_sales()
except Exception:
    logging.exception("Failed to load Gold sales data")
    st.error("Sales could not be loaded. Check the app logs for details.")
    st.stop()

if sales.empty:
    st.info("No sales records are available yet.")
    st.stop()


# Filters
st.sidebar.header("Filter sales")

first_date = sales["order_date"].min().date()
last_date = sales["order_date"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(first_date, last_date),
    min_value=first_date,
    max_value=last_date,
)

categories = sorted(sales["category"].unique().tolist())

selected_categories = st.sidebar.multiselect(
    "Categories",
    options=categories,
    default=categories,
)

if len(date_range) != 2:
    st.info("Select both a start date and an end date.")
    st.stop()

start_date, end_date = date_range

filtered = sales[
    sales["order_date"].dt.date.between(start_date, end_date)
    & sales["category"].isin(selected_categories)
].copy()

if filtered.empty:
    st.info("No sales match these filters. Try another selection.")
    st.stop()


# Summary metrics
revenue = filtered["line_revenue"].sum()
orders = filtered["order_id"].nunique()
units = int(filtered["quantity"].sum())

revenue_column, orders_column, units_column = st.columns(3)

revenue_column.metric("Revenue", f"£{revenue:,.2f}")
orders_column.metric("Orders", f"{orders:,}")
units_column.metric("Units sold", f"{units:,}")


# Charts
daily_revenue = (
    filtered.groupby("order_date")["line_revenue"]
    .sum()
    .sort_index()
    .rename("Revenue (£)")
)

product_revenue = (
    filtered.groupby("product")["line_revenue"]
    .sum()
    .rename("Revenue (£)")
)

left, right = st.columns(2)

with left:
    st.subheader("Revenue over time")
    st.line_chart(daily_revenue)

with right:
    st.subheader("Revenue by product")
    st.bar_chart(product_revenue)


# Transaction details
st.subheader("Sales records")

st.dataframe(
    filtered.sort_values(["order_date", "order_id", "line_id"]),
    hide_index=True,
)

st.caption(f"{len(filtered)} product lines across {orders} orders")