class MiddlewareController:
    def __init__(self, app, middlewares):
        self.app = app
        self.middlewares = middlewares

    async def __call__(self, scope, receive, send):
        """
        Executa os middlewares em ordem, garantindo que cada um chame o próximo corretamente.
        """
        index = 0

        async def next_middleware(scope, receive, send):
            nonlocal index
            if index < len(self.middlewares):
                middleware = self.middlewares[index]
                index += 1
                await middleware(scope, receive, send, next_middleware)
            else:
                await self.app(scope, receive, send)

        await next_middleware(scope, receive, send)
