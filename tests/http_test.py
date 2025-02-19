import os, sys

current_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(project_dir)

from Protocols.protocols.httpServer import httpServerProtocol
from Protocols.protocols.httpServer.Router.Router import Router

server = httpServerProtocol.HttpServerProtocol("localhost", 8081)

router = Router()

@router.get(url="/user/{int: id}")
async def test(handler, params):
    print("Né que funciona 1")
    response_data = {"message": f"Received query parameters: {params}"} # Structure your data
    return httpServerProtocol.JSONResponse(data=response_data) # Return JSONResponse

@router.get(url="/user/")
async def test_2(handler, params):
    print("Né que funciona 2")
    response_data = {"message": f"Received query parameters: {params}"} # Structure your data
    return httpServerProtocol.JSONResponse(data=response_data) # Return JSONResponse

@router.get(url="/")
async def test_3(handler, params):
    print("Né que funciona 3")
    response_data = {"message": f"Received query parameters: {params}"} # Structure your data
    return httpServerProtocol.JSONResponse(data=response_data) # Return JSONResponse

server.register_router(router)
server.start_http_server()
