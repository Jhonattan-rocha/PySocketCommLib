import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

from Protocols.protocols.httpServer import httpServerProtocol

server = httpServerProtocol.HttpServerProtocol("localhost", 8081)

@server.add_handler(url="/user/{int: id}",method="GET")
def test(handler, params):
    print("Né que funciona 1")
    response_data = {"message": f"Received query parameters: {params}"} # Structure your data
    return httpServerProtocol.JSONResponse(data=response_data) # Return JSONResponse

@server.add_handler(url="/user/",method="GET")
def test_2(handler, params):
    print("Né que funciona 2")
    response_data = {"message": f"Received query parameters: {params}"} # Structure your data
    return httpServerProtocol.JSONResponse(data=response_data) # Return JSONResponse


server.start_http_server()
