#!/usr/bin/env python3
"""
Скрипт для настройки и проверки прокси
"""

import os
import sys
import requests
import time
from dotenv import load_dotenv

def check_env_file():
    """Проверяет и создает .env файл если его нет"""
    if not os.path.exists(".env"):
        print("📝 Создание .env файла...")
        
        # Запрашиваем данные прокси у пользователя
        print("\n🔧 Настройка прокси:")
        proxy_host = input("Введите IP адрес прокси (например, 185.232.18.41): ").strip()
        proxy_port = input("Введите порт прокси (например, 63518): ").strip()
        proxy_user = input("Введите имя пользователя прокси: ").strip()
        proxy_pass = input("Введите пароль прокси: ").strip()
        proxy_type = input("Введите тип прокси (http/https/socks5) [по умолчанию: http]: ").strip() or "http"
        
        # Создаем .env файл
        env_content = f"""# Настройки прокси
PROXY={proxy_host}:{proxy_port}
PROXY_USER={proxy_user}
PROXY_PASS={proxy_pass}
PROXY_TYPE={proxy_type}

# Telegram настройки (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
"""
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
            
        print("✅ .env файл создан!")
        return True
    else:
        print("✅ .env файл найден")
        return True

def test_proxy_connection():
    """Тестирует подключение к прокси"""
    print("\n🔍 Тестирование прокси...")
    
    load_dotenv()
    
    proxy = os.getenv("PROXY")
    proxy_user = os.getenv("PROXY_USER")
    proxy_pass = os.getenv("PROXY_PASS")
    
    if not all([proxy, proxy_user, proxy_pass]):
        print("❌ Прокси не настроен в .env файле")
        return False
    
    # Определяем тип прокси
    proxy_type = os.getenv("PROXY_TYPE", "http")
    
    if proxy_type.lower() == "socks5":
        proxies = {
            "http": f"socks5://{proxy_user}:{proxy_pass}@{proxy}",
            "https": f"socks5://{proxy_user}:{proxy_pass}@{proxy}"
        }
    else:
        proxies = {
            "http": f"http://{proxy_user}:{proxy_pass}@{proxy}",
            "https": f"http://{proxy_user}:{proxy_pass}@{proxy}"
        }
    
    # Тестируем несколько сервисов
    services = [
        ("https://api.ipify.org", "IPify"),
        ("https://ipinfo.io/ip", "IPInfo"),
        ("https://icanhazip.com", "ICanHazIP")
    ]
    
    success_count = 0
    
    for url, name in services:
        try:
            print(f"🔗 Тестирование {name}...", end=" ")
            response = requests.get(url, proxies=proxies, timeout=10)
            ip = response.text.strip()
            print(f"✅ {ip}")
            success_count += 1
        except Exception as e:
            print(f"❌ {e}")
    
    if success_count > 0:
        print(f"\n🎉 Прокси работает! Успешных тестов: {success_count}/{len(services)}")
        return True
    else:
        print("\n❌ Прокси не работает")
        return False

def test_browser_proxy():
    """Тестирует прокси через браузер"""
    print("\n🌐 Тестирование прокси через браузер...")
    
    try:
        from proxy_manager import ProxyManager
        
        manager = ProxyManager()
        
        if not manager.is_configured():
            print("❌ Прокси не настроен")
            return False
        
        # Тестируем подключение
        success, message = manager.test_proxy_connection()
        print(f"🔗 {message}")
        
        if success:
            print("✅ Прокси работает через ProxyManager")
            return True
        else:
            print("❌ Прокси не работает через ProxyManager")
            return False
            
    except ImportError:
        print("❌ ProxyManager не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка тестирования браузера: {e}")
        return False

def show_current_ip():
    """Показывает текущий IP без прокси"""
    print("\n🌍 Проверка текущего IP (без прокси)...")
    
    try:
        response = requests.get("https://api.ipify.org", timeout=10)
        current_ip = response.text.strip()
        print(f"📍 Ваш текущий IP: {current_ip}")
        return current_ip
    except Exception as e:
        print(f"❌ Не удалось получить текущий IP: {e}")
        return None

def main():
    """Основная функция"""
    print("🚀 Настройка и проверка прокси\n")
    
    # Проверяем .env файл
    if not check_env_file():
        return
    
    # Показываем текущий IP
    current_ip = show_current_ip()
    
    # Тестируем прокси
    proxy_works = test_proxy_connection()
    
    # Тестируем через браузер
    browser_works = test_browser_proxy()
    
    print("\n📊 Результаты:")
    print(f"Текущий IP: {current_ip}")
    print(f"Прокси (requests): {'✅' if proxy_works else '❌'}")
    print(f"Прокси (browser): {'✅' if browser_works else '❌'}")
    
    if proxy_works and browser_works:
        print("\n🎉 Прокси настроен и работает корректно!")
        print("💡 Теперь можно запускать final_upload.py")
    elif proxy_works:
        print("\n⚠️ Прокси работает частично")
        print("💡 Проверьте настройки браузера")
    else:
        print("\n❌ Прокси не работает")
        print("💡 Проверьте настройки в .env файле")

if __name__ == "__main__":
    main() 