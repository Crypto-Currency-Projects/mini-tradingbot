from manager import LocalOrderManager
from gateway import BybitGateway
class BybitRestApi():
    def __init__(self, gateway:BybitGateway):
        """"""
        self.order_manager = LocalOrderManager(gateway)

        self.key = ""
        self.secret = b""

        self.order_count = 1_000_000
        self.order_count_lock = Lock()
        self.connect_time = 0

