import socket


class Types:
    TCP_IPV4 = (socket.AF_INET, socket.SOCK_STREAM)
    TCP_IPV6 = (socket.AF_INET6, socket.SOCK_STREAM)
    UDP_IPV4 = (socket.AF_INET, socket.SOCK_DGRAM)
    UDP_IPV6 = (socket.AF_INET6, socket.SOCK_DGRAM)
    #--não suportada ainda
    # RAW = (socket.AF_INET, socket.SOCK_RAW)
