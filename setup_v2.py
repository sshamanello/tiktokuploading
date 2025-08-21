#!/usr/bin/env python3
"""
Скрипт настройки Video Uploader v2.0
"""

import os
import sys
from pathlib import Path
import subprocess
import platform

def print_header():
    """Печатает заголовок"""
    print("=" * 60)
    print("🎬 Video Uploader v2.0 - Setup Script")
    print("=" * 60)
    print()

def check_python_version():
    """Проверяет версию Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"   Текущая версия: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python версия: {version.major}.{version.minor}.{version.micro}")
    return True

def install_dependencies():
    """Устанавливает зависимости"""
    print("\n📦 Установка зависимостей...")
    
    try:
        # Обновляем pip
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        
        # Устанавливаем основные зависимости
        requirements_file = Path("requirements_new.txt")
        if requirements_file.exists():
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_new.txt"], 
                          check=True)
            print("✅ Зависимости установлены успешно")
        else:
            print("❌ Файл requirements_new.txt не найден")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False
    
    return True

def create_directories():
    """Создает необходимые директории"""
    print("\n📁 Создание директорий...")
    
    directories = [
        "VideosDirPath",
        "uploaded", 
        "CookiesDir",
        "logs",
        "src/gui/static",
        "src/gui/templates"
    ]
    
    for dir_path in directories:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ {dir_path}")
    
    return True

def create_sample_files():
    """Создает образцы файлов"""
    print("\n📄 Создание образцов файлов...")
    
    # Создаем .env образец
    env_sample = Path(".env.example")
    if not env_sample.exists():
        env_content = """# Video Uploader Environment Variables
# =====================================

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# TikTok настройки
TIKTOK_ENABLED=true
TIKTOK_COOKIES_PATH=./CookiesDir/tiktok_session.cookie

# Прокси настройки (опционально)
PROXY=host:port
PROXY_USER=username
PROXY_PASS=password
PROXY_TYPE=http

# Другие настройки
LOG_LEVEL=INFO
MAX_CONCURRENT_UPLOADS=2
"""
        env_sample.write_text(env_content, encoding='utf-8')
        print("✅ .env.example создан")
    
    # Создаем образец titles.txt
    titles_file = Path("titles.txt")
    if not titles_file.exists():
        titles_content = """Мое первое видео в TikTok
Крутой контент каждый день
Подписывайтесь на канал!
Новое видео уже готово
Смешные моменты дня
"""
        titles_file.write_text(titles_content, encoding='utf-8')
        print("✅ titles.txt создан с примерами")
    
    # Создаем пустой cookie файл
    cookie_file = Path("CookiesDir/empty.cookie")
    if not cookie_file.exists():
        cookie_file.write_text("# Поместите сюда ваши TikTok cookies\n", encoding='utf-8')
        print("✅ Образец cookie файла создан")
    
    return True

def check_system_requirements():
    """Проверяет системные требования"""
    print("\n🔍 Проверка системных требований...")
    
    # Проверяем операционную систему
    os_name = platform.system()
    print(f"✅ Операционная система: {os_name}")
    
    # Проверяем Chrome/Chromium
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # Windows
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",  # Windows 32-bit
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "/usr/bin/google-chrome",  # Linux
        "/usr/bin/chromium-browser",  # Linux
    ]
    
    chrome_found = False
    for chrome_path in chrome_paths:
        if Path(chrome_path).exists():
            print(f"✅ Chrome найден: {chrome_path}")
            chrome_found = True
            break
    
    if not chrome_found:
        print("⚠️  Chrome не найден в стандартных местах")
        print("   Убедитесь что Google Chrome установлен")
    
    return True

def test_basic_functionality():
    """Тестирует базовый функционал"""
    print("\n🧪 Тестирование базового функционала...")
    
    try:
        # Тест импорта основных модулей
        sys.path.insert(0, "src")
        
        from src.core.config_manager import ConfigManager
        config_manager = ConfigManager()
        print("✅ ConfigManager импортирован")
        
        from src.core.logger import LoggerManager
        logger_manager = LoggerManager()
        print("✅ LoggerManager импортирован")
        
        # Тест создания конфигурации
        if Path("config.yaml").exists():
            config = config_manager.load_config()
            print("✅ Конфигурация загружена")
        else:
            print("⚠️  config.yaml не найден, будет использована конфигурация по умолчанию")
        
        print("✅ Базовое тестирование прошло успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False

def print_next_steps():
    """Печатает следующие шаги"""
    print("\n🚀 Установка завершена! Следующие шаги:")
    print()
    print("1. 📝 Настройте конфигурацию:")
    print("   - Отредактируйте config.yaml")
    print("   - При необходимости создайте .env файл")
    print()
    print("2. 🍪 Настройте TikTok cookies:")
    print("   - Войдите в TikTok через браузер") 
    print("   - Экспортируйте cookies в CookiesDir/")
    print()
    print("3. 📱 Настройте Telegram (опционально):")
    print("   - Создайте бота через @BotFather")
    print("   - Добавьте токен и chat_id в конфигурацию")
    print()
    print("4. ▶️  Запустите приложение:")
    print("   python main.py                    # Веб-интерфейс")
    print("   python main.py --upload video.mp4 # Разовая загрузка") 
    print("   python main.py --batch            # Пакетная загрузка")
    print()
    print("5. 🌐 Откройте веб-интерфейс:")
    print("   http://127.0.0.1:8080")
    print()
    print("📚 Подробная документация: README_v2.md")
    print()

def main():
    """Основная функция"""
    print_header()
    
    # Проверяем версию Python
    if not check_python_version():
        sys.exit(1)
    
    # Проверяем системные требования
    check_system_requirements()
    
    # Устанавливаем зависимости
    if not install_dependencies():
        print("\n❌ Не удалось установить зависимости")
        sys.exit(1)
    
    # Создаем директории
    create_directories()
    
    # Создаем образцы файлов
    create_sample_files()
    
    # Тестируем функционал
    if not test_basic_functionality():
        print("\n⚠️  Есть проблемы с функционалом, но установка завершена")
    
    # Показываем следующие шаги
    print_next_steps()
    
    print("✨ Готово! Наслаждайтесь Video Uploader v2.0!")

if __name__ == "__main__":
    main()