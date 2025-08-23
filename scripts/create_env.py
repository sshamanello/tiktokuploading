#!/usr/bin/env python3
"""
Скрипт для создания .env файла с правильной кодировкой
"""

env_content = """# Настройки прокси
PROXY=185.232.18.41:63519
PROXY_USER=cy3jmdzR
PROXY_PASS=FG4Av12z
PROXY_TYPE=socks5

# Telegram настройки (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
"""

# Создаем .env файл с правильной кодировкой UTF-8
with open(".env", "w", encoding="utf-8") as f:
    f.write(env_content)

print("✅ Файл .env создан с правильной кодировкой UTF-8")
print("📝 Содержимое файла:")
print(env_content) 