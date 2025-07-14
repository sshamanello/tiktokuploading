from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import sys

def create_stealth_browser(brave_path=None):
    options = Options()
    if brave_path:
        options.binary_location = brave_path

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Уберём disable-webgl и disable-gpu для совместимости
    # options.add_argument("--disable-gpu")
    # options.add_argument("--disable-webgl")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """
        },
    )
    return driver


if __name__ == "__main__":
    brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
    driver = create_stealth_browser(brave_path=brave_path)

    try:
        driver.get("https://fon.bet/sports/basketball")
        input("🛑 Реши капчу в браузере и нажми Enter здесь...")

        WebDriverWait(driver, 10).until(lambda d: d.title and d.title.lower() != "fon.bet")

        # Сохраняем страницу
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✅ Страница сохранена в debug_page.html")

    finally:
        driver.quit()