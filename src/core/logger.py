import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import json

class ColoredFormatter(logging.Formatter):
    """Цветной форматтер для консольного вывода"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m'   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """JSON форматтер для структурированного логирования"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Добавляем exception info если есть
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Добавляем дополнительные поля
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry['extra_' + key] = value
        
        return json.dumps(log_entry, ensure_ascii=False)

class Logger:
    """Улучшенная система логирования"""
    
    def __init__(self, name: str, level: str = "INFO", log_file: Optional[str] = None, 
                 json_format: bool = False, console_colors: bool = True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Очищаем существующие handlers
        self.logger.handlers.clear()
        
        # Консольный handler
        console_handler = logging.StreamHandler(sys.stdout)
        if console_colors:
            console_formatter = ColoredFormatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            
            if json_format:
                file_formatter = JSONFormatter()
            else:
                file_formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """Возвращает объект logger"""
        return self.logger

class LoggerManager:
    """Менеджер для управления логгерами приложения"""
    
    _instance = None
    _loggers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def setup_logging(self, config: dict):
        """Настраивает систему логирования из конфига"""
        level = config.get('log_level', 'INFO')
        log_file = config.get('log_file', './logs/uploader.log')
        json_format = config.get('json_logging', False)
        console_colors = config.get('console_colors', True)
        
        # Создаем директорию для логов
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Настраиваем корневой логгер
        root_logger = Logger(
            name='uploader',
            level=level,
            log_file=log_file,
            json_format=json_format,
            console_colors=console_colors
        )
        
        self._loggers['root'] = root_logger
        
        # Настраиваем специализированные логгеры
        specialized_loggers = {
            'scheduler': 'uploader.scheduler',
            'tiktok': 'uploader.tiktok', 
            'instagram': 'uploader.instagram',
            'file_manager': 'uploader.file_manager',
            'gui': 'uploader.gui',
            'notifications': 'uploader.notifications'
        }
        
        for name, logger_name in specialized_loggers.items():
            logger = Logger(
                name=logger_name,
                level=level,
                log_file=log_file,
                json_format=json_format,
                console_colors=console_colors
            )
            self._loggers[name] = logger
    
    def get_logger(self, name: str = 'root') -> logging.Logger:
        """Получает логгер по имени"""
        if name not in self._loggers:
            # Создаем логгер по умолчанию если не найден
            logger = Logger(name=f'uploader.{name}')
            self._loggers[name] = logger
        
        return self._loggers[name].get_logger()
    
    def add_upload_context(self, logger: logging.Logger, platform: str, 
                          video_name: str, upload_id: str = None):
        """Добавляет контекст загрузки к логгеру"""
        # Создаем LoggerAdapter для добавления контекста
        class UploadAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                return f"[{platform.upper()}] [{video_name}] {msg}", kwargs
        
        return UploadAdapter(logger, {
            'platform': platform,
            'video_name': video_name,
            'upload_id': upload_id
        })

def setup_exception_logging():
    """Настраивает логирование необработанных исключений"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger = LoggerManager().get_logger('root')
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception

# Декораторы для логирования
def log_function_call(logger_name: str = 'root'):
    """Декоратор для логирования вызовов функций"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = LoggerManager().get_logger(logger_name)
            logger.debug(f"Calling {func.__name__} with args={args[:2]}... kwargs={list(kwargs.keys())}")
            
            try:
                start_time = datetime.now()
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(f"{func.__name__} completed in {duration:.2f}s")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} failed: {e}")
                raise
        
        return wrapper
    return decorator

def log_errors(logger_name: str = 'root', reraise: bool = True):
    """Декоратор для логирования ошибок"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = LoggerManager().get_logger(logger_name)
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Error in {func.__name__}: {e}")
                if reraise:
                    raise
                return None
        
        return wrapper
    return decorator