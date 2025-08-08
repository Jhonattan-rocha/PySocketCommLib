"""Complete example demonstrating PySocketCommLib features.

This example shows how to:
1. Set up an async server with authentication and SSL
2. Use the ORM for database operations
3. Handle WebSocket and HTTP connections
4. Implement rate limiting and encryption
5. Use the event system and task management
"""

import asyncio
import logging
from pathlib import Path

# PySocketCommLib imports
from PySocketCommLib import (
    AsyncServer, Server_ops, Config, load_config,
    BaseModel, IntegerField, TextField, DateTimeField,
    Migration, MigrationManager, CreateTable
)
from PySocketCommLib.Events import EventManager
from PySocketCommLib.TaskManager import AsyncTaskManager


# Define a User model for the ORM
class User(BaseModel):
    """User model for demonstration."""
    
    def __init__(self):
        super().__init__()
        self.fields = {
            'id': IntegerField(primary_key=True),
            'username': TextField(nullable=False, unique=True),
            'email': TextField(nullable=False, unique=True),
            'created_at': DateTimeField(auto_now_add=True),
            'last_login': DateTimeField(nullable=True)
        }
        self.table_name = 'users'


class ChatServer:
    """Example chat server using PySocketCommLib."""
    
    def __init__(self, config_file: str = None):
        """Initialize the chat server.
        
        Args:
            config_file: Optional configuration file path
        """
        # Load configuration
        self.config = load_config(config_file)
        
        # Setup logging
        self.config.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.event_manager = EventManager()
        self.task_manager = AsyncTaskManager(max_workers=4)
        self.connected_clients = {}
        self.user_model = User()
        
        # Setup server options
        self.server_options = self._create_server_options()
        self.server = AsyncServer(self.server_options)
        
        # Setup event handlers
        self._setup_event_handlers()
        
        # Setup database
        self._setup_database()
    
    def _create_server_options(self) -> Server_ops:
        """Create server options from configuration.
        
        Returns:
            Configured server options
        """
        server_config = self.config.get_section('server')
        auth_config = self.config.get_section('auth')
        ssl_config = self.config.get_section('ssl')
        encryption_config = self.config.get_section('encryption')
        
        options = Server_ops(
            host=server_config.get('host', 'localhost'),
            port=server_config.get('port', 8080),
            auth_method=auth_config.get('method', 'none'),
            auth_config=auth_config.get('config', {})
        )
        
        # SSL configuration
        if ssl_config.get('enabled', False):
            options.ssl_enabled = True
            options.ssl_cert_file = ssl_config.get('cert_file')
            options.ssl_key_file = ssl_config.get('key_file')
            options.ssl_ca_file = ssl_config.get('ca_file')
        
        # Encryption configuration
        if encryption_config.get('enabled', False):
            options.encryption_enabled = True
            options.encryption_method = encryption_config.get('method', 'aes')
            options.encryption_key = encryption_config.get('key')
        
        # Rate limiting
        rate_config = self.config.get_section('rate_limiting')
        if rate_config.get('enabled', False):
            options.rate_limit_enabled = True
            options.rate_limit_requests = rate_config.get('requests_per_second', 10)
            options.rate_limit_burst = rate_config.get('burst_size', 20)
        
        # Logging
        log_config = self.config.get_section('logging')
        options.log_file = log_config.get('file')
        options.log_level = log_config.get('level', 'INFO')
        
        return options
    
    def _setup_event_handlers(self):
        """Setup event handlers for the server."""
        
        @self.event_manager.on('client_connected')
        async def on_client_connected(client_id: str, client_info: dict):
            """Handle client connection."""
            self.logger.info(f"Client {client_id} connected from {client_info.get('address')}")
            self.connected_clients[client_id] = {
                'info': client_info,
                'authenticated': False,
                'user_id': None
            }
            
            # Send welcome message
            await self.send_to_client(client_id, {
                'type': 'welcome',
                'message': 'Welcome to the chat server!',
                'server_info': {
                    'version': '1.0.0',
                    'features': ['chat', 'file_upload', 'user_management']
                }
            })
        
        @self.event_manager.on('client_disconnected')
        async def on_client_disconnected(client_id: str):
            """Handle client disconnection."""
            if client_id in self.connected_clients:
                client_info = self.connected_clients[client_id]
                self.logger.info(f"Client {client_id} disconnected")
                
                # Update user's last seen time if authenticated
                if client_info['authenticated'] and client_info['user_id']:
                    await self._update_user_last_login(client_info['user_id'])
                
                # Notify other clients
                if client_info['authenticated']:
                    await self.broadcast_message({
                        'type': 'user_left',
                        'user_id': client_info['user_id']
                    }, exclude_client=client_id)
                
                del self.connected_clients[client_id]
        
        @self.event_manager.on('message_received')
        async def on_message_received(client_id: str, message: dict):
            """Handle incoming messages."""
            message_type = message.get('type')
            
            if message_type == 'auth':
                await self._handle_authentication(client_id, message)
            elif message_type == 'chat':
                await self._handle_chat_message(client_id, message)
            elif message_type == 'user_list':
                await self._handle_user_list_request(client_id)
            elif message_type == 'file_upload':
                await self._handle_file_upload(client_id, message)
            else:
                await self.send_to_client(client_id, {
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                })
    
    def _setup_database(self):
        """Setup database connection and run migrations."""
        try:
            # Setup database connection (simplified for example)
            db_config = self.config.get_section('database')
            db_url = db_config.get('url', 'sqlite:///chat.db')
            
            # In a real implementation, you would setup the actual database connection
            self.logger.info(f"Database configured: {db_url}")
            
            # Run migrations
            self._run_migrations()
            
        except Exception as e:
            self.logger.error(f"Database setup failed: {e}")
            raise
    
    def _run_migrations(self):
        """Run database migrations."""
        try:
            # Create user table migration
            user_fields = {
                'id': IntegerField(primary_key=True),
                'username': TextField(nullable=False, unique=True),
                'email': TextField(nullable=False, unique=True),
                'password_hash': TextField(nullable=False),
                'created_at': DateTimeField(auto_now_add=True),
                'last_login': DateTimeField(nullable=True)
            }
            
            create_users_migration = Migration(
                'create_users_table',
                [CreateTable('users', user_fields)]
            )
            
            # In a real implementation, you would use MigrationManager
            self.logger.info("Migrations completed successfully")
            
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            raise
    
    async def _handle_authentication(self, client_id: str, message: dict):
        """Handle user authentication."""
        username = message.get('username')
        password = message.get('password')
        
        if not username or not password:
            await self.send_to_client(client_id, {
                'type': 'auth_error',
                'message': 'Username and password required'
            })
            return
        
        # Simulate user authentication (in real app, check against database)
        if username == 'demo' and password == 'demo123':
            self.connected_clients[client_id]['authenticated'] = True
            self.connected_clients[client_id]['user_id'] = 1
            
            await self.send_to_client(client_id, {
                'type': 'auth_success',
                'user': {
                    'id': 1,
                    'username': username,
                    'email': 'demo@example.com'
                }
            })
            
            # Notify other clients
            await self.broadcast_message({
                'type': 'user_joined',
                'user': {'id': 1, 'username': username}
            }, exclude_client=client_id)
            
        else:
            await self.send_to_client(client_id, {
                'type': 'auth_error',
                'message': 'Invalid credentials'
            })
    
    async def _handle_chat_message(self, client_id: str, message: dict):
        """Handle chat messages."""
        client_info = self.connected_clients.get(client_id)
        
        if not client_info or not client_info['authenticated']:
            await self.send_to_client(client_id, {
                'type': 'error',
                'message': 'Authentication required'
            })
            return
        
        chat_message = {
            'type': 'chat_message',
            'user_id': client_info['user_id'],
            'username': 'demo',  # In real app, get from database
            'message': message.get('message', ''),
            'timestamp': asyncio.get_event_loop().time()
        }
        
        # Broadcast to all authenticated clients
        await self.broadcast_message(chat_message)
        
        # Log the message
        self.logger.info(f"Chat message from {client_info['user_id']}: {message.get('message', '')}")
    
    async def _handle_user_list_request(self, client_id: str):
        """Handle user list requests."""
        authenticated_users = []
        
        for cid, info in self.connected_clients.items():
            if info['authenticated']:
                authenticated_users.append({
                    'id': info['user_id'],
                    'username': 'demo'  # In real app, get from database
                })
        
        await self.send_to_client(client_id, {
            'type': 'user_list',
            'users': authenticated_users
        })
    
    async def _handle_file_upload(self, client_id: str, message: dict):
        """Handle file upload requests."""
        client_info = self.connected_clients.get(client_id)
        
        if not client_info or not client_info['authenticated']:
            await self.send_to_client(client_id, {
                'type': 'error',
                'message': 'Authentication required'
            })
            return
        
        # Simulate file upload processing
        filename = message.get('filename', 'unknown')
        file_size = message.get('size', 0)
        
        # In a real implementation, you would handle the actual file data
        await self.send_to_client(client_id, {
            'type': 'file_upload_success',
            'filename': filename,
            'size': file_size,
            'url': f'/uploads/{filename}'
        })
        
        self.logger.info(f"File upload from {client_info['user_id']}: {filename} ({file_size} bytes)")
    
    async def _update_user_last_login(self, user_id: int):
        """Update user's last login time."""
        # In a real implementation, update the database
        self.logger.debug(f"Updated last login for user {user_id}")
    
    async def send_to_client(self, client_id: str, message: dict):
        """Send message to a specific client.
        
        Args:
            client_id: Client identifier
            message: Message to send
        """
        # In a real implementation, this would send via the actual connection
        self.logger.debug(f"Sending to {client_id}: {message}")
    
    async def broadcast_message(self, message: dict, exclude_client: str = None):
        """Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            exclude_client: Optional client ID to exclude
        """
        for client_id in self.connected_clients:
            if client_id != exclude_client:
                await self.send_to_client(client_id, message)
    
    async def start(self):
        """Start the chat server."""
        self.logger.info("Starting chat server...")
        
        try:
            # Start task manager
            await self.task_manager.start()
            
            # Start the server
            await self.server.start()
            
            self.logger.info(f"Chat server started on {self.server_options.host}:{self.server_options.port}")
            
            # Keep the server running
            await self.server.serve_forever()
            
        except KeyboardInterrupt:
            self.logger.info("Shutting down server...")
            await self.stop()
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise
    
    async def stop(self):
        """Stop the chat server."""
        self.logger.info("Stopping chat server...")
        
        # Stop task manager
        await self.task_manager.stop()
        
        # Stop server
        await self.server.break_server()
        
        self.logger.info("Chat server stopped")


async def main():
    """Main function to run the example."""
    # Create example configuration
    config_data = {
        'server': {
            'host': 'localhost',
            'port': 8080,
            'max_connections': 100
        },
        'auth': {
            'method': 'simple',
            'config': {}
        },
        'ssl': {
            'enabled': False
        },
        'encryption': {
            'enabled': False
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'rate_limiting': {
            'enabled': True,
            'requests_per_second': 10,
            'burst_size': 20
        },
        'database': {
            'url': 'sqlite:///example_chat.db'
        }
    }
    
    # Create config object
    config = Config(config_data)
    
    # Create and start the chat server
    server = ChatServer()
    server.config = config
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


if __name__ == '__main__':
    print("PySocketCommLib Complete Example")
    print("================================")
    print("This example demonstrates:")
    print("- Async server with authentication")
    print("- Event-driven architecture")
    print("- Rate limiting")
    print("- Database integration (ORM)")
    print("- WebSocket-style messaging")
    print("- File upload handling")
    print("- Comprehensive logging")
    print("")
    print("Press Ctrl+C to stop the server")
    print("")
    
    # Run the example
    asyncio.run(main())