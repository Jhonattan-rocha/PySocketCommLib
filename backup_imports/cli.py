"""Command Line Interface for PySocketCommLib."""

import argparse
import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Optional

# Add current directory to Python path for absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use absolute imports
from config import load_config, Config
from Options.Ops import Server_ops


def create_server_options(config: Config) -> Server_ops:
    """Create server options from configuration.
    
    Args:
        config: Configuration instance
        
    Returns:
        Server options instance
    """
    server_config = config.get_section('server')
    auth_config = config.get_section('auth')
    ssl_config = config.get_section('ssl')
    
    # Create basic server options
    options = Server_ops(
        host=server_config.get('host', 'localhost'),
        port=server_config.get('port', 8080),
        auth_method=auth_config.get('method', 'none'),
        auth_config=auth_config.get('config', {})
    )
    
    # Add logging configuration
    log_config = config.get_section('logging')
    options.log_file = log_config.get('file')
    options.log_level = log_config.get('level', 'INFO')
    
    return options


async def run_server(config_file: Optional[str] = None, **kwargs) -> None:
    """Run the async server.
    
    Args:
        config_file: Optional configuration file path
        **kwargs: Additional configuration overrides
    """
    # Load configuration
    config = load_config(config_file)
    
    # Override with command line arguments
    for key, value in kwargs.items():
        if value is not None:
            config.set(key, value)
    
    # Setup logging
    config.setup_logging()
    
    # Create server
    options = create_server_options(config)
    server = AsyncServer(options)
    
    try:
        print(f"Starting server on {options.host}:{options.port}")
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        await server.break_server()
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


def generate_config(output_file: str) -> None:
    """Generate a sample configuration file.
    
    Args:
        output_file: Path to output configuration file
    """
    config = Config()
    config.save_to_file(output_file)
    print(f"Sample configuration saved to {output_file}")


def validate_config(config_file: str) -> None:
    """Validate a configuration file.
    
    Args:
        config_file: Path to configuration file to validate
    """
    try:
        config = load_config(config_file)
        print(f"Configuration file {config_file} is valid")
        
        # Print summary
        server_config = config.get_section('server')
        print(f"Server: {server_config.get('host')}:{server_config.get('port')}")
        print(f"Auth: {config.get('auth.method')}")
        print(f"SSL: {'enabled' if config.get('ssl.enabled') else 'disabled'}")
        print(f"Encryption: {'enabled' if config.get('encryption.enabled') else 'disabled'}")
        
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PySocketCommLib - Socket communication library CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run server with default settings
  pysocketcomm server
  
  # Run server with custom host and port
  pysocketcomm server --host 0.0.0.0 --port 9000
  
  # Run server with configuration file
  pysocketcomm server --config config.json
  
  # Generate sample configuration
  pysocketcomm config generate --output config.json
  
  # Validate configuration file
  pysocketcomm config validate --file config.json
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Run the server')
    server_parser.add_argument(
        '--config', '-c',
        type=str,
        help='Configuration file path'
    )
    server_parser.add_argument(
        '--host',
        type=str,
        help='Server host address'
    )
    server_parser.add_argument(
        '--port', '-p',
        type=int,
        help='Server port number'
    )
    server_parser.add_argument(
        '--auth-method',
        choices=['none', 'simple', 'token'],
        help='Authentication method'
    )
    server_parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level'
    )
    server_parser.add_argument(
        '--log-file',
        type=str,
        help='Log file path'
    )
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='config_action')
    
    # Generate config
    generate_parser = config_subparsers.add_parser('generate', help='Generate sample configuration')
    generate_parser.add_argument(
        '--output', '-o',
        type=str,
        default='config.json',
        help='Output configuration file path'
    )
    
    # Validate config
    validate_parser = config_subparsers.add_parser('validate', help='Validate configuration file')
    validate_parser.add_argument(
        '--file', '-f',
        type=str,
        required=True,
        help='Configuration file to validate'
    )
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version information')
    
    args = parser.parse_args()
    
    if args.command == 'server':
        # Prepare server arguments
        server_kwargs = {}
        if args.host:
            server_kwargs['server.host'] = args.host
        if args.port:
            server_kwargs['server.port'] = args.port
        if args.auth_method:
            server_kwargs['auth.method'] = args.auth_method
        if args.log_level:
            server_kwargs['logging.level'] = args.log_level
        if args.log_file:
            server_kwargs['logging.file'] = args.log_file
        
        # Run server
        asyncio.run(run_server(args.config, **server_kwargs))
        
    elif args.command == 'config':
        if args.config_action == 'generate':
            generate_config(args.output)
        elif args.config_action == 'validate':
            validate_config(args.file)
        else:
            config_parser.print_help()
            
    elif args.command == 'version':
        from . import __version__
        print(f"PySocketCommLib version {__version__}")
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()