from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio
import signal
import sys
from datetime import datetime

from .core.config_manager import ConfigManager, AppConfig
from .core.logger import LoggerManager, setup_exception_logging
from .core.file_manager import FileManager, VideoFile
from .core.scheduler import TaskScheduler, TaskPriority
from .core.platform_base import VideoMetadata, UploadResult
from .platforms.tiktok_uploader import TikTokUploader
from .platforms.instagram_uploader import InstagramUploader

class UploaderApp:
    """Основное приложение для загрузки видео"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Инициализация менеджеров
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        
        # Настройка логирования
        self.logger_manager = LoggerManager()
        self.logger_manager.setup_logging({
            'log_level': self.config.log_level,
            'log_file': self.config.log_file,
            'json_logging': False,
            'console_colors': True
        })
        
        self.logger = self.logger_manager.get_logger('root')
        
        # Настройка обработки исключений
        setup_exception_logging()
        
        # Валидация конфигурации
        self._validate_config()
        
        # Инициализация компонентов
        self.file_manager = FileManager(
            self.config.videos_dir,
            self.config.uploaded_dir, 
            self.config.titles_file
        )
        
        self.scheduler = None
        if self.config.scheduler_enabled:
            self.scheduler = TaskScheduler(
                config={
                    'max_concurrent_uploads': self.config.max_concurrent_uploads,
                    'scheduler_state_file': './scheduler_state.json'
                },
                logger=self.logger_manager.get_logger('scheduler')
            )
        
        # Инициализация платформ
        self.platforms = {}
        try:
            self._init_platforms()
        except Exception as e:
            self.logger.error(f"Critical error during platform initialization: {e}")
            self.logger.debug("Platform initialization error details:", exc_info=True)
        
        # Состояние приложения
        self.is_running = False
        
        self.logger.info("UploaderApp initialized successfully")
    
    def _validate_config(self):
        """Валидирует конфигурацию"""
        errors = self.config_manager.validate_config(self.config)
        if errors:
            self.logger.error("Configuration validation failed:")
            for error in errors:
                self.logger.error(f"  - {error}")
            
            # Создаем недостающие директории
            Path(self.config.videos_dir).mkdir(parents=True, exist_ok=True)
            Path(self.config.uploaded_dir).mkdir(parents=True, exist_ok=True)
            
            # Создаем файл заголовков если не существует
            titles_path = Path(self.config.titles_file)
            if not titles_path.exists():
                titles_path.touch()
                self.logger.info(f"Created titles file: {titles_path}")
    
    def _init_platforms(self):
        """Инициализирует платформы для загрузки"""
        self.logger.info("Initializing platforms...")
        
        # TikTok
        if self.config.tiktok.enabled:
            tiktok_config = {
                'cookies_path': self.config.tiktok.cookies_path,
                'proxy': self.config.tiktok.proxy,
                'proxy_user': self.config.tiktok.proxy_user,
                'proxy_pass': self.config.tiktok.proxy_pass,
                'retry_attempts': self.config.tiktok.retry_attempts
            }
            
            try:
                self.platforms['tiktok'] = TikTokUploader(
                    tiktok_config,
                    self.logger_manager.get_logger('tiktok')
                )
                self.logger.info("TikTok uploader initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize TikTok uploader: {e}")
                self.logger.debug("TikTok initialization error details:", exc_info=True)
        
        # Instagram
        if self.config.instagram.enabled:
            instagram_config = {
                'cookies_path': self.config.instagram.cookies_path,
                'proxy': self.config.instagram.proxy,
                'proxy_user': self.config.instagram.proxy_user,
                'proxy_pass': self.config.instagram.proxy_pass,
                'retry_attempts': self.config.instagram.retry_attempts
            }
            
            try:
                self.platforms['instagram'] = InstagramUploader(
                    instagram_config,
                    self.logger_manager.get_logger('instagram')
                )
                self.logger.info("Instagram uploader initialized (not implemented yet)")
            except Exception as e:
                self.logger.error(f"Failed to initialize Instagram uploader: {e}")
                self.logger.debug("Instagram initialization error details:", exc_info=True)
        
        self.logger.info(f"Platform initialization complete. Available platforms: {list(self.platforms.keys())}")
    
    async def start(self):
        """Запускает приложение"""
        if self.is_running:
            self.logger.warning("App already running")
            return
        
        self.is_running = True
        self.logger.info("Starting UploaderApp...")
        
        # Запускаем планировщик если включен
        if self.scheduler:
            self.scheduler.start()
            
            # Настраиваем callbacks
            self.scheduler.on_task_start = self._on_task_start
            self.scheduler.on_task_complete = self._on_task_complete
            self.scheduler.on_task_fail = self._on_task_fail
        
        # Добавляем обработчики сигналов для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("UploaderApp started successfully")
    
    async def stop(self):
        """Останавливает приложение"""
        if not self.is_running:
            return
        
        self.logger.info("Stopping UploaderApp...")
        self.is_running = False
        
        # Останавливаем планировщик
        if self.scheduler:
            self.scheduler.stop()
        
        # Очищаем ресурсы платформ
        for platform in self.platforms.values():
            platform.cleanup()
        
        self.logger.info("UploaderApp stopped")
    
    def upload_single_video(self, platform_name: str, video_path: Path, 
                           title: str = None, **kwargs) -> UploadResult:
        """Загружает одно видео немедленно"""
        if platform_name not in self.platforms:
            return UploadResult(
                success=False,
                platform=platform_name,
                message=f"Platform {platform_name} not configured"
            )
        
        platform = self.platforms[platform_name]
        
        # Подготавливаем метаданные
        if not title:
            title = self.file_manager.get_next_title() or video_path.stem
        
        metadata = VideoMetadata(
            file_path=video_path,
            title=title,
            **kwargs
        )
        
        self.logger.info(f"Starting immediate upload: {video_path.name} to {platform_name}")
        
        try:
            # Аутентификация если нужна
            if not platform.authenticate():
                return UploadResult(
                    success=False,
                    platform=platform_name,
                    message="Authentication failed"
                )
            
            # Выполняем загрузку
            result = platform.upload_video(metadata)
            
            if result.success:
                # Перемещаем видео в папку загруженных
                video_file = VideoFile.from_path(video_path)
                self.file_manager.move_to_uploaded(video_file)
                
                # Убираем использованный заголовок
                if not kwargs.get('title'):
                    self.file_manager.remove_used_title()
                
                self.logger.info(f"Upload successful: {result.message}")
            else:
                self.logger.error(f"Upload failed: {result.message}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return UploadResult(
                success=False,
                platform=platform_name,
                message=f"Upload error: {e}"
            )
        finally:
            platform.cleanup()
    
    def schedule_upload(self, platform_name: str, video_path: Path,
                       title: str = None, scheduled_time: datetime = None,
                       priority: TaskPriority = TaskPriority.NORMAL) -> Optional[str]:
        """Добавляет загрузку в планировщик"""
        if not self.scheduler:
            self.logger.error("Scheduler not enabled")
            return None
        
        if platform_name not in self.platforms:
            self.logger.error(f"Platform {platform_name} not configured") 
            return None
        
        if not title:
            title = self.file_manager.get_next_title() or video_path.stem
        
        task_id = self.scheduler.add_task(
            platform=platform_name,
            video_path=video_path,
            title=title,
            scheduled_time=scheduled_time,
            priority=priority
        )
        
        self.logger.info(f"Task scheduled: {task_id}")
        return task_id
    
    def schedule_batch_upload(self, platform_name: str, max_videos: int = 5) -> List[str]:
        """Планирует загрузку нескольких видео"""
        if not self.scheduler:
            self.logger.error("Scheduler not enabled")
            return []
        
        videos = self.file_manager.get_pending_videos()[:max_videos]
        task_ids = []
        
        for video in videos:
            title = self.file_manager.get_next_title() or video.filename
            task_id = self.schedule_upload(platform_name, video.path, title)
            if task_id:
                task_ids.append(task_id)
        
        self.logger.info(f"Scheduled {len(task_ids)} videos for batch upload")
        return task_ids
    
    def get_app_status(self) -> Dict[str, Any]:
        """Получает статус приложения"""
        status = {
            'is_running': self.is_running,
            'platforms': list(self.platforms.keys()),
            'file_stats': self.file_manager.get_storage_stats(),
            'config': {
                'videos_dir': self.config.videos_dir,
                'uploaded_dir': self.config.uploaded_dir,
                'scheduler_enabled': self.config.scheduler_enabled,
                'gui_enabled': self.config.gui_enabled
            }
        }
        
        if self.scheduler:
            status['scheduler'] = self.scheduler.get_queue_stats()
        
        return status
    
    def _on_task_start(self, task):
        """Callback при начале выполнения задачи"""
        self.logger.info(f"Task started: {task.id} - {task.platform} - {task.title[:50]}...")
    
    def _on_task_complete(self, task, success: bool):
        """Callback при завершении задачи"""
        if success:
            # Перемещаем видео в папку загруженных
            try:
                video_file = VideoFile.from_path(task.video_path)
                self.file_manager.move_to_uploaded(video_file)
                self.logger.info(f"Video moved to uploaded: {task.video_path.name}")
            except Exception as e:
                self.logger.error(f"Failed to move video: {e}")
        
        self.logger.info(f"Task completed: {task.id} - Success: {success}")
    
    def _on_task_fail(self, task):
        """Callback при неудачном выполнении задачи"""
        self.logger.error(f"Task failed permanently: {task.id} - {task.last_error}")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())

# Пример использования
async def main():
    """Пример основной функции"""
    app = UploaderApp()
    
    try:
        await app.start()
        
        # Пример автозагрузки видео
        videos = app.file_manager.get_pending_videos()
        if videos and 'tiktok' in app.platforms:
            result = app.upload_single_video('tiktok', videos[0].path)
            print(f"Upload result: {result.success} - {result.message}")
        
        # Пример планирования загрузки
        if videos and app.scheduler:
            task_ids = app.schedule_batch_upload('tiktok', max_videos=3)
            print(f"Scheduled tasks: {task_ids}")
        
        # Показываем статус
        status = app.get_app_status()
        print(f"App status: {status}")
        
        # Ждем завершения (в реальном приложении здесь будет GUI или web интерфейс)
        # await asyncio.sleep(60)
        
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())