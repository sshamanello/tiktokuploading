#!/usr/bin/env python3
"""
Video Uploader Application v2.0
Improved architecture with scheduler, GUI and multi-platform support
"""

import asyncio
import sys
import argparse
from pathlib import Path
import signal
import logging

# Добавляем src в path для импортов
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Проверяем версию Python
if sys.version_info < (3, 8):
    print("ERROR: Python 3.8 or higher required")
    sys.exit(1)

try:
    from src.uploader_app import UploaderApp
    from src.gui.web_interface import WebInterface
    from src.core.config_manager import ConfigManager
except ImportError as e:
    print(f"ERROR: Import error: {e}")
    print("TIP: Try running: python setup_v2.py")
    print("TIP: Or install dependencies: pip install -r requirements_minimal.txt")
    sys.exit(1)

def setup_cli():
    """Настройка аргументов командной строки"""
    parser = argparse.ArgumentParser(description="Video Uploader v2.0")
    parser.add_argument("--config", "-c", help="Path to config file", default="config.yaml")
    parser.add_argument("--gui", "-g", action="store_true", help="Start with GUI (default)")
    parser.add_argument("--no-gui", action="store_true", help="Start without GUI")
    parser.add_argument("--upload", "-u", help="Upload single video immediately", metavar="VIDEO_PATH")
    parser.add_argument("--platform", "-p", help="Platform to upload to", default="tiktok")
    parser.add_argument("--title", "-t", help="Video title")
    parser.add_argument("--batch", "-b", action="store_true", help="Schedule batch upload")
    parser.add_argument("--max-videos", type=int, default=5, help="Max videos for batch upload")
    parser.add_argument("--host", default="127.0.0.1", help="GUI host")
    parser.add_argument("--port", type=int, default=8080, help="GUI port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    return parser.parse_args()

async def run_single_upload(app: UploaderApp, video_path: str, platform: str, title: str = None):
    """Выполняет разовую загрузку видео"""
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"ERROR: Video file not found: {video_path}")
        return False
    
    print(f"Starting upload: {video_file.name} to {platform}")
    
    result = app.upload_single_video(
        platform_name=platform,
        video_path=video_file,
        title=title
    )
    
    if result.success:
        print(f"SUCCESS: Upload successful: {result.message}")
        if result.url:
            print(f"URL: {result.url}")
        return True
    else:
        print(f"ERROR: Upload failed: {result.message}")
        return False

async def run_batch_upload(app: UploaderApp, platform: str, max_videos: int):
    """Планирует пакетную загрузку"""
    print(f"Scheduling batch upload: {max_videos} videos to {platform}")
    
    task_ids = app.schedule_batch_upload(platform, max_videos)
    
    if task_ids:
        print(f"SUCCESS: Scheduled {len(task_ids)} tasks:")
        for task_id in task_ids:
            print(f"   - {task_id}")
        
        print("\nWaiting for tasks to complete...")
        print("Press Ctrl+C to stop monitoring\n")
        
        try:
            # Мониторим выполнение задач
            while True:
                if not app.scheduler:
                    break
                
                stats = app.scheduler.get_queue_stats()
                print(f"\rSTATUS: Running: {stats['running']}, Pending: {stats['pending']}, "
                      f"Completed: {stats['completed']}, Failed: {stats['failed']}", end="", flush=True)
                
                if stats['running'] == 0 and stats['pending'] == 0:
                    print(f"\nSUCCESS: All tasks completed!")
                    break
                
                await asyncio.sleep(2)
                
        except KeyboardInterrupt:
            print(f"\n\nMonitoring stopped. Tasks will continue in background.")
            
    else:
        print("ERROR: No tasks were scheduled")

async def run_gui_mode(app: UploaderApp, host: str, port: int, debug: bool):
    """Запускает приложение в GUI режиме"""
    print(f"Starting web interface at http://{host}:{port}")
    
    web_interface = WebInterface(app)
    
    # Запускаем веб-сервер в отдельной задаче
    server_task = asyncio.create_task(
        asyncio.to_thread(web_interface.run, host, port, debug)
    )
    
    try:
        print("SUCCESS: Web interface started successfully!")
        print(f"Open http://{host}:{port} in your browser")
        print("Press Ctrl+C to stop the server\n")
        
        await server_task
        
    except KeyboardInterrupt:
        print("\nShutting down web interface...")
        server_task.cancel()
    except Exception as e:
        print(f"ERROR: Web interface error: {e}")

async def main():
    """Основная функция приложения"""
    args = setup_cli()
    
    # Настройка логирования для CLI
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    print("Video Uploader v2.0")
    print("=" * 50)
    
    try:
        # Создаем и запускаем приложение
        app = UploaderApp(args.config)
        await app.start()
        
        # Показываем статус приложения
        status = app.get_app_status()
        print(f"Videos directory: {status['config']['videos_dir']}")
        print(f"Uploaded directory: {status['config']['uploaded_dir']}")  
        print(f"Available platforms: {', '.join(status['platforms'])}")
        print(f"Pending videos: {status['file_stats']['videos_count']}")
        
        if status['config']['scheduler_enabled']:
            scheduler_stats = status.get('scheduler', {})
            print(f"Scheduler: {scheduler_stats.get('total_tasks', 0)} total tasks")
        
        print()
        
        # Выбираем режим работы
        if args.upload:
            # Режим разовой загрузки
            success = await run_single_upload(
                app, args.upload, args.platform, args.title
            )
            return 0 if success else 1
            
        elif args.batch:
            # Режим пакетной загрузки
            await run_batch_upload(app, args.platform, args.max_videos)
            return 0
            
        elif args.no_gui:
            # Режим без GUI - просто держим приложение запущенным
            print("Running in background mode...")
            print("Press Ctrl+C to stop\n")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping background service...")
                
        else:
            # GUI режим (по умолчанию)
            await run_gui_mode(app, args.host, args.port, args.debug)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"ERROR: Application error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Остановка приложения
        if 'app' in locals():
            await app.stop()
    
    return 0

def cli():
    """Entry point для CLI"""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

if __name__ == "__main__":
    cli()