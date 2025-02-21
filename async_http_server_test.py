from Protocols import AsyncHttpServerProtocol, Response, JSONResponse
from Protocols import Router
from Protocols.protocols.httpServer.middlewares import RateLimiterMiddleware, CORSMiddleware, ErrorHandlerMiddleware, GzipMiddleware, LoggingMiddleware

server_instance = AsyncHttpServerProtocol() # Instance name changed to server_instance

my_router = Router()

@my_router.get("/")
async def index_route(scope, receive, send, params): # ASGI handler signature
    return Response(body=b"Hello from the Router index!", content_type='text/plain')

@my_router.get("/users")
async def users_route(scope, receive, send, params): # ASGI handler signature
    data = {"users": ["Alice", "Bob"]}
    return JSONResponse(data=data)

@server_instance.get("/direct_route") # Use server_instance
async def direct_handler(scope, receive, send, params): # ASGI handler signature
    return Response(body=b"Hello from direct route!", content_type='text/plain')

server_instance.add_middleware(RateLimiterMiddleware(server_instance, 60, 60))
server_instance.add_middleware(CORSMiddleware(server_instance, "*"))
server_instance.add_middleware(ErrorHandlerMiddleware(server_instance))
server_instance.add_middleware(GzipMiddleware(server_instance))
server_instance.add_middleware(LoggingMiddleware(server_instance))
server_instance.register_router(my_router)
