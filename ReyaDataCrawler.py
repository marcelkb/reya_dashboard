import datetime
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import ccxt
import pandas as pd
from ccxt_wrapper.Reya import Reya
from sdk.reya_rest_api import TradingConfig, ReyaTradingClient

from dotenv import load_dotenv

from Telegram import Telegram
from pages.exchanges.edgeX import EdgeX
from pages.exchanges.lighter import Lighter

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Create a logger for this module
from peewee import (
    Model, CharField, DateTimeField, DecimalField, AutoField, FloatField, SQL
)
from playhouse.mysql_ext import MariaDBConnectorDatabase

# Load environment variables
load_dotenv()

# Connect to MariaDB
db = MariaDBConnectorDatabase(
    os.getenv("DB_SCHEMA"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
)


class BaseModel(Model):
    class Meta:
        database = db


class FundingRate(BaseModel):
    id = AutoField()
    symbol = CharField(max_length=32)
    ticker = CharField(max_length=64, null=True)
    fundingRate = DecimalField(max_digits=20, decimal_places=10, null=True)
    interval = CharField(max_length=16, null=True)
    fundingDatetime = CharField(max_length=64, null=True)
    fundingRateAnnualized = DecimalField(max_digits=20, decimal_places=10, null=True)
    timestamp = DateTimeField()


class Staking(BaseModel):
    id = AutoField()
    # Add staking metrics
    stakeApy = DecimalField(max_digits=20, decimal_places=10, null=True)
    sharePrice = DecimalField(max_digits=36, decimal_places=18, null=True)
    timestamp = DateTimeField()


class FundingData(BaseModel):
    symbol = CharField()
    exchange = CharField()
    rate = FloatField()
    rate_1y = FloatField()
    next_funding = CharField()
    interval = FloatField()
    timestamp = DateTimeField()


def create_table():
    # Create table if not exists
    db.connect()
    db.create_tables([FundingRate, Staking, FundingData])


def main():
    ReyaDataCrawler().run()


class ReyaDataCrawler:
    top3_symbols = ["BTC/RUSD:RUSD", "ETH/RUSD:RUSD", "SOL/RUSD:RUSD"]
    SYMBOLS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'HYPE/USDT:USDT', 'ENA/USDT:USDT', 'TAO/USDT:USDT', "ARB/USDT:USDT", "LTC/USDT:USDT"]  # predefined subset, since the x scales fast big

    # --- Exchange configurations ---
    ALL_EXCHANGES = {
        'binance': ccxt.binance({'enableRateLimit': True}),
        'okx': ccxt.okx({'enableRateLimit': True}),
        'bybit': ccxt.bybit({'enableRateLimit': True}),
        'kucoin': ccxt.kucoinfutures({'enableRateLimit': True}),
        #'bitget': ccxt.bitget({'enableRateLimit': True}),
        #'bingx': ccxt.bingx({'enableRateLimit': True}),
        'hyperliquid': ccxt.hyperliquid({'enableRateLimit': True}),
        'reya': Reya({'enableRateLimit': True}),
        "lighter": Lighter({'enableRateLimit': True}),
        "edgex": EdgeX({'enableRateLimit': True})
    }
    # Jupiter, DyDx, orderly, avantis, myx, radium, drift, ligther

    TELEGRAM_NOTIFY = True

    # Store last sent arbitrages in memory (dict)
    last_sent = {}

    # Track last funding rate summary sent
    last_funding_summary_sent = None

    def __init__(self):
        config = TradingConfig.from_env()

        # signer = ReyaSignerAdapter(private_key = config.private_key, wallet_address=config.wallet_address, account_id=config.account_id, chain_id=config.chain_id) TODO not working right now
        signer = None
        self.exchange = Reya({
            'walletAddress': config.wallet_address,
            'privateKey': config.private_key,
            'options': {'signer': signer,
                        'account_id': config.account_id},
            'verbose': True,
        })
        client = ReyaTradingClient()
        self.exchange.withClient(client)
        self.telegram = Telegram()

        # load markets
        self.exchange.load_markets()
        #self.init_symbols()

    def init_symbols(self):
        # base are all reya symbols that are also available on binance
        markets = self.exchange.load_markets()
        market_names = list(markets.keys())
        market_names = [name.replace("RUSD", "USDT") for name in market_names]
        logging.info(f"Markets found: {market_names}")

        binance_markets = self.ALL_EXCHANGES['binance'].load_markets()
        binance_symbols = set(binance_markets.keys())

        # keep only those symbols that exist on Binance
        common_symbols = [s for s in market_names if s in binance_symbols]
        self.SYMBOLS = common_symbols
        logging.info(f"{len(self.SYMBOLS)} SYMBOLS found on reya and binance: {self.SYMBOLS}")

    def run(self):
        while True:
            print("fetch reya funding rates:")
            try:
                self.fetching_reya_funding_and_apy()
                self.fetch_funding_rates()

                # Check if we should send the 30-minute funding summary
                self.send_funding_summary_if_needed()

            except Exception as e:
                print(f"Error occurred: {e}")
                time.sleep(5)
                continue  # dont sleep long
            print("sleep 5min")
            time.sleep(300)

    def send_funding_summary_if_needed(self):
        """Send a funding rate summary every 30 minutes for BTC, ETH, SOL"""
        now = datetime.datetime.utcnow()

        # Check if 30 minutes have passed since last summary
        if self.last_funding_summary_sent is None or \
                (now - self.last_funding_summary_sent) >= datetime.timedelta(minutes=30):

            try:
                self.send_funding_summary()
                self.last_funding_summary_sent = now
                logging.info("Funding summary sent successfully")
            except Exception as e:
                logging.error(f"Error sending funding summary: {e}")

    def send_funding_summary(self):
        """Fetch and send current funding rates for BTC, ETH, SOL across some exchanges"""
        top_symbols = ['BTC', 'ETH', 'SOL']
        SUMMARY_EXCHANGES = {
            'bybit': self.ALL_EXCHANGES['bybit'],
            'hyperliquid': self.ALL_EXCHANGES['hyperliquid'],
            'reya': self.ALL_EXCHANGES['reya'],
        }
        summary_data = {symbol: [] for symbol in top_symbols}

        def fetch_single_for_summary(exchange_name, exchange, symbol, max_retries=3, retry_delay=1):
            for attempt in range(max_retries):
                try:
                    factor = 100
                    fetch_symbol = f"{symbol}/USDT:USDT"

                    if exchange.name == "Hyperliquid":
                        fetch_symbol = f"{symbol}/USDC:USDC"
                    elif exchange.name == "Reya":
                        fetch_symbol = f"{symbol}/RUSD:RUSD"
                        factor = 1

                    funding_rate = exchange.fetch_funding_rate(fetch_symbol)

                    if funding_rate and 'fundingRate' in funding_rate:
                        rate = funding_rate['fundingRate']
                        interval = float((funding_rate.get('interval') or '8').replace("h", ""))
                        if rate is not None:
                            return {
                                'exchange': exchange.name,
                                'rate_1h': float(rate) * factor / interval,
                                'rate_1y': (float(rate) / interval) * 24 * factor * 365,
                            }
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.warning(
                            f"Error fetching {exchange_name} {symbol} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                    else:
                        logging.error(f"Error fetching {exchange_name} {symbol} after {max_retries} attempts: {e}")

            return None

        # Fetch rates for all exchanges in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for symbol in top_symbols:
                for exchange_name, exchange in SUMMARY_EXCHANGES.items():
                    futures.append((symbol, executor.submit(fetch_single_for_summary, exchange_name, exchange, symbol)))

            for symbol, future in futures:
                result = future.result()
                if result:
                    summary_data[symbol].append(result)

        # Format and send message
        message = self.format_funding_summary(summary_data)
        if message:
            self.telegram.sendMessage(message)

    def format_funding_summary(self, summary_data):
        """Format the funding rate summary into a readable message"""
        message = "📊 <b>Funding Rate Summary</b>\n"
        message += f"🕐 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"

        for symbol in ['BTC', 'ETH', 'SOL']:
            rates = summary_data.get(symbol, [])
            if not rates:
                continue

            message += f"<b>{symbol}</b>\n"

            # Sort by 1h rate
            rates_sorted = sorted(rates, key=lambda x: x['rate_1y'], reverse=True)

            for rate_data in rates_sorted:
                rate_1y = rate_data['rate_1y']
                exchange = rate_data['exchange']

                # Add emoji based on rate direction
                emoji = "🔴" if rate_1y < -1 else "🟢" if rate_1y > 1 else "⚪"

                message += f"{emoji} <b>{exchange}</b>: "
                message += f"{rate_1y:+.2f}% (1Y)\n"

            message += "\n"

        return message if len(summary_data) > 0 else None

    def fetching_reya_funding_and_apy(self):
        apy = self.exchange.get_current_stake_apy()
        stakeApy = apy['apy']
        price = apy['share_price']
        Staking.create(timestamp=datetime.datetime.utcnow(),
                       stakeApy=stakeApy,
                       sharePrice=price)
        logging.info(f"stake APY: {stakeApy}, share price: {price}")
        for symbol in self.top3_symbols:
            try:
                funding = self.exchange.fetch_funding_rate(symbol)

                FundingRate.create(
                    timestamp=datetime.datetime.utcnow(),
                    symbol=symbol,
                    ticker=funding['info'].get('ticker', ''),
                    fundingRate=funding['info'].get('fundingRate', None),
                    interval=funding.get('interval', ''),
                    fundingDatetime=funding.get('fundingDatetime', ''),
                    fundingRateAnnualized=funding['info'].get('fundingRateAnnualized', None),
                )

                logging.info(f"[{datetime.datetime.utcnow().isoformat()}] {symbol} funding rate: "
                             f"{funding['info'].get('fundingRate', '')}@{funding.get('interval', '')}, "
                             f"yearly: {funding['info'].get('fundingRateAnnualized', '')}%")

            except Exception as e:
                logging.error(f"Error fetching {symbol}: {e}")

    def fetch_funding_rates(self):
        """Fetch funding rates from all exchanges in parallel"""
        funding_data = []

        def fetch_single(exchange_name, exchange, symbol, sem):
            with sem:  # allow only 2 concurrent tasks per exchange
                try:
                    logging.info(f"Fetching {exchange_name}/{symbol}")
                    factor = 100
                    if exchange.name == "Hyperliquid":
                        symbol = symbol.replace("USDT", "USDC")
                    elif exchange.name == "Reya":
                        symbol = symbol.replace("USDT", "RUSD")
                        factor = 1

                    funding_rate = exchange.fetch_funding_rate(symbol)

                    if funding_rate and 'fundingRate' in funding_rate:
                        rate = funding_rate['fundingRate']
                        interval = float((funding_rate.get('interval') or '8').replace("h", ""))
                        if rate is not None and rate != 0:
                            return {
                                'Symbol': self.extract_base_symbol(symbol),
                                'Exchange': exchange.name,
                                'Rate': float(rate) * factor / interval,
                                'Yearly Rate': (float(rate) / interval) * 24 * factor * 365,
                                'Next Funding': funding_rate.get('fundingDatetime') or 'N/A',
                                'Interval': interval,
                            }
                except Exception as e:
                    logging.error(f"Error fetching {exchange_name} {symbol} rate: {e}")
                return None

        tasks = []
        semaphores = {ex: threading.Semaphore(2) for ex in self.ALL_EXCHANGES}  # max 2 per exchange

        with ThreadPoolExecutor(max_workers=10) as executor:
            for exchange_name, exchange in self.ALL_EXCHANGES.items():
                sem = semaphores[exchange_name]
                for symbol in self.SYMBOLS:
                    tasks.append(executor.submit(fetch_single, exchange_name, exchange, symbol, sem))

            for future in as_completed(tasks):
                result = future.result()
                if result:
                    df = pd.DataFrame([result])  # create a 1-row DataFrame
                    self.insert_from_dataframe(df)  # insert immediately
                    funding_data.append(result)

        df = pd.DataFrame(funding_data)
        # self.insert_from_dataframe(df)
        if self.TELEGRAM_NOTIFY:
            best, all = self.find_best_arbitrage_opportunities(df)
            for _, row in best.iterrows():
                if not self.should_send(row):
                    continue  # Skip if still in cooldown
                try:
                    self.sendMessage(row)
                except Exception as e:
                    logging.error(f"Error sending message: {e}")

    def sendMessage(self, row):
        formatted = f"""Arbitrage Opportunity
🚀 <b>{row['Symbol']}</b>
                
📈 <b>Long</b> on <b>{row['Long Exchange']}</b>  
at <b>{row['Long Rate (1h)']:.4f}% (1h)</b> | <b>{row['Long Rate (1Y)']:.2f}% (1Y)</b>
                
📉 <b>Short</b> on <b>{row['Short Exchange']}</b>  
at <b>{row['Short Rate (1h)']:.4f}% (1h)</b> | <b>{row['Short Rate (1Y)']:.2f}% (1Y)</b>

🔎 <b>Spread:</b> <b>{row['Spread (1h)']:.4f}% (1h)</b> | <b>{row['Spread (1Y)']:.2f}% (1Y)</b>
"""
        self.telegram.sendMessage(formatted)

    def should_send(self, row, cooldown_hours=24):
        """Check if we should send this arbitrage opportunity via telegram."""
        key = (row['Symbol'], row['Long Exchange'], row['Short Exchange'])
        now = datetime.datetime.utcnow()

        if key not in self.last_sent:
            self.last_sent[key] = now
            return True

        last_time = self.last_sent[key]
        if now - last_time >= datetime.timedelta(hours=cooldown_hours):
            self.last_sent[key] = now
            return True

        return False

    def extract_base_symbol(self, symbol):
        return symbol.replace('/USDT:USDT', '').replace("/USDC:USDC", "").replace("/RUSD:RUSD", "")

    def insert_from_dataframe(self, df: pd.DataFrame):
        logging.info("Inserting from dataframe")
        with db.atomic():
            for _, row in df.iterrows():
                FundingData.create(
                    symbol=row["Symbol"],
                    exchange=row["Exchange"],
                    rate=row["Rate"],
                    rate_1y=row["Yearly Rate"],
                    next_funding=row["Next Funding"],
                    interval=row["Interval"],
                    timestamp=datetime.datetime.utcnow()
                )

    # ==========================
    # Arbitrage Detection
    # ==========================
    def find_best_arbitrage_opportunities(self, df):
        logging.info(f"Finding best arbitrage opportunities")
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

            # ✅ only keep if Reya is involved on either side
            if "reya" in (best_pos["Exchange"].lower(), best_neg["Exchange"].lower()):
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
        logging.info(f"sort")
        all_results = pd.DataFrame(all_results).sort_values(by="Spread (1h)", ascending=False)
        best_results = pd.DataFrame(best_results).sort_values(by="Spread (1h)", ascending=False)
        return pd.DataFrame(best_results), pd.DataFrame(all_results)


if __name__ == '__main__':
    create_table()
    main()
