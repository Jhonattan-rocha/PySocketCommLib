"""Simple client example for PySocketCommLib.

This example demonstrates how to create a basic client that connects
to the PySocketCommLib server and performs common operations.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleClient:
    """Simple client for connecting to PySocketCommLib server."""
    
    def __init__(self, host: str = 'localhost', port: int = 8080, 
                 use_ssl: bool = False):
        """Initialize the client.
        
        Args:
            host: Server host address
            port: Server port number
            use_ssl: Whether to use SSL/TLS connection
        """
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.authenticated = False
        self.user_info: Optional[Dict[str, Any]] = None
        
        # Message handlers
        self.message_handlers = {
            'welcome': self._handle_welcome,
            'auth_success': self._handle_auth_success,
            'auth_error': self._handle_auth_error,
            'chat_message': self._handle_chat_message,
            'user_joined': self._handle_user_joined,
            'user_left': self._handle_user_left,
            'user_list': self._handle_user_list,
            'error': self._handle_error
        }
    
    async def connect(self) -> bool:
        """Connect to the server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            
            if self.use_ssl:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port, ssl=ssl_context
                )
            else:
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port
                )
            
            self.connected = True
            logger.info("Connected to server")
            
            # Start message listening task
            asyncio.create_task(self._listen_for_messages())
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        self.connected = False
        self.authenticated = False
        self.user_info = None
        logger.info("Disconnected from server")
    
    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with the server.
        
        Args:
            username: Username for authentication
            password: Password for authentication
            
        Returns:
            True if authentication successful, False otherwise
        """
        if not self.connected:
            logger.error("Not connected to server")
            return False
        
        auth_message = {
            'type': 'auth',
            'username': username,
            'password': password
        }
        
        await self._send_message(auth_message)
        
        # Wait for authentication response (simplified)
        await asyncio.sleep(1)
        return self.authenticated
    
    async def send_chat_message(self, message: str):
        """Send a chat message.
        
        Args:
            message: Message text to send
        """
        if not self.authenticated:
            logger.error("Not authenticated")
            return
        
        chat_message = {
            'type': 'chat',
            'message': message
        }
        
        await self._send_message(chat_message)
    
    async def request_user_list(self):
        """Request the list of online users."""
        if not self.authenticated:
            logger.error("Not authenticated")
            return
        
        user_list_message = {
            'type': 'user_list'
        }
        
        await self._send_message(user_list_message)
    
    async def upload_file(self, filename: str, file_data: bytes):
        """Upload a file to the server.
        
        Args:
            filename: Name of the file
            file_data: File content as bytes
        """
        if not self.authenticated:
            logger.error("Not authenticated")
            return
        
        # In a real implementation, you would handle file data properly
        upload_message = {
            'type': 'file_upload',
            'filename': filename,
            'size': len(file_data)
            # Note: In a real implementation, you would send the actual file data
            # using a proper protocol (e.g., base64 encoding or separate transfer)
        }
        
        await self._send_message(upload_message)
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send a message to the server.
        
        Args:
            message: Message dictionary to send
        """
        if not self.writer:
            logger.error("No connection to server")
            return
        
        try:
            # Convert message to JSON and send
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            # Send message length first (4 bytes), then message
            self.writer.write(len(message_bytes).to_bytes(4, 'big'))
            self.writer.write(message_bytes)
            await self.writer.drain()
            
            logger.debug(f"Sent message: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def _listen_for_messages(self):
        """Listen for incoming messages from the server."""
        while self.connected and self.reader:
            try:
                # Read message length (4 bytes)
                length_bytes = await self.reader.read(4)
                if not length_bytes:
                    break
                
                message_length = int.from_bytes(length_bytes, 'big')
                
                # Read message data
                message_bytes = await self.reader.read(message_length)
                if not message_bytes:
                    break
                
                # Parse JSON message
                message_json = message_bytes.decode('utf-8')
                message = json.loads(message_json)
                
                logger.debug(f"Received message: {message}")
                
                # Handle the message
                await self._handle_message(message)
                
            except Exception as e:
                logger.error(f"Error reading message: {e}")
                break
        
        # Connection lost
        self.connected = False
        logger.warning("Connection to server lost")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from server.
        
        Args:
            message: Received message dictionary
        """
        message_type = message.get('type')
        
        if message_type in self.message_handlers:
            await self.message_handlers[message_type](message)
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    async def _handle_welcome(self, message: Dict[str, Any]):
        """Handle welcome message."""
        logger.info(f"Server: {message.get('message', 'Welcome!')}")
        server_info = message.get('server_info', {})
        if server_info:
            logger.info(f"Server version: {server_info.get('version', 'unknown')}")
            logger.info(f"Server features: {', '.join(server_info.get('features', []))}")
    
    async def _handle_auth_success(self, message: Dict[str, Any]):
        """Handle successful authentication."""
        self.authenticated = True
        self.user_info = message.get('user', {})
        logger.info(f"Authentication successful! Welcome, {self.user_info.get('username', 'User')}")
    
    async def _handle_auth_error(self, message: Dict[str, Any]):
        """Handle authentication error."""
        self.authenticated = False
        logger.error(f"Authentication failed: {message.get('message', 'Unknown error')}")
    
    async def _handle_chat_message(self, message: Dict[str, Any]):
        """Handle incoming chat message."""
        username = message.get('username', 'Unknown')
        text = message.get('message', '')
        timestamp = message.get('timestamp', 0)
        
        print(f"[{username}]: {text}")
    
    async def _handle_user_joined(self, message: Dict[str, Any]):
        """Handle user joined notification."""
        user = message.get('user', {})
        username = user.get('username', 'Unknown')
        logger.info(f"{username} joined the chat")
    
    async def _handle_user_left(self, message: Dict[str, Any]):
        """Handle user left notification."""
        user_id = message.get('user_id')
        logger.info(f"User {user_id} left the chat")
    
    async def _handle_user_list(self, message: Dict[str, Any]):
        """Handle user list response."""
        users = message.get('users', [])
        logger.info("Online users:")
        for user in users:
            logger.info(f"  - {user.get('username', 'Unknown')} (ID: {user.get('id')})")
    
    async def _handle_error(self, message: Dict[str, Any]):
        """Handle error message."""
        error_msg = message.get('message', 'Unknown error')
        logger.error(f"Server error: {error_msg}")


async def interactive_client():
    """Run an interactive client session."""
    client = SimpleClient()
    
    # Connect to server
    if not await client.connect():
        print("Failed to connect to server")
        return
    
    print("Connected to server!")
    print("Commands:")
    print("  /auth <username> <password> - Authenticate")
    print("  /users - List online users")
    print("  /quit - Quit the client")
    print("  <message> - Send chat message")
    print()
    
    try:
        while client.connected:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, ">>> "
                )
                
                if user_input.startswith('/quit'):
                    break
                elif user_input.startswith('/auth'):
                    parts = user_input.split()
                    if len(parts) >= 3:
                        username, password = parts[1], parts[2]
                        await client.authenticate(username, password)
                    else:
                        print("Usage: /auth <username> <password>")
                elif user_input.startswith('/users'):
                    await client.request_user_list()
                elif user_input.strip():
                    await client.send_chat_message(user_input)
                
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Input error: {e}")
    
    finally:
        await client.disconnect()
        print("Disconnected from server")


async def automated_client_demo():
    """Run an automated client demonstration."""
    client = SimpleClient()
    
    print("Starting automated client demo...")
    
    # Connect
    if not await client.connect():
        print("Failed to connect to server")
        return
    
    print("Connected to server")
    
    # Wait for welcome message
    await asyncio.sleep(1)
    
    # Authenticate
    print("Authenticating...")
    success = await client.authenticate('demo', 'demo123')
    
    if success:
        print("Authentication successful!")
        
        # Send some chat messages
        await asyncio.sleep(1)
        await client.send_chat_message("Hello from automated client!")
        
        await asyncio.sleep(2)
        await client.send_chat_message("This is a demonstration of PySocketCommLib")
        
        # Request user list
        await asyncio.sleep(1)
        await client.request_user_list()
        
        # Wait a bit more
        await asyncio.sleep(3)
        
    else:
        print("Authentication failed")
    
    # Disconnect
    await client.disconnect()
    print("Demo completed")


def main():
    """Main function."""
    print("PySocketCommLib Simple Client Example")
    print("=====================================")
    print()
    print("Choose mode:")
    print("1. Interactive client")
    print("2. Automated demo")
    print()
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == '1':
            print("Starting interactive client...")
            asyncio.run(interactive_client())
        elif choice == '2':
            print("Starting automated demo...")
            asyncio.run(automated_client_demo())
        else:
            print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Client error: {e}")


if __name__ == '__main__':
    main()