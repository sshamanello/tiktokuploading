import requests

proxy_host = "185.232.18.41"
proxy_port = "63518"
proxy_user = "cy3jmdzR"
proxy_pass = "FG4Av12z"

proxies = {
    "http": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
    "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
}

try:
    ip = requests.get("https://api.ipify.org", proxies=proxies, timeout=10).text
    print("✅ Прокси работает. Ваш IP:", ip)
except Exception as e:
    print("❌ Прокси не работает:", e)
