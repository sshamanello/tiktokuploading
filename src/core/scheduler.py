import asyncio
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
import time
from pathlib import Path
import json
from queue import Queue, PriorityQueue, Empty
import uuid

class TaskStatus(Enum):
    """Статусы задач планировщика"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"

class TaskPriority(Enum):
    """Приоритеты задач"""
    LOW = 3
    NORMAL = 2  
    HIGH = 1
    URGENT = 0

@dataclass
class ScheduledTask:
    """Запланированная задача"""
    id: str
    platform: str
    video_path: Path
    title: str
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    scheduled_time: Optional[datetime] = None
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    attempts: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """Для сортировки в PriorityQueue"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.scheduled_time < other.scheduled_time if self.scheduled_time else True

class TaskScheduler:
    """Планировщик задач для загрузки видео"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.is_running = False
        self.tasks: Dict[str, ScheduledTask] = {}
        self.task_queue = PriorityQueue()
        self.worker_threads = []
        self.max_concurrent = config.get('max_concurrent_uploads', 2)
        self.running_tasks = set()
        self.lock = threading.RLock()
        
        # Файл для сохранения состояния
        self.state_file = Path(config.get('scheduler_state_file', './scheduler_state.json'))
        
        # Callbacks
        self.on_task_start: Optional[Callable] = None
        self.on_task_complete: Optional[Callable] = None
        self.on_task_fail: Optional[Callable] = None
    
    def start(self):
        """Запускает планировщик"""
        if self.is_running:
            self.logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        self.logger.info("Starting task scheduler...")
        
        # Загружаем сохраненное состояние
        self._load_state()
        
        # Запускаем worker threads
        for i in range(self.max_concurrent):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        # Запускаем планировщик cron-задач
        schedule_thread = threading.Thread(
            target=self._schedule_loop,
            name="ScheduleLoop",
            daemon=True
        )
        schedule_thread.start()
        self.worker_threads.append(schedule_thread)
        
        self.logger.info(f"Scheduler started with {self.max_concurrent} workers")
    
    def stop(self):
        """Останавливает планировщик"""
        if not self.is_running:
            return
        
        self.logger.info("Stopping task scheduler...")
        self.is_running = False
        
        # Сохраняем состояние
        self._save_state()
        
        # Ждем завершения worker threads
        for worker in self.worker_threads:
            if worker.is_alive():
                worker.join(timeout=5)
        
        self.logger.info("Scheduler stopped")
    
    def add_task(self, platform: str, video_path: Path, title: str, 
                description: str = None, tags: List[str] = None,
                scheduled_time: datetime = None, priority: TaskPriority = TaskPriority.NORMAL,
                metadata: Dict[str, Any] = None) -> str:
        """Добавляет задачу в планировщик"""
        
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            id=task_id,
            platform=platform,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags or [],
            scheduled_time=scheduled_time or datetime.now(),
            priority=priority,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.tasks[task_id] = task
            
            # Если время не указано или уже прошло, добавляем в очередь сразу
            if not scheduled_time or scheduled_time <= datetime.now():
                task.status = TaskStatus.PENDING
                self.task_queue.put(task)
                self.logger.info(f"Task {task_id} added to queue immediately")
            else:
                task.status = TaskStatus.SCHEDULED
                self.logger.info(f"Task {task_id} scheduled for {scheduled_time}")
        
        # Сохраняем состояние
        self._save_state()
        
        return task_id
    
    def add_recurring_task(self, platform: str, video_directory: Path,
                          cron_expression: str, title_template: str = "{filename}",
                          priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Добавляет повторяющуюся задачу"""
        # TODO: Реализовать поддержку cron expressions
        # Пока делаем простую реализацию
        
        task_id = f"recurring_{uuid.uuid4()}"
        
        def schedule_next_videos():
            """Планирует следующие видео из директории"""
            try:
                videos = list(video_directory.glob("*.mp4"))
                for video in videos[:1]:  # Берем одно видео за раз
                    title = title_template.format(filename=video.stem)
                    self.add_task(
                        platform=platform,
                        video_path=video,
                        title=title,
                        priority=priority
                    )
            except Exception as e:
                self.logger.error(f"Error in recurring task {task_id}: {e}")
        
        # Используем библиотeku schedule для простых recurring tasks
        if cron_expression == "daily":
            schedule.every().day.at("09:00").do(schedule_next_videos)
        elif cron_expression == "hourly":
            schedule.every().hour.do(schedule_next_videos)
        else:
            self.logger.warning(f"Unsupported cron expression: {cron_expression}")
        
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """Отменяет задачу"""
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status in [TaskStatus.RUNNING]:
                self.logger.warning(f"Cannot cancel running task {task_id}")
                return False
            
            task.status = TaskStatus.CANCELLED
            self.logger.info(f"Task {task_id} cancelled")
            
        self._save_state()
        return True
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Получает статус задачи"""
        with self.lock:
            task = self.tasks.get(task_id)
            return task.status if task else None
    
    def get_all_tasks(self, status_filter: Optional[TaskStatus] = None) -> List[ScheduledTask]:
        """Получает все задачи с опциональной фильтрацией"""
        with self.lock:
            tasks = list(self.tasks.values())
            if status_filter:
                tasks = [task for task in tasks if task.status == status_filter]
            return tasks
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Получает статистику очереди"""
        with self.lock:
            stats = {
                'total_tasks': len(self.tasks),
                'pending': len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
                'running': len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]), 
                'completed': len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
                'failed': len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED]),
                'scheduled': len([t for t in self.tasks.values() if t.status == TaskStatus.SCHEDULED]),
                'queue_size': self.task_queue.qsize(),
                'running_workers': len(self.running_tasks)
            }
            return stats
    
    def _worker_loop(self):
        """Основной цикл worker thread"""
        while self.is_running:
            try:
                # Получаем задачу из очереди с timeout
                try:
                    task = self.task_queue.get(timeout=1)
                except Empty:
                    # Нет задач в очереди, продолжаем
                    continue
                
                # Проверяем, что задача еще актуальна
                with self.lock:
                    if task.id not in self.tasks or task.status == TaskStatus.CANCELLED:
                        continue
                    
                    task.status = TaskStatus.RUNNING
                    task.attempts += 1
                    self.running_tasks.add(task.id)
                
                self.logger.info(f"Starting task {task.id}: {task.platform} - {task.title[:50]}...")
                
                try:
                    # Вызываем callback начала задачи
                    if self.on_task_start:
                        self.on_task_start(task)
                    
                    # Выполняем задачу
                    success = self._execute_task(task)
                    
                    with self.lock:
                        if success:
                            task.status = TaskStatus.COMPLETED
                            task.last_error = None
                            self.logger.info(f"Task {task.id} completed successfully")
                            
                            # Вызываем callback успешного завершения
                            if self.on_task_complete:
                                self.on_task_complete(task, True)
                        else:
                            self._handle_task_failure(task)
                            
                except Exception as e:
                    self.logger.error(f"Task {task.id} failed with exception: {e}")
                    with self.lock:
                        task.last_error = str(e)
                        self._handle_task_failure(task)
                
                finally:
                    with self.lock:
                        self.running_tasks.discard(task.id)
                    
                    self.task_queue.task_done()
                    
            except Exception as e:
                if self.is_running:  # Игнорируем ошибки при остановке
                    self.logger.error(f"Worker loop error: {e}", exc_info=True)
                continue
    
    def _schedule_loop(self):
        """Цикл для обработки запланированных задач и cron jobs"""
        while self.is_running:
            try:
                # Проверяем запланированные задачи
                current_time = datetime.now()
                
                with self.lock:
                    for task in list(self.tasks.values()):
                        if (task.status == TaskStatus.SCHEDULED and 
                            task.scheduled_time and 
                            task.scheduled_time <= current_time):
                            
                            task.status = TaskStatus.PENDING
                            self.task_queue.put(task)
                            self.logger.info(f"Task {task.id} moved to pending queue")
                
                # Запускаем cron jobs
                schedule.run_pending()
                
                time.sleep(30)  # Проверяем каждые 30 секунд
                
            except Exception as e:
                self.logger.error(f"Schedule loop error: {e}", exc_info=True)
                time.sleep(30)
    
    def _execute_task(self, task: ScheduledTask) -> bool:
        """Выполняет задачу загрузки"""
        try:
            # Здесь должна быть интеграция с platform uploaders
            # Пока делаем заглушку
            
            self.logger.info(f"Executing task: {task.platform} upload of {task.video_path.name}")
            
            # Имитация работы
            time.sleep(2)
            
            # В реальной реализации:
            # 1. Создать uploader для платформы
            # 2. Подготовить метаданные
            # 3. Выполнить upload
            # 4. Обработать результат
            
            # Временная заглушка - 90% успех
            import random
            return random.random() > 0.1
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            return False
    
    def _handle_task_failure(self, task: ScheduledTask):
        """Обрабатывает неудачное выполнение задачи"""
        if task.attempts < task.max_attempts:
            # Планируем повторную попытку с задержкой
            retry_delay = min(300, 60 * (2 ** (task.attempts - 1)))  # Экспоненциальная задержка
            retry_time = datetime.now() + timedelta(seconds=retry_delay)
            
            task.status = TaskStatus.SCHEDULED
            task.scheduled_time = retry_time
            
            self.logger.warning(f"Task {task.id} will retry in {retry_delay}s (attempt {task.attempts}/{task.max_attempts})")
        else:
            task.status = TaskStatus.FAILED
            self.logger.error(f"Task {task.id} failed permanently after {task.attempts} attempts")
            
            # Вызываем callback неудачного завершения
            if self.on_task_fail:
                self.on_task_fail(task)
    
    def _save_state(self):
        """Сохраняет состояние планировщика в файл"""
        try:
            state = {
                'tasks': {},
                'saved_at': datetime.now().isoformat()
            }
            
            for task_id, task in self.tasks.items():
                # Сериализуем только важные поля
                state['tasks'][task_id] = {
                    'id': task.id,
                    'platform': task.platform,
                    'video_path': str(task.video_path),
                    'title': task.title,
                    'description': task.description,
                    'tags': task.tags,
                    'scheduled_time': task.scheduled_time.isoformat() if task.scheduled_time else None,
                    'priority': task.priority.name,
                    'status': task.status.name,
                    'created_at': task.created_at.isoformat(),
                    'attempts': task.attempts,
                    'max_attempts': task.max_attempts,
                    'last_error': task.last_error,
                    'metadata': task.metadata
                }
            
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Failed to save scheduler state: {e}")
    
    def _load_state(self):
        """Загружает состояние планировщика из файла"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            for task_data in state.get('tasks', {}).values():
                task = ScheduledTask(
                    id=task_data['id'],
                    platform=task_data['platform'],
                    video_path=Path(task_data['video_path']),
                    title=task_data['title'],
                    description=task_data.get('description'),
                    tags=task_data.get('tags', []),
                    scheduled_time=datetime.fromisoformat(task_data['scheduled_time']) if task_data.get('scheduled_time') else None,
                    priority=TaskPriority[task_data.get('priority', 'NORMAL')],
                    status=TaskStatus[task_data.get('status', 'PENDING')],
                    created_at=datetime.fromisoformat(task_data.get('created_at', datetime.now().isoformat())),
                    attempts=task_data.get('attempts', 0),
                    max_attempts=task_data.get('max_attempts', 3),
                    last_error=task_data.get('last_error'),
                    metadata=task_data.get('metadata', {})
                )
                
                self.tasks[task.id] = task
                
                # Добавляем в очередь pending задачи
                if task.status == TaskStatus.PENDING:
                    self.task_queue.put(task)
                elif task.status == TaskStatus.RUNNING:
                    # Задачи которые были в процессе выполнения переводим в pending
                    task.status = TaskStatus.PENDING
                    self.task_queue.put(task)
            
            self.logger.info(f"Loaded {len(self.tasks)} tasks from state file")
            
        except Exception as e:
            self.logger.error(f"Failed to load scheduler state: {e}")