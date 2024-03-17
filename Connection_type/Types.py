import socket

class Types:    
    TCP_IPV4 = (socket.AF_INET, socket.SOCK_STREAM)
    TCP_IPV6 = (socket.AF_INET6, socket.SOCK_STREAM)
    #--não suportada ainda
    # UDP_IPV4 = (socket.AF_INET, socket.SOCK_DGRAM)
    # UDP_IPV6 = (socket.AF_INET6, socket.SOCK_DGRAM)
    # RAW = (socket.AF_INET, socket.SOCK_RAW)
    