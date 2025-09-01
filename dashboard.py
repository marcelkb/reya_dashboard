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

# --- LOAD DATA ---
def load_funding_data():
    conn = get_connection()
    query = """
        SELECT 
           *
        FROM fundingrate
        ORDER BY fundingrate.timestamp ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    # Convert timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def load_staking_apy():
    conn = get_connection()
    query = """
        SELECT 
            *
        FROM staking
        ORDER BY staking.timestamp ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    # Convert timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

with st.spinner("Loading data from database..."):
    df_funding = load_funding_data()
    print(f"funding data: Loaded {len(df_funding)} rows from database ✅")
    df_staking = load_staking_apy()
    print(f"staking data: Loaded {len(df_funding)} rows from database ✅")

# Convert timestamps
df_funding["timestamp"] = pd.to_datetime(df_funding["timestamp"])
df_staking["timestamp"] = pd.to_datetime(df_staking["timestamp"])

# Sidebar filters
symbols = df_funding["symbol"].unique().tolist()
selected_symbols = st.sidebar.multiselect("Select symbols", symbols, default=symbols)

# Filter data
filtered_df = df_funding[df_funding["symbol"].isin(selected_symbols)]

# --- INFO CARDS ---
st.subheader("📊 Latest Funding Rates")
cols = st.columns(len(selected_symbols))  # one column per symbol
for i, symbol in enumerate(selected_symbols):
    sub_df = filtered_df[filtered_df["symbol"] == symbol]
    if not sub_df.empty:
        latest = sub_df.sort_values("timestamp").iloc[-1]
        # round to 2 digits
        try:
            annualized = float(latest['fundingRateAnnualized'])
            annualized_str = f"{annualized:.2f}%"
        except:
            annualized_str = str(latest['fundingRateAnnualized'])
        cols[i].metric(
            label=f"{symbol} (annualized)",
            value=annualized_str
        )

st.subheader("📊 Latest RUSD APY")
cols = st.columns(2)  # one column per symbol
latest = df_staking.sort_values("timestamp").iloc[-1]

try:
    annualized = float(latest['stakeApy'])
    annualized_str = f"{annualized*100:.2f}%"
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
st.subheader("Annualized Funding Rate Over Time")
annualized_chart = (
    alt.Chart(filtered_df)
    .mark_line(point=True)
    .encode(
        x="timestamp:T",
        y="fundingRateAnnualized:Q",
        color="symbol:N",   # add symbol as legend
        tooltip=["timestamp", "symbol", "fundingRateAnnualized"]
    )
    .interactive()
)
st.altair_chart(annualized_chart, use_container_width=True)

# Convert decimal (0.21) → percent (21.0)
df_staking["stakeApy_pct"] = df_staking["stakeApy"] * 100

# Set timestamp as index for rolling
df_staking = df_staking.set_index("timestamp")

# Rolling averages (time-based, per symbol)
df_staking["stakeApy_7d"] = (
    df_staking["stakeApy_pct"]
    .rolling("7D").mean()
    .reset_index(level=0, drop=True)
)

df_staking["stakeApy_30d"] = (
    df_staking["stakeApy_pct"]
    .rolling("30D").mean()
    .reset_index(level=0, drop=True)
)

# Reset index so Streamlit/Altair can use timestamp column again
df_staking = df_staking.reset_index()

st.subheader("Average APY")

# Map internal column names -> friendly labels
rename_map = {
    "stakeApy_pct": "Raw APY",
    "stakeApy_7d": "7D Avg",
    "stakeApy_30d": "30D Avg"
}

avg_chart = (
    alt.Chart(df_staking)
    .transform_fold(
        list(rename_map.keys()),
        as_=["metric", "value"]
    )
    .transform_calculate(
        metric_label=f"datum.metric == 'stakeApy_pct' ? 'Raw APY' : "
                     f"datum.metric == 'stakeApy_7d' ? '7D Avg' : '30D Avg'"
    )
    .mark_line(point=False)
    .encode(
        x="timestamp:T",
        y="value:Q",
        color=alt.Color("metric_label:N", title="Metric"),
        tooltip=["timestamp:T", "metric_label:N", "value:Q"]
    )
    .interactive()
)

st.altair_chart(avg_chart, use_container_width=True)

# Funding rate chart with legend
st.subheader("Hourly Funding Rate Over Time")
funding_chart = (
    alt.Chart(filtered_df)
    .mark_line(point=True)
    .encode(
        x="timestamp:T",
        y="fundingRate:Q",
        color="symbol:N",   # add symbol as legend
        tooltip=["timestamp", "symbol", "fundingRate"]
    )
    .interactive()
)
st.altair_chart(funding_chart, use_container_width=True)

# Show table
with st.expander("📂 Funding Rate Data"):
    st.dataframe(filtered_df.sort_values("timestamp", ascending=False))
with st.expander("📂 Staking Data"):
    st.dataframe(df_staking.sort_values("timestamp", ascending=False))