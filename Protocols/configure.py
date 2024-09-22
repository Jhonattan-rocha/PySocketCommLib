from Protocols import HttpServerProtocol
from Protocols import WebSocketClient
from Protocols import WebSocketServer

def config(proto: str):
    """Protocols
    Args:
        proto (str): name of protocol
    Returns:
        Protocol Class: A class of protocol
    """
    protocols = {"http": HttpServerProtocol, "websocket_client": WebSocketClient,
                "websocket_server": WebSocketServer}

    return protocols[proto.lower()]
