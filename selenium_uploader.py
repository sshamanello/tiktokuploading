import os
import time
import pickle
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from browser import create_stealth_browser

COOKIES_PATH = "./cookies/toptrailer82.pkl"
VIDEO_FOLDER = "./VideosDirPath"
UPLOADED_FOLDER = "./uploaded"
TITLES_FILE = "titles.txt"
USERNAME = "toptrailer82"

os.makedirs(UPLOADED_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)

def get_next_video():
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".mov"))]
    if not videos:
        return None
    return videos[0]

def get_next_title():
    if not os.path.exists(TITLES_FILE):
        raise FileNotFoundError("titles.txt не найден!")
    with open(TITLES_FILE, "r", encoding="utf-8") as f:
        titles = f.readlines()
    if not titles:
        raise ValueError("titles.txt пуст!")
    title = titles[0].strip()
    with open(TITLES_FILE, "w", encoding="utf-8") as f:
        f.writelines(titles[1:])
    return title

def save_cookies(driver, path):
    with open(path, "wb") as file:
        pickle.dump(driver.get_cookies(), file)

def load_cookies(driver, path):
    if not os.path.exists(path):
        return False
    driver.get("https://www.tiktok.com/")
    with open(path, "rb") as file:
        cookies = pickle.load(file)
        for cookie in cookies:
            if "sameSite" in cookie:
                del cookie["sameSite"]
            try:
                driver.add_cookie(cookie)
            except:
                continue
    return True

def wait_and_click(driver, selector, timeout=15):
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector))).click()

def upload_video():
    video = get_next_video()
    if not video:
        print("[!] Нет видео для загрузки.")
        return

    title = get_next_title()
    video_path = os.path.join(VIDEO_FOLDER, video)
    print(f"⏫ Загружаем: {video} | Заголовок: {title}")

    driver = create_stealth_browser(brave_path="C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")
    driver.set_window_size(1280, 800)
    driver.get("https://www.tiktok.com/")

    cookies_loaded = load_cookies(driver, COOKIES_PATH)
    if not cookies_loaded:
        print("[!] Куки не найдены. Откроется окно авторизации.")
        driver.get("https://www.tiktok.com/login")
        print("👉 Авторизуйся вручную в браузере, затем нажми Enter здесь.")
        input("⬇️ Жду, когда ты нажмешь Enter после авторизации...")

        save_cookies(driver, COOKIES_PATH)
        print("[✔] Куки сохранены.")
    else:
        print("[✔] Куки загружены.")

    driver.get("https://www.tiktok.com/upload?lang=ru-RU")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, '//input[@type="file"]')))

    # Загрузка видео
    file_input = driver.find_element(By.XPATH, '//input[@type="file"]')
    file_input.send_keys(os.path.abspath(video_path))

    # Ввод заголовка
    caption_xpath = '//div[contains(@class,"public-DraftStyleDefault-block") and @data-offset-key]'
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, caption_xpath)))
    caption = driver.find_element(By.XPATH, caption_xpath)
    caption.click()
    caption.send_keys(Keys.CONTROL + "a")
    caption.send_keys(Keys.DELETE)
    caption.send_keys(title)

    # Ждём кнопку публикации и нажимаем
    post_button_selector = "button[data-e2e='upload-post']"
    WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.CSS_SELECTOR, post_button_selector)))
    time.sleep(1)
    driver.find_element(By.CSS_SELECTOR, post_button_selector).click()

    print("[✔] Видео отправлено на загрузку. Ждём подтверждение...")

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Загружено') or contains(text(), 'Published')]"))
    )

    driver.quit()
    os.rename(video_path, os.path.join(UPLOADED_FOLDER, video))
    print("[✔] Готово: видео загружено и перемещено.")

if __name__ == "__main__":
    upload_video()
