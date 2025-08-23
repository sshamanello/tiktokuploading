import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_telegram_message(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ TELEGRAM токен или chat_id не указаны.")
        return
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Ошибка отправки в Telegram: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Telegram ошибка: {e}")