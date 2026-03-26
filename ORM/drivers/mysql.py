import socket
import ssl
import struct
import hashlib
import logging

from ...exceptions import ConnectionError as OrmConnectionError, QueryError, ProtocolError

logger = logging.getLogger(__name__)


class MySQLSocketClient:
    """
    Cliente MySQL usando sockets raw — implementa o MySQL Client/Server Protocol v4.1+.

    Suporta:
    - Handshake v10
    - Autenticação mysql_native_password (SHA1)
    - Queries simples e com parâmetros (%s)
    - Transações (BEGIN / COMMIT / ROLLBACK)
    - SSL opcional
    """

    # Capability flags
    CLIENT_LONG_PASSWORD    = 0x00000001
    CLIENT_LONG_FLAG        = 0x00000004
    CLIENT_CONNECT_WITH_DB  = 0x00000008
    CLIENT_PROTOCOL_41      = 0x00000200
    CLIENT_TRANSACTIONS     = 0x00002000
    CLIENT_SECURE_CONNECTION = 0x00008000
    CLIENT_MULTI_RESULTS    = 0x00020000
    CLIENT_PLUGIN_AUTH      = 0x00080000

    # Command bytes
    COM_QUIT  = 0x01
    COM_QUERY = 0x03
    COM_PING  = 0x0e

    def __init__(self, host: str, port: int, username: str, database: str,
                 password: str, use_ssl: bool = False,
                 ssl_certfile: str = None, ssl_keyfile: str = None):
        self.host = host
        self.port = port
        self.username = username
        self.database = database
        self.password = password
        self.use_ssl = use_ssl
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile
        self.sock: socket.socket | ssl.SSLSocket | None = None
        self._seq = 0
        self.server_version = ""
        self.connection_id = 0
        logging.basicConfig(
            filename='./mysql.txt', level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Packet I/O
    # ------------------------------------------------------------------

    def _recv_exactly(self, n: int) -> bytes:
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise OrmConnectionError("Conexão fechada pelo servidor MySQL.")
            buf += chunk
        return buf

    def _read_packet(self) -> bytes:
        header = self._recv_exactly(4)
        length = struct.unpack('<I', header[:3] + b'\x00')[0]
        self._seq = header[3]
        return self._recv_exactly(length)

    def _write_packet(self, data: bytes, seq: int = None) -> None:
        if seq is None:
            self._seq = (self._seq + 1) & 0xff
            seq = self._seq
        header = struct.pack('<I', len(data))[:3] + bytes([seq & 0xff])
        self.sock.sendall(header + data)

    # ------------------------------------------------------------------
    # Length-encoded integers / strings
    # ------------------------------------------------------------------

    @staticmethod
    def _lenenc_int(data: bytes, offset: int):
        """Returns (value, new_offset). value=None means SQL NULL."""
        first = data[offset]
        if first < 0xfb:
            return first, offset + 1
        if first == 0xfb:
            return None, offset + 1
        if first == 0xfc:
            return struct.unpack('<H', data[offset + 1:offset + 3])[0], offset + 3
        if first == 0xfd:
            return struct.unpack('<I', data[offset + 1:offset + 4] + b'\x00')[0], offset + 4
        # 0xfe
        return struct.unpack('<Q', data[offset + 1:offset + 9])[0], offset + 9

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def _parse_handshake(self, data: bytes) -> dict:
        offset = 1  # skip protocol version byte (0x0a)
        end = data.index(b'\x00', offset)
        server_version = data[offset:end].decode()
        offset = end + 1

        conn_id = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        scramble1 = data[offset:offset + 8]
        offset += 9  # 8 bytes scramble + 1 filler byte

        caps_lower = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        charset = data[offset]
        offset += 1
        offset += 2  # status flags
        caps_upper = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        caps = caps_lower | (caps_upper << 16)

        auth_data_len = data[offset]
        offset += 1 + 10  # auth_plugin_data_len + 10 reserved bytes

        scramble2_len = max(13, auth_data_len - 8) if auth_data_len else 13
        scramble2 = data[offset:offset + scramble2_len - 1]  # strip null terminator
        offset += scramble2_len

        end = data.find(b'\x00', offset)
        auth_plugin = data[offset:end].decode() if end > offset else 'mysql_native_password'

        return {
            'server_version': server_version,
            'conn_id': conn_id,
            'scramble': scramble1 + scramble2,
            'caps': caps,
            'charset': charset,
            'auth_plugin': auth_plugin,
        }

    def _native_password(self, password: str, scramble: bytes) -> bytes:
        """mysql_native_password: SHA1(password) XOR SHA1(scramble + SHA1(SHA1(password)))"""
        if not password:
            return b''
        pwd = password.encode('utf-8')
        h1 = hashlib.sha1(pwd).digest()
        h2 = hashlib.sha1(h1).digest()
        h3 = hashlib.sha1(scramble + h2).digest()
        return bytes(a ^ b for a, b in zip(h1, h3))

    def _send_handshake_response(self, hs: dict) -> None:
        caps = (self.CLIENT_LONG_PASSWORD | self.CLIENT_LONG_FLAG |
                self.CLIENT_CONNECT_WITH_DB | self.CLIENT_PROTOCOL_41 |
                self.CLIENT_TRANSACTIONS | self.CLIENT_SECURE_CONNECTION |
                self.CLIENT_MULTI_RESULTS | self.CLIENT_PLUGIN_AUTH)

        auth_response = self._native_password(self.password, hs['scramble'])

        payload = struct.pack('<I', caps)        # capability flags
        payload += struct.pack('<I', 16777215)   # max-packet-size
        payload += bytes([33])                   # charset: utf8mb4
        payload += b'\x00' * 23                  # reserved
        payload += self.username.encode('utf-8') + b'\x00'
        # CLIENT_SECURE_CONNECTION: 1-byte length prefix
        payload += bytes([len(auth_response)]) + auth_response
        payload += self.database.encode('utf-8') + b'\x00'
        payload += b'mysql_native_password\x00'

        self._write_packet(payload, seq=1)

    def _check_ok_or_err(self, data: bytes) -> bool:
        """Returns True on OK, raises RuntimeError on ERR, False for other."""
        if data[0] == 0x00:
            return True
        if data[0] == 0xff:
            error_code = struct.unpack('<H', data[1:3])[0]
            msg_offset = 9 if len(data) > 3 and data[3:4] == b'#' else 3
            msg = data[msg_offset:].decode('utf-8', errors='replace')
            raise QueryError(f"MySQL error {error_code}: {msg}")
        return False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, timeout: int = 30) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.host, self.port))

            if self.use_ssl:
                ctx = ssl.create_default_context()
                if self.ssl_certfile and self.ssl_keyfile:
                    ctx.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
                sock = ctx.wrap_socket(sock, server_hostname=self.host)

            self.sock = sock
            self._seq = 0xff  # will become 0 after first _write_packet increments

            # Server greeting
            data = self._read_packet()
            if data[0] == 0xff:
                raise ProtocolError("Servidor enviou erro durante o handshake.")

            hs = self._parse_handshake(data)
            self.server_version = hs['server_version']
            self.connection_id = hs['conn_id']
            self.logger.info(f"Conectado ao MySQL {hs['server_version']} (conn_id={hs['conn_id']})")

            self._send_handshake_response(hs)

            result = self._read_packet()
            self._check_ok_or_err(result)

            self.logger.info("Autenticação MySQL bem-sucedida.")
            return True

        except Exception as e:
            self.logger.error(f"Falha ao conectar ao MySQL: {e}")
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def disconnect(self) -> None:
        if self.sock:
            try:
                self._write_packet(bytes([self.COM_QUIT]), seq=0)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            self.logger.info("Desconectado do MySQL.")

    def reconnect(self) -> bool:
        self.disconnect()
        return self.connect()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def run(self, query_string: str, params: tuple = None):
        if not self.sock:
            raise OrmConnectionError("Conexão não estabelecida. Chame connect() primeiro.")

        if params:
            query_string = self._substitute_params(query_string, params)

        self._seq = 0xff  # reset sequence for each new command
        payload = bytes([self.COM_QUERY]) + query_string.encode('utf-8')
        self._write_packet(payload, seq=0)
        return self._read_result()

    def _escape_value(self, value) -> str:
        if value is None:
            return 'NULL'
        if isinstance(value, bool):
            return '1' if value else '0'
        if isinstance(value, (int, float)):
            return str(value)
        s = str(value)
        s = s.replace('\\', '\\\\').replace("'", "\\'").replace('\x00', '\\0')
        return f"'{s}'"

    def _substitute_params(self, query: str, params: tuple) -> str:
        parts = query.split('%s')
        if len(parts) != len(params) + 1:
            raise ValueError(
                f"Número de parâmetros incorreto: "
                f"{len(params)} fornecidos, {len(parts) - 1} esperados."
            )
        result = parts[0]
        for val, part in zip(params, parts[1:]):
            result += self._escape_value(val) + part
        return result

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _read_result(self):
        data = self._read_packet()

        if data[0] == 0x00:  # OK packet
            return True

        if data[0] == 0xff:  # ERR packet
            self._check_ok_or_err(data)

        # Column count (lenenc int)
        col_count, _ = self._lenenc_int(data, 0)

        # Column definitions
        columns = []
        for _ in range(col_count):
            col_data = self._read_packet()
            columns.append(self._parse_column_name(col_data))

        # EOF after column definitions (absent when CLIENT_DEPRECATE_EOF is set — we don't set it)
        eof = self._read_packet()
        if eof[0] == 0xff:
            self._check_ok_or_err(eof)

        # Row packets
        rows = []
        while True:
            row_data = self._read_packet()
            if row_data[0] == 0xfe and len(row_data) < 9:  # EOF
                break
            if row_data[0] == 0xff:  # ERR
                self._check_ok_or_err(row_data)
            rows.append(self._parse_text_row(row_data, col_count))

        return [dict(zip(columns, row)) for row in rows]

    def _parse_column_name(self, data: bytes) -> str:
        """
        Column definition packet layout (text protocol):
        catalog, schema, table, org_table, name, org_name — all lenenc strings.
        We skip the first 4 and return the 5th (name).
        """
        offset = 0
        for _ in range(4):  # skip catalog, schema, table, org_table
            length, offset = self._lenenc_int(data, offset)
            if length is not None:
                offset += length
        length, offset = self._lenenc_int(data, offset)
        return data[offset:offset + length].decode('utf-8', errors='replace')

    def _parse_text_row(self, data: bytes, col_count: int) -> list:
        row = []
        offset = 0
        for _ in range(col_count):
            if data[offset] == 0xfb:  # NULL
                row.append(None)
                offset += 1
            else:
                length, offset = self._lenenc_int(data, offset)
                if length is None:
                    row.append(None)
                else:
                    row.append(data[offset:offset + length].decode('utf-8', errors='replace'))
                    offset += length
        return row

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def begin(self) -> bool:
        return self.run("BEGIN") is not None

    def commit(self) -> bool:
        return self.run("COMMIT") is not None

    def rollback(self) -> bool:
        return self.run("ROLLBACK") is not None
