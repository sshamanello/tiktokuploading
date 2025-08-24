from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
from pathlib import Path
import logging

class UploadStatus(Enum):
    PENDING = "pending"
    UPLOADING = "uploading" 
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"

@dataclass
class VideoMetadata:
    """Метаданные видео для загрузки"""
    file_path: Path
    title: str
    description: Optional[str] = None
    tags: List[str] = None
    schedule_time: Optional[int] = None
    privacy: str = "public"  # public, private, friends
    allow_comments: bool = True
    allow_duet: bool = True
    allow_stitch: bool = True
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass 
class UploadResult:
    """Результат загрузки видео"""
    success: bool
    platform: str
    video_id: Optional[str] = None
    url: Optional[str] = None
    message: str = ""
    status: UploadStatus = UploadStatus.PENDING
    error_details: Optional[Dict[str, Any]] = None

class Platform(ABC):
    """Абстрактный базовый класс для всех платформ"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.platform_name = self.__class__.__name__.replace("Uploader", "").lower()
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Аутентификация на платформе"""
        pass
    
    @abstractmethod 
    def upload_video(self, metadata: VideoMetadata) -> UploadResult:
        """Загрузка видео на платформу"""
        pass
    
    @abstractmethod
    def validate_video(self, file_path: Path) -> bool:
        """Проверка совместимости видео с платформой"""
        pass
    
    @abstractmethod
    def get_upload_limits(self) -> Dict[str, Any]:
        """Получение лимитов платформы"""
        pass
    
    def pre_upload_hook(self, metadata: VideoMetadata) -> VideoMetadata:
        """Хук, выполняемый перед загрузкой (можно переопределить)"""
        return metadata
    
    def post_upload_hook(self, result: UploadResult) -> UploadResult:
        """Хук, выполняемый после загрузки (можно переопределить)"""
        return result
    
    def cleanup(self):
        """Очистка ресурсов (можно переопределить)"""
        pass