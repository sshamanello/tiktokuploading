import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime
import mimetypes

@dataclass
class VideoFile:
    """Представление видеофайла"""
    path: Path
    filename: str
    size: int
    duration: Optional[float] = None
    width: Optional[int] = None 
    height: Optional[int] = None
    format: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_path(cls, file_path: Path) -> 'VideoFile':
        """Создает VideoFile из пути к файлу"""
        stat = file_path.stat()
        
        return cls(
            path=file_path,
            filename=file_path.name,
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime)
        )

class FileManager:
    """Менеджер для работы с видеофайлами"""
    
    SUPPORTED_FORMATS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
    
    def __init__(self, videos_dir: str, uploaded_dir: str, titles_file: str):
        self.videos_dir = Path(videos_dir)
        self.uploaded_dir = Path(uploaded_dir)
        self.titles_file = Path(titles_file)
        self.logger = logging.getLogger(__name__)
        
        # Создаем директории если не существуют
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем файл с заголовками если не существует
        if not self.titles_file.exists():
            self.titles_file.touch()
    
    def get_pending_videos(self) -> List[VideoFile]:
        """Получает список видео для загрузки"""
        videos = []
        
        try:
            for file_path in self.videos_dir.iterdir():
                if file_path.is_file() and self._is_video_file(file_path):
                    try:
                        video = VideoFile.from_path(file_path)
                        videos.append(video)
                    except Exception as e:
                        self.logger.warning(f"Could not process file {file_path}: {e}")
            
            # Сортируем по дате создания
            videos.sort(key=lambda x: x.created_at or datetime.min)
            
        except Exception as e:
            self.logger.error(f"Failed to scan videos directory: {e}")
        
        return videos
    
    def get_next_title(self) -> Optional[str]:
        """Получает следующий заголовок из файла"""
        try:
            if not self.titles_file.exists():
                return None
                
            with open(self.titles_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return None
            
            # Берем первую непустую строку
            for line in lines:
                title = line.strip()
                if title:
                    return title
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to read titles file: {e}")
            return None
    
    def remove_used_title(self):
        """Удаляет использованный заголовок из файла"""
        try:
            if not self.titles_file.exists():
                return
                
            with open(self.titles_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return
            
            # Удаляем первую непустую строку
            new_lines = []
            first_removed = False
            
            for line in lines:
                if not first_removed and line.strip():
                    first_removed = True
                    continue
                new_lines.append(line)
            
            # Записываем обратно
            with open(self.titles_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
        except Exception as e:
            self.logger.error(f"Failed to update titles file: {e}")
    
    def add_titles(self, titles: List[str]):
        """Добавляет заголовки в файл"""
        try:
            with open(self.titles_file, 'a', encoding='utf-8') as f:
                for title in titles:
                    if title.strip():
                        f.write(title.strip() + '\n')
                        
        except Exception as e:
            self.logger.error(f"Failed to add titles: {e}")
    
    def move_to_uploaded(self, video_file: VideoFile) -> bool:
        """Перемещает видео в папку загруженных"""
        try:
            destination = self.uploaded_dir / video_file.filename
            
            # Если файл с таким именем уже существует, добавляем timestamp
            if destination.exists():
                timestamp = datetime.now().strftime("_%Y%m%d_%H%M%S")
                name_parts = video_file.filename.rsplit('.', 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}{timestamp}.{name_parts[1]}"
                else:
                    new_name = f"{video_file.filename}{timestamp}"
                destination = self.uploaded_dir / new_name
            
            shutil.move(str(video_file.path), str(destination))
            self.logger.info(f"Moved video to uploaded: {destination.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move video {video_file.filename}: {e}")
            return False
    
    def backup_video(self, video_file: VideoFile, backup_dir: str = "backup") -> bool:
        """Создает резервную копию видео"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            destination = backup_path / video_file.filename
            shutil.copy2(str(video_file.path), str(destination))
            
            self.logger.info(f"Created backup: {destination}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to backup video {video_file.filename}: {e}")
            return False
    
    def get_video_info(self, file_path: Path) -> Optional[dict]:
        """Получает информацию о видео (требует ffprobe)"""
        try:
            import subprocess
            import json
            
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                self.logger.warning(f"ffprobe failed for {file_path}: {result.stderr}")
                return None
                
        except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.debug(f"Could not get video info for {file_path}: {e}")
            return None
    
    def validate_video_file(self, file_path: Path) -> Tuple[bool, str]:
        """Валидирует видеофайл"""
        if not file_path.exists():
            return False, "File does not exist"
        
        if not file_path.is_file():
            return False, "Path is not a file"
        
        if not self._is_video_file(file_path):
            return False, f"Unsupported file format. Supported: {', '.join(self.SUPPORTED_FORMATS)}"
        
        # Проверяем размер файла (не более 4GB)
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 4096:
            return False, f"File too large: {size_mb:.1f}MB (max 4GB)"
        
        if size_mb < 0.1:
            return False, f"File too small: {size_mb:.3f}MB"
        
        return True, "Valid video file"
    
    def cleanup_temp_files(self):
        """Очищает временные файлы"""
        temp_patterns = ['*.tmp', '*.temp', '*_temp.*']
        
        for pattern in temp_patterns:
            for temp_file in self.videos_dir.glob(pattern):
                try:
                    temp_file.unlink()
                    self.logger.debug(f"Removed temp file: {temp_file}")
                except Exception as e:
                    self.logger.warning(f"Could not remove temp file {temp_file}: {e}")
    
    def get_storage_stats(self) -> dict:
        """Получает статистику использования дискового пространства"""
        def get_dir_size(path: Path) -> int:
            total = 0
            try:
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        total += file_path.stat().st_size
            except Exception:
                pass
            return total
        
        videos_size = get_dir_size(self.videos_dir)
        uploaded_size = get_dir_size(self.uploaded_dir)
        
        return {
            'videos_count': len(self.get_pending_videos()),
            'videos_size_mb': videos_size / (1024 * 1024),
            'uploaded_size_mb': uploaded_size / (1024 * 1024),
            'total_size_mb': (videos_size + uploaded_size) / (1024 * 1024)
        }
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Проверяет, является ли файл видео"""
        # Проверяем расширение
        if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
            return True
        
        # Проверяем MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith('video/'):
            return True
        
        return False