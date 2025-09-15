
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import plotly.graph_objects as go
from datetime import datetime
import mysql.connector

st.set_page_config(page_title="Funding Rate Heatmap", layout="wide")
st.title("📊 Funding Rates")

DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
DB_SCHEMA = st.secrets["DB_SCHEMA"]

# --- Exchange configurations ---
ALL_EXCHANGES = {
    'Binance',
    'OKX',
    'Bybit',
    'KuCoin Futures',
    #'Bitget',
    #'BingX',
    'Hyperliquid',
    'Reya',
    "Lighter",
    "EdgeX"
}
#Jupiter, Dy{Dx, orderly, avantis, myx, radium, drift, ligther

SYMBOLS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']

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
        SELECT f.*
        FROM fundingdata f
        JOIN (
            SELECT symbol, exchange, MAX(timestamp) AS max_ts
            FROM fundingdata
            GROUP BY symbol, exchange
        ) latest
          ON f.symbol = latest.symbol
        AND f.exchange = latest.exchange
        AND f.timestamp = latest.max_ts ORDER BY TIMESTAMP desc;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    # Convert timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def create_heatmap(df_pivot):
    """Create a heatmap using Plotly"""

    # Create custom colorscale (red for negative, green for positive)
    colorscale = [
        [0.0, '#33CC33'],    # Muted green for most negative
        [0.3, '#A3E6A3'],    # Muted light green
        [0.5, '#F5F5F5'],  # Muted white for zero
        [0.7, '#E6A3A3'],    # Muted light red
        [1.0, '#CC3333']     # Muted red for most positive
    ]

    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.values,
        x=df_pivot.columns,
        y=df_pivot.index,
        colorscale=colorscale,
        zmid=0,  # ensures 0 is centered in the colorscale
        text=df_pivot.values,
        texttemplate='%{text:.3f}%',
        textfont={"size": 12},
        hoverongaps=False,
        colorbar=dict(
            title="Funding Rate (%)",
        )
    ))

    fig.update_layout(
        title="Funding Rates Heatmap (%/1Y)",
        xaxis_title="Exchanges",
        yaxis_title="Symbols",
        xaxis=dict(side='top'),
        height=400,
        font=dict(size=12)
    )

    return fig


# ==========================
# Arbitrage Detection
# ==========================
def find_best_arbitrage_opportunities(df):
    best_results = []
    all_results = []
    for symbol in df["Symbol"].unique():
        sub = df[df["Symbol"] == symbol]
        positives = sub[sub["Rate"] > 0]
        negatives = sub[sub["Rate"] < 0]

        if positives.empty or negatives.empty:
            continue  # no arbitrage possible for this symbol

        # Find max positive & min negative
        best_pos = positives.loc[positives["Rate"].idxmax()]
        best_neg = negatives.loc[negatives["Rate"].idxmin()]

        # # Compare all positive vs negative exchanges
        # for _, pos in positives.iterrows():
        #     for _, neg in negatives.iterrows():
        #         best_results.append({
        #             "Symbol": symbol,
        #             "Long Exchange": neg["Exchange"],
        #             "Long Rate": neg["Rate"],
        #             "Short Exchange": pos["Exchange"],
        #             "Short Rate": pos["Rate"],
        #             "Spread": pos["Rate"] - neg["Rate"]
        #         })
        best_results.append({
            "Symbol": symbol,
            "Long Exchange": best_neg["Exchange"],
            "Long Rate (1h)": best_neg["Rate"],
            "Long Rate (1Y)": best_neg["Yearly Rate"],
            "Short Exchange": best_pos["Exchange"],
            "Short Rate (1h)": best_pos["Rate"],
            "Short Rate (1Y)": best_pos["Yearly Rate"],
            "Spread (1h)": best_pos["Rate"] - best_neg["Rate"],
            "Spread (1Y)": best_pos["Yearly Rate"] - best_neg["Yearly Rate"]

        })

        # Compare ALL positives vs negatives
        for _, pos in positives.iterrows():
            for _, neg in negatives.iterrows():
                all_results.append({
                    "Symbol": symbol,
                    "Long Exchange": neg["Exchange"],
                    "Long Rate (1h)": neg["Rate"],
                    "Long Rate (1Y)": neg["Yearly Rate"],
                    "Short Exchange": pos["Exchange"],
                    "Short Rate (1h)": pos["Rate"],
                    "Short Rate (1Y)": pos["Yearly Rate"],
                    "Spread (1h)": pos["Rate"] - neg["Rate"],
                    "Spread (1Y)": pos["Yearly Rate"] - neg["Yearly Rate"],
                })
    all_results = pd.DataFrame(all_results).sort_values(by="Spread (1h)", ascending=False)
    best_results = pd.DataFrame(best_results).sort_values(by="Spread (1h)", ascending=False)

    return pd.DataFrame(best_results), pd.DataFrame(all_results)


# --- Sidebar Controls ---
st.sidebar.header("⚙️ Controls")

# Exchange selection
st.sidebar.subheader("📈 Select Exchanges")
available_exchanges = list(ALL_EXCHANGES)
default_exchanges = ['Reya', 'Hyperliquid', 'Lighter', 'EdgeX'] #'binance', 'bybit',

selected_exchanges = st.sidebar.multiselect(
    "Choose exchanges to fetch data from:",
    options=available_exchanges,
    default=[ex for ex in default_exchanges if ex in available_exchanges],
    help="Select which exchanges to include in the funding rate comparison"
)

# Show warning if no exchanges selected
if not selected_exchanges:
    st.sidebar.warning("⚠️ Please select at least one exchange")
    st.stop()

if st.sidebar.button("🔄 Refresh Data", type="primary"):
    st.cache_data.clear()
    st.rerun()

# auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30s)", value=False)
#
# if auto_refresh:
#     st.sidebar.info("Auto-refresh enabled")
#     # Auto refresh every 30 seconds
#     import time
#
#     time.sleep(30)
#     st.rerun()

# Show last update time
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()


# --- Main Content ---
try:
    # Fetch funding rates

    with st.spinner("Loading data from database..."):
        funding_data = load_funding_data()
        print(f"funding data: Loaded {len(funding_data)} entries from database ✅")

    if funding_data is None or len(funding_data) == 0:
        st.error("❌ No funding rate data available. Please check your internet connection or try again later.")
        st.stop()

    # Update last update time
    st.session_state.last_update = funding_data.iloc[-1]["timestamp"]
    st.sidebar.info(f"**Last updated:**  \n{st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
    funding_data = funding_data.rename(columns={
        "symbol": "Symbol",
        "exchange": "Exchange",
        "rate": "Rate",
        "rate_1y": "Yearly Rate",
        "next_funding": "Next Funding",
        "interval": "Interval"
    })
    funding_data = funding_data.drop(columns="timestamp")
    funding_data = funding_data[funding_data["Exchange"].isin(selected_exchanges)]
    df = funding_data


    # Create pivot table for heatmap
    df_pivot = df.pivot(index='Symbol', columns='Exchange', values='Yearly Rate')
    df_pivot = df_pivot.fillna(0)  # Fill NaN values with 0

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📊 Total Symbols", len(df_pivot.index))

    with col2:
        st.metric("🏢 Total Exchanges", len(df_pivot.columns))

    with col3:
        highest_rate = df['Yearly Rate'].max()
        st.metric("📈 Highest Rate", f"{highest_rate:.3f}%")

    with col4:
        lowest_rate = df['Yearly Rate'].min()
        st.metric("📉 Lowest Rate", f"{lowest_rate:.3f}%")

    # Create two tabs
    tab1, tab2 = st.tabs(["📊 Arbitrage Opportunities", "📋 Data Table"])

    with tab1:
        st.subheader("📊 Arbitrage Opportunities")
        st.markdown("Finds all pairs with the biggest spread between a negative and a positive rate")

        arb_df, arb_df_all = find_best_arbitrage_opportunities(df)

        tabArb1, tabArb2 = st.tabs(["🚀 Best Arbitrage Opportunities", "📋 All Arbitrage Opportunities"])
        with tabArb1:
            st.subheader("🚀 Best Arbitrage Opportunities")

            for _, row in arb_df.iterrows():
                spread_color = "#228B22" if row['Spread (1h)'] > 0 else "#B22222"
                with st.container():
                    st.markdown(f"""
                         <div style="padding:18px; border-radius:14px; margin-bottom:14px;
                                     background: linear-gradient(135deg, #f0f4f8, #d9e2ec);
                                     color:#1a1a1a; font-family:Arial, sans-serif;
                                     box-shadow: 0px 3px 8px rgba(0,0,0,0.12)">
                             <h3 style="margin:0; color:#2c5282;">{row['Symbol']}</h3>
                             <p style="margin:4px 0;">📉 <b>Long</b> on <b>{row['Long Exchange']}</b> 
                                at <b>{row['Long Rate (1h)']:.4f}% (1h)</b> | <b>{row['Long Rate (1Y)']:.2f}% (1Y)</b></p>
                             <p style="margin:4px 0;">📈 <b>Short</b> on <b>{row['Short Exchange']}</b> 
                                at <b>{row['Short Rate (1h)']:.4f}% (1h)</b> | <b>{row['Short Rate (1Y)']:.2f}% (1Y)</b></p>
                             <h4 style="margin:8px 0; color:{spread_color};">
                                 Spread: {row['Spread (1h)']:.4f}% (1h) | {row['Spread (1Y)']:.2f}% (1Y)
                             </h4>
                         </div>
                         """, unsafe_allow_html=True)
            if (len(arb_df) == 0):
                st.info("No arbitrage opportunities detected ⚖️")

        with tabArb2:
            st.subheader("📂 All Arbitrage Opportunities")

            if not arb_df_all.empty:
                st.dataframe(
                    arb_df_all,
                    column_config={
                        "Long Rate (1h)": st.column_config.NumberColumn(format="%.6f%%"),
                        "Long Rate (1Y)": st.column_config.NumberColumn(format="%.6f%%"),
                        "Short Rate (1h)": st.column_config.NumberColumn(format="%.6f%%"),
                        "Short Rate (1Y)": st.column_config.NumberColumn(format="%.6f%%"),
                        "Spread Rate (1h)": st.column_config.NumberColumn(format="%.6f%%"),
                        "Short Spread (1Y)": st.column_config.NumberColumn(format="%.6f%%")
                    },
                    use_container_width=True,
                )

        # Display heatmap
        fig = create_heatmap(df_pivot)
        st.plotly_chart(fig, use_container_width=True)

        # -- funding table --

        st.subheader("Hourly Funding Rates")
        # Convert to DataFrame

        df = pd.DataFrame(funding_data)
        df_symbol_rate = df[["Exchange", "Symbol", "Rate"]]
        df_symbol_rate = df_symbol_rate.pivot(index="Symbol", columns="Exchange", values="Rate").reset_index()

        # --- Build AgGrid ---
        gb = GridOptionsBuilder.from_dataframe(df_symbol_rate)

        # JS for coloring negative green, positive red
        cell_style_jscode = JsCode("""
        function(params) {
            if (params.value < 0) {
                return { 'color': 'green', 'font-weight': 'bold' };
            } else if (params.value > 0) {
                return { 'color': 'red', 'font-weight': 'bold' };
            }
            return {};
        }
        """)

        # JS for formatting values as percentages
        value_formatter = JsCode("""
        function(params) {
            if (params.value === null || params.value === undefined) return '';
            return (params.value).toFixed(4) + '%';
        }
        """)

        for col in df_symbol_rate.columns[1:]:
            gb.configure_column(
                col,
                filter=False,
                cellStyle=cell_style_jscode,
                valueFormatter=value_formatter
            )

        gb.configure_default_column(resizable=True, filter=False, sortable=True)
        grid_options = gb.build()
        #grid_options['domLayout'] = 'autoHeight'
        # --- Display table ---
        AgGrid(
            df_symbol_rate,
            gridOptions=grid_options,
            fit_columns_on_grid_load=True,
            theme="alpine",
            allow_unsafe_jscode=True  # <-- this fixes the JSON serialization error
        )

        # Show summary statistics
        st.subheader("📊 Summary Statistics")
        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:
            st.write("**Average Funding Rate by Exchange:**")
            exchange_avg = df.groupby('Exchange')['Yearly Rate'].mean().sort_values(ascending=False)
            st.dataframe(exchange_avg.round(4))

        with summary_col2:
            st.write("**Average Funding Rate by Symbol:**")
            symbol_avg = df.groupby('Symbol')['Yearly Rate'].mean().sort_values(ascending=False)
            st.dataframe(symbol_avg.round(4))

    with tab2:
        # Display data table with AgGrid
        st.subheader("📋 Funding Rates Data")

        # --- Build AgGrid ---
        gb = GridOptionsBuilder.from_dataframe(df)

        # JS for coloring negative green, positive red
        cell_style_jscode = JsCode("""
        function(params) {
            // Only apply styling to the 'rate' column
            if (!params.colDef.field.toLowerCase().includes('rate')) {
                return {};
            }
            if (params.value < 0) {
                return { 'color': 'green', 'font-weight': 'bold' };
            } else if (params.value > 0) {
                return { 'color': 'red', 'font-weight': 'bold' };
            }
            return {};
        }
        """)

        # # JS for formatting values as percentages
        # value_formatter = JsCode("""
        # function(params) {
        #     if (params.value === null || params.value === undefined) return '';
        #     return (params.value * 100).toFixed(3) + '%';
        # }
        # """)

        for col in df.columns[1:]:
            gb.configure_column(
                col,
                filter=False,
                cellStyle=cell_style_jscode,
                #valueFormatter=value_formatter
            )

        gb.configure_default_column(resizable=True, filter=False, sortable=True)
        grid_options = gb.build()

        # --- Display table ---
        AgGrid(
            df,
            gridOptions=grid_options,
            height=300,
            fit_columns_on_grid_load=True,
            theme="alpine",
            allow_unsafe_jscode=True  # <-- this fixes the JSON serialization error
        )

except Exception as e:
    st.error(f"❌ An error occurred: {str(e)}")
    st.info("Please check your internet connection and try refreshing the data.")


# --- Footer ---
st.markdown("---")
st.markdown(
    "💡 **Note:** Funding rates are updated every 8 hours on most exchanges. Positive rates indicate longs pay shorts, negative rates indicate shorts pay longs. The crawler fetches new data every 5 minutes")
st.markdown(
    "⚠️ **Disclaimer:** This data is for informational purposes only and should not be considered as financial advice.")