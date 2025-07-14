import os
import time
import pickle
import random
import shutil

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Настройки
COOKIES_FILE = "./CookiesDir/tiktok_session-toptrailer82.cookie"
VIDEO_FOLDER = "./VideosDirPath"
UPLOADED_FOLDER = "./uploaded"
TITLES_FILE = "titles.txt"
UPLOAD_URL = "https://www.tiktok.com/upload"

os.makedirs(UPLOADED_FOLDER, exist_ok=True)

def random_delay(base=1.0, variance=0.5):
    time.sleep(base + random.uniform(-variance, variance))

def load_cookies(driver, path):
    driver.get("https://www.tiktok.com/")
    with open(path, "rb") as f:
        cookies = pickle.load(f)
    for cookie in cookies:
        driver.add_cookie(cookie)
    driver.get(UPLOAD_URL)

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
    shutil.move(
        os.path.join(VIDEO_FOLDER, video_filename),
        os.path.join(UPLOADED_FOLDER, video_filename)
    )

def upload_video():
    video_file, title = get_video_and_title()
    print(f"⏫ Загружаем: {video_file} | Заголовок: {title}")

    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    load_cookies(driver, COOKIES_FILE)
    random_delay(5)

    try:
        # Ждём поле загрузки файла
        upload_input = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
        )
        upload_input.send_keys(os.path.abspath(os.path.join(VIDEO_FOLDER, video_file)))
        print("📤 Видео выбрано.")
    except Exception as e:
        print(f"[!] Ошибка при выборе видео: {e}")
        driver.quit()
        return

    random_delay(10)

    try:
        caption_area = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-e2e="caption-container"]//div[@role="textbox"]'))
        )
        caption_area.click()
        random_delay(1)
        caption_area.send_keys(Keys.CONTROL + "a")
        caption_area.send_keys(Keys.BACKSPACE)
        caption_area.send_keys(title)
        print("📝 Заголовок вставлен.")
    except Exception as e:
        print(f"[!] Ошибка при вставке заголовка: {e}")
        driver.quit()
        return

    input("🟢 Проверь всё вручную. Нажми Enter — и видео будет опубликовано...")

    try:
        publish_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(@data-e2e, "upload-post")]'))
        )
        publish_button.click()
        print("✅ Видео отправлено.")
    except Exception as e:
        print(f"[✖] Не удалось нажать кнопку 'Опубликовать': {e}")

    random_delay(5)
    driver.quit()
    move_uploaded(video_file)
    print("📁 Видео перемещено в папку uploaded.")

if __name__ == "__main__":
    upload_video()
