from src.datatypes import TickData, Symbol, OrderRequest, CancelRequest
from src.strategy import Strategy
from typing import Any, Callable, Optional, Type, Union, List
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

from copy import copy
from src.datatypes import OrderData, CancelRequest
import uuid


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
        key = setting["Key"]
        secret = setting["Secret"]
        server = setting["Server"]

        self.rest_api.connect(key, secret, server)
        # self.ws_api.connect(key, secret, server)

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
            client=None,
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
        self.client = client

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
    def __init__(self, gateway: BybitGateway):
        """"""
        self.gateway = gateway
        self.order_manager = gateway.order_manager
        self.logger = LogFactory.get_logger("SAMPLE_LOGGER")

        self.url_base: str = ""
        self.key = ""
        self.secret = b""

        self.order_count = 1_000_000
        self.order_count_lock = Lock()
        self.connect_time = 0

        self._active: bool = False

        self._tasks_lock = Lock()
        self._tasks: List[multiprocessing.pool.AsyncResult] = []
        self._sessions_lock = Lock()
        self._sessions: List[requests.Session] = []

        self._streams_lock = Lock()
        self._streams: List[Thread] = []

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
            self.url_base = REST_HOST
        else:
            self.url_base = TESTNET_REST_HOST

        self.start(3)
        self.logger.info("REST API启动成功")

        self.query_contract()
        # self.query_order()
        # self.query_position()

    def start(self, n: int = 3):
        """
        Start rest client with session count n.
        """
        if self._active:
            return
        self._active = True

    def query_contract(self):
        """"""
        self.add_request(
            "GET",
            "/v2/public/symbols",
            self.on_query_contract
        )

    def on_query_contract(self, data: dict, request: Request):
        """"""
        if self.check_error("查询合约", data):
            return

        for d in data["result"]:
            print(d)
            # self.gateway.on_contract(contract)

        self.logger.info("合约信息查询成功")

    def check_error(self, name: str, data: dict):
        """"""
        if data["ret_code"]:
            error_code = data["ret_code"]
            error_msg = data["ret_msg"]
            msg = f"{name}失败，错误代码：{error_code}，信息：{error_msg}"
            self.logger.info(msg)
            return True

        return False

    def add_request(
            self,
            method: str,
            path: str,
            callback: CALLBACK_TYPE,
            params: dict = None,
            data: Union[dict, str, bytes] = None,
            headers: dict = None,
            on_failed: ON_FAILED_TYPE = None,
            on_error: ON_ERROR_TYPE = None,
            extra: Any = None,
    ):
        """
        Add a new request.
        :param method: GET, POST, PUT, DELETE, QUERY
        :param path:
        :param callback: callback function if 2xx status, type: (dict, Request)
        :param params: dict for query string
        :param data: Http body. If it is a dict, it will be converted to form-data. Otherwise, it will be converted to bytes.
        :param headers: dict for headers
        :param on_failed: callback function if Non-2xx status, type, type: (code, Request)
        :param on_error: callback function when catching Python exception, type: (etype, evalue, tb, Request)
        :param extra: Any extra data which can be used when handling callback
        :return: Request
        """
        request = Request(
            method=method,
            path=path,
            params=params,
            data=data,
            headers=headers,
            callback=callback,
            on_failed=on_failed,
            on_error=on_error,
            extra=extra,
            client=self,
        )
        task = pool.apply_async(
            self._process_request,
            args=[request, ],
            callback=self._clean_finished_tasks,
            # error_callback=lambda e: self.on_error(type(e), e, e.__traceback__, request),
        )
        self._push_task(task)
        return request

    def _clean_finished_tasks(self, result: None):
        with self._tasks_lock:
            not_finished_tasks = [i for i in self._tasks if not i.ready()]
            self._tasks = not_finished_tasks

    def _push_task(self, task):
        with self._tasks_lock:
            self._tasks.append(task)

    def _process_request(
            self, request: Request
    ):
        """
        Sending request to server and get result.
        """
        try:
            with self._get_session() as session:
                request = self.sign(request)
                url = self.url_base + request.path

                # send request
                uid = uuid.uuid4()
                stream = request.stream
                method = request.method
                headers = request.headers
                params = request.params
                data = request.data
                self.logger.info("[%s] sending request %s %s, headers:%s, params:%s, data:%s",
                                 uid, method, url,
                                 headers, params, data)
                response = session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    stream=stream,
                )
                request.response = response
                status_code = response.status_code

                self.logger.info("[%s] received response from %s:%s", uid, method, url)

                # check result & call corresponding callbacks
                if not stream:  # normal API:
                    # just call callback with all contents received.
                    if status_code // 100 == 2:  # 2xx codes are all successful
                        if status_code == 204:
                            json_body = None
                        else:
                            json_body = response.json()
                        self._process_json_body(json_body, request)
                    else:
                        if request.on_failed:
                            request.status = RequestStatus.failed
                            request.on_failed(status_code, request)
                        else:
                            self.on_failed(status_code, request)
                else:  # streaming API:
                    if request.on_connected:
                        request.on_connected(request)
                    # split response by lines, and call one callback for each line.
                    for line in response.iter_lines(chunk_size=None):
                        if line:
                            request.processing_line = line
                            json_body = json.loads(line)
                            self._process_json_body(json_body, request)
                    request.status = RequestStatus.success
        except Exception:
            request.status = RequestStatus.error
            t, v, tb = sys.exc_info()
            if request.on_error:
                request.on_error(t, v, tb, request)
            else:
                self.on_error(t, v, tb, request)

    def _get_session(self):
        with self._sessions_lock:
            if self._sessions:
                return self.Session(self, self._sessions.pop())
            else:
                return self.Session(self, self._create_session())


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


class LocalOrderManager:
    """
    Management tool to support use local order id for trading.
    """

    def __init__(self, gateway: BybitGateway, order_prefix: str = ""):
        """"""
        self.gateway = gateway

        # For generating local orderid
        self.order_prefix = order_prefix
        self.order_count = 0
        self.orders = {}  # local_orderid:order

        # Map between local and system orderid
        self.local_sys_orderid_map = {}
        self.sys_local_orderid_map = {}

        # Push order data buf
        self.push_data_buf = {}  # sys_orderid:data

        # Callback for processing push order data
        self.push_data_callback = None

        # Cancel request buf
        self.cancel_request_buf = {}  # local_orderid:req

        # Hook cancel order function
        self._cancel_order = gateway.cancel_order
        gateway.cancel_order = self.cancel_order

    def new_order_link_id(self):
        """
        Generate a new local orderid.
        """
        self.order_count += 1
        order_link_id = self.order_prefix + str(self.order_count) + uuid.uuid4()
        return order_link_id

    def get_order_link_id(self, order_id: str):
        """
        Get order_link_id with order_id.
        """
        order_link_id = self.sys_local_orderid_map.get(order_id, "")

        if not order_link_id:
            order_link_id = self.new_local_orderid()
            self.update_orderid_map(order_link_id, order_id)

        return order_link_id

    def get_order_id(self, order_link_id: str):
        """
        Get order_id with local order_link_id.
        """
        order_id = self.local_sys_orderid_map.get(order_link_id, "")
        return order_id

    def update_order_id_map(self, order_link_id: str, order_id: str):
        """
        Update orderid map.
        """
        self.sys_local_orderid_map[order_id] = order_link_id
        self.local_sys_orderid_map[order_link_id] = order_id

        self.check_cancel_request(order_link_id)
        self.check_push_data(order_id)

    def check_push_data(self, sys_orderid: str):
        """
        Check if any order push data waiting.
        """
        if sys_orderid not in self.push_data_buf:
            return

        data = self.push_data_buf.pop(sys_orderid)
        if self.push_data_callback:
            self.push_data_callback(data)

    def add_push_data(self, sys_orderid: str, data: dict):
        """
        Add push data into buf.
        """
        self.push_data_buf[sys_orderid] = data

    def get_order_with_sys_orderid(self, order_id: str):
        """
        Get order_link_id by order_id
        :param order_id:
        :return:
        """
        order_link_id = self.sys_local_orderid_map.get(order_id, None)
        if not order_link_id:
            return None
        else:
            return self.get_order_with_local_orderid(order_link_id)

    def get_order_with_order_link_id(self, order_link_id: str):
        """"""
        order = self.orders[order_link_id]
        return copy(order)

    def on_order(self, order: OrderData):
        """
        Keep an order buf before pushing it to bybit_gateway.
        """
        self.orders[order.order_link_id] = copy(order)
        self.gateway.on_order(order)

    def cancel_order(self, req: CancelRequest):
        """
        """
        order_link_id = self.get_sys_orderid(req.order_link_id)
        if not order_link_id:
            self.cancel_request_buf[req.order_link_id] = req
            return

        self._cancel_order(req)

    def check_cancel_request(self, order_link_id: str):
        """
        """
        if order_link_id not in self.cancel_request_buf:
            return

        req = self.cancel_request_buf.pop(order_link_id)
        self.gateway.cancel_order(req)


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
