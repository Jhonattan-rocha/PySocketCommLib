"""Log Formatter Module

Implementa formatadores personalizados para logs:
- Formatação JSON estruturada
- Formatação colorida para console
- Formatação compacta para produção
- Formatação detalhada para debug
"""

import json
import logging
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ColorCode(Enum):
    """Códigos de cor ANSI"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Cores de texto
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Cores de fundo
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'


class LogFormatter(logging.Formatter):
    """Formatador de logs personalizado"""
    
    def __init__(self, format_type: str = 'json', use_colors: bool = None,
                 compact: bool = False, include_traceback: bool = True):
        """
        Args:
            format_type: Tipo de formatação ('json', 'text', 'compact')
            use_colors: Usar cores (auto-detecta se None)
            compact: Formato compacto
            include_traceback: Incluir traceback em exceções
        """
        super().__init__()
        
        self.format_type = format_type
        self.compact = compact
        self.include_traceback = include_traceback
        
        # Auto-detecta suporte a cores
        if use_colors is None:
            self.use_colors = self._supports_color()
        else:
            self.use_colors = use_colors
        
        # Mapeamento de níveis para cores
        self.level_colors = {
            'DEBUG': ColorCode.CYAN,
            'INFO': ColorCode.GREEN,
            'WARNING': ColorCode.YELLOW,
            'ERROR': ColorCode.RED,
            'CRITICAL': ColorCode.MAGENTA
        }
    
    def _supports_color(self) -> bool:
        """Verifica se o terminal suporta cores"""
        # Verifica se está rodando em um terminal
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
        
        # Verifica variáveis de ambiente
        import os
        term = os.environ.get('TERM', '')
        colorterm = os.environ.get('COLORTERM', '')
        
        # Terminais que suportam cores
        color_terms = ['xterm', 'xterm-color', 'xterm-256color', 'screen', 'linux']
        
        return (term in color_terms or 
                'color' in term.lower() or 
                colorterm in ['truecolor', '24bit'])
    
    def _colorize(self, text: str, color: ColorCode) -> str:
        """Adiciona cor ao texto"""
        if not self.use_colors:
            return text
        return f"{color.value}{text}{ColorCode.RESET.value}"
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata o registro de log"""
        if self.format_type == 'json':
            return self._format_json(record)
        elif self.format_type == 'compact':
            return self._format_compact(record)
        else:
            return self._format_text(record)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """Formatação JSON"""
        try:
            # Tenta fazer parse da mensagem como JSON
            log_data = json.loads(record.getMessage())
            
            # Se já é JSON estruturado, retorna formatado
            if self.compact:
                return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
            else:
                return json.dumps(log_data, ensure_ascii=False, indent=2)
        
        except (json.JSONDecodeError, ValueError):
            # Se não é JSON, cria estrutura JSON
            log_data = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z',
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread_id': record.thread,
                'process_id': record.process
            }
            
            # Adiciona informações de exceção
            if record.exc_info and self.include_traceback:
                log_data['exception'] = {
                    'type': record.exc_info[0].__name__,
                    'message': str(record.exc_info[1]),
                    'traceback': self.formatException(record.exc_info)
                }
            
            if self.compact:
                return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
            else:
                return json.dumps(log_data, ensure_ascii=False, indent=2)
    
    def _format_compact(self, record: logging.LogRecord) -> str:
        """Formatação compacta"""
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = record.levelname[0]  # Primeira letra do nível
        
        # Coloriza o nível se suportado
        if self.use_colors and record.levelname in self.level_colors:
            level = self._colorize(level, self.level_colors[record.levelname])
        
        message = record.getMessage()
        
        # Tenta extrair informações estruturadas
        try:
            log_data = json.loads(message)
            if isinstance(log_data, dict) and 'message' in log_data:
                message = log_data['message']
                
                # Adiciona contexto se disponível
                if 'context' in log_data and 'correlation_id' in log_data['context']:
                    correlation_id = log_data['context']['correlation_id'][:8]
                    message = f"[{correlation_id}] {message}"
        except (json.JSONDecodeError, ValueError):
            pass
        
        return f"{timestamp} {level} {message}"
    
    def _format_text(self, record: logging.LogRecord) -> str:
        """Formatação de texto detalhada"""
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        
        # Coloriza o nível se suportado
        if self.use_colors and level in self.level_colors:
            level = self._colorize(f"{level:8}", self.level_colors[level])
        else:
            level = f"{level:8}"
        
        # Informações do código
        location = f"{record.module}:{record.funcName}:{record.lineno}"
        if self.use_colors:
            location = self._colorize(location, ColorCode.DIM)
        
        message = record.getMessage()
        
        # Tenta extrair informações estruturadas
        context_info = ""
        try:
            log_data = json.loads(message)
            if isinstance(log_data, dict):
                if 'message' in log_data:
                    message = log_data['message']
                
                # Adiciona contexto
                if 'context' in log_data:
                    context = log_data['context']
                    context_parts = []
                    
                    if 'correlation_id' in context:
                        context_parts.append(f"corr:{context['correlation_id'][:8]}")
                    if 'user_id' in context and context['user_id']:
                        context_parts.append(f"user:{context['user_id']}")
                    if 'component' in context and context['component']:
                        context_parts.append(f"comp:{context['component']}")
                    
                    if context_parts:
                        context_info = f" [{', '.join(context_parts)}]"
                        if self.use_colors:
                            context_info = self._colorize(context_info, ColorCode.BLUE)
                
                # Adiciona informações extras relevantes
                extra_info = ""
                if 'extra' in log_data:
                    extra = log_data['extra']
                    extra_parts = []
                    
                    if 'http_status_code' in extra:
                        status = extra['http_status_code']
                        color = ColorCode.GREEN if status < 400 else ColorCode.RED
                        if self.use_colors:
                            extra_parts.append(self._colorize(f"status:{status}", color))
                        else:
                            extra_parts.append(f"status:{status}")
                    
                    if 'duration_ms' in extra:
                        duration = extra['duration_ms']
                        extra_parts.append(f"duration:{duration:.1f}ms")
                    
                    if extra_parts:
                        extra_info = f" ({', '.join(extra_parts)})"
                
                message += extra_info
        
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Monta a linha final
        log_line = f"{timestamp} {level} {location}{context_info} - {message}"
        
        # Adiciona traceback se houver exceção
        if record.exc_info and self.include_traceback:
            log_line += "\n" + self.formatException(record.exc_info)
        
        return log_line


class ProductionFormatter(LogFormatter):
    """Formatador otimizado para produção"""
    
    def __init__(self):
        super().__init__(
            format_type='json',
            use_colors=False,
            compact=True,
            include_traceback=True
        )


class DevelopmentFormatter(LogFormatter):
    """Formatador otimizado para desenvolvimento"""
    
    def __init__(self):
        super().__init__(
            format_type='text',
            use_colors=True,
            compact=False,
            include_traceback=True
        )


class CompactFormatter(LogFormatter):
    """Formatador compacto para logs de alta frequência"""
    
    def __init__(self):
        super().__init__(
            format_type='compact',
            use_colors=True,
            compact=True,
            include_traceback=False
        )