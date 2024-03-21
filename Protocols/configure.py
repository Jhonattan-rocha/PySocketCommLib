from Protocols.protocols.httpProtocol import HttpProtocol

def config(proto: str):
    """Protocols

    Args:
        proto (str): name of protocol

    Returns:
        Protocol Class: A class of protocol
    """
    protocols = {"http": HttpProtocol}

    return protocols[proto.lower()]
