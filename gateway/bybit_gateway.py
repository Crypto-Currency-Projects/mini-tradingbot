from gateway.rest_gateway import BybitRestApi
from gateway.websocket import WebsocketClient
from datatypes import TickData, Symbol, OrderRequest, CancelRequest
from strategy import Strategy
from manager import LocalOrderManager
import time


class BybitGateway(object):
    def __init__(self):
        self._rest = BybitRestApi(self)
        self._websocket = WebsocketClient(self)
        self.strategy_map = {}
        self.order_manager = LocalOrderManager(self, str(time.time()))

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

    def send_order(self, req: OrderRequest):
        """"""
        return self.rest_api.send_order(req)

    def cancel_order(self, req: CancelRequest):
        """"""
        self.rest_api.cancel_order(req)
