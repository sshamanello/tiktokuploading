import os, time, shutil, pickle, logging, requests, zipfile
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

# === INIT ===
load_dotenv()
logging.basicConfig(filename="upload.log", level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()

def log(msg): print(msg); logger.info(msg)

# === ПУТИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_FOLDER = os.path.join(BASE_DIR, "VideosDirPath")
UPLOADED_FOLDER = os.path.join(BASE_DIR, "uploaded")
TITLES_FILE = os.path.join(BASE_DIR, "titles.txt")
COOKIES_FILE = os.path.join(BASE_DIR, "CookiesDir", "tiktok_session-toptrailer82.cookie")
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
os.makedirs(UPLOADED_FOLDER, exist_ok=True)

# === TELEGRAM ===
def send_telegram_message(text: str):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("❌ TELEGRAM токен или chat_id не указаны.")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        log(f"❌ Telegram ошибка: {e}")

# === ДРАЙВЕР С ПРОКСИ ===
def get_driver():
    proxy = os.getenv("PROXY")
    proxy_user = os.getenv("PROXY_USER")
    proxy_pass = os.getenv("PROXY_PASS")
    proxy_type = os.getenv("PROXY_TYPE", "http")

    options = uc.ChromeOptions()
    
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
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Скрытие автоматизации
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Установка User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    if proxy and proxy_user and proxy_pass:
        # Создание расширения для прокси с авторизацией
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth Extension",
            "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
            "background": {"scripts": ["background.js"]},
            "minimum_chrome_version":"22.0.0"
        }
        """
        
        # Улучшенный background.js для прокси
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "{proxy_type}",
                    host: "{proxy.split(':')[0]}",
                    port: parseInt({proxy.split(':')[1]})
                }},
                bypassList: ["localhost", "127.0.0.1", "::1"]
            }}
        }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{
            console.log('Proxy settings applied');
        }});
        
        chrome.webRequest.onAuthRequired.addListener(
            function(details) {{
                return {{
                    authCredentials: {{
                        username: "{proxy_user}",
                        password: "{proxy_pass}"
                    }}
                }};
            }},
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        
        // Дополнительная обработка ошибок прокси
        chrome.webRequest.onErrorOccurred.addListener(
            function(details) {{
                console.log('Proxy error:', details);
            }},
            {{urls: ["<all_urls>"]}}
        );
        """
        
        ext_path = os.path.join(BASE_DIR, "proxy_auth_extension.zip")
        ext_dir = os.path.join(BASE_DIR, "proxy_auth_temp")
        os.makedirs(ext_dir, exist_ok=True)
        
        with open(os.path.join(ext_dir, "manifest.json"), "w") as f: 
            f.write(manifest_json)
        with open(os.path.join(ext_dir, "background.js"), "w") as f: 
            f.write(background_js)
            
        with zipfile.ZipFile(ext_path, 'w') as zipf:
            zipf.write(os.path.join(ext_dir, "manifest.json"), "manifest.json")
            zipf.write(os.path.join(ext_dir, "background.js"), "background.js")
            
        options.add_extension(ext_path)
        log(f"🧩 Подключено прокси-расширение: {proxy_type}://{proxy}")
        
    elif proxy:
        # Прокси без авторизации
        options.add_argument(f"--proxy-server={proxy_type}://{proxy}")
        log(f"🧩 Прокси без авторизации: {proxy_type}://{proxy}")
    else:
        log("⚠️ Прокси не настроен")

    try:
        driver = uc.Chrome(options=options)
        
        # Дополнительные скрипты для скрытия автоматизации
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        return driver
    except Exception as e:
        log(f"❌ Ошибка создания драйвера: {e}")
        raise

# === ПРОВЕРКА IP ===
def check_ip(driver):
    """Проверяет IP адрес через браузер"""
    try:
        # Проверяем IP через несколько сервисов
        ip_services = [
            "https://api.ipify.org",
            "https://ipinfo.io/ip",
            "https://icanhazip.com"
        ]
        
        for service in ip_services:
            try:
                driver.get(service)
                time.sleep(3)
                ip = driver.find_element(By.TAG_NAME, "body").text.strip()
                log(f"🌍 IP через {service}: {ip}")
                return ip
            except Exception as e:
                log(f"⚠️ Не удалось проверить IP через {service}: {e}")
                continue
        
        return None
    except Exception as e:
        log(f"❌ Ошибка проверки IP: {e}")
        return None

# === КУКИ ===
def load_cookies(driver, path):
    driver.get("https://www.tiktok.com/")
    with open(path, "rb") as f:
        cookies = pickle.load(f)
    for cookie in cookies:
        try: driver.add_cookie(cookie)
        except: continue
    driver.refresh()

def remove_cookie_banner(driver):
    try:
        driver.execute_script("""const b=document.querySelector('.tiktok-cookie-banner');if(b)b.remove();""")
        log("🧹 Баннер cookie удалён.")
    except Exception as e:
        log(f"⚠️ Баннер не удалён: {e}")

def get_video_and_title():
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".mov"))]
    if not videos: raise Exception("❌ Нет видео.")
    with open(TITLES_FILE, "r", encoding="utf-8") as f: titles = f.readlines()
    if not titles: raise Exception("❌ titles.txt пуст.")
    title = titles[0].strip()
    with open(TITLES_FILE, "w", encoding="utf-8") as f: f.writelines(titles[1:])
    return videos[0], title

def move_uploaded(filename):
    shutil.move(os.path.join(VIDEO_FOLDER, filename), os.path.join(UPLOADED_FOLDER, filename))

def upload_video():
    video_file, title = get_video_and_title()
    log(f"🎞 Загрузка: {video_file} | Заголовок: {title}")
    driver = get_driver()
    wait = WebDriverWait(driver, 60)

    try:
        load_cookies(driver, COOKIES_FILE)
        log("🍪 Куки загружены.")

        check_ip(driver) # Проверяем IP

        driver.get(TIKTOK_UPLOAD_URL)
        remove_cookie_banner(driver)

        upload_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="file"]')))
        upload_input.send_keys(os.path.abspath(os.path.join(VIDEO_FOLDER, video_file)))
        log("📤 Видео выбрано.")

        wait.until(EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Загружено")]')))
        log("📥 Видео загружено.")

        caption = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]')))
        ActionChains(driver).move_to_element(caption).click().perform()
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)\
            .send_keys(Keys.BACKSPACE).send_keys(title).perform()
        log("📝 Заголовок вставлен.")

        publish = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@data-e2e="post_video_button"]')))
        time.sleep(1); publish.click(); log("✅ Кнопка 'Опубликовать' нажата."); time.sleep(8)

        move_uploaded(video_file)
        log("📁 Перемещено в uploaded.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        send_telegram_message(f"✅ Загружено: {video_file}\n📌 Заголовок: {title}\n🕒 Время публикации: {now}")
    except Exception as e:
        log(f"🚨 Ошибка: {e}")
        send_telegram_message(f"🚨 Ошибка загрузки: {e}")
    finally:
        try:
            driver.quit()
        except Exception as e:
            log(f"⚠️ Ошибка закрытия драйвера: {e}")
        log("❎ Браузер закрыт.")

if __name__ == "__main__":
    upload_video()
