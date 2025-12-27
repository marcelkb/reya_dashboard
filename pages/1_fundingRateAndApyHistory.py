import streamlit as st
import pandas as pd
import altair as alt
import mysql.connector

DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
DB_SCHEMA = st.secrets["DB_SCHEMA"]

st.set_page_config(page_title="Funding Rate Monitor", layout="wide")

st.title("📈 Reya Funding Rate and APY Monitor")


# --- DB CONNECTION ---
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_SCHEMA,
    )


# --- LOAD DATA WITH TIME FILTER ---
def load_funding_data(days=30):
    conn = get_connection()
    # Aggregate to hourly for data older than 7 days
    query = """
            SELECT symbol, timestamp, fundingRate, fundingRateAnnualized
            FROM fundingrate
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY timestamp ASC \
            """
    df = pd.read_sql(query, conn, params=(days,))
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_staking_apy(days=30):
    conn = get_connection()
    query = """
            SELECT
                timestamp, stakeApy, sharePrice
            FROM staking
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY timestamp ASC \
            """
    df = pd.read_sql(query, conn, params=(days,))
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


# Sidebar - Time Range Filter (at the top)
st.sidebar.subheader("⏱️ Time Range")
time_options = {
    "Last 24 Hours": 1,
    "Last 7 Days": 7,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
    "Last 360 Days": 360
}
time_range = st.sidebar.selectbox(
    "Select time period",
    list(time_options.keys()),
    index=3  # Default to 90 days
)
days_to_load = time_options[time_range]

# Load data with time filter
with st.spinner("Loading data from database..."):
    df_funding = load_funding_data(days=days_to_load)
    print(f"funding data: Loaded {len(df_funding)} rows from database ✅")
    df_staking = load_staking_apy(days=days_to_load)
    print(f"staking data: Loaded {len(df_staking)} rows from database ✅")


# Downsample if still too many points
def smart_downsample(df, time_col='timestamp', max_points=2000):
    """Intelligently downsample based on data volume"""
    if len(df) <= max_points:
        return df

    # Calculate appropriate frequency
    time_span = (df[time_col].max() - df[time_col].min()).total_seconds()
    target_freq_seconds = time_span / max_points

    if target_freq_seconds < 3600:  # Less than 1 hour
        freq = '1H'
    elif target_freq_seconds < 86400:  # Less than 1 day
        freq = '6H'
    else:
        freq = '1D'

    if 'symbol' in df.columns:
        return (df.set_index(time_col)
                .groupby('symbol')
                .resample(freq)
                .mean()
                .reset_index())
    else:
        return (df.set_index(time_col)
                .resample(freq)
                .mean()
                .reset_index())


df_funding = smart_downsample(df_funding)
df_staking = smart_downsample(df_staking)

# Sidebar - Symbol filters
symbols = df_funding["symbol"].unique().tolist()
selected_symbols = st.sidebar.multiselect("Select symbols", symbols, default=symbols)

# Filter data
filtered_df = df_funding[df_funding["symbol"].isin(selected_symbols)]

# --- INFO CARDS ---
st.subheader("📊 Latest Funding Rates")
if selected_symbols:
    cols = st.columns(len(selected_symbols))
    for i, symbol in enumerate(selected_symbols):
        sub_df = filtered_df[filtered_df["symbol"] == symbol]
        if not sub_df.empty:
            latest = sub_df.sort_values("timestamp").iloc[-1]
            try:
                annualized = float(latest['fundingRateAnnualized'])
                annualized_str = f"{annualized:.2f}%"
            except:
                annualized_str = str(latest['fundingRateAnnualized'])
            cols[i].metric(
                label=f"{symbol} (annualized)",
                value=annualized_str
            )

st.subheader("📊 Latest sRUSD APY")
cols = st.columns(2)
if not df_staking.empty:
    latest = df_staking.sort_values("timestamp").iloc[-1]

    try:
        annualized = float(latest['stakeApy'])
        annualized_str = f"{annualized * 100:.2f}%"
    except:
        annualized_str = str(latest['stakeApy'])

    cols[0].metric(
        label=f"RUSD APY",
        value=annualized_str
    )
    cols[1].metric(
        label=f"RUSD SharePrice",
        value=f"{latest['sharePrice']:.4f}"
    )

# Annualized funding rate chart with legend
st.subheader("Funding Rate Over Time")
annualized_chart = (
    alt.Chart(filtered_df)
    .mark_line(point=False)  # Remove points for performance
    .encode(
        x=alt.X("timestamp:T", axis=alt.Axis(format="%d.%m %H:%M")),
        y=alt.Y("fundingRateAnnualized:Q", title="Annualized Funding Rate (%)"),
        color="symbol:N",
        tooltip=["timestamp:T", "symbol:N", alt.Tooltip("fundingRateAnnualized:Q", format=".2f")]
    )
    .interactive()
)
st.altair_chart(annualized_chart, use_container_width=True)

# Convert decimal (0.21) → percent (21.0)
df_staking["stakeApy_pct"] = df_staking["stakeApy"] * 100

# Set timestamp as index for rolling
df_staking = df_staking.set_index("timestamp")

# Rolling averages (time-based)
df_staking["stakeApy_7d"] = (
    df_staking["stakeApy_pct"]
    .rolling("7D", min_periods=1).mean()
    .reset_index(level=0, drop=True)
)

df_staking["stakeApy_30d"] = (
    df_staking["stakeApy_pct"]
    .rolling("30D", min_periods=1).mean()
    .reset_index(level=0, drop=True)
)

# Reset index
df_staking = df_staking.reset_index()

st.subheader("Average APY")

avg_chart = (
    alt.Chart(df_staking)
    .transform_fold(
        ["stakeApy_pct", "stakeApy_7d", "stakeApy_30d"],
        as_=["metric", "value"]
    )
    .transform_calculate(
        metric_label=f"datum.metric == 'stakeApy_pct' ? 'Raw APY' : "
                     f"datum.metric == 'stakeApy_7d' ? '7D Avg' : '30D Avg'"
    )
    .mark_line(point=False)
    .encode(
        x=alt.X("timestamp:T", axis=alt.Axis(format="%d.%m %H:%M")),
        y=alt.Y("value:Q", title="APY (%)"),
        color=alt.Color("metric_label:N", title="Metric"),
        tooltip=["timestamp:T", "metric_label:N", alt.Tooltip("value:Q", format=".2f")]
    )
    .interactive()
)

st.altair_chart(avg_chart, use_container_width=True)

st.subheader("Funding Rate Averages")

# Set timestamp as index for rolling
filtered_df = filtered_df.sort_values(["symbol", "timestamp"]).drop_duplicates(subset=["symbol", "timestamp"])
filtered_df = filtered_df.set_index("timestamp")

filtered_df["funding_7d"] = (
    filtered_df.groupby("symbol")["fundingRateAnnualized"]
    .rolling("7D", min_periods=1).mean()
    .reset_index(level=0, drop=True)
)

filtered_df["funding_30d"] = (
    filtered_df.groupby("symbol")["fundingRateAnnualized"]
    .rolling("30D", min_periods=1).mean()
    .reset_index(level=0, drop=True)
)

# Reset index
filtered_df = filtered_df.reset_index()

# Melt for Altair
avg_df = filtered_df.melt(
    id_vars=["timestamp", "symbol"],
    value_vars=["fundingRateAnnualized", "funding_7d", "funding_30d"],
    var_name="metric",
    value_name="value"
)

# Map column names to friendly labels
metric_map = {
    "fundingRateAnnualized": "Raw Funding Rate",
    "funding_7d": "7D Avg",
    "funding_30d": "30D Avg"
}
avg_df["metric_label"] = avg_df["metric"].map(metric_map)

# Plot
annualized_chart = (
    alt.Chart(avg_df)
    .mark_line(point=False)
    .encode(
        x=alt.X("timestamp:T", axis=alt.Axis(format="%d.%m %H:%M")),
        y=alt.Y("value:Q", title="Funding Rate (%)"),
        color=alt.Color("symbol:N", title="Symbol"),
        strokeDash="metric_label:N",
        tooltip=["timestamp:T", "symbol:N", "metric_label:N", alt.Tooltip("value:Q", format=".2f")]
    )
    .interactive()
)

st.altair_chart(annualized_chart, use_container_width=True)

# Hourly funding rate chart
st.subheader("Hourly Funding Rate Over Time")
funding_chart = (
    alt.Chart(filtered_df)
    .mark_line(point=False)
    .encode(
        x=alt.X("timestamp:T", axis=alt.Axis(format="%d.%m %H:%M")),
        y=alt.Y("fundingRate:Q", title="Hourly Funding Rate (%)"),
        color="symbol:N",
        tooltip=["timestamp:T", "symbol:N", alt.Tooltip("fundingRate:Q", format=".4f")]
    )
    .interactive()
)
st.altair_chart(funding_chart, use_container_width=True)

# Show data info
st.sidebar.markdown("---")
st.sidebar.info(f"📊 Showing {len(filtered_df)} funding data points\n\n📊 Showing {len(df_staking)} staking data points")

# Show table
with st.expander("📂 Funding Rate Data"):
    st.dataframe(filtered_df.sort_values("timestamp", ascending=False))
with st.expander("📂 Staking Data"):
    st.dataframe(df_staking.sort_values("timestamp", ascending=False))

# --- Footer ---
st.markdown("---")
st.markdown("💡 **Note:** The crawler fetches new data every 5 minutes")
st.markdown(
    "⚠️ **Disclaimer:** This data is for informational purposes only and should not be considered as financial advice.")
