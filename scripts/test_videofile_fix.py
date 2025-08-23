#!/usr/bin/env python3
"""
Тест исправления VideoFile
"""
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_videofile_creation():
    """Тестирует создание VideoFile"""
    print("Testing VideoFile creation...")
    
    try:
        from src.core.file_manager import VideoFile
        print("SUCCESS: VideoFile imported successfully")
        
        # Найдем тестовый файл
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
        
        # Тестируем создание VideoFile
        video_file = VideoFile.from_path(test_video)
        print(f"SUCCESS: VideoFile created: {video_file.filename}")
        print(f"SUCCESS: Size: {video_file.size} bytes")
        print(f"SUCCESS: Path: {video_file.path}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_import_in_app():
    """Тестирует импорт в приложении"""
    print("\nTesting import in UploaderApp...")
    
    try:
        from src.uploader_app import UploaderApp, VideoFile
        print("SUCCESS: Both UploaderApp and VideoFile imported successfully")
        
        # Проверяем, что VideoFile доступен
        print(f"SUCCESS: VideoFile class: {VideoFile}")
        print(f"SUCCESS: VideoFile.from_path method: {VideoFile.from_path}")
        
        return True
        
    except Exception as e:
        print(f"ERROR importing in app: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_videofile_creation()
    success2 = test_import_in_app()
    
    if success1 and success2:
        print("\nSUCCESS: All tests passed! VideoFile should work correctly.")
    else:
        print("\nERROR: Some tests failed.")
        
    exit(0 if (success1 and success2) else 1)