import os
import zipfile
import tempfile
import requests
import time
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options

load_dotenv()

class ProxyManager:
    """Класс для управления прокси-соединениями"""
    
    def __init__(self):
        self.proxy = os.getenv("PROXY")
        self.proxy_user = os.getenv("PROXY_USER")
        self.proxy_pass = os.getenv("PROXY_PASS")
        self.proxy_type = os.getenv("PROXY_TYPE", "http")
        
    def is_configured(self):
        """Проверяет, настроен ли прокси"""
        return all([self.proxy, self.proxy_user, self.proxy_pass])
    
    def get_proxy_dict(self):
        """Возвращает словарь прокси для requests"""
        if not self.is_configured():
            return None
            
        if self.proxy_type.lower() == "socks5":
            # Для SOCKS5 прокси используем специальный формат
            return {
                "http": f"socks5://{self.proxy_user}:{self.proxy_pass}@{self.proxy}",
                "https": f"socks5://{self.proxy_user}:{self.proxy_pass}@{self.proxy}"
            }
        else:
            # Для HTTP/HTTPS прокси
            return {
                "http": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy}",
                "https": f"http://{self.proxy_user}:{self.proxy_pass}@{self.proxy}"
            }
    
    def test_proxy_connection(self):
        """Тестирует подключение к прокси"""
        if not self.is_configured():
            return False, "Прокси не настроен"
            
        proxies = self.get_proxy_dict()
        
        try:
            # Увеличиваем timeout для SOCKS5 прокси
            timeout = 15 if self.proxy_type.lower() == "socks5" else 10
            response = requests.get("https://api.ipify.org", proxies=proxies, timeout=timeout)
            ip = response.text.strip()
            return True, f"Прокси работает, IP: {ip}"
        except Exception as e:
            return False, f"Ошибка подключения: {e}"
    
    def create_proxy_extension(self, temp_dir=None):
        """Создает расширение Chrome для прокси"""
        if not self.is_configured():
            return None
            
        if not temp_dir:
            temp_dir = tempfile.mkdtemp()
            
        host, port = self.proxy.split(":")
        
        manifest_json = {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth Extension",
            "permissions": [
                "proxy", "tabs", "unlimitedStorage", "storage", 
                "<all_urls>", "webRequest", "webRequestBlocking"
            ],
            "background": {"scripts": ["background.js"]},
            "minimum_chrome_version": "22.0.0"
        }
        
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "{self.proxy_type}",
                    host: "{host}",
                    port: parseInt({port})
                }},
                bypassList: ["localhost", "127.0.0.1", "::1"]
            }}
        }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{
            console.log('Proxy settings applied successfully');
        }});
        
        chrome.webRequest.onAuthRequired.addListener(
            function(details) {{
                return {{
                    authCredentials: {{
                        username: "{self.proxy_user}",
                        password: "{self.proxy_pass}"
                    }}
                }};
            }},
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        
        // Логирование ошибок прокси
        chrome.webRequest.onErrorOccurred.addListener(
            function(details) {{
                console.log('Proxy error:', details);
            }},
            {{urls: ["<all_urls>"]}}
        );
        
        // Логирование успешных запросов
        chrome.webRequest.onCompleted.addListener(
            function(details) {{
                console.log('Request completed:', details.url);
            }},
            {{urls: ["<all_urls>"]}}
        );
        """
        
        # Создаем файлы расширения
        manifest_path = os.path.join(temp_dir, "manifest.json")
        background_path = os.path.join(temp_dir, "background.js")
        
        with open(manifest_path, "w") as f:
            import json
            json.dump(manifest_json, f, indent=2)
            
        with open(background_path, "w") as f:
            f.write(background_js)
        
        # Создаем ZIP архив
        extension_path = os.path.join(temp_dir, "proxy_extension.zip")
        with zipfile.ZipFile(extension_path, 'w') as zipf:
            zipf.write(manifest_path, "manifest.json")
            zipf.write(background_path, "background.js")
            
        return extension_path
    
    def add_proxy_to_options(self, options):
        """Добавляет настройки прокси к Chrome options"""
        if not self.is_configured():
            return options
            
        # Создаем расширение для прокси
        extension_path = self.create_proxy_extension()
        if extension_path:
            options.add_extension(extension_path)
            
        return options
    
    def get_enhanced_chrome_options(self):
        """Возвращает улучшенные Chrome options с прокси"""
        options = Options()
        
        # Основные настройки для обхода детекции
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-features=TranslateUI")
        
        # Скрытие автоматизации (убираем для совместимости с undetected_chromedriver)
        # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option('useAutomationExtension', False)
        
        # Установка User-Agent
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Добавляем прокси если настроен
        if self.is_configured():
            self.add_proxy_to_options(options)
            
        return options

def test_proxy_manager():
    """Тестирует ProxyManager"""
    print("🧪 Тестирование ProxyManager...")
    
    manager = ProxyManager()
    
    if not manager.is_configured():
        print("❌ Прокси не настроен")
        print("📝 Создайте .env файл с переменными:")
        print("PROXY=host:port")
        print("PROXY_USER=username")
        print("PROXY_PASS=password")
        print("PROXY_TYPE=http (или socks5)")
        return
    
    print("✅ Прокси настроен")
    print(f"🔧 Тип прокси: {manager.proxy_type}")
    
    # Тестируем подключение
    success, message = manager.test_proxy_connection()
    print(f"🔗 Подключение: {message}")
    
    # Тестируем создание расширения
    try:
        extension_path = manager.create_proxy_extension()
        print(f"📦 Расширение создано: {extension_path}")
    except Exception as e:
        print(f"❌ Ошибка создания расширения: {e}")
    
    # Тестируем Chrome options
    try:
        options = manager.get_enhanced_chrome_options()
        print("✅ Chrome options созданы успешно")
    except Exception as e:
        print(f"❌ Ошибка создания Chrome options: {e}")

if __name__ == "__main__":
    test_proxy_manager() 