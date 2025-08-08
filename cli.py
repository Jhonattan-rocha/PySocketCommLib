#!/usr/bin/env python3
"""CLI para PySocketCommLib."""

import sys
import os
import argparse
from pathlib import Path

# Adicionar diretório do projeto ao path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Imports locais
try:
    from config import load_config, Config
    from Server.asyncserv.server import Server_ops
    from Options.Ops import Server_ops as ServerOptions
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    print("Certifique-se de que todos os módulos estão disponíveis.")
    sys.exit(1)

# Versão do projeto
__version__ = "1.0.0"

def create_parser():
    """Cria o parser de argumentos."""
    parser = argparse.ArgumentParser(
        description='PySocketCommLib - Biblioteca de comunicação por sockets',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--version', 
        action='version', 
        version=f'PySocketCommLib {__version__}'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # Comando server
    server_parser = subparsers.add_parser('server', help='Gerenciar servidor')
    server_parser.add_argument('--start', action='store_true', help='Iniciar servidor')
    server_parser.add_argument('--stop', action='store_true', help='Parar servidor')
    server_parser.add_argument('--config', type=str, help='Arquivo de configuração')
    server_parser.add_argument('--host', type=str, default='localhost', help='Host do servidor')
    server_parser.add_argument('--port', type=int, default=8080, help='Porta do servidor')
    
    # Comando config
    config_parser = subparsers.add_parser('config', help='Gerenciar configuração')
    config_parser.add_argument('--show', action='store_true', help='Mostrar configuração atual')
    config_parser.add_argument('--create', type=str, help='Criar arquivo de configuração')
    config_parser.add_argument('--validate', type=str, help='Validar arquivo de configuração')
    
    return parser

def handle_server_command(args):
    """Manipula comandos do servidor."""
    if args.start:
        print(f"🚀 Iniciando servidor em {args.host}:{args.port}")
        
        # Carregar configuração se especificada
        config = None
        if args.config:
            try:
                config = load_config(args.config)
                print(f"📋 Configuração carregada de: {args.config}")
            except Exception as e:
                print(f"❌ Erro ao carregar configuração: {e}")
                return 1
        
        # Criar opções do servidor
        try:
            server_options = ServerOptions(
                host=args.host,
                port=args.port,
                config=config
            )
            print("✅ Servidor configurado com sucesso")
            print("💡 Implementação do servidor será adicionada em versões futuras")
            return 0
        except Exception as e:
            print(f"❌ Erro ao configurar servidor: {e}")
            return 1
    
    elif args.stop:
        print("🛑 Parando servidor...")
        print("💡 Implementação será adicionada em versões futuras")
        return 0
    
    else:
        print("❓ Especifique --start ou --stop")
        return 1

def handle_config_command(args):
    """Manipula comandos de configuração."""
    if args.show:
        try:
            config = Config()
            print("📋 Configuração atual:")
            print(f"  Host padrão: {config.get('server.host', 'localhost')}")
            print(f"  Porta padrão: {config.get('server.port', 8080)}")
            print(f"  Debug: {config.get('debug', False)}")
            return 0
        except Exception as e:
            print(f"❌ Erro ao mostrar configuração: {e}")
            return 1
    
    elif args.create:
        try:
            config_file = Path(args.create)
            default_config = {
                "server": {
                    "host": "localhost",
                    "port": 8080,
                    "max_connections": 100
                },
                "logging": {
                    "level": "INFO",
                    "file": "server.log"
                },
                "debug": False
            }
            
            config = Config(default_config)
            config.save_to_file(str(config_file))
            print(f"✅ Arquivo de configuração criado: {config_file}")
            return 0
        except Exception as e:
            print(f"❌ Erro ao criar configuração: {e}")
            return 1
    
    elif args.validate:
        try:
            config = load_config(args.validate)
            print(f"✅ Configuração válida: {args.validate}")
            return 0
        except Exception as e:
            print(f"❌ Configuração inválida: {e}")
            return 1
    
    else:
        print("❓ Especifique --show, --create ou --validate")
        return 1

def main():
    """Função principal."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == 'server':
            return handle_server_command(args)
        elif args.command == 'config':
            return handle_config_command(args)
        else:
            print(f"❌ Comando desconhecido: {args.command}")
            return 1
    except KeyboardInterrupt:
        print("\n🛑 Operação cancelada pelo usuário")
        return 1
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
