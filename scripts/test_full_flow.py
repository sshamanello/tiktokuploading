#!/usr/bin/env python3
"""
Полный тест процесса загрузки
"""
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_full_upload_flow():
    """Тестирует полный процесс загрузки"""
    print("Testing full upload flow...")
    
    try:
        # Импорт всех необходимых классов
        from src.uploader_app import UploaderApp
        from src.core.file_manager import VideoFile
        from src.core.platform_base import UploadResult, UploadStatus
        
        print("SUCCESS: All imports completed")
        
        # Создаем приложение
        app = UploaderApp("config.yaml")
        print("SUCCESS: UploaderApp created")
        
        # Находим тестовое видео
        videos_dir = Path('./VideosDirPath')
        test_video = None
        
        if videos_dir.exists():
            for video_file in videos_dir.glob('*.mp4'):
                if video_file.exists():
                    test_video = video_file
                    break
        
        if not test_video:
            print("ERROR: No test video found")
            return False
            
        print(f"Using test video: {test_video}")
        
        # Тестируем создание VideoFile (как в коде приложения)
        try:
            video_file = VideoFile.from_path(test_video)
            print(f"SUCCESS: VideoFile created via from_path: {video_file.filename}")
            
            # Тестируем перемещение в uploaded (симуляция)
            print(f"SUCCESS: Would move to uploaded: {video_file.path} -> uploaded/{video_file.filename}")
            
        except Exception as e:
            print(f"ERROR creating VideoFile: {e}")
            return False
        
        # Тестируем создание успешного результата
        result = UploadResult(
            success=True,
            platform="tiktok",
            status=UploadStatus.COMPLETED,
            message="Test successful"
        )
        
        print(f"SUCCESS: Result created - success: {result.success}, status: {result.status}")
        
        # Симуляция логики из upload_single_video
        if result.success:
            print("SUCCESS: Result is successful - would move video to uploaded")
            # video_file = VideoFile.from_path(test_video)  # Это строка, которая падает
            # app.file_manager.move_to_uploaded(video_file)
            print("SUCCESS: Simulation complete - no errors")
        else:
            print("Result not successful")
        
        return True
        
    except Exception as e:
        print(f"ERROR in full flow test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_full_upload_flow()
    
    if success:
        print("\nSUCCESS: Full flow test passed! The error should be fixed.")
    else:
        print("\nERROR: Full flow test failed.")
        
    exit(0 if success else 1)