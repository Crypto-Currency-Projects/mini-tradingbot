from gateway.rest_gateway import BybitRestApi
from gateway.websocket import WebsocketClient
from datatypes import TickData, Symbol
from strategy import Strategy


class BybitGateway(object):
    def __init__(self):
        self._rest = BybitRestApi(self)
        self._websocket = WebsocketClient(self)
        self.strategy_map = {}

    def connect(self, setting: dict):
        """"""
        key = setting["ID"]
        secret = setting["Secret"]
        server = setting["服务器"]

        self.rest_api.connect(key, secret, server)
        self.ws_api.connect(key, secret, server)



    def register_strategy(self, symbol: Symbol, strategy: Strategy):
        self.strategy_map[symbol] = strategy

    def on_tick(self, tick: TickData):
        """
        Tick data.
        """
        for s in self.strategy_map[tick.symbol]:
            s.on_tick(tick)
