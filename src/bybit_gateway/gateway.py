from src.datatypes import TickData, Symbol, OrderRequest, CancelRequest
from src.strategy import Strategy
from src.manager import LocalOrderManager
from typing import Any, Callable, Optional, Type, Union
from types import TracebackType
from multiprocessing import Pool
from enum import Enum
from src.logger import LogFactory
import multiprocessing
import os
import time
import requests
import json
import logging
import socket
import ssl
import sys
import hmac
import hashlib
import traceback
from datetime import datetime
from threading import Lock, Thread
from time import sleep
from typing import Optional

class RequestStatus(Enum):
    ready = 0  # Request created
    success = 1  # Request successful (status code 2xx)
    failed = 2  # Request failed (status code not 2xx)
    error = 3  # Exception raised


pool: multiprocessing.pool.Pool = Pool(os.cpu_count() * 20)

CALLBACK_TYPE = Callable[[dict, "Request"], Any]
ON_FAILED_TYPE = Callable[[int, "Request"], Any]
ON_ERROR_TYPE = Callable[[Type, Exception, TracebackType, "Request"], Any]
CONNECTED_TYPE = Callable[["Request"], Any]

REST_HOST = "https://api.bybit.com"
TESTNET_REST_HOST = "https://api-testnet.bybit.com"


class BybitGateway(object):
    def __init__(self):
        self.order_manager = LocalOrderManager(self, str(time.time()))
        self.rest_api = BybitRestApi(self)
        self.ws_api = WebsocketClient(self)
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

    def send_order(self, req: OrderRequest):
        """"""
        return self.rest_api.send_order(req)

    def cancel_order(self, req: CancelRequest):
        """"""
        self.rest_api.cancel_order(req)

    def query_position(self):
        """"""
        self.rest_api.query_position()

    def close(self):
        """"""
        self.rest_api.stop()
        self.ws_api.stop()


class Request:
    def __init__(
            self,
            method: str,
            path: str,
            params: dict,
            data: Union[dict, str, bytes],
            headers: dict,
            callback: CALLBACK_TYPE = None,
            on_failed: ON_FAILED_TYPE = None,
            on_error: ON_ERROR_TYPE = None,
            stream: bool = False,
            on_connected: CONNECTED_TYPE = None,  # for streaming request
            extra: Any = None,
            client: "RestClient" = None,
    ):
        """"""
        self.method = method
        self.path = path
        self.callback = callback
        self.params = params
        self.data = data
        self.headers = headers

        self.stream = stream
        self.on_connected = on_connected
        self.processing_line: Optional[str] = ''

        self.on_failed = on_failed
        self.on_error = on_error
        self.extra = extra

        self.response: Optional[requests.Response] = None
        self.status = RequestStatus.ready
        self.client: "RestClient" = client

    def __str__(self):
        if self.response is None:
            status_code = "terminated"
        else:
            status_code = self.response.status_code

        if self.stream:
            response = self.processing_line
        else:
            if self.response is None:
                response = None
            else:
                response = self.response.text

        return (
            "request: {method} {path} {http_code}: \n"
            "full_url: {full_url}\n"
            "status: {status}\n"
            "headers: {headers}\n"
            "params: {params}\n"
            "data: {data}\n"
            "response: {response}\n".format(
                full_url=self.client.make_full_url(self.path),
                status=self.status.name,
                method=self.method,
                path=self.path,
                http_code=status_code,
                headers=self.headers,
                params=self.params,
                data=self.data,
                response=response,
            )
        )


class BybitRestApi:
    def __init__(self, order_manager: LocalOrderManager):
        """"""
        self.order_manager = order_manager
        self.logger: Optional[logging.Logger] = None

        self.url_base: str = ""
        self.key = ""
        self.secret = b""

        self.order_count = 1_000_000
        self.order_count_lock = Lock()
        self.connect_time = 0

        self._active: bool = False

    def sign(self, request: Request):
        """
        Generate ByBit signature.
        """
        request.headers = {"Referer": "vn.py"}

        if request.method == "GET":
            api_params = request.params
            if api_params is None:
                api_params = request.params = {}
        else:
            api_params = request.data
            if api_params is None:
                api_params = request.data = {}

        api_params["api_key"] = self.key
        api_params["recv_window"] = 30 * 1000
        api_params["timestamp"] = generate_timestamp(-5)

        data2sign = "&".join(
            [f"{k}={v}" for k, v in sorted(api_params.items())])
        signature = sign(self.secret, data2sign.encode())
        api_params["sign"] = signature

        return request

    def init(self,
             url_base: str,
             log_path: Optional[str] = None,
             ):
        """
        Init rest client with url_base which is the API root address.
        e.g. 'https://www.bitmex.com/api/v1/'
        :param url_base:
        :param log_path: optional. file to save logger.
        """
        self.url_base = url_base

        if log_path is not None:
            self.logger = LogFactory.get_file_logger(log_path)
            self.logger.setLevel(logging.DEBUG)

    def connect(
            self,
            key: str,
            secret: str,
            server: str,
    ):
        """
        Initialize connection to REST server.
        """
        self.key = key
        self.secret = secret.encode()

        self.connect_time = (
                int(datetime.now().strftime("%y%m%d%H%M%S")) * self.order_count
        )

        if server == "REAL":
            self.init(REST_HOST)
        else:
            self.init(TESTNET_REST_HOST)

        self.start(3)
        self.logger.info("REST API启动成功")

        # self.query_contract()
        # self.query_order()
        # self.query_position()

    def start(self, n: int = 3):
        """
        Start rest client with session count n.
        """
        if self._active:
            return
        self._active = True


class WebsocketClient(object):
    """
    Websocket API

    After creating the client object, use start() to run worker and ping threads.
    The worker thread connects websocket automatically.

    Use stop to stp threads and disconnect websocket before destroying the client
    object (especially when exiting the programme).

    Default serialization format is json.

    Callbacks to overrides:
    * unpack_data
    * on_connected
    * on_disconnected
    * on_packet
    * on_error

    After start() is called, the ping thread will ping server every 60 seconds.

    If you want to send anything other than JSON, override send_packet.
    """

    def __init__(self, gateway: BybitGateway):
        """Constructor"""
        self.gateway = gateway
        self.host = None

        self._ws_lock = Lock()
        self._ws = None

        self._worker_thread = None
        self._ping_thread = None
        self._active = False

        self.ping_interval = 60  # seconds
        self.header = {}

        self.logger: Optional[logging.Logger] = None

        # For debugging
        self._last_sent_text = None
        self._last_received_text = None

    def init(self, host: str, ping_interval: int = 60, log_path: Optional[str] = None,
             ):
        """
        :param host:
        :param ping_interval: unit: seconds, type: int
        :param log_path: optional. file to save logger.
        """
        self.host = host
        self.ping_interval = ping_interval  # seconds
        if log_path is not None:
            self.logger = LogFactory.get_file_logger(log_path)
            self.logger.setLevel(logging.DEBUG)



def generate_timestamp(expire_after: float = 30) -> int:
    """
    :param expire_after: expires in seconds.
    :return: timestamp in milliseconds
    """
    return int(time.time() * 1000 + expire_after * 1000)


def sign(secret: bytes, data: bytes) -> str:
    """"""
    return hmac.new(
        secret, data, digestmod=hashlib.sha256
    ).hexdigest()