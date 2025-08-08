class HTTPVersionMiddleware:
    def __init__(self):
        pass
    
    async def __call__(self, scope, receive, send, next_middleware):
        http_version = scope.get("http_version", "1.1")  # Padrão para HTTP/1.1
        headers = [(b"server", b"Custom-HTTP-Server")]

        if http_version == "1.1":
            headers.append((b"connection", b"keep-alive"))  # Mantém conexão ativa
            headers.append((b"cache-control", b"public, max-age=3600"))  # Cache otimizado

        elif http_version == "2":
            headers.append((b"x-http2-enabled", b"true"))  # Indica suporte a HTTP/2
            headers.append((b"cache-control", b"public, max-age=3600"))
            # HTTP/2 tem multiplexing, então podemos priorizar recursos
            headers.append((b"x-priority", b"high"))

        elif http_version == "3":
            headers.append((b"x-http3-enabled", b"true"))  # Indica suporte a HTTP/3
            headers.append((b"alt-svc", b'h3=":443"; ma=2592000'))  # Informa ao navegador que HTTP/3 está disponível
            headers.append((b"cache-control", b"public, max-age=7200"))  # HTTP/3 foca em carregamento rápido
            headers.append((b"x-priority", b"highest"))

        # Modifica a resposta para adicionar os headers personalizados
        async def custom_send(message):
            if message["type"] == "http.response.start":
                message["headers"].extend(headers)
            await send(message)

        await next_middleware(scope, receive, custom_send)
