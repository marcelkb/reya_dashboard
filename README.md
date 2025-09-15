# 🌐 Reya Exchange Dashboard

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?logo=python)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Alpha-orange)

A dashboard for monitoring and analyzing **Reya Exchange** metrics.

---

## ✨ Features

- 📈 Current & historical **rUSD APY**
- 💹 Current & historical **Funding Rates**
- ⚡ Supported assets: **BTC**, **ETH**, **SOL**
- 🚀 Dashboard showing arbitrage oportunities between different exchanges (cex and dex)

---

## 🔍 How it Works

- **ReyaDataCrawler**  
  - Uses a custom **CCXT wrapper** to fetch data from Reya’s REST API  
  - Collects **funding rates** and **rUSD APY** at regular intervals  
  - Persists everything into a database for statistics and visualization  

> ⚠️ The Reya API does not currently provide historical data.  
> Statistics begin from the moment the crawler is started.

---

## 🛠️ Tech Stack

- 🐍 **Python** (crawler + CCXT wrapper)  
- 🗄️ **Database** (MariaDB)  
- 📊 **Dashboard & charts** Streamlit for visualization  

---

You can find it here: 
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://reyadashboard.streamlit.app)

<img width="2539" height="1143" alt="image" src="https://github.com/user-attachments/assets/596ca499-8a4c-4dd5-9c52-342c7d0cec8f" />
<img width="1632" height="865" alt="image" src="https://github.com/user-attachments/assets/97ad6597-a77d-48e3-b18f-89bbb3482546" />

