#run with streamlit run C:\Users\Marcel\Downloads\MartingaleDcaBot\dashboard\app.py
import streamlit as st

history = st.Page("pages/1_fundingRateAndApyHistory.py", title="Funding Rate and APY Monitor", icon="📊")
arbitrage = st.Page("pages/2_fundingRateArbitrage.py", title="Funding Rate Arbitrage", icon="📊")

pg = st.navigation([history, arbitrage])
st.set_page_config(page_title="Reya Dashboard", page_icon=":material/home:")
pg.run()