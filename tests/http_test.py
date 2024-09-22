import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

from Protocols.protocols import httpServerProtocol

server = httpServerProtocol.HttpServerProtocol("localhost", 8080)

@server.add_handler(url="/user/{int: id}",method="GET")
def test(handler, params):
    print("Né que funciona 1")
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    response = f"Received query parameters: {params}"
    handler.wfile.write(response.encode())

@server.add_handler(url="/user/",method="GET")
def test_2(handler, params):
    print("Né que funciona 2")
    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    response = f"Received query parameters: {params}"
    handler.wfile.write(response.encode())


server.start_http_server()
