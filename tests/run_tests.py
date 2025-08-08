#!/usr/bin/env python3
"""Test Runner - Executa todos os testes do PySocketCommLib."""

import sys
import os
import unittest
from pathlib import Path

# Adicionar diretório do projeto ao path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

def discover_tests():
    """Descobre e executa todos os testes."""
    tests_dir = Path(__file__).parent
    
    # Descobrir testes
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir), pattern='test_*.py')
    
    # Executar testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Relatório final
    print(f"\n{'='*60}")
    print("RESUMO DOS TESTES")
    print(f"{'='*60}")
    print(f"Testes executados: {result.testsRun}")
    print(f"Falhas: {len(result.failures)}")
    print(f"Erros: {len(result.errors)}")
    print(f"Sucessos: {result.testsRun - len(result.failures) - len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ FALHAS:")
        for test, traceback in result.failures:
            print(f"  • {test}: {traceback.split('\n')[-2]}")
    
    if result.errors:
        print(f"\n💥 ERROS:")
        for test, traceback in result.errors:
            print(f"  • {test}: {traceback.split('\n')[-2]}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = discover_tests()
    sys.exit(0 if success else 1)
