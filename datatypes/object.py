from constant import (
    OrderType,
    Side,
    Symbol,
    TimeInForce,
    TriggerPriceType,
    OrderStatus,
)

ACTIVE_STATUSES = set([OrderStatus.NEW, OrderStatus.CREATED, OrderStatus.PARTIALLY_FILLED])


class TickData():
    """
    Tick data contains information about:
        * last trade in market
        * orderbook snapshot
        * intraday market statistics.
    """

    symbol: str
    interval: int

    name: str = ""
    volume: float = 0
    open_interest: float = 0
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0

    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0


class PositionData:
    """
    Positon data is used for tracking each individual position holding.
    """

    user_id: int
    size: str

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_positionid = f"{self.vt_symbol}.{self.direction.value}"


class OrderData:
    """
    Order data contains information for tracking lastest status
    of a specific order.
    """

    status: OrderStatus = OrderStatus.DEFAULT
    time: str = ""

    def __init__(self,
                 symbol: Symbol,
                 order_link_id: str,
                 order_type: OrderType,
                 price: float,
                 size: int,
                 time_in_force: TimeInForce
                 ):
        self.symbol = symbol
        self.order_link_id = order_link_id
        self.type = order_type
        self.price = price
        self.size = size
        self.time_in_force = time_in_force

    def is_active(self):
        """
        Check if the order is active.
        """
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False

    def create_cancel_request(self):
        """
        Create cancel request object from order.
        """
        pass


class OrderRequest:
    """
    Request sending to specific gateway for creating a new order.
    """
    def __init__(self,
                 symbol: Symbol,
                 order_link_id: str,
                 order_type: OrderType,
                 price: float,
                 size: int
                 ):
        self.symbol = symbol
        self.order_link_id = order_link_id
        self.type = order_type
        self.price = price
        self.size = size

    def create_order_data(self, orderid: str, gateway_name: str):
        """
        Create order data from request.
        """
        order = OrderData(
            symbol=self.symbol,
            order_link_id=orderid,
            order_type=self.type,
            side=self.side,
            price=self.price,
            size=self.size,
        )
        return order


class CancelReq:
    """
    Request sending to specific gateway for canceling an existing order.
    """
    order_id: str
    order_link_id: str
    symbol: Symbol
