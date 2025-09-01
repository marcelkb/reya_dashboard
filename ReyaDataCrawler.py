import datetime
import logging
import os
import time

from dotenv import load_dotenv
from sdk import ReyaTradingClient, stake, TradingConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Create a logger for this module
from exchange.Reya import Reya

from peewee import (
    Model, CharField, DateTimeField, DecimalField, AutoField
)
from playhouse.mysql_ext import MariaDBConnectorDatabase
from datetime import datetime
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

def create_table():
    # Create table if not exists
    db.connect()
    db.create_tables([FundingRate, Staking])

def main():
    config = TradingConfig.from_env()

    #signer = ReyaSignerAdapter(private_key = config.private_key, wallet_address=config.wallet_address, account_id=config.account_id, chain_id=config.chain_id) TODO not working right now
    signer = None
    exchange = Reya({
        'walletAddress': config.wallet_address,
        'privateKey': config.private_key,
        'options':{'signer': signer,
        'account_id': config.account_id},
        'verbose': True,
    })
    client = ReyaTradingClient()
    exchange.withClient(client)

    # load markets
    exchange.load_markets()

    symbols = ["BTC/RUSD:RUSD", "ETH/RUSD:RUSD", "SOL/RUSD:RUSD"]

    while True:
        print("fetch funding rates:")
        apy = exchange.get_current_stake_apy()
        stakeApy = apy['apy']
        price = apy['share_price']
        Staking.create(timestamp=datetime.utcnow(),
                        stakeApy=stakeApy,
                    sharePrice=price)
        print(f"stake APY: {stakeApy}, share price: {price}")
        for symbol in symbols:
            try:
                funding = exchange.fetch_funding_rate(symbol)

                FundingRate.create(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    ticker=funding['info'].get('ticker', ''),
                    fundingRate=funding['info'].get('fundingRate', None),
                    interval=funding.get('interval', ''),
                    fundingDatetime=funding.get('fundingDatetime', ''),
                    fundingRateAnnualized=funding['info'].get('fundingRateAnnualized', None),
                )

                print(f"[{datetime.utcnow().isoformat()}] {symbol} funding rate: "
                      f"{funding['info'].get('fundingRate', '')}@{funding.get('interval', '')}, "
                      f"yearly: {funding['info'].get('fundingRateAnnualized', '')}%")

            except Exception as e:
                print(f"Error fetching {symbol}: {e}")

        print("sleep 5min")
        time.sleep(300)


if __name__ == '__main__':
    create_table()
    main()

