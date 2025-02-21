class MiddlewareController:
    def __init__(self, app, middlewares):
        self.app = app
        self.middlewares = middlewares

    async def __call__(self, scope, receive, send):
        """
        Executa os middlewares em ordem, permitindo que um middleware pare a execução antes de chamar o próximo.
        """
        index = 0

        async def next_middleware():
            nonlocal index
            if index < len(self.middlewares):
                middleware = self.middlewares[index]
                index += 1
                await middleware(scope, receive, next_middleware)
            else:
                await self.app(scope, receive, send)

        await next_middleware()
