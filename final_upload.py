import os
import time
import random
import shutil
import requests
import pickle
import os

from dotenv import load_dotenv
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

load_dotenv()
# Настройки
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_FOLDER = os.path.join(BASE_DIR, "VideosDirPath")
UPLOADED_FOLDER = os.path.join(BASE_DIR, "uploaded")
TITLES_FILE = os.path.join(BASE_DIR, "titles.txt")
COOKIES_FILE = os.path.join(BASE_DIR, "CookiesDir", "tiktok_session-toptrailer82.cookie")
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
print(f"📂 BASE_DIR: {BASE_DIR}")
print(f"🎞 VIDEO_FOLDER: {VIDEO_FOLDER}")

os.makedirs(UPLOADED_FOLDER, exist_ok=True)
#Отправка месседжа боту
import requests

def send_telegram_message(text: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("❌ Не найдены TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в .env")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("❌ Ошибка отправки в Telegram:", e)


def remove_cookie_banner(driver):
    try:
        driver.execute_script("""
            const banner = document.querySelector('.tiktok-cookie-banner');
            if (banner) banner.remove();
        """)
        print("🧹 Баннер cookie удалён через JS.")
    except Exception as e:
        print(f"⚠️ Не удалось удалить баннер через JS: {e}")

def load_cookies(driver, path):
    driver.get("https://www.tiktok.com/")
    with open(path, "rb") as f:
        cookies = pickle.load(f)
    for cookie in cookies:
        driver.add_cookie(cookie)
    driver.refresh()

def get_video_and_title():
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".mov"))]
    if not videos:
        raise Exception("Нет видео для загрузки.")
    with open(TITLES_FILE, "r", encoding="utf-8") as f:
        titles = f.readlines()
    if not titles:
        raise Exception("Файл titles.txt пуст.")
    title = titles[0].strip()
    with open(TITLES_FILE, "w", encoding="utf-8") as f:
        f.writelines(titles[1:])
    return videos[0], title

def move_uploaded(video_filename):
    shutil.move(os.path.join(VIDEO_FOLDER, video_filename), os.path.join(UPLOADED_FOLDER, video_filename))

def upload_video():
    video_file, title = get_video_and_title()
    print(f"⏫ Загружаем: {video_file} | Заголовок: {title}")
    
    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 60)

    load_cookies(driver, COOKIES_FILE)

    driver.get(TIKTOK_UPLOAD_URL)
    remove_cookie_banner(driver)

    # Ждём появление input загрузки видео
    upload_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="file"]')))
    upload_input.send_keys(os.path.abspath(os.path.join(VIDEO_FOLDER, video_file)))
    print("📤 Видео выбрано.")
    wait.until(
        EC.presence_of_element_located((
            By.XPATH,
            '//span[contains(text(), "Загружено")]'
        ))
    )
    print("📥 Видео загружено.")
    # Удаление баннера куков принудительно
    try:
        driver.execute_script("""
            let banner = document.querySelector('tiktok-cookie-banner');
            if (banner) {
                banner.remove();
            }
        """)
        print("🧹 Баннер cookie удалён через JS.")
    except Exception as e:
        print(f"❌ Не удалось удалить баннер cookie: {e}")
    # 1. Ждём и находим поле caption (Draft.js contenteditable)
    caption = wait.until(EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "public-DraftEditor-content") and @contenteditable="true"]')))

    # 2. Кликаем для активации
    actions = ActionChains(driver)
    actions.move_to_element(caption).click().perform()
    time.sleep(1)

    # 3. Выделяем и очищаем текст
    actions = ActionChains(driver)
    actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
    time.sleep(0.5)

    # 4. Вводим заголовок
    actions = ActionChains(driver)
    actions.send_keys(title).perform()
    print("📝 Заголовок вставлен.")

    # 5. Ждём кнопку и нажимаем
    publish_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@data-e2e="post_video_button"]')))
    time.sleep(1)
    publish_button.click()
    print("✅ Кнопка 'Опубликовать' нажата.")
   # ⏳ Подождать завершения редиректа
    time.sleep(8)
    print("🔁 Ожидание редиректа завершено.")

    try:
        # Пауза на всякий случай (TikTok иногда обрабатывает дольше)
        time.sleep(2)
        move_uploaded(video_file)
        print("📁 Видео перемещено в папку uploaded.")
    finally:
        driver.quit()
        print("❎ Браузер закрыт.")
        send_telegram_message(f"✅ Загружено видео: {video_file}\n📌 Заголовок: {title}")


if __name__ == "__main__":
    upload_video()
