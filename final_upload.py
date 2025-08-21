import os, time, shutil, pickle, logging, requests, zipfile
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import undetected_chromedriver as uc
from proxy_manager import ProxyManager
import time


# === INIT ===
load_dotenv()
logging.basicConfig(filename="upload.log", level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S", encoding='utf-8')
logger = logging.getLogger()

def log(msg): 
    try:
        print(msg)
        logger.info(msg)
    except UnicodeEncodeError:
        # Если не удается вывести эмодзи, заменяем их на текст
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(safe_msg)
        logger.info(safe_msg)

# === ПУТИ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_FOLDER = os.path.join(BASE_DIR, "VideosDirPath")
UPLOADED_FOLDER = os.path.join(BASE_DIR, "uploaded")
TITLES_FILE = os.path.join(BASE_DIR, "titles.txt")
COOKIES_FILE = os.path.join(BASE_DIR, "CookiesDir", "tiktok_session-toptrailer82.cookie")
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
os.makedirs(UPLOADED_FOLDER, exist_ok=True)

# === TELEGRAM ===
# Используем функцию из telegram_notify.py
from telegram_notify import send_telegram_message

# === ДРАЙВЕР С ПРОКСИ ===
def get_driver():
    # Инициализируем ProxyManager
    proxy_manager = ProxyManager()

    # Проверяем и тестируем прокси
    if proxy_manager.is_configured():
        success, message = proxy_manager.test_proxy_connection()
        if not success:
            log("⚠️ Прокси не работает, продолжаем без прокси")
    else:
        log("ℹ️ Прокси не настроен, продолжаем без него")

    # Получаем ChromeOptions (с прокси, если есть)
    options = proxy_manager.get_enhanced_chrome_options()

    try:
    # Важно: указываем актуальную версию Chrome
        # options.binary_location = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" # Example: set a default binary location
        driver = uc.Chrome(version_main=138, options=options)

        # Убираем следы автоматизации
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: (params) => Promise.resolve({ state: 'granted' })
                    })
                });
            """
        })

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

def remove_cookie_banner(driver, timeout=12, prefer="accept"):
    """
    Закрывает cookie-баннер TikTok.
    prefer: "accept" (Разрешить все) или "reject" (Отклонить).
    Возвращает True, если баннер убран (клик/удаление), иначе False.
    """
    import time
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.common.by import By

    deadline = time.time() + timeout
    action = "accept" if prefer not in ("reject", "decline") else "reject"

    js_handle_banner = r"""
    const prefer = arguments[0];
    // Список потенциальных хостов/контейнеров баннера
    const hostSel = "tiktok-cookie-banner, .tiktok-cookie-banner, .paas_tiktok";
    let clicked = false, removed = 0;

    // Пытаемся кликнуть в Shadow DOM (если открыт)
    const tryClickInRoot = (root, texts) => {
      if (!root) return false;
      const btns = root.querySelectorAll('button');
      for (const b of btns) {
        const t = (b.textContent || '').trim();
        for (const n of texts) {
          if (t === n || t.includes(n)) {
            try { b.click(); return true; } catch (e) {
              try {
                b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                return true;
              } catch(_) {}
            }
          }
        }
      }
      return false;
    };

    // 1) Ищем кастомный тег и пробуем кликнуть внутри shadowRoot
    const hosts = Array.from(document.querySelectorAll(hostSel));
    for (const host of hosts) {
      const root = host.shadowRoot || null;
      if (prefer === "accept") {
        if (tryClickInRoot(root, ["Разрешить все","Allow all","Accept all"])) { clicked = true; break; }
      } else {
        if (tryClickInRoot(root, ["Отклонить","Reject","Decline"])) { clicked = true; break; }
      }
    }

    // 2) Если не кликнулось через shadowRoot, пробуем обычный DOM внутри контейнеров
    if (!clicked) {
      for (const host of hosts) {
        const btns = host.querySelectorAll('button');
        for (const b of btns) {
          const t = (b.textContent || '').trim();
          if ((prefer === "accept" && (t === "Разрешить все" || /Allow|Accept/i.test(t))) ||
              (prefer !== "accept" && (t.startsWith("Отклонить") || /Reject|Decline/i.test(t)))) {
            try { b.click(); clicked = true; break; } catch (e) {
              try {
                b.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                clicked = true; break;
              } catch(_) {}
            }
          }
        }
        if (clicked) break;
      }
    }

    // 3) Если так и не вышло — скрываем/удаляем хосты, чтобы они не перехватывали клики
    if (!clicked) {
      const blockers = document.querySelectorAll(hostSel);
      blockers.forEach(el => {
        try {
          el.style.setProperty('display','none','important');
          el.style.setProperty('pointer-events','none','important');
          el.remove();
          removed++;
        } catch(e){}
      });
    }

    const remaining = !!document.querySelector(hostSel);
    return { clicked, removed, remaining };
    """

    def try_here():
        try:
            res = driver.execute_script(js_handle_banner, action) or {}
            clicked = bool(res.get("clicked"))
            remaining = bool(res.get("remaining"))
            if clicked:
                return "clicked"
            if not remaining:
                return "removed"
            return None
        except WebDriverException:
            return None

    # Основные попытки в текущем документе
    while time.time() < deadline:
        outcome = try_here()
        if outcome in ("clicked", "removed"):
            if outcome == "clicked":
                log("✅ Cookie: нажали «Разрешить все».")
            else:
                log("🧹 Cookie: баннер удалён/скрыт.")
            return True
        time.sleep(0.25)

    # Попробуем сделать то же самое во всех iframe
    try:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for idx, frame in enumerate(frames):
            try:
                driver.switch_to.frame(frame)
                for _ in range(8):  # короткие попытки внутри фрейма
                    outcome = try_here()
                    if outcome in ("clicked", "removed"):
                        driver.switch_to.default_content()
                        log(f"✅ Cookie в iframe #{idx}: {outcome}.")
                        return True
                    time.sleep(0.2)
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()
    except Exception:
        pass

    # На всякий случай — последний штрих: провалимся не будет
    log("🚫 Cookie-баннер не закрыт (возможен закрытый Shadow DOM).")
    return False

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
    log(f"🎬 Загрузка: {video_file} | Заголовок: {title}")
    driver = get_driver()
    wait = WebDriverWait(driver, 60)

    try:
        load_cookies(driver, COOKIES_FILE)

        driver.get(TIKTOK_UPLOAD_URL)

        upload_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="file"]')))
        upload_input.send_keys(os.path.abspath(os.path.join(VIDEO_FOLDER, video_file)))
        remove_cookie_banner(driver,timeout=3, prefer="accept")
        wait.until(EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Загружено")]')))

        caption = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]')))
        ActionChains(driver).move_to_element(caption).click().perform()
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)\
            .send_keys(Keys.BACKSPACE).send_keys(title).perform()

        publish = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@data-e2e="post_video_button"]')))
        time.sleep(1); publish.click(); time.sleep(8)

        move_uploaded(video_file)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success_msg = f"✅ Загружено: {video_file}\n📌 Заголовок: {title}\n🕒 Время: {now}"
        log(success_msg)
        send_telegram_message(success_msg)
    except Exception as e:
        error_msg = str(e)
        
        # Упрощаем сообщения об ошибках
        if "NoSuchWindowException" in error_msg:
            error_msg = "❌ Ошибка браузера: окно было закрыто"
        elif "no such window" in error_msg.lower():
            error_msg = "❌ Ошибка браузера: окно было закрыто"
        elif "web view not found" in error_msg.lower():
            error_msg = "❌ Ошибка браузера: окно было закрыто"
        elif "❌ Нет видео" in error_msg:
            error_msg = "❌ Нет видео для загрузки"
        elif "❌ titles.txt пуст" in error_msg:
            error_msg = "❌ Нет заголовков для видео"
        else:
            # Убираем технические детали из ошибки
            if "Stacktrace:" in error_msg:
                error_msg = error_msg.split("Stacktrace:")[0].strip()
            if "Session info:" in error_msg:
                error_msg = error_msg.split("Session info:")[0].strip()
            if "from unknown error:" in error_msg:
                error_msg = error_msg.split("from unknown error:")[0].strip()
            
            error_msg = f"❌ Ошибка загрузки: {error_msg}"
        
        log(error_msg)
        send_telegram_message(error_msg)
    finally:
        try:
            driver.quit()
        except Exception as e:
            log(f"⚠️ Ошибка закрытия драйвера: {e}")

if __name__ == "__main__":
    upload_video()
