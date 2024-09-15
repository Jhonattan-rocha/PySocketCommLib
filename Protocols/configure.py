from Protocols.protocols.httpServerProtocol import HttpServerProtocol


def config(proto: str):
    """Protocols

    Args:
        proto (str): name of protocol

    Returns:
        Protocol Class: A class of protocol
    """
    protocols = {"http": HttpServerProtocol}

    return protocols[proto.lower()]
