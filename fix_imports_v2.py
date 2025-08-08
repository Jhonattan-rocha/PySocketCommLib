#!/usr/bin/env python3
"""Fix Imports V2 - Corrige imports para funcionar sem instalação de pacote."""

import os
import sys
from pathlib import Path
import re

class ImportFixerV2:
    """Corrige imports para funcionar como projeto local."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.fixes_applied = []
    
    def fix_cli_file(self):
        """Corrige especificamente o arquivo CLI."""
        print("🖥️  Corrigindo CLI para funcionar localmente...")
        
        cli_file = self.project_root / 'cli.py'
        if not cli_file.exists():
            print("  ❌ cli.py não encontrado")
            return
        
        try:
            content = cli_file.read_text(encoding='utf-8')
            
            # Novo conteúdo do CLI com imports locais
            new_content = '''#!/usr/bin/env python3
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
'''
            
            cli_file.write_text(new_content, encoding='utf-8')
            print("  ✅ CLI reescrito com imports locais")
            self.fixes_applied.append('cli.py rewritten')
            
        except Exception as e:
            print(f"  ❌ Erro ao corrigir CLI: {e}")
    
    def fix_init_files(self):
        """Corrige arquivos __init__.py para usar imports locais."""
        print("\n📦 Corrigindo arquivos __init__.py para imports locais...")
        
        init_files_fixes = {
            '__init__.py': {
                'from PySocketCommLib.Server import': 'from .Server import',
                'from PySocketCommLib.Client import': 'from .Client import',
                'from PySocketCommLib.Auth import': 'from .Auth import',
                'from PySocketCommLib.Abstracts import': 'from .Abstracts import',
                'from PySocketCommLib.ORM import': 'from .ORM import',
                'from PySocketCommLib.Crypt import': 'from .Crypt import',
                'from PySocketCommLib.Events import': 'from .Events import',
                'from PySocketCommLib.Files import': 'from .Files import',
                'from PySocketCommLib.Options import': 'from .Options import',
                'from PySocketCommLib.TaskManager import': 'from .TaskManager import',
                'from PySocketCommLib.Connection_type import': 'from .Connection_type import',
                'from PySocketCommLib.Protocols import': 'from .Protocols import',
            },
            'Abstracts/__init__.py': {
                'from PySocketCommLib.Abstracts.AsyncCrypts import': 'from .AsyncCrypts import',
                'from PySocketCommLib.Abstracts.AsyncTask import': 'from .AsyncTask import',
                'from PySocketCommLib.Abstracts.Auth import': 'from .Auth import',
                'from PySocketCommLib.Abstracts.SyncCrypts import': 'from .SyncCrypts import',
                'from PySocketCommLib.Abstracts.ThreadTask import': 'from .ThreadTask import',
            }
        }
        
        for file_path, fixes in init_files_fixes.items():
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
                
            try:
                content = full_path.read_text(encoding='utf-8')
                original_content = content
                
                for old_import, new_import in fixes.items():
                    content = content.replace(old_import, new_import)
                
                if content != original_content:
                    full_path.write_text(content, encoding='utf-8')
                    print(f"  ✅ {file_path}")
                    self.fixes_applied.append(file_path)
                    
            except Exception as e:
                print(f"  ❌ Erro em {file_path}: {e}")
    
    def run(self):
        """Executa as correções."""
        print("🔧 Aplicando correções para funcionamento local...")
        
        self.fix_cli_file()
        self.fix_init_files()
        
        print(f"\n✅ Correções aplicadas: {len(self.fixes_applied)}")
        for fix in self.fixes_applied:
            print(f"  • {fix}")
        
        print("\n💡 Teste o CLI com: python cli.py --version")

def main():
    """Função principal."""
    project_root = os.getcwd()
    fixer = ImportFixerV2(project_root)
    fixer.run()

if __name__ == '__main__':
    main()