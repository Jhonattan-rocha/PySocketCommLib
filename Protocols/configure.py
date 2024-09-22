from Protocols.protocols.httpServerProtocol import HttpServerProtocol
from Protocols.protocols.websocket.client import WebSocketClient
from Protocols.protocols.websocket.server import WebSocketServer

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
