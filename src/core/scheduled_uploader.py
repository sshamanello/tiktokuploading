import asyncio
import random
from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging
import json
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

class ScheduleType(Enum):
    """Типы расписаний"""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"

@dataclass
class UploadSchedule:
    """Расписание для автоматических загрузок"""
    id: str
    name: str
    platform: str
    schedule_type: ScheduleType
    upload_times: List[str]  # Список времен в формате "HH:MM"
    days_of_week: List[int]  # 0-6, где 0=понедельник
    enabled: bool = True
    auto_select_video: bool = True
    auto_select_title: bool = True
    video_directory: Optional[str] = None
    titles_file: Optional[str] = None
    max_videos_per_day: int = 5
    created_at: datetime = None
    last_run: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class ScheduledUploader:
    """Расширенная система планирования загрузок с расписанием"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger, scheduler):
        self.config = config
        self.logger = logger
        self.scheduler = scheduler  # Базовый планировщик задач
        self.schedules: Dict[str, UploadSchedule] = {}
        self.is_running = False
        
        # Файлы для сохранения состояния
        self.schedules_file = Path(config.get('schedules_file', './schedules.json'))
        self.used_videos_file = Path(config.get('used_videos_file', './used_videos.json'))
        self.used_titles_file = Path(config.get('used_titles_file', './used_titles.json'))
        
        # Списки использованных элементов
        self.used_videos = set()
        self.used_titles = set()
        
        self._load_state()
    
    def create_schedule(self, name: str, platform: str, schedule_type: ScheduleType,
                       upload_times: List[str], days_of_week: List[int] = None,
                       auto_select_video: bool = True, auto_select_title: bool = True,
                       video_directory: str = None, titles_file: str = None,
                       max_videos_per_day: int = 5) -> str:
        """Создает новое расписание"""
        
        schedule_id = str(uuid.uuid4())
        
        if days_of_week is None:
            days_of_week = list(range(7))  # Все дни недели
        
        schedule = UploadSchedule(
            id=schedule_id,
            name=name,
            platform=platform,
            schedule_type=schedule_type,
            upload_times=upload_times,
            days_of_week=days_of_week,
            auto_select_video=auto_select_video,
            auto_select_title=auto_select_title,
            video_directory=video_directory or self.config.get('videos_dir', './VideosDirPath'),
            titles_file=titles_file or self.config.get('titles_file', './titles.txt'),
            max_videos_per_day=max_videos_per_day
        )
        
        self.schedules[schedule_id] = schedule
        self._save_schedules()
        
        self.logger.info(f"Created schedule '{name}' with ID {schedule_id}")
        return schedule_id
    
    def update_schedule(self, schedule_id: str, **kwargs) -> bool:
        """Обновляет существующее расписание"""
        if schedule_id not in self.schedules:
            return False
        
        schedule = self.schedules[schedule_id]
        for key, value in kwargs.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        self._save_schedules()
        self.logger.info(f"Updated schedule {schedule_id}")
        return True
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Удаляет расписание"""
        if schedule_id not in self.schedules:
            return False
        
        del self.schedules[schedule_id]
        self._save_schedules()
        
        self.logger.info(f"Deleted schedule {schedule_id}")
        return True
    
    def get_schedule(self, schedule_id: str) -> Optional[UploadSchedule]:
        """Получает расписание по ID"""
        return self.schedules.get(schedule_id)
    
    def get_all_schedules(self) -> List[UploadSchedule]:
        """Получает все расписания"""
        return list(self.schedules.values())
    
    def start_scheduler(self):
        """Запускает планировщик расписаний"""
        if self.is_running:
            self.logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        self.logger.info("Starting scheduled uploader...")
        
        # Запускаем асинхронную задачу для проверки расписаний
        asyncio.create_task(self._schedule_loop())
    
    def stop_scheduler(self):
        """Останавливает планировщик расписаний"""
        self.is_running = False
        self.logger.info("Stopping scheduled uploader...")
    
    async def _schedule_loop(self):
        """Основной цикл проверки расписаний"""
        while self.is_running:
            try:
                current_time = datetime.now()
                current_weekday = current_time.weekday()
                current_time_str = current_time.strftime("%H:%M")
                
                for schedule in self.schedules.values():
                    if not schedule.enabled:
                        continue
                    
                    # Проверяем, нужно ли выполнять задачу
                    should_run = self._should_run_schedule(schedule, current_time, current_weekday, current_time_str)
                    
                    if should_run:
                        await self._execute_scheduled_upload(schedule, current_time)
                
                # Проверяем каждую минуту
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Schedule loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def _should_run_schedule(self, schedule: UploadSchedule, current_time: datetime, 
                           current_weekday: int, current_time_str: str) -> bool:
        """Проверяет, нужно ли выполнять расписание"""
        
        # Проверяем день недели
        if current_weekday not in schedule.days_of_week:
            return False
        
        # Проверяем время
        if current_time_str not in schedule.upload_times:
            return False
        
        # Проверяем, не выполнялось ли уже сегодня в это время
        if schedule.last_run:
            last_run_date = schedule.last_run.date()
            current_date = current_time.date()
            last_run_time = schedule.last_run.strftime("%H:%M")
            
            if (last_run_date == current_date and 
                last_run_time == current_time_str):
                return False
        
        # Проверяем лимит видео в день
        if schedule.schedule_type == ScheduleType.DAILY:
            today_uploads = self._count_today_uploads(schedule.platform)
            if today_uploads >= schedule.max_videos_per_day:
                return False
        
        return True
    
    async def _execute_scheduled_upload(self, schedule: UploadSchedule, current_time: datetime):
        """Выполняет запланированную загрузку"""
        try:
            self.logger.info(f"Executing scheduled upload: {schedule.name}")
            
            # Выбираем видео
            video_path = None
            if schedule.auto_select_video:
                video_path = self._select_random_video(schedule.video_directory)
            
            if not video_path:
                self.logger.warning(f"No video found for schedule {schedule.name}")
                return
            
            # Выбираем название
            title = ""
            if schedule.auto_select_title:
                title = self._select_random_title(schedule.titles_file)
            
            if not title:
                title = f"Auto upload {current_time.strftime('%Y-%m-%d %H:%M')}"
            
            # Создаем задачу в базовом планировщике
            task_id = self.scheduler.add_task(
                platform=schedule.platform,
                video_path=video_path,
                title=title,
                scheduled_time=current_time,
                metadata={
                    'schedule_id': schedule.id,
                    'schedule_name': schedule.name,
                    'auto_selected': True
                }
            )
            
            # Обновляем время последнего выполнения
            schedule.last_run = current_time
            self._save_schedules()
            
            self.logger.info(f"Scheduled upload task {task_id} for {video_path.name} with title '{title}'")
            
        except Exception as e:
            self.logger.error(f"Failed to execute scheduled upload: {e}", exc_info=True)
    
    def _select_random_video(self, video_directory: str) -> Optional[Path]:
        """Выбирает случайное видео из директории"""
        try:
            video_dir = Path(video_directory)
            if not video_dir.exists():
                self.logger.error(f"Video directory not found: {video_directory}")
                return None
            
            # Получаем все видео файлы
            video_files = []
            for ext in ['.mp4', '.mov', '.avi', '.webm']:
                video_files.extend(video_dir.glob(f"*{ext}"))
            
            # Фильтруем уже использованные
            available_videos = [v for v in video_files if str(v) not in self.used_videos]
            
            if not available_videos:
                # Если все видео использованы, сбрасываем список
                self.logger.info("All videos used, resetting used videos list")
                self.used_videos.clear()
                available_videos = video_files
            
            if not available_videos:
                return None
            
            # Выбираем случайное видео
            selected_video = random.choice(available_videos)
            self.used_videos.add(str(selected_video))
            self._save_used_items()
            
            return selected_video
            
        except Exception as e:
            self.logger.error(f"Failed to select random video: {e}")
            return None
    
    def _select_random_title(self, titles_file: str) -> str:
        """Выбирает случайное название из файла"""
        try:
            titles_path = Path(titles_file)
            if not titles_path.exists():
                self.logger.error(f"Titles file not found: {titles_file}")
                return ""
            
            # Читаем все названия
            with open(titles_path, 'r', encoding='utf-8') as f:
                all_titles = [line.strip() for line in f.readlines() if line.strip()]
            
            if not all_titles:
                return ""
            
            # Фильтруем уже использованные
            available_titles = [t for t in all_titles if t not in self.used_titles]
            
            if not available_titles:
                # Если все названия использованы, сбрасываем список
                self.logger.info("All titles used, resetting used titles list")
                self.used_titles.clear()
                available_titles = all_titles
            
            # Выбираем случайное название
            selected_title = random.choice(available_titles)
            self.used_titles.add(selected_title)
            self._save_used_items()
            
            return selected_title
            
        except Exception as e:
            self.logger.error(f"Failed to select random title: {e}")
            return ""
    
    def _count_today_uploads(self, platform: str) -> int:
        """Подсчитывает количество загрузок сегодня для платформы"""
        today = datetime.now().date()
        count = 0
        
        for task in self.scheduler.get_all_tasks():
            if (task.platform == platform and 
                task.created_at.date() == today and
                task.status.value in ['completed', 'running', 'pending']):
                count += 1
        
        return count
    
    def _save_schedules(self):
        """Сохраняет расписания в файл"""
        try:
            schedules_data = {}
            for schedule_id, schedule in self.schedules.items():
                schedules_data[schedule_id] = {
                    **asdict(schedule),
                    'schedule_type': schedule.schedule_type.value,
                    'created_at': schedule.created_at.isoformat(),
                    'last_run': schedule.last_run.isoformat() if schedule.last_run else None
                }
            
            self.schedules_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.schedules_file, 'w', encoding='utf-8') as f:
                json.dump(schedules_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to save schedules: {e}")
    
    def _load_schedules(self):
        """Загружает расписания из файла"""
        if not self.schedules_file.exists():
            return
        
        try:
            with open(self.schedules_file, 'r', encoding='utf-8') as f:
                schedules_data = json.load(f)
            
            for schedule_id, data in schedules_data.items():
                schedule = UploadSchedule(
                    id=data['id'],
                    name=data['name'],
                    platform=data['platform'],
                    schedule_type=ScheduleType(data['schedule_type']),
                    upload_times=data['upload_times'],
                    days_of_week=data['days_of_week'],
                    enabled=data.get('enabled', True),
                    auto_select_video=data.get('auto_select_video', True),
                    auto_select_title=data.get('auto_select_title', True),
                    video_directory=data.get('video_directory'),
                    titles_file=data.get('titles_file'),
                    max_videos_per_day=data.get('max_videos_per_day', 5),
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_run=datetime.fromisoformat(data['last_run']) if data.get('last_run') else None
                )
                
                self.schedules[schedule_id] = schedule
            
            self.logger.info(f"Loaded {len(self.schedules)} schedules")
            
        except Exception as e:
            self.logger.error(f"Failed to load schedules: {e}")
    
    def _save_used_items(self):
        """Сохраняет списки использованных элементов"""
        try:
            used_data = {
                'videos': list(self.used_videos),
                'titles': list(self.used_titles)
            }
            
            self.used_videos_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.used_videos_file, 'w', encoding='utf-8') as f:
                json.dump(used_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save used items: {e}")
    
    def _load_used_items(self):
        """Загружает списки использованных элементов"""
        if not self.used_videos_file.exists():
            return
        
        try:
            with open(self.used_videos_file, 'r', encoding='utf-8') as f:
                used_data = json.load(f)
            
            self.used_videos = set(used_data.get('videos', []))
            self.used_titles = set(used_data.get('titles', []))
            
            self.logger.info(f"Loaded {len(self.used_videos)} used videos and {len(self.used_titles)} used titles")
            
        except Exception as e:
            self.logger.error(f"Failed to load used items: {e}")
    
    def _load_state(self):
        """Загружает все состояние"""
        self._load_schedules()
        self._load_used_items()
    
    def get_schedule_stats(self) -> Dict[str, Any]:
        """Получает статистику расписаний"""
        enabled_schedules = [s for s in self.schedules.values() if s.enabled]
        
        return {
            'total_schedules': len(self.schedules),
            'enabled_schedules': len(enabled_schedules),
            'disabled_schedules': len(self.schedules) - len(enabled_schedules),
            'used_videos': len(self.used_videos),
            'used_titles': len(self.used_titles),
            'is_running': self.is_running
        }