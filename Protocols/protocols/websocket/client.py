import os
import struct
import base64
import socket

class WebSocketClient:

    def __init__(self) -> None:
        pass

    def decode_websocket_message(self, message: bytes) -> str:
        # Primeiro byte: FIN e opcode
        first_byte = message[0]
        fin = first_byte >> 7
        opcode = first_byte & 0x0F

        # Segundo byte: máscara e comprimento do payload
        second_byte = message[1]
        masked = second_byte >> 7
        payload_length = second_byte & 0x7F

        offset = 2  # O offset inicial está nos primeiros 2 bytes

        if payload_length == 126:
            payload_length = struct.unpack(">H", message[offset:offset + 2])[0]
            offset += 2
        elif payload_length == 127:
            payload_length = struct.unpack(">Q", message[offset:offset + 8])[0]
            offset += 8

        return message[offset:offset + payload_length].decode('cp850')


    def encode_message_with_mask(self, message: str) -> bytearray:
        # Converter a mensagem em bytes
        message_bytes = message.encode('cp850')
        
        # Gerar uma máscara de 4 bytes
        mask = os.urandom(4)  # Gera 4 bytes aleatórios
        
        # Construir o frame do WebSocket
        frame = bytearray()
        
        # Primeiro byte: FIN e opcode (0x1 para texto)
        frame.append(0x81)  # 10000001 (FIN = 1, opcode = 0x1)

        # Segundo byte: máscara habilitada (bit mais significativo = 1) e comprimento do payload
        payload_length = len(message_bytes)
        
        if payload_length <= 125:
            frame.append(0x80 | payload_length)  # Ativando o bit de máscara (0x80)
        elif payload_length >= 126 and payload_length <= 65535:
            frame.append(0x80 | 126)
            frame.extend(struct.pack('>H', payload_length))  # 2 bytes para comprimento
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack('>Q', payload_length))  # 8 bytes para comprimento

        # Adicionar a máscara ao frame
        frame.extend(mask)
        
        # Aplicar a máscara ao payload
        masked_message = bytearray()
        for i in range(payload_length):
            masked_message.append(message_bytes[i] ^ mask[i % 4])

        # Adicionar o payload mascarado ao frame
        frame.extend(masked_message)
        
        return frame

    def handshake(self, client: socket.socket):
        # Envia a requisição HTTP para fazer o upgrade para WebSocket
        key = base64.b64encode(b"123kg-pasduouo-pasojdpa").decode()
        handshake = (
            "GET / HTTP/1.1\r\n"
            "Host: localhost:8080\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        client.send(handshake.encode())

        # Recebe e imprime a resposta do handshake do servidor
        response = client.recv(1024).decode()
        print(f"Server Response: {response}")

