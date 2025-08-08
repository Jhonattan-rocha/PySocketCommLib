"""Unit tests for server functionality."""

import unittest
import asyncio
import tempfile
import ssl
from unittest.mock import Mock, patch, AsyncMock

from Server.asyncserv.server import AsyncServer
from Options.Ops import Server_ops
from config import Config


class TestServerOptions(unittest.TestCase):
    """Test server options configuration."""
    
    def test_server_options_creation(self):
        """Test basic server options creation."""
        options = Server_ops(
            host='localhost',
            port=8080,
            auth_method='none'
        )
        
        self.assertEqual(options.host, 'localhost')
        self.assertEqual(options.port, 8080)
        self.assertEqual(options.auth_method, 'none')
    
    def test_server_options_with_ssl(self):
        """Test server options with SSL configuration."""
        options = Server_ops(
            host='0.0.0.0',
            port=8443,
            auth_method='simple',
            ssl_enabled=True,
            ssl_cert_file='cert.pem',
            ssl_key_file='key.pem'
        )
        
        self.assertTrue(options.ssl_enabled)
        self.assertEqual(options.ssl_cert_file, 'cert.pem')
        self.assertEqual(options.ssl_key_file, 'key.pem')
    
    def test_server_options_with_encryption(self):
        """Test server options with encryption."""
        options = Server_ops(
            host='localhost',
            port=8080,
            auth_method='token',
            encryption_enabled=True,
            encryption_method='aes'
        )
        
        self.assertTrue(options.encryption_enabled)
        self.assertEqual(options.encryption_method, 'aes')


class TestAsyncServer(unittest.TestCase):
    """Test AsyncServer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.options = Server_ops(
            host='localhost',
            port=0,  # Use random available port
            auth_method='none'
        )
        self.server = AsyncServer(self.options)
    
    def test_server_initialization(self):
        """Test server initialization."""
        self.assertEqual(self.server.host, 'localhost')
        self.assertEqual(self.server.port, 0)
        self.assertIsNotNone(self.server.logger)
        self.assertIsNone(self.server.ssl_context)
    
    def test_server_with_ssl_context(self):
        """Test server initialization with SSL."""
        ssl_options = Server_ops(
            host='localhost',
            port=0,
            auth_method='none',
            ssl_enabled=True
        )
        
        with patch('ssl.create_default_context') as mock_ssl:
            mock_context = Mock()
            mock_ssl.return_value = mock_context
            
            server = AsyncServer(ssl_options)
            self.assertIsNotNone(server.ssl_context)
    
    def test_logging_setup(self):
        """Test logging configuration."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_log:
            log_options = Server_ops(
                host='localhost',
                port=0,
                auth_method='none',
                log_file=temp_log.name,
                log_level='DEBUG'
            )
            
            server = AsyncServer(log_options)
            self.assertIsNotNone(server.logger)
            self.assertEqual(server.logger.level, 10)  # DEBUG level
    
    @patch('Server.asyncserv.server.asyncio.start_server')
    async def test_server_start(self, mock_start_server):
        """Test server start functionality."""
        mock_server = AsyncMock()
        mock_start_server.return_value = mock_server
        
        # Start server
        await self.server.start()
        
        # Verify start_server was called with correct parameters
        mock_start_server.assert_called_once()
        call_args = mock_start_server.call_args
        self.assertEqual(call_args[1]['host'], 'localhost')
        self.assertEqual(call_args[1]['port'], 0)
    
    async def test_client_handler(self):
        """Test client connection handling."""
        # Mock reader and writer
        mock_reader = AsyncMock()
        mock_writer = Mock()
        mock_writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        mock_writer.close = AsyncMock()
        mock_writer.wait_closed = AsyncMock()
        
        # Mock reading data
        mock_reader.read.return_value = b'test message'
        
        # Test client handler
        await self.server.handle_client(mock_reader, mock_writer)
        
        # Verify reader was called
        mock_reader.read.assert_called()
        mock_writer.close.assert_called()


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_config_initialization(self):
        """Test config initialization with defaults."""
        config = Config()
        
        # Test default values
        self.assertEqual(config.get('server.host'), 'localhost')
        self.assertEqual(config.get('server.port'), 8080)
        self.assertEqual(config.get('auth.method'), 'none')
        self.assertFalse(config.get('ssl.enabled'))
        self.assertFalse(config.get('encryption.enabled'))
    
    def test_config_set_get(self):
        """Test config set and get operations."""
        config = Config()
        
        # Test setting values
        config.set('server.host', '0.0.0.0')
        config.set('server.port', 9000)
        config.set('auth.method', 'token')
        
        # Test getting values
        self.assertEqual(config.get('server.host'), '0.0.0.0')
        self.assertEqual(config.get('server.port'), 9000)
        self.assertEqual(config.get('auth.method'), 'token')
    
    def test_config_sections(self):
        """Test config section operations."""
        config = Config()
        
        # Get server section
        server_config = config.get_section('server')
        self.assertIsInstance(server_config, dict)
        self.assertIn('host', server_config)
        self.assertIn('port', server_config)
        
        # Get auth section
        auth_config = config.get_section('auth')
        self.assertIsInstance(auth_config, dict)
        self.assertIn('method', auth_config)
    
    def test_config_from_dict(self):
        """Test config creation from dictionary."""
        config_dict = {
            'server': {
                'host': '192.168.1.100',
                'port': 8443
            },
            'auth': {
                'method': 'simple',
                'config': {'username': 'admin'}
            },
            'ssl': {
                'enabled': True,
                'cert_file': '/path/to/cert.pem'
            }
        }
        
        config = Config(config_dict)
        
        self.assertEqual(config.get('server.host'), '192.168.1.100')
        self.assertEqual(config.get('server.port'), 8443)
        self.assertEqual(config.get('auth.method'), 'simple')
        self.assertTrue(config.get('ssl.enabled'))
        self.assertEqual(config.get('ssl.cert_file'), '/path/to/cert.pem')
    
    def test_config_file_operations(self):
        """Test config file save and load operations."""
        config = Config()
        config.set('server.host', 'test.example.com')
        config.set('server.port', 9999)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            # Save config to file
            config.save_to_file(temp_file.name)
            
            # Load config from file
            new_config = Config()
            new_config.load_from_file(temp_file.name)
            
            # Verify loaded values
            self.assertEqual(new_config.get('server.host'), 'test.example.com')
            self.assertEqual(new_config.get('server.port'), 9999)
    
    def test_config_environment_variables(self):
        """Test config loading from environment variables."""
        with patch.dict('os.environ', {
            'PYSOCKETCOMM_SERVER_HOST': 'env.example.com',
            'PYSOCKETCOMM_SERVER_PORT': '7777',
            'PYSOCKETCOMM_AUTH_METHOD': 'token'
        }):
            config = Config()
            config.load_from_env()
            
            self.assertEqual(config.get('server.host'), 'env.example.com')
            self.assertEqual(config.get('server.port'), 7777)
            self.assertEqual(config.get('auth.method'), 'token')


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        from Server.asyncserv.helpers.rate_limiter import AsyncTokenBucket, RateLimiter
        self.AsyncTokenBucket = AsyncTokenBucket
        self.RateLimiter = RateLimiter
    
    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = self.AsyncTokenBucket(capacity=10, refill_rate=1.0)
        
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.refill_rate, 1.0)
        self.assertEqual(bucket.tokens, 10)  # Should start full
    
    async def test_token_consumption(self):
        """Test token consumption."""
        bucket = self.AsyncTokenBucket(capacity=5, refill_rate=1.0)
        
        # Should be able to consume tokens
        self.assertTrue(await bucket.consume(3))
        self.assertEqual(bucket.tokens, 2)
        
        # Should not be able to consume more than available
        self.assertFalse(await bucket.consume(5))
        self.assertEqual(bucket.tokens, 2)  # Should remain unchanged
    
    async def test_token_refill(self):
        """Test token refill mechanism."""
        bucket = self.AsyncTokenBucket(capacity=5, refill_rate=5.0)  # 5 tokens per second
        
        # Consume all tokens
        await bucket.consume(5)
        self.assertEqual(bucket.tokens, 0)
        
        # Wait a bit and refill
        await asyncio.sleep(0.2)  # 200ms
        bucket.refill()
        
        # Should have refilled approximately 1 token (5 * 0.2 = 1)
        self.assertGreater(bucket.tokens, 0)
        self.assertLessEqual(bucket.tokens, 1)
    
    def test_rate_limiter_client_management(self):
        """Test rate limiter client management."""
        limiter = self.RateLimiter(capacity=10, refill_rate=1.0)
        
        # Get bucket for client
        bucket1 = limiter.get_bucket('client1')
        bucket2 = limiter.get_bucket('client1')  # Same client
        bucket3 = limiter.get_bucket('client2')  # Different client
        
        # Same client should get same bucket
        self.assertIs(bucket1, bucket2)
        
        # Different client should get different bucket
        self.assertIsNot(bucket1, bucket3)
    
    async def test_rate_limiter_cleanup(self):
        """Test rate limiter cleanup of old buckets."""
        limiter = self.RateLimiter(capacity=10, refill_rate=1.0, cleanup_interval=0.1)
        
        # Get bucket for client
        bucket = limiter.get_bucket('test_client')
        self.assertIn('test_client', limiter.buckets)
        
        # Wait for cleanup
        await asyncio.sleep(0.2)
        
        # Bucket should still exist (recently accessed)
        self.assertIn('test_client', limiter.buckets)
        
        # Manually trigger cleanup with old timestamp
        import time
        limiter.last_access['test_client'] = time.time() - 3600  # 1 hour ago
        limiter.cleanup_old_buckets()
        
        # Bucket should be cleaned up
        self.assertNotIn('test_client', limiter.buckets)


if __name__ == '__main__':
    # Run async tests
    def run_async_test(coro):
        """Helper to run async tests."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    # Patch async test methods
    for test_class in [TestAsyncServer, TestRateLimiting]:
        for attr_name in dir(test_class):
            attr = getattr(test_class, attr_name)
            if callable(attr) and asyncio.iscoroutinefunction(attr) and attr_name.startswith('test_'):
                # Wrap async test method
                def make_sync_test(async_method):
                    def sync_test(self):
                        return run_async_test(async_method(self))
                    return sync_test
                
                setattr(test_class, attr_name, make_sync_test(attr))
    
    unittest.main()