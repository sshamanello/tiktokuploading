from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional, Dict, Any
import asyncio
import json
from pathlib import Path
from datetime import datetime
import logging
import uvicorn

from ..uploader_app import UploaderApp
from ..core.scheduler import TaskPriority, TaskStatus

class WebSocketManager:
    """Менеджер WebSocket соединений для real-time уведомлений"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                # Соединение разорвано, удаляем его
                await self.disconnect_safe(connection)
    
    async def disconnect_safe(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

class WebInterface:
    """Веб-интерфейс для управления загрузчиком"""
    
    def __init__(self, uploader_app: UploaderApp):
        self.app = FastAPI(
            title="Video Uploader",
            description="Web interface for video uploading to social platforms",
            version="2.0.0"
        )
        
        self.uploader_app = uploader_app
        self.logger = logging.getLogger(__name__)
        self.websocket_manager = WebSocketManager()
        
        # Настройка шаблонов и статических файлов
        self.templates = Jinja2Templates(directory="src/gui/templates")
        
        # Создаем директорию для статических файлов если не существует
        static_dir = Path("src/gui/static")
        static_dir.mkdir(parents=True, exist_ok=True)
        
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Регистрируем маршруты
        self._setup_routes()
        
        # Подписываемся на события планировщика
        if self.uploader_app.scheduler:
            self.uploader_app.scheduler.on_task_start = self._on_task_start
            self.uploader_app.scheduler.on_task_complete = self._on_task_complete
            self.uploader_app.scheduler.on_task_fail = self._on_task_fail
    
    def _setup_routes(self):
        """Настройка маршрутов"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Главная страница с дашбордом"""
            status = self.uploader_app.get_app_status()
            videos = self.uploader_app.file_manager.get_pending_videos()
            
            # Получаем задачи планировщика
            tasks = []
            if self.uploader_app.scheduler:
                tasks = self.uploader_app.scheduler.get_all_tasks()
            
            return self.templates.TemplateResponse("dashboard.html", {
                "request": request,
                "status": status,
                "videos": videos[:10],  # Показываем первые 10
                "tasks": tasks[:20],    # Показываем последние 20 задач
                "platforms": list(self.uploader_app.platforms.keys())
            })
        
        @self.app.get("/api/status")
        async def get_status():
            """API для получения статуса приложения"""
            return self.uploader_app.get_app_status()
        
        @self.app.get("/api/videos")
        async def get_videos():
            """API для получения списка видео"""
            videos = self.uploader_app.file_manager.get_pending_videos()
            return [{
                "filename": v.filename,
                "size_mb": round(v.size / (1024*1024), 2),
                "created_at": v.created_at.isoformat() if v.created_at else None
            } for v in videos]
        
        @self.app.get("/api/tasks")
        async def get_tasks(status: Optional[str] = None):
            """API для получения списка задач"""
            if not self.uploader_app.scheduler:
                return []
            
            status_filter = TaskStatus(status) if status else None
            tasks = self.uploader_app.scheduler.get_all_tasks(status_filter)
            
            return [{
                "id": task.id,
                "platform": task.platform,
                "title": task.title[:50] + "..." if len(task.title) > 50 else task.title,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
                "attempts": task.attempts,
                "max_attempts": task.max_attempts,
                "last_error": task.last_error
            } for task in tasks]
        
        @self.app.post("/api/upload")
        async def immediate_upload(
            platform: str = Form(...),
            title: Optional[str] = Form(None),
            description: Optional[str] = Form(None),
            file: Optional[UploadFile] = File(None)
        ):
            """API для немедленной загрузки видео"""
            try:
                if file:
                    # Загружаем файл во временную директорию
                    upload_dir = Path(self.uploader_app.config.videos_dir)
                    file_path = upload_dir / file.filename
                    
                    with open(file_path, "wb") as buffer:
                        content = await file.read()
                        buffer.write(content)
                else:
                    # Берем первое доступное видео
                    videos = self.uploader_app.file_manager.get_pending_videos()
                    if not videos:
                        return JSONResponse({"success": False, "message": "No videos available"})
                    
                    file_path = videos[0].path
                
                result = self.uploader_app.upload_single_video(
                    platform_name=platform,
                    video_path=file_path,
                    title=title,
                    description=description
                )
                
                # Отправляем уведомление через WebSocket
                await self.websocket_manager.broadcast({
                    "type": "upload_result",
                    "data": {
                        "success": result.success,
                        "message": result.message,
                        "platform": result.platform,
                        "filename": file_path.name
                    }
                })
                
                return {
                    "success": result.success,
                    "message": result.message,
                    "video_id": result.video_id,
                    "url": result.url
                }
                
            except Exception as e:
                self.logger.error(f"Upload API error: {e}")
                return JSONResponse(
                    {"success": False, "message": f"Upload failed: {e}"},
                    status_code=500
                )
        
        @self.app.post("/api/schedule")
        async def schedule_upload(
            platform: str = Form(...),
            title: Optional[str] = Form(None),
            description: Optional[str] = Form(None),
            scheduled_time: Optional[str] = Form(None),
            priority: str = Form("normal"),
            filename: Optional[str] = Form(None)
        ):
            """API для планирования загрузки"""
            try:
                if not self.uploader_app.scheduler:
                    return JSONResponse({"success": False, "message": "Scheduler not enabled"})
                
                # Определяем видеофайл
                if filename:
                    video_path = Path(self.uploader_app.config.videos_dir) / filename
                else:
                    videos = self.uploader_app.file_manager.get_pending_videos()
                    if not videos:
                        return JSONResponse({"success": False, "message": "No videos available"})
                    video_path = videos[0].path
                
                # Парсим время
                schedule_time = None
                if scheduled_time:
                    try:
                        schedule_time = datetime.fromisoformat(scheduled_time)
                    except ValueError:
                        return JSONResponse({"success": False, "message": "Invalid time format"})
                
                # Парсим приоритет
                priority_map = {
                    "low": TaskPriority.LOW,
                    "normal": TaskPriority.NORMAL,
                    "high": TaskPriority.HIGH,
                    "urgent": TaskPriority.URGENT
                }
                task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
                
                task_id = self.uploader_app.schedule_upload(
                    platform_name=platform,
                    video_path=video_path,
                    title=title,
                    scheduled_time=schedule_time,
                    priority=task_priority
                )
                
                if task_id:
                    await self.websocket_manager.broadcast({
                        "type": "task_scheduled",
                        "data": {
                            "task_id": task_id,
                            "platform": platform,
                            "filename": video_path.name,
                            "scheduled_time": schedule_time.isoformat() if schedule_time else None
                        }
                    })
                    
                    return {"success": True, "task_id": task_id}
                else:
                    return JSONResponse({"success": False, "message": "Failed to schedule task"})
                
            except Exception as e:
                self.logger.error(f"Schedule API error: {e}")
                return JSONResponse(
                    {"success": False, "message": f"Scheduling failed: {e}"},
                    status_code=500
                )
        
        @self.app.post("/api/batch-schedule")
        async def batch_schedule(
            platform: str = Form(...),
            max_videos: int = Form(5)
        ):
            """API для планирования пакетной загрузки"""
            try:
                task_ids = self.uploader_app.schedule_batch_upload(platform, max_videos)
                
                if task_ids:
                    await self.websocket_manager.broadcast({
                        "type": "batch_scheduled",
                        "data": {
                            "task_ids": task_ids,
                            "platform": platform,
                            "count": len(task_ids)
                        }
                    })
                
                return {"success": True, "task_ids": task_ids, "count": len(task_ids)}
                
            except Exception as e:
                return JSONResponse(
                    {"success": False, "message": f"Batch scheduling failed: {e}"},
                    status_code=500
                )
        
        @self.app.delete("/api/tasks/{task_id}")
        async def cancel_task(task_id: str):
            """API для отмены задачи"""
            if not self.uploader_app.scheduler:
                return JSONResponse({"success": False, "message": "Scheduler not enabled"})
            
            success = self.uploader_app.scheduler.cancel_task(task_id)
            if success:
                await self.websocket_manager.broadcast({
                    "type": "task_cancelled",
                    "data": {"task_id": task_id}
                })
            
            return {"success": success}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint для real-time уведомлений"""
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    # Отправляем периодические обновления статуса
                    status = self.uploader_app.get_app_status()
                    await self.websocket_manager.send_message({
                        "type": "status_update",
                        "data": status
                    }, websocket)
                    
                    await asyncio.sleep(5)  # Обновляем каждые 5 секунд
                    
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
    
    async def _on_task_start(self, task):
        """Callback для начала задачи"""
        await self.websocket_manager.broadcast({
            "type": "task_started",
            "data": {
                "task_id": task.id,
                "platform": task.platform,
                "title": task.title[:50],
                "filename": task.video_path.name
            }
        })
    
    async def _on_task_complete(self, task, success: bool):
        """Callback для завершения задачи"""
        await self.websocket_manager.broadcast({
            "type": "task_completed",
            "data": {
                "task_id": task.id,
                "success": success,
                "platform": task.platform,
                "filename": task.video_path.name
            }
        })
    
    async def _on_task_fail(self, task):
        """Callback для неудачной задачи"""
        await self.websocket_manager.broadcast({
            "type": "task_failed",
            "data": {
                "task_id": task.id,
                "platform": task.platform,
                "filename": task.video_path.name,
                "error": task.last_error
            }
        })
    
    def run(self, host: str = "127.0.0.1", port: int = 8080, debug: bool = False):
        """Запускает веб-сервер"""
        self.logger.info(f"Starting web interface on http://{host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info" if not debug else "debug",
            reload=debug
        )