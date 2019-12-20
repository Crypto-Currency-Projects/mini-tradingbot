from src.bybit_gateway import BybitGateway
from copy import copy
from src.datatypes import OrderData, CancelRequest
import uuid


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
