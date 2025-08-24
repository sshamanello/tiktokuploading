import os
import time
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

load_dotenv()

proxy = os.getenv("PROXY")
proxy_user = os.getenv("PROXY_USER")
proxy_pass = os.getenv("PROXY_PASS")
proxy_type = os.getenv("PROXY_TYPE", "http")

options = uc.ChromeOptions()
options.add_argument("--start-maximized")

if proxy and proxy_user and proxy_pass:
    proxy_auth = f"{proxy_user}:{proxy_pass}@{proxy}"
    options.add_argument(f"--proxy-server={proxy_type}://{proxy}")
    print(f"🧩 Прокси добавлен: {proxy_type}://{proxy}")

print("🟡 Запуск браузера...")
driver = uc.Chrome(options=options)
print("🌐 Открытие 2ip.ru...")
driver.get("https://2ip.ru")
time.sleep(10)  # Дай странице прогрузиться

try:
    ip_text = driver.find_element(By.XPATH, '//div[contains(@class, "ip") or contains(@id, "d_clip_button")]').text
    print(f"🌍 IP через браузер: {ip_text}")
except Exception as e:
    print(f"❌ Не удалось получить IP: {e}")

input("🔵 Нажми Enter, чтобы закрыть браузер...")
driver.quit()
