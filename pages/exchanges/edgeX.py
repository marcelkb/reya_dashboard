import json
import math

import ccxt
from typing import Any, Dict, Optional, List
from ccxt.base.types import Strings, Int, FundingRate, Entry

from pages.exchanges.abstract.edgeX import ImplicitAPI

class EdgeX(ccxt.Exchange, ImplicitAPI):
    base_url = "https://pro.edgex.exchange"

    def __init__(self, config: Dict[str, Any] = {}):
        super().__init__(config)

    # -----------------------------
    # CCXT describe
    # -----------------------------
    def describe(self) -> Dict[str, Any]:
        return self.deep_extend(
            super(EdgeX, self).describe(),
            {
                "id": "edgex",
                "name": "EdgeX",
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
                    "www": "https://pro.edgex.exchange/",
                    "doc": [
                        "https://edgex-1.gitbook.io/edgex-documentation/api/",
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
        # {
        #     "code": "SUCCESS",
        #     "data": {
        #         "global": {
        #             "appName": "edgeX",
        #             "appEnv": "testnet",
        #             "appOnlySignOn": "https://testnet.edgex.exchange",
        #             "feeAccountId": "123456",
        #             "feeAccountL2Key": "0x1e240",
        #             "poolAccountId": "542076087396467085",
        #             "poolAccountL2Key": "0x3bf794b4433e0a8b353da361bb7284c670914d27ed04698e6abed0bf1198028",
        #             "fastWithdrawAccountId": "542076087396467085",
        #             "fastWithdrawAccountL2Key": "0x3bf794b4433e0a8b353da361bb7284c670914d27ed04698e6abed0bf1198028",
        #             "fastWithdrawMaxAmount": "100000",
        #             "fastWithdrawRegistryAddress": "0xb2846943C2EdA3830Fb784d2a6de93435267b11D",
        #             "starkExChainId": "0xaa36a7",
        #             "starkExContractAddress": "0xa3Cb2622C532e46c4376FAd4AbFDf9eDC717BABf",
        #             "starkExCollateralCoin": {
        #                 "coinId": "1000",
        #                 "coinName": "USDT",
        #                 "stepSize": "0.000001",
        #                 "showStepSize": "0.0001",
        #                 "iconUrl": "https://static.edgex.exchange/icons/coin/USDT.svg",
        #                 "starkExAssetId": "0x33bda5c923bae4e84825b74762d5482889b9512465fbffc50d1ae4b82e345c3",
        #                 "starkExResolution": "0xf4240"
        #             },
        #             "starkExMaxFundingRate": 1120,
        #             "starkExOrdersTreeHeight": 64,
        #             "starkExPositionsTreeHeight": 64,
        #             "starkExFundingValidityPeriod": 604800,
        #             "starkExPriceValidityPeriod": 31536000,
        #             "maintenanceReason": ""
        #         },
        #         "coinList": [
        #             {
        #                 "coinId": "1000",
        #                 "coinName": "USDT",
        #                 "stepSize": "0.000001",
        #                 "showStepSize": "0.0001",
        #                 "iconUrl": "https://static.edgex.exchange/icons/coin/USDT.svg",
        #                 "starkExAssetId": "0x33bda5c923bae4e84825b74762d5482889b9512465fbffc50d1ae4b82e345c3",
        #                 "starkExResolution": "0xf4240"
        #             },
        #             {
        #                 "coinId": "1001",
        #                 "coinName": "BTC",
        #                 "stepSize": "0.001",
        #                 "showStepSize": "0.001",
        #                 "iconUrl": "https://static.edgex.exchange/icons/coin/BTC.svg",
        #                 "starkExAssetId": null,
        #                 "starkExResolution": null
        #             }
        #         ],
        #         "contractList": [
        #             {
        #                 "contractId": "10000001",
        #                 "contractName": "BTCUSDT",
        #                 "baseCoinId": "1001",
        #                 "quoteCoinId": "1000",
        #                 "tickSize": "0.1",
        #                 "stepSize": "0.001",
        #                 "minOrderSize": "0.001",
        #                 "maxOrderSize": "50.000",
        #                 "maxOrderBuyPriceRatio": "0.05",
        #                 "minOrderSellPriceRatio": "0.05",
        #                 "maxPositionSize": "60.000",
        #                 "riskTierList": [
        #                     {
        #                         "tier": 1,
        #                         "positionValueUpperBound": "50000",
        #                         "maxLeverage": "100",
        #                         "maintenanceMarginRate": "0.005",
        #                         "starkExRisk": "21474837",
        #                         "starkExUpperBound": "214748364800000000000"
        #                     },
        #                     {
        #                         "tier": 22,
        #                         "positionValueUpperBound": "79228162514264337593543",
        #                         "maxLeverage": "6",
        #                         "maintenanceMarginRate": "0.105",
        #                         "starkExRisk": "450971567",
        #                         "starkExUpperBound": "340282366920938463463374607431768211455"
        #                     }
        #                 ],
        res = self.publicGetApiMetadata(params)
        # the SDK/docs return a list of market objects
        result = res if isinstance(res, list) else self.safe_value(res, 'data', res)
        result = result['contractList']
        self.markets = {self.safe_string(m, 'contractId', str(self.safe_integer(m,'contractId'))) : m for m in result }
        self.markets_by_id = self.markets
        out = []
        for mid, m in self.markets.items():
            quoteToken = self._getSymbol(m.get("contractName"))
            underlyingAsset = "USDT"
            tickSize = m.get('tickSize')
            if not tickSize:
                tickSize = "1"
            out.append({
                'id': self.safe_string(m, 'contractId'),
                'symbol': f"{quoteToken}/{underlyingAsset}:{underlyingAsset}".upper(),
                'base': quoteToken.upper() if quoteToken is not None else '',
                'quote': underlyingAsset.upper() if underlyingAsset is not None else '',
                'asset_pair_id': self.safe_string_2(m, 'contractId', 'contractId'),
                'type': 'swap',
                'spot': False,
                'margin': False,
                'swap': True,
                'future': False,
                'option': False,
                'active': None,
                'precision': {'amount': tickSize},
                'limits': {'cost': {'min': 1}},
                'info': m,
            })
        return out

    def _getSymbol(self, perp_name):
        return perp_name.replace('USDT', '').replace("USD", "")

    def _decimal_places(self, x):
        return int(-math.log10(float(x)))

    def load_markets(self, params: Optional[Dict] = None) -> List[Dict]:
        return []


    def get_base_token(self, symbol: str) -> str:
        return symbol.replace("/USDT:USDT", "").replace("/USDC:USDC", "")

    def fetch_funding_rate(self, symbol: str, params: object = {}) -> FundingRate | None:
        # {
        #     "code": "SUCCESS",
        #     "data": [
        #         {
        #             "contractId": "10000001",
        #             "fundingTime": "1734595200000",
        #             "fundingTimestamp": "1734597720000",
        #             "oraclePrice": "101559.9220921285450458526611328125",
        #             "indexPrice": "101522.558968500",
        #             "fundingRate": "-0.00005537",
        #             "isSettlement": false,
        #             "forecastFundingRate": "-0.00012293",
        #             "previousFundingRate": "0.00000567",
        #             "previousFundingTimestamp": "1734595140000",
        #             "premiumIndex": "-0.00036207",
        #             "avgPremiumIndex": "-0.00032293",
        #             "premiumIndexTimestamp": "1734597720000",
        #             "impactMarginNotional": "100",
        #             "impactAskPrice": "101485.8",
        #             "impactBidPrice": "101484.7",
        #             "interestRate": "0.0003",
        #             "predictedFundingRate": "0.00005000",
        #             "fundingRateIntervalMin": "240",
        #             "starkExFundingIndex": "101559.9220921285450458526611328125"
        #         }
        #     ],
        #     "msg": null,
        #     "errorParam": null,
        #     "requestTime": "1734597737870",
        #     "responseTime": "1734597737873",
        #     "traceId": "5e27ebfb0ae79f51bbd347d2bf3585f9"
        # }
        # ]
        markets = self.fetch_markets(params)

        contract_id = self.get_contract_id(markets, symbol)

        request = {"contractId": contract_id}
        data = self.publicGetApiFunding(self.extend(request, params or {}))['data']
        return self._parse_funding_rate(symbol, data)

    def get_contract_id(self, markets, symbol):
        for market in markets:
            # your symbol seems to match contractName (ex: BTCUSD)
            if market["symbol"] == symbol:
                return market["id"]
        return None

    def _parse_funding_rate(self, symbol, rate) -> FundingRate:
        # [{'avgPremiumIndex': '-0.00043085', 'contractId': '10000001', 'forecastFundingRate': '0.00005000',
        #   'fundingRate': '0.00005000', 'fundingRateIntervalMin': '240', 'fundingTime': '1757952000000',
        #   'fundingTimestamp': '1757957160000', 'impactAskPrice': '114608.0', 'impactBidPrice': '114606.6',
        #   'impactMarginNotional': '100', 'indexPrice': '114668.763751750', 'interestRate': '0.0003',
        #   'isSettlement': False, 'oraclePrice': '114671.950000338256359100341796875',
        #   'predictedFundingRate': '0.00005000', 'premiumIndex': '-0.00052990', 'premiumIndexTimestamp': '1757957160000',
        #   'previousFundingRate': '0.00005000', 'previousFundingTimestamp': '1757951940000',
        #   'starkExFundingIndex': '114671.950000338256359100341796875'}]

        symbol = symbol
        funding = self.safe_number(rate[0], 'fundingRate')
        markPx = 0
        oraclePx = 0
        fundingTimestamp = (int(math.floor(self.milliseconds()) / 60 / 60 / 1000) + 1) * 60 * 60 * 1000

        additionalInfo = {}
        additionalInfo['fundingDatetime'] = fundingTimestamp
        additionalInfo['fundingRateAnnualized'] = funding * 3 * 365

        return {
            'info': self.extend(rate[0], additionalInfo),
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
            'interval': '4h',
        }

