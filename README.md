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


<img width="2552" height="1217" alt="image" src="https://github.com/user-attachments/assets/286e2a9d-ae59-4bed-a6f1-6de3a763b1c9" />
