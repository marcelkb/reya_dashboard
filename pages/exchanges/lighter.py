import json
import math

import ccxt
import aiohttp
import asyncio
from typing import Any, Dict, Optional, List
from ccxt.base.types import Strings, Int, FundingRate, Entry

from pages.exchanges.abstract.lighter import ImplicitAPI


class Lighter(ccxt.Exchange, ImplicitAPI):
    base_url = "https://mainnet.zklighter.elliot.ai"

    def __init__(self, config: Dict[str, Any] = {}):
        super().__init__(config)

    # -----------------------------
    # CCXT describe
    # -----------------------------
    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(Lighter, self).describe(),
            {
                "id": "lighter",
                "name": "Lighter",
                "countries": ["US"],
                "version": "v1",
                "rateLimit": 100,
                "certified": False,
                "pro": False,
                "has": {
                    "spot": True,
                    "margin": False,
                    "swap": False,
                    "future": False,
                    "option": False,
                    "fetchMarkets": True,
                    "fetchCurrencies": True,
                    "fetchTicker": True,
                    "fetchOrderBook": True,
                    "fetchOHLCV": True,
                    "fetchBalance": True,
                    "fetchTrades": True,
                    "fetchMyTrades": True,
                    "createOrder": True,
                    "cancelOrder": True,
                    "fetchOrder": True,
                    "fetchOrders": True,
                    "fetchOpenOrders": True,
                    "fetchClosedOrders": True,
                },
                "urls": {
                    "api": {
                        "public": self.base_url,
                        "private": self.base_url,
                    },
                    "www": "https://lighter.xyz",
                    "doc": [
                        "https://apibetadocs.lighter.xyz/docs/",
                        "https://github.com/elliottech/lighter-python",
                    ],
                },
                "timeframes": {
                    "1m": "1m",
                    "5m": "5m",
                    "15m": "15m",
                    "1h": "1h",
                    "4h": "4h",
                    "1d": "1d",
                },
            },
        )

        # -------------------
        # Signing: call SDK signer only for private endpoints, TODO right now not working good
        # -------------------

    def sign(self, path: str, api: str = "public", method: str = "GET", params: Optional[Dict] = None,
             headers: Optional[Dict] = None, body: Optional[Any] = None):
        """
        Build URL, headers, body. For private endpoints call the signer supplied in options['signer'].
        The signer must return a dict of headers to attach (including signature and nonce if required).
        """
        params = params or {}
        headers = headers or {}
        url = self.urls["api"][api] + "/" + path.lstrip("/")

        if api == "public":
            # replace placeholders in path, e.g. /prices/{symbol}
            used_keys = []
            for k, v in params.items():
                placeholder = "{" + k + "}"
                if placeholder in url:
                    url = url.replace(placeholder, str(v))
                    used_keys.append(k)

            # remove used params
            for k in used_keys:
                params.pop(k, None)

            if method == "GET":
                if params:
                    url += "?" + self.urlencode(params)
                body = None
            else:
                body = self.json(params) if params else None
                headers["Content-Type"] = "application/json"

            return {
                "url": url,
                "method": method,
                "body": body,
                "headers": headers,
            }

    def fetch_markets(self, params: Optional[Dict] = None) -> List[Dict]:
        return []

    def load_markets(self, params: Optional[Dict] = None) -> List[Dict]:
        return []


    def get_base_token(self, symbol: str) -> str:
        return symbol.replace("/USDT:USDT", "").replace("/USDC:USDC", "")

    def fetch_funding_rate(self, symbol: str, params: object = {}) -> FundingRate | None:
        data = self.publicGetApiFunding(params)
        if "funding_rates" in data:
            for rate in data["funding_rates"]:
                if rate["symbol"] == self.get_base_token(symbol) and rate["exchange"] == "lighter":
                    fr = self._parse_funding_rate(symbol, rate)
                    return fr

    def _parse_funding_rate(self, symbol, rate) -> FundingRate:
        # Summary
        # {
        #     "market_id": 42,
        #     "exchange": "binance",
        #     "symbol": "SPX",
        #     "rate": 0.0001
        # },
        #
        symbol = symbol
        funding = self.safe_number(rate, 'rate')
        markPx = 0
        oraclePx = 0
        fundingTimestamp = (int(math.floor(self.milliseconds()) / 60 / 60 / 1000) + 1) * 60 * 60 * 1000

        additionalInfo = {}
        additionalInfo['fundingDatetime'] = fundingTimestamp
        additionalInfo['fundingRateAnnualized'] = funding * 3 * 365

        return {
            'info': self.extend(rate, additionalInfo),
            'symbol': symbol,
            'markPrice': markPx,
            'indexPrice': oraclePx,
            'interestRate': None,
            'estimatedSettlePrice': None,
            'timestamp': None,
            'datetime': None,
            'fundingRate': funding,
            'fundingTimestamp': fundingTimestamp,
            'fundingDatetime': self.iso8601(fundingTimestamp),
            'nextFundingRate': None,
            'nextFundingTimestamp': None,
            'nextFundingDatetime': None,
            'previousFundingRate': None,
            'previousFundingTimestamp': None,
            'previousFundingDatetime': None,
            'interval': '8h',
        }

