import time
import random
from typing import Callable, Any, Optional, List, Union
from functools import wraps
import logging
from dataclasses import dataclass
from enum import Enum

class RetryStrategy(Enum):
    """Стратегии повторных попыток"""
    FIXED = "fixed"              # Фиксированная задержка
    EXPONENTIAL = "exponential"  # Экспоненциальная задержка  
    LINEAR = "linear"           # Линейное увеличение
    RANDOM = "random"           # Случайная задержка

@dataclass
class RetryConfig:
    """Конфигурация для retry механизма"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True  # Добавлять случайность к задержке
    exceptions: tuple = (Exception,)  # Исключения для retry
    on_retry: Optional[Callable] = None  # Callback при retry

class RetryManager:
    """Менеджер для обработки повторных попыток"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def retry(self, config: RetryConfig):
        """Декоратор для добавления retry логики к функции"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                return self._execute_with_retry(func, config, args, kwargs)
            return wrapper
        return decorator
    
    def execute_with_retry(self, func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
        """Выполняет функцию с retry логикой"""
        return self._execute_with_retry(func, config, args, kwargs)
    
    def _execute_with_retry(self, func: Callable, config: RetryConfig, args: tuple, kwargs: dict) -> Any:
        """Внутренняя функция выполнения с retry"""
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                if attempt > 0:
                    delay = self._calculate_delay(config, attempt)
                    self.logger.info(f"Retrying {func.__name__} (attempt {attempt + 1}/{config.max_attempts}) after {delay:.1f}s")
                    time.sleep(delay)
                
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                
                return result
                
            except config.exceptions as e:
                last_exception = e
                self.logger.warning(f"{func.__name__} failed on attempt {attempt + 1}: {e}")
                
                # Вызываем callback если есть
                if config.on_retry:
                    try:
                        config.on_retry(attempt, e, args, kwargs)
                    except Exception as callback_error:
                        self.logger.error(f"Retry callback failed: {callback_error}")
                
                # Если это последняя попытка, не ждем
                if attempt == config.max_attempts - 1:
                    break
        
        # Все попытки исчерпаны
        self.logger.error(f"{func.__name__} failed after {config.max_attempts} attempts")
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError(f"Function {func.__name__} failed after {config.max_attempts} attempts")
    
    def _calculate_delay(self, config: RetryConfig, attempt: int) -> float:
        """Вычисляет задержку перед следующей попыткой"""
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
            
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_factor ** (attempt - 1))
            
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt
            
        elif config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(config.base_delay, config.max_delay)
            
        else:
            delay = config.base_delay
        
        # Ограничиваем максимальной задержкой
        delay = min(delay, config.max_delay)
        
        # Добавляем jitter если включен
        if config.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # Не может быть отрицательной
        
        return delay

# Предопределенные конфигурации retry
class RetryConfigs:
    """Предопределенные конфигурации для различных сценариев"""
    
    # Для сетевых запросов
    NETWORK = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL,
        exceptions=(ConnectionError, TimeoutError, OSError)
    )
    
    # Для загрузки файлов
    FILE_UPLOAD = RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL,
        exceptions=(ConnectionError, TimeoutError, OSError, Exception)
    )
    
    # Для операций с браузером
    BROWSER = RetryConfig(
        max_attempts=3,
        base_delay=3.0,
        strategy=RetryStrategy.FIXED,
        exceptions=(Exception,)  # Selenium exceptions
    )
    
    # Для API вызовов
    API_CALL = RetryConfig(
        max_attempts=4,
        base_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL,
        exceptions=(ConnectionError, TimeoutError)
    )
    
    # Быстрые retry для простых операций
    QUICK = RetryConfig(
        max_attempts=2,
        base_delay=0.5,
        strategy=RetryStrategy.FIXED,
        jitter=False
    )

# Удобные функции для использования
def retry_on_exception(exceptions: Union[Exception, tuple] = (Exception,), 
                      max_attempts: int = 3, 
                      delay: float = 1.0,
                      strategy: RetryStrategy = RetryStrategy.EXPONENTIAL):
    """Простой декоратор retry"""
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=delay,
        strategy=strategy,
        exceptions=exceptions if isinstance(exceptions, tuple) else (exceptions,)
    )
    
    manager = RetryManager()
    return manager.retry(config)

def retry_network_call(max_attempts: int = 3, delay: float = 1.0):
    """Декоратор для сетевых вызовов"""
    return retry_on_exception(
        exceptions=(ConnectionError, TimeoutError, OSError),
        max_attempts=max_attempts,
        delay=delay
    )

# Примеры использования в комментариях
"""
# Простое использование декоратора
@retry_on_exception(max_attempts=3, delay=2.0)
def upload_video():
    # Ваш код загрузки
    pass

# Использование с предопределенной конфигурацией
retry_manager = RetryManager(logger)

@retry_manager.retry(RetryConfigs.FILE_UPLOAD)
def upload_large_file():
    # Ваш код
    pass

# Программное использование
def some_function():
    retry_manager = RetryManager()
    
    def risky_operation():
        # операция которая может упасть
        pass
    
    return retry_manager.execute_with_retry(
        risky_operation, 
        RetryConfigs.NETWORK
    )

# С кастомным callback
def on_retry_callback(attempt, exception, args, kwargs):
    print(f"Attempt {attempt} failed with {exception}")

config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    on_retry=on_retry_callback
)
"""