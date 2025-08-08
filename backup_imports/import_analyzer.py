#!/usr/bin/env python3
"""Import Analyzer - Mapeia conflitos de importação no PySocketCommLib."""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

class ImportAnalyzer:
    """Analisa imports em arquivos Python para detectar conflitos."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.relative_imports = defaultdict(list)
        self.absolute_imports = defaultdict(list)
        self.import_conflicts = defaultdict(list)
        self.module_names = set()
        self.problematic_files = []
        
    def scan_project(self) -> Dict:
        """Escaneia todo o projeto em busca de arquivos Python."""
        print(f"Analisando projeto em: {self.project_root}")
        
        for py_file in self.project_root.rglob('*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                self._analyze_file(py_file)
            except Exception as e:
                self.problematic_files.append((str(py_file), str(e)))
                
        return self._generate_report()
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Determina se um arquivo deve ser ignorado."""
        skip_patterns = {
            '__pycache__',
            '.git',
            'venv',
            'env',
            '.pytest_cache'
        }
        
        return any(pattern in str(file_path) for pattern in skip_patterns)
    
    def _analyze_file(self, file_path: Path):
        """Analisa imports em um arquivo específico."""
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError as e:
                self.problematic_files.append((str(file_path), f"Syntax Error: {e}"))
                return
                
        relative_path = file_path.relative_to(self.project_root)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.absolute_imports[str(relative_path)].append(alias.name)
                    self.module_names.add(alias.name.split('.')[0])
                    
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:  # Import relativo
                    module = node.module or ''
                    self.relative_imports[str(relative_path)].append({
                        'level': node.level,
                        'module': module,
                        'names': [alias.name for alias in node.names]
                    })
                else:  # Import absoluto from
                    if node.module:
                        self.absolute_imports[str(relative_path)].append(node.module)
                        self.module_names.add(node.module.split('.')[0])
    
    def _detect_conflicts(self):
        """Detecta conflitos potenciais entre imports."""
        # Detecta módulos que podem conflitar com nomes de diretórios
        project_dirs = {d.name for d in self.project_root.iterdir() if d.is_dir()}
        
        for module in self.module_names:
            if module in project_dirs:
                self.import_conflicts['name_conflicts'].append({
                    'module': module,
                    'conflict_type': 'directory_name_conflict'
                })
    
    def _generate_report(self) -> Dict:
        """Gera relatório completo da análise."""
        self._detect_conflicts()
        
        report = {
            'summary': {
                'total_files_analyzed': len(self.relative_imports) + len(self.absolute_imports),
                'files_with_relative_imports': len(self.relative_imports),
                'files_with_absolute_imports': len(self.absolute_imports),
                'problematic_files': len(self.problematic_files),
                'unique_modules': len(self.module_names)
            },
            'relative_imports': dict(self.relative_imports),
            'absolute_imports': dict(self.absolute_imports),
            'import_conflicts': dict(self.import_conflicts),
            'problematic_files': self.problematic_files,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Gera recomendações para resolver conflitos."""
        recommendations = []
        
        if self.relative_imports:
            recommendations.append(
                "Converter imports relativos para absolutos para melhor compatibilidade"
            )
        
        if self.import_conflicts.get('name_conflicts'):
            recommendations.append(
                "Resolver conflitos de nomes entre módulos e diretórios"
            )
        
        if self.problematic_files:
            recommendations.append(
                "Corrigir arquivos com erros de sintaxe ou encoding"
            )
        
        recommendations.extend([
            "Implementar importações consistentes em todo o projeto",
            "Considerar uso de __init__.py para controlar exports",
            "Atualizar CLI para usar importações absolutas",
            "Modernizar testes legados com imports corretos"
        ])
        
        return recommendations
    
    def print_report(self, report: Dict):
        """Imprime relatório formatado."""
        print("\n" + "="*60)
        print("RELATÓRIO DE ANÁLISE DE IMPORTS - PySocketCommLib")
        print("="*60)
        
        # Resumo
        summary = report['summary']
        print(f"\n📊 RESUMO:")
        print(f"  • Arquivos analisados: {summary['total_files_analyzed']}")
        print(f"  • Com imports relativos: {summary['files_with_relative_imports']}")
        print(f"  • Com imports absolutos: {summary['files_with_absolute_imports']}")
        print(f"  • Arquivos problemáticos: {summary['problematic_files']}")
        print(f"  • Módulos únicos: {summary['unique_modules']}")
        
        # Imports relativos
        if report['relative_imports']:
            print(f"\n🔄 IMPORTS RELATIVOS ({len(report['relative_imports'])} arquivos):")
            for file, imports in list(report['relative_imports'].items())[:5]:
                print(f"  📁 {file}:")
                for imp in imports[:3]:
                    level_dots = '.' * imp['level']
                    print(f"    {level_dots}{imp['module']} -> {imp['names'][:3]}")
                if len(imports) > 3:
                    print(f"    ... e mais {len(imports) - 3} imports")
            if len(report['relative_imports']) > 5:
                print(f"  ... e mais {len(report['relative_imports']) - 5} arquivos")
        
        # Conflitos
        if report['import_conflicts']:
            print(f"\n⚠️  CONFLITOS DETECTADOS:")
            for conflict_type, conflicts in report['import_conflicts'].items():
                print(f"  • {conflict_type}: {len(conflicts)} conflitos")
                for conflict in conflicts[:3]:
                    print(f"    - {conflict}")
        
        # Arquivos problemáticos
        if report['problematic_files']:
            print(f"\n❌ ARQUIVOS PROBLEMÁTICOS ({len(report['problematic_files'])}):")
            for file, error in report['problematic_files'][:5]:
                print(f"  • {file}: {error}")
        
        # Recomendações
        print(f"\n💡 RECOMENDAÇÕES:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
        
        print("\n" + "="*60)

def main():
    """Função principal."""
    project_root = os.getcwd()
    
    print("🔍 Iniciando análise de imports...")
    analyzer = ImportAnalyzer(project_root)
    report = analyzer.scan_project()
    analyzer.print_report(report)
    
    # Salvar relatório em arquivo
    import json
    report_file = os.path.join(project_root, 'import_analysis_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Relatório detalhado salvo em: {report_file}")
    print("\n✅ Análise concluída!")

if __name__ == '__main__':
    main()