"""Configuration management for PySocketCommLib."""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration manager for PySocketCommLib.
    
    Supports loading configuration from:
    - Environment variables
    - JSON configuration files
    - Direct parameter setting
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._load_defaults()
        
        if config_file:
            self.load_from_file(config_file)
        
        self._load_from_env()
    
    def _load_defaults(self) -> None:
        """Load default configuration values."""
        self._config = {
            # Server settings
            'server': {
                'host': 'localhost',
                'port': 8080,
                'max_connections': 100,
                'timeout': 30.0,
                'buffer_size': 4096,
            },
            
            # Authentication settings
            'auth': {
                'method': 'none',
                'token': None,
                'config': {}
            },
            
            # SSL/TLS settings
            'ssl': {
                'enabled': False,
                'cert_file': None,
                'key_file': None,
                'ca_file': None,
                'verify_mode': 'none'  # none, optional, required
            },
            
            # Encryption settings
            'encryption': {
                'enabled': False,
                'method': 'aes',  # aes, rsa, fernet
                'key_size': 256,
                'config': {}
            },
            
            # Logging settings
            'logging': {
                'level': 'INFO',
                'file': None,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'max_size': 10485760,  # 10MB
                'backup_count': 5
            },
            
            # Rate limiting settings
            'rate_limit': {
                'enabled': True,
                'requests_per_second': 10,
                'burst_size': 20,
                'cleanup_interval': 300
            },
            
            # Database settings (for ORM)
            'database': {
                'type': 'sqlite',
                'host': 'localhost',
                'port': 5432,
                'name': 'database.db',
                'user': None,
                'password': None,
                'pool_size': 5,
                'max_overflow': 10
            },
            
            # WebSocket settings
            'websocket': {
                'enabled': False,
                'path': '/ws',
                'compression': True,
                'max_message_size': 1048576  # 1MB
            },
            
            # HTTP settings
            'http': {
                'enabled': False,
                'static_path': None,
                'cors_enabled': False,
                'cors_origins': ['*']
            }
        }
    
    def load_from_file(self, config_file: str) -> None:
        """Load configuration from JSON file.
        
        Args:
            config_file: Path to JSON configuration file
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            
            self._merge_config(file_config)
            
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in config file {config_file}: {e}")
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables.
        
        Environment variables should be prefixed with PYSOCKETCOMM_
        and use double underscores to separate nested keys.
        
        Example: PYSOCKETCOMM_SERVER__HOST=0.0.0.0
        """
        prefix = 'PYSOCKETCOMM_'
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix and convert to lowercase
            config_key = key[len(prefix):].lower()
            
            # Split nested keys
            keys = config_key.split('__')
            
            # Convert value to appropriate type
            converted_value = self._convert_env_value(value)
            
            # Set nested configuration
            self._set_nested_config(keys, converted_value)
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean values
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off'):
            return False
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # JSON values
        if value.startswith(('{', '[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        
        # String value
        return value
    
    def _set_nested_config(self, keys: list, value: Any) -> None:
        """Set nested configuration value."""
        current = self._config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """Merge new configuration with existing configuration."""
        def merge_dict(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
            return base
        
        merge_dict(self._config, new_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'server.host')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        current = self._config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'server.host')
            value: Value to set
        """
        keys = key.split('.')
        current = self._config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section.
        
        Args:
            section: Section name (e.g., 'server')
            
        Returns:
            Configuration section dictionary
        """
        return self._config.get(section, {})
    
    def save_to_file(self, config_file: str) -> None:
        """Save current configuration to JSON file.
        
        Args:
            config_file: Path to save configuration file
        """
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def setup_logging(self) -> None:
        """Setup logging based on configuration."""
        log_config = self.get_section('logging')
        
        level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = log_config.get('format')
        log_file = log_config.get('file')
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format=log_format,
            handlers=[]
        )
        
        logger = logging.getLogger()
        logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            from logging.handlers import RotatingFileHandler
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=log_config.get('max_size', 10485760),
                backupCount=log_config.get('backup_count', 5)
            )
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)
    
    def __repr__(self) -> str:
        return f"Config({json.dumps(self._config, indent=2)})"


# Global configuration instance
config = Config()


def load_config(config_file: Optional[str] = None) -> Config:
    """Load configuration from file or environment.
    
    Args:
        config_file: Optional path to configuration file
        
    Returns:
        Configuration instance
    """
    global config
    config = Config(config_file)
    return config


def get_config() -> Config:
    """Get current configuration instance.
    
    Returns:
        Current configuration instance
    """
    return config