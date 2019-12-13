from gateway.rest_gateway import BybitRestApi
from gateway.websocket import WebsocketClient


class BybitGateway(object):
    def __init__(self, rest_client: BybitRestApi, websocket_client: WebsocketClient):
        self._rest = rest_client
        self._websocket = websocket_client