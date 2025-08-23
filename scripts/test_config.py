#!/usr/bin/env python3
"""
Тест конфигурации платформы TikTok
"""
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.uploader_app import UploaderApp

def test_platforms():
    """Тестирует инициализацию платформ"""
    print("Testing platform configuration...")
    
    try:
        app = UploaderApp("config.yaml")
        
        print(f"Configuration loaded:")
        print(f"   - TikTok enabled: {app.config.tiktok.enabled}")
        print(f"   - TikTok cookies: {app.config.tiktok.cookies_path}")
        print(f"   - Cookies file exists: {Path(app.config.tiktok.cookies_path).exists()}")
        
        print(f"Available platforms: {list(app.platforms.keys())}")
        
        if 'tiktok' in app.platforms:
            print("SUCCESS: TikTok platform initialized")
            
            # Проверяем метаданные платформы
            platform = app.platforms['tiktok']
            print(f"   - Platform name: {platform.platform_name}")
            print(f"   - Upload limits: {platform.get_upload_limits()}")
        else:
            print("ERROR: TikTok platform NOT initialized")
            
        return len(app.platforms) > 0
        
    except Exception as e:
        print(f"ERROR during initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_platforms()
    exit(0 if success else 1)