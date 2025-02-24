import os
import mimetypes
from typing import Dict, Callable
from .Response import Response

class FileResponse(Response):
    def __init__(self, file_path: str, status: int = 200, headers: Dict[str, str] = None, content_type: str = None, block_size: int = 8192):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        self.block_size = block_size
        self.file_path = file_path
        custom_headers = headers if headers else {}
        custom_headers['Content-Type'] = content_type if content_type else mime_type
        super().__init__(status=status, headers=custom_headers, content_type=mime_type)

    async def send_asgi(self, send: Callable):
        """ Envia um arquivo em blocos de maneira assíncrona. """
        if ".." in self.file_path:
            response = Response(body=b"Forbidden", status=403)
            await response.send_asgi(send)
            return

        await send({
            'type': 'http.response.start',
            'status': self.status,
            'headers': [(k.encode('utf-8'), v.encode('utf-8')) for k, v in self.headers.items()],
        })

        try:
            with open(self.file_path, 'rb') as f:
                while True:
                    chunk = f.read(self.block_size)
                    if not chunk:
                        break  # Sai do loop se o arquivo terminou
                    await send({
                        'type': 'http.response.body',
                        'body': chunk,
                        'more_body': True,  # Indica que ainda tem mais corpo para enviar
                    })

            # Envia o último bloco com `more_body=False`
            await send({
                'type': 'http.response.body',
                'body': b"",
                'more_body': False,  # Agora indica que o corpo terminou
            })

        except Exception as e:
            response = Response(status=500, body=f"Error reading file: {e}".encode("utf-8"))
            await response.send_asgi(send)
