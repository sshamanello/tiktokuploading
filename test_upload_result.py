#!/usr/bin/env python3
"""
Тест результата загрузки видео
"""
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.uploader_app import UploaderApp
from src.core.platform_base import VideoMetadata

def test_upload_result():
    """Тестирует результат загрузки видео"""
    print("Testing upload result handling...")
    
    try:
        app = UploaderApp("config.yaml")
        
        print(f"Available platforms: {list(app.platforms.keys())}")
        
        if 'tiktok' not in app.platforms:
            print("ERROR: TikTok platform not available")
            return False
        
        # Найдем первое видео для тестирования
        videos = app.file_manager.get_pending_videos()
        if not videos:
            print("ERROR: No pending videos found")
            return False
        
        test_video = videos[0]
        print(f"Test video: {test_video.path}")
        print(f"Video exists: {test_video.path.exists()}")
        
        # Имитируем успешный результат
        from src.core.platform_base import UploadResult, UploadStatus
        
        # Тест 1: Успешный результат
        success_result = UploadResult(
            success=True,
            platform="tiktok",
            status=UploadStatus.COMPLETED,
            message="Test upload successful"
        )
        
        print(f"Success result: {success_result.success}")
        print(f"Success status: {success_result.status}")
        
        # Тест 2: Неуспешный результат  
        fail_result = UploadResult(
            success=False,
            platform="tiktok", 
            status=UploadStatus.FAILED,
            message="Test upload failed"
        )
        
        print(f"Fail result: {fail_result.success}")
        print(f"Fail status: {fail_result.status}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_upload_result()
    exit(0 if success else 1)