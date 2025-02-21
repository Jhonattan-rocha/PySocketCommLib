from Protocols import AsyncHttpServerProtocol
from Protocols import WebSocketClient
from Protocols import WebSocketServer

def config(proto: str) -> AsyncHttpServerProtocol | WebSocketClient | WebSocketServer:
    """Protocols
    Args:
        proto (str): name of protocol
    Returns:
        Protocol Class: A class of protocol
    """
    protocols = {"http": AsyncHttpServerProtocol, "websocket_client": WebSocketClient,
                "websocket_server": WebSocketServer}

    return protocols[proto.lower()]
