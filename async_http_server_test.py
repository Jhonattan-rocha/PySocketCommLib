import uvicorn
from Protocols import AsyncHttpServerProtocol, Response, JSONResponse
from Protocols import Router
from Protocols.protocols.httpServer.middlewares import (
    RateLimiterMiddleware, CORSMiddleware, ErrorHandlerMiddleware, 
    GzipMiddleware, LoggingMiddleware, MiddlewareController, SecurityMiddleware, CacheControlMiddleware
)
from contextlib import asynccontextmanager

# Criando um roteador
my_router = Router()

# Definindo rotas para o roteador
@my_router.get("/")
async def index_route(params): 
    return Response(body=b"Hello from the Router index!", content_type='text/plain')

@my_router.get("/users")
async def users_route(params): 
    data = {"users": ["Alice", "Bob"]}
    return JSONResponse(data=data)

# Registrando uma rota diretamente no servidor
@my_router.get("/direct_route") 
async def direct_handler(params): 
    return Response(body=b"Hello from direct route!", content_type='text/plain')

@asynccontextmanager
async def lifespan(app):
    await app.startup()
    print("Iniciou")
    yield
    print("Fechou")
    await app.shutdown()

# Criando a instância do servidor
server_instance = AsyncHttpServerProtocol(lifespan=lifespan, max_workers=2, static_dir="./static")

# Registrando o roteador no servidor
server_instance.register_router(my_router)

# Criando o controlador de middlewares
app = MiddlewareController(server_instance, [
    RateLimiterMiddleware(60, 10),
    CORSMiddleware("*"),
    ErrorHandlerMiddleware(),
    GzipMiddleware(1000),
    LoggingMiddleware(),
    SecurityMiddleware(),
    CacheControlMiddleware()
])

# Executando o servidor com Uvicorn
if __name__ == "__main__":
    uvicorn.run(server_instance, host="127.0.0.1", port=8000, lifespan="on")
