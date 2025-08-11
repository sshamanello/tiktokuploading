import os
import requests
import time
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Загружаем переменные окружения
load_dotenv()

def test_proxy_requests():
    """Тестирует прокси через requests"""
    print("🔍 Тестирование прокси через requests...")
    
    proxy = os.getenv("PROXY")
    proxy_user = os.getenv("PROXY_USER")
    proxy_pass = os.getenv("PROXY_PASS")
    
    if not all([proxy, proxy_user, proxy_pass]):
        print("❌ Прокси не настроен в .env файле")
        return False
    
    proxies = {
        "http": f"http://{proxy_user}:{proxy_pass}@{proxy}",
        "https": f"http://{proxy_user}:{proxy_pass}@{proxy}"
    }
    
    try:
        # Тестируем несколько сервисов
        services = [
            "https://api.ipify.org",
            "https://ipinfo.io/ip",
            "https://icanhazip.com"
        ]
        
        for service in services:
            try:
                response = requests.get(service, proxies=proxies, timeout=10)
                ip = response.text.strip()
                print(f"✅ {service}: {ip}")
            except Exception as e:
                print(f"❌ {service}: {e}")
                
        return True
    except Exception as e:
        print(f"❌ Ошибка тестирования прокси: {e}")
        return False

def test_proxy_browser():
    """Тестирует прокси через браузер"""
    print("\n🌐 Тестирование прокси через браузер...")
    
    try:
        from proxy_manager import ProxyManager
        
        manager = ProxyManager()
        
        if not manager.is_configured():
            print("❌ Прокси не настроен в .env файле")
            return False
        
        # Получаем Chrome options с прокси
        options = manager.get_enhanced_chrome_options()
        options.add_argument("--headless")  # Запуск в фоновом режиме
        
        driver = uc.Chrome(options=options)
        
        # Скрываем автоматизацию
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Тестируем IP
        services = [
            "https://api.ipify.org",
            "https://ipinfo.io/ip",
            "https://icanhazip.com"
        ]
        
        for service in services:
            try:
                driver.get(service)
                time.sleep(3)
                ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                print(f"✅ {service}: {ip}")
            except Exception as e:
                print(f"❌ {service}: {e}")
        
        driver.quit()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования браузера: {e}")
        return False

def check_env_file():
    """Проверяет наличие .env файла и его содержимое"""
    print("📋 Проверка .env файла...")
    
    if not os.path.exists(".env"):
        print("❌ Файл .env не найден")
        print("📝 Создайте файл .env со следующими переменными:")
        print("PROXY=host:port")
        print("PROXY_USER=username")
        print("PROXY_PASS=password")
        print("PROXY_TYPE=http (или socks5)")
        return False
    
    required_vars = ["PROXY", "PROXY_USER", "PROXY_PASS"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env файл настроен корректно")
    return True

if __name__ == "__main__":
    print("🚀 Тестирование прокси...\n")
    
    if not check_env_file():
        exit(1)
    
    # Тестируем прокси через requests
    requests_ok = test_proxy_requests()
    
    # Тестируем прокси через браузер
    browser_ok = test_proxy_browser()
    
    print("\n📊 Результаты тестирования:")
    print(f"Requests: {'✅' if requests_ok else '❌'}")
    print(f"Browser: {'✅' if browser_ok else '❌'}")
    
    if requests_ok and browser_ok:
        print("\n🎉 Прокси работает корректно!")
    else:
        print("\n⚠️ Прокси работает частично или не работает")
        print("💡 Проверьте настройки прокси в .env файле") 