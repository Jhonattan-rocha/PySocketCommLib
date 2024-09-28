import socket
import base64
import hashlib
import struct

class WebSocketServer:

    def __init__(self) -> None:
        pass

    def encode_message(self, message_bytes: bytes):
        # Construir o frame do WebSocket
        frame = bytearray()
        
        # Primeiro byte: FIN e opcode (0x1 para texto)
        frame.append(0x81)  # 10000001 (FIN = 1, opcode = 0x1)

        # Segundo byte: sem máscara (bit 0) e comprimento do payload
        payload_length = len(message_bytes)
        
        if payload_length <= 125:
            frame.append(payload_length)
        elif payload_length >= 126 and payload_length <= 65535:
            frame.append(126)
            frame.extend(struct.pack('>H', payload_length))  # 2 bytes para comprimento
        else:
            frame.append(127)
            frame.extend(struct.pack('>Q', payload_length))  # 8 bytes para comprimento

        # Adicionando o payload (dados)
        frame.extend(message_bytes)
        
        return frame

    def decode_message(self, message: bytes):
        # Primeiro byte: FIN e opcode
        first_byte = message[0]
        fin = first_byte >> 7
        opcode = first_byte & 0x0F

        # Segundo byte: máscara e comprimento do payload
        second_byte = message[1]
        masked = second_byte >> 7
        payload_length = second_byte & 0x7F

        offset = 2  # O offset inicial está nos primeiros 2 bytes

        # Se o payload_length for 126 ou 127, o comprimento é especificado em bytes adicionais
        if payload_length == 126:
            payload_length = struct.unpack(">H", message[offset:offset + 2])[0]
            offset += 2
        elif payload_length == 127:
            payload_length = struct.unpack(">Q", message[offset:offset + 8])[0]
            offset += 8

        # Se a mensagem estiver mascarada, devemos ler a máscara de 4 bytes
        if masked:
            mask = message[offset:offset + 4]
            offset += 4

            # Desmascarar os dados
            decoded_bytes = bytearray()
            for i in range(payload_length):
                decoded_bytes.append(message[offset + i] ^ mask[i % 4])

            return decoded_bytes.decode('cp850')
        else:
            # Se não estiver mascarada, retornar diretamente os dados
            return message[offset:offset + payload_length].decode('cp850')
    
    def handshake(self, client_socket: socket.socket):
        request = client_socket.recv(1024).decode()
        print(f"Recebido: {request}")

        # Extraindo a chave do WebSocket do cabeçalho
        key = None
        for line in request.split("\r\n"):
            if "Sec-WebSocket-Key" in line:
                key = line.split(": ")[1]

        # Respondendo com o handshake do WebSocket
        accept_key = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        handshake = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        client_socket.send(handshake.encode())

        # A partir deste ponto, a conexão WebSocket está estabelecida

