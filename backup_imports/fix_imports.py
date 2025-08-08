#!/usr/bin/env python3
"""Fix Imports - Corrige conflitos de importação no PySocketCommLib."""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json
import re

class ImportFixer:
    """Corrige imports problemáticos em arquivos Python."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.fixes_applied = []
        self.backup_dir = self.project_root / 'backup_imports'
        self.dry_run = True
        
        # Mapeamento de correções conhecidas
        self.import_mappings = {
            # Imports relativos para absolutos
            'from . import': 'from PySocketCommLib import',
            'from .Server import': 'from PySocketCommLib.Server import',
            'from .Client import': 'from PySocketCommLib.Client import',
            'from .Auth import': 'from PySocketCommLib.Auth import',
            'from .Abstracts import': 'from PySocketCommLib.Abstracts import',
            'from .ORM import': 'from PySocketCommLib.ORM import',
            'from .Crypt import': 'from PySocketCommLib.Crypt import',
            'from .Events import': 'from PySocketCommLib.Events import',
            'from .Files import': 'from PySocketCommLib.Files import',
            'from .Options import': 'from PySocketCommLib.Options import',
            'from .TaskManager import': 'from PySocketCommLib.TaskManager import',
            'from .Connection_type import': 'from PySocketCommLib.Connection_type import',
            'from .Protocols import': 'from PySocketCommLib.Protocols import',
        }
        
        # Correções específicas para arquivos problemáticos
        self.file_specific_fixes = {
            'cli.py': [
                ('from . import __version__', 'from PySocketCommLib import __version__'),
                ('from .config import', 'from PySocketCommLib.config import'),
                ('from .Server.asyncserv.server import', 'from PySocketCommLib.Server.asyncserv.server import'),
            ],
            'Abstracts/AsyncCrypts.py': [
                ('from ..Options import AsyncCrypt_ops', 'from PySocketCommLib.Options import AsyncCrypt_ops'),
            ]
        }
    
    def load_analysis_report(self) -> Dict:
        """Carrega o relatório de análise de imports."""
        report_file = self.project_root / 'import_analysis_report.json'
        if not report_file.exists():
            print("❌ Relatório de análise não encontrado. Execute import_analyzer.py primeiro.")
            return {}
            
        with open(report_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_backup(self):
        """Cria backup dos arquivos antes das modificações."""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir()
            
        print(f"📁 Criando backup em: {self.backup_dir}")
        
        for py_file in self.project_root.rglob('*.py'):
            if 'backup_imports' in str(py_file) or '__pycache__' in str(py_file):
                continue
                
            relative_path = py_file.relative_to(self.project_root)
            backup_file = self.backup_dir / relative_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                backup_file.write_text(py_file.read_text(encoding='utf-8'), encoding='utf-8')
            except Exception as e:
                print(f"⚠️  Erro ao fazer backup de {py_file}: {e}")
    
    def fix_relative_imports(self, report: Dict):
        """Corrige imports relativos para absolutos."""
        print("\n🔄 Corrigindo imports relativos...")
        
        for file_path, imports in report.get('relative_imports', {}).items():
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
                
            try:
                content = full_path.read_text(encoding='utf-8')
                original_content = content
                
                # Aplicar correções específicas do arquivo
                if file_path in self.file_specific_fixes:
                    for old_import, new_import in self.file_specific_fixes[file_path]:
                        if old_import in content:
                            content = content.replace(old_import, new_import)
                            self.fixes_applied.append({
                                'file': file_path,
                                'type': 'specific_fix',
                                'old': old_import,
                                'new': new_import
                            })
                
                # Aplicar correções gerais
                for old_pattern, new_pattern in self.import_mappings.items():
                    if old_pattern in content:
                        content = content.replace(old_pattern, new_pattern)
                        self.fixes_applied.append({
                            'file': file_path,
                            'type': 'general_fix',
                            'old': old_pattern,
                            'new': new_pattern
                        })
                
                # Salvar se houve mudanças
                if content != original_content and not self.dry_run:
                    full_path.write_text(content, encoding='utf-8')
                    print(f"  ✅ {file_path}")
                elif content != original_content:
                    print(f"  🔍 {file_path} (dry run)")
                    
            except Exception as e:
                print(f"  ❌ Erro em {file_path}: {e}")
    
    def fix_cli_imports(self):
        """Corrige especificamente os imports do CLI."""
        print("\n🖥️  Corrigindo imports do CLI...")
        
        cli_file = self.project_root / 'cli.py'
        if not cli_file.exists():
            print("  ❌ cli.py não encontrado")
            return
            
        try:
            content = cli_file.read_text(encoding='utf-8')
            original_content = content
            
            # Adicionar sys.path no início se necessário
            if 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))' not in content:
                import_section = "import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n\n"
                
                # Encontrar onde inserir
                lines = content.split('\n')
                insert_index = 0
                
                # Pular shebang e docstrings
                for i, line in enumerate(lines):
                    if line.startswith('#!') or line.startswith('"""') or line.startswith("'''"):
                        continue
                    if line.strip() and not line.startswith('#'):
                        insert_index = i
                        break
                
                lines.insert(insert_index, import_section.strip())
                content = '\n'.join(lines)
            
            # Corrigir imports específicos do CLI
            cli_fixes = [
                ('from . import __version__', 'from PySocketCommLib import __version__'),
                ('from .config import load_config, Config', 'from config import load_config, Config'),
                ('from .Server.asyncserv.server import Server_ops', 'from Server.asyncserv.server import Server_ops'),
            ]
            
            for old_import, new_import in cli_fixes:
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    self.fixes_applied.append({
                        'file': 'cli.py',
                        'type': 'cli_fix',
                        'old': old_import,
                        'new': new_import
                    })
            
            if content != original_content and not self.dry_run:
                cli_file.write_text(content, encoding='utf-8')
                print("  ✅ cli.py corrigido")
            elif content != original_content:
                print("  🔍 cli.py (dry run)")
                
        except Exception as e:
            print(f"  ❌ Erro ao corrigir CLI: {e}")
    
    def fix_init_files(self):
        """Corrige imports em arquivos __init__.py."""
        print("\n📦 Corrigindo arquivos __init__.py...")
        
        for init_file in self.project_root.rglob('__init__.py'):
            if 'backup_imports' in str(init_file):
                continue
                
            try:
                content = init_file.read_text(encoding='utf-8')
                original_content = content
                
                # Converter imports relativos para absolutos
                relative_path = init_file.relative_to(self.project_root)
                parent_module = str(relative_path.parent).replace(os.sep, '.')
                
                if parent_module != '.':
                    # Substituir imports relativos
                    content = re.sub(
                        r'from \.([\w.]+) import',
                        f'from PySocketCommLib.{parent_module}.\\1 import',
                        content
                    )
                    
                    content = re.sub(
                        r'from \. import',
                        f'from PySocketCommLib.{parent_module} import',
                        content
                    )
                
                if content != original_content and not self.dry_run:
                    init_file.write_text(content, encoding='utf-8')
                    print(f"  ✅ {relative_path}")
                elif content != original_content:
                    print(f"  🔍 {relative_path} (dry run)")
                    
            except Exception as e:
                print(f"  ❌ Erro em {init_file}: {e}")
    
    def generate_fix_report(self):
        """Gera relatório das correções aplicadas."""
        report = {
            'total_fixes': len(self.fixes_applied),
            'fixes_by_type': {},
            'fixes_by_file': {},
            'fixes_applied': self.fixes_applied
        }
        
        # Agrupar por tipo
        for fix in self.fixes_applied:
            fix_type = fix['type']
            if fix_type not in report['fixes_by_type']:
                report['fixes_by_type'][fix_type] = 0
            report['fixes_by_type'][fix_type] += 1
        
        # Agrupar por arquivo
        for fix in self.fixes_applied:
            file_name = fix['file']
            if file_name not in report['fixes_by_file']:
                report['fixes_by_file'][file_name] = 0
            report['fixes_by_file'][file_name] += 1
        
        return report
    
    def print_summary(self, report: Dict):
        """Imprime resumo das correções."""
        print("\n" + "="*60)
        print("RESUMO DAS CORREÇÕES DE IMPORTS")
        print("="*60)
        
        print(f"\n📊 ESTATÍSTICAS:")
        print(f"  • Total de correções: {report['total_fixes']}")
        print(f"  • Arquivos modificados: {len(report['fixes_by_file'])}")
        
        if report['fixes_by_type']:
            print(f"\n🔧 TIPOS DE CORREÇÃO:")
            for fix_type, count in report['fixes_by_type'].items():
                print(f"  • {fix_type}: {count}")
        
        if report['fixes_by_file']:
            print(f"\n📁 ARQUIVOS MODIFICADOS:")
            for file_name, count in list(report['fixes_by_file'].items())[:10]:
                print(f"  • {file_name}: {count} correções")
            if len(report['fixes_by_file']) > 10:
                print(f"  ... e mais {len(report['fixes_by_file']) - 10} arquivos")
        
        print("\n" + "="*60)
    
    def run(self, dry_run: bool = True, create_backup: bool = True):
        """Executa o processo de correção de imports."""
        self.dry_run = dry_run
        
        print(f"🔧 Iniciando correção de imports {'(DRY RUN)' if dry_run else '(APLICANDO MUDANÇAS)'}...")
        
        # Carregar relatório de análise
        report = self.load_analysis_report()
        if not report:
            return
        
        # Criar backup se não for dry run
        if not dry_run and create_backup:
            self.create_backup()
        
        # Aplicar correções
        self.fix_relative_imports(report)
        self.fix_cli_imports()
        self.fix_init_files()
        
        # Gerar e exibir relatório
        fix_report = self.generate_fix_report()
        self.print_summary(fix_report)
        
        # Salvar relatório
        report_file = self.project_root / f"import_fixes_report{'_dry_run' if dry_run else ''}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(fix_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Relatório salvo em: {report_file}")
        
        if dry_run:
            print("\n💡 Para aplicar as correções, execute: python fix_imports.py --apply")
        else:
            print("\n✅ Correções aplicadas com sucesso!")

def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Corrige conflitos de importação')
    parser.add_argument('--apply', action='store_true', help='Aplicar correções (padrão: dry run)')
    parser.add_argument('--no-backup', action='store_true', help='Não criar backup')
    
    args = parser.parse_args()
    
    project_root = os.getcwd()
    fixer = ImportFixer(project_root)
    
    fixer.run(
        dry_run=not args.apply,
        create_backup=not args.no_backup
    )

if __name__ == '__main__':
    main()