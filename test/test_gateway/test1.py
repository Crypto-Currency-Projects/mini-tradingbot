from src.bybit_gateway.gateway import BybitGateway
import json

if __name__ == "__main__":
    with open("../../setting.json", "r") as f:
        setting = json.load(f)
    client = BybitGateway()
    client.connect(setting)
