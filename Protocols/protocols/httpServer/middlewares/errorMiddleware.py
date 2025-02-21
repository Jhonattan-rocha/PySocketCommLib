from ..Responses.Response import Response
import traceback
import logging

class ErrorHandlerMiddleware:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("httpServer")

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        except Exception as e:
            self.logger.error(f"Erro interno do servidor: {e}")
            traceback.print_exc()
            error_message = f"Erro interno do servidor: {str(e)}"
            response = Response(status=500, body=error_message.encode('utf-8'))
            await response.send_asgi(send)
