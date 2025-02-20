from Protocols import AsyncHttpServerProtocol, AsyncResponse, AsyncJSONResponse
from Protocols import Router
import os

server_instance = AsyncHttpServerProtocol() # Instance name changed to server_instance

my_router = Router()

@my_router.get("/")
async def index_route(scope, receive, send, params): # ASGI handler signature
    return AsyncResponse(body=b"Hello from the Router index!", content_type='text/plain')

@my_router.get("/users")
async def users_route(scope, receive, send, params): # ASGI handler signature
    data = {"users": ["Alice", "Bob"]}
    return AsyncJSONResponse(data=data)

@server_instance.get("/direct_route") # Use server_instance
async def direct_handler(scope, receive, send, params): # ASGI handler signature
    return AsyncResponse(body=b"Hello from direct route!", content_type='text/plain')

server_instance.register_router(my_router)
    