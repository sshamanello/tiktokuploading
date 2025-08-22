import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import logging

@dataclass
class PlatformConfig:
    """Конфигурация платформы"""
    enabled: bool = False
    cookies_path: Optional[str] = None
    proxy: Optional[str] = None
    proxy_user: Optional[str] = None
    proxy_pass: Optional[str] = None
    retry_attempts: int = 3
    upload_delay: int = 5
    rate_limit: int = 10  # uploads per hour

@dataclass
class AppConfig:
    """Основная конфигурация приложения"""
    # Пути
    videos_dir: str = "./VideosDirPath"
    uploaded_dir: str = "./uploaded"
    titles_file: str = "./titles.txt"
    
    # Telegram
    telegram_enabled: bool = False
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Логирование
    log_level: str = "INFO"
    log_file: str = "./logs/uploader.log"
    
    # Планировщик
    scheduler_enabled: bool = True
    max_concurrent_uploads: int = 2
    
    # GUI
    gui_enabled: bool = True
    gui_host: str = "127.0.0.1" 
    gui_port: int = 8080
    
    # Платформы
    tiktok: PlatformConfig = None
    instagram: PlatformConfig = None
    
    def __post_init__(self):
        if self.tiktok is None:
            self.tiktok = PlatformConfig()
        if self.instagram is None:
            self.instagram = PlatformConfig()

class ConfigManager:
    """Менеджер конфигурации приложения"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config.yaml")
        self.logger = logging.getLogger(__name__)
        self._config: Optional[AppConfig] = None
        
        # Загружаем переменные окружения
        load_dotenv()
    
    def load_config(self) -> AppConfig:
        """Загружает конфигурацию из файла и окружения"""
        if self._config is not None:
            return self._config
            
        # Сначала загружаем базовую конфигурацию
        if self.config_path.exists():
            config_data = self._load_from_file()
        else:
            config_data = {}
            self.logger.warning(f"Config file {self.config_path} not found, using defaults")
        
        # Переопределяем значения из переменных окружения
        config_data = self._override_from_env(config_data)
        
        # Создаем объект конфигурации
        self._config = self._create_config_object(config_data)
        
        return self._config
    
    def save_config(self, config: AppConfig):
        """Сохраняет конфигурацию в файл"""
        try:
            # Создаем директорию если нужно
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Конвертируем в словарь и сохраняем
            config_dict = asdict(config)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
                
            self.logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise
    
    def _load_from_file(self) -> Dict[str, Any]:
        """Загружает конфигурацию из файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    return yaml.safe_load(f) or {}
                    
        except Exception as e:
            self.logger.error(f"Failed to load config from {self.config_path}: {e}")
            return {}
    
    def _override_from_env(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Переопределяет значения из переменных окружения"""
        # Основные настройки
        env_mappings = {
            'VIDEOS_DIR': ['videos_dir'],
            'UPLOADED_DIR': ['uploaded_dir'],
            'TITLES_FILE': ['titles_file'],
            'LOG_LEVEL': ['log_level'],
            'LOG_FILE': ['log_file'],
            
            # Telegram
            'TELEGRAM_BOT_TOKEN': ['telegram_token'],
            'TELEGRAM_CHAT_ID': ['telegram_chat_id'],
            
            # TikTok
            'TIKTOK_COOKIES_PATH': ['tiktok', 'cookies_path'],
            'PROXY': ['tiktok', 'proxy'],
            'PROXY_USER': ['tiktok', 'proxy_user'],
            'PROXY_PASS': ['tiktok', 'proxy_pass'],
            
            # Instagram (заготовка)
            'INSTAGRAM_COOKIES_PATH': ['instagram', 'cookies_path'],
        }
        
        for env_key, config_path in env_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                # Создаем вложенную структуру если нужно
                current = config_data
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Устанавливаем значение
                current[config_path[-1]] = value
        
        # Булевы значения
        bool_mappings = {
            'TELEGRAM_ENABLED': ['telegram_enabled'],
            'SCHEDULER_ENABLED': ['scheduler_enabled'],
            'GUI_ENABLED': ['gui_enabled'],
            'TIKTOK_ENABLED': ['tiktok', 'enabled'],
            'INSTAGRAM_ENABLED': ['instagram', 'enabled'],
        }
        
        for env_key, config_path in bool_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                bool_value = value.lower() in ('true', '1', 'yes', 'on')
                
                current = config_data
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                current[config_path[-1]] = bool_value
        
        return config_data
    
    def _create_config_object(self, config_data: Dict[str, Any]) -> AppConfig:
        """Создает объект конфигурации из словаря"""
        try:
            # Создаем конфигурации платформ
            tiktok_data = config_data.get('tiktok', {})
            instagram_data = config_data.get('instagram', {})
            
            tiktok_config = PlatformConfig(**tiktok_data) if tiktok_data else PlatformConfig()
            instagram_config = PlatformConfig(**instagram_data) if instagram_data else PlatformConfig()
            
            # Создаем основную конфигурацию, оставляем только известные поля
            known_fields = {
                'videos_dir', 'uploaded_dir', 'titles_file', 
                'telegram_enabled', 'telegram_token', 'telegram_chat_id',
                'log_level', 'log_file',
                'scheduler_enabled', 'max_concurrent_uploads',
                'gui_enabled', 'gui_host', 'gui_port'
            }
            
            main_config = {k: v for k, v in config_data.items() if k in known_fields}
            main_config['tiktok'] = tiktok_config
            main_config['instagram'] = instagram_config
            
            return AppConfig(**main_config)
            
        except TypeError as e:
            self.logger.error(f"Invalid configuration format: {e}")
            self.logger.info("Using default configuration")
            return AppConfig()
    
    def validate_config(self, config: AppConfig) -> List[str]:
        """Валидирует конфигурацию и возвращает список ошибок"""
        errors = []
        
        # Проверяем пути
        if not Path(config.videos_dir).exists():
            errors.append(f"Videos directory does not exist: {config.videos_dir}")
        
        if not Path(config.titles_file).exists():
            errors.append(f"Titles file does not exist: {config.titles_file}")
        
        # Проверяем Telegram настройки
        if config.telegram_enabled:
            if not config.telegram_token:
                errors.append("Telegram enabled but token not provided")
            if not config.telegram_chat_id:
                errors.append("Telegram enabled but chat_id not provided")
        
        # Проверяем настройки платформ
        if config.tiktok.enabled:
            if config.tiktok.cookies_path and not Path(config.tiktok.cookies_path).exists():
                errors.append(f"TikTok cookies file not found: {config.tiktok.cookies_path}")
        
        return errors
    
    def create_default_config_file(self):
        """Создает файл конфигурации по умолчанию"""
        default_config = AppConfig()
        self.save_config(default_config)
        self.logger.info(f"Created default configuration file: {self.config_path}")