import sys
import subprocess
import traceback
from proxy_manager import ProxyManager
from telegram_notify import send_telegram_message

def main():
    try:
        # Проверяем прокси без вывода
        proxy_manager = ProxyManager()
        if not proxy_manager.is_configured():
            error_msg = "❌ Прокси не настроен. Загрузка отменена."
            print(error_msg)
            send_telegram_message(error_msg)
            return
        
        success, message = proxy_manager.test_proxy_connection()
        if not success:
            error_msg = f"❌ Прокси не работает: {message}\nЗагрузка отменена."
            print(error_msg)
            send_telegram_message(error_msg)
            return
        
        # Запускаем скрипт загрузки
        result = subprocess.run([sys.executable, "final_upload.py"], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Ищем информацию о загруженном видео в выводе
            output = result.stdout
            if "✅ Загружено:" in output:
                # Извлекаем информацию о загруженном видео
                lines = output.split('\n')
                for line in lines:
                    if "✅ Загружено:" in line:
                        success_msg = line.strip()
                        print(success_msg)
                        # Не отправляем в Telegram, так как final_upload.py уже отправил детальное сообщение
                        break
            else:
                # Только если final_upload.py не отправил детальное сообщение
                success_msg = "✅ Видео успешно загружено!"
                print(success_msg)
                send_telegram_message(success_msg)
        else:
            # Ищем информацию об ошибке
            error_output = result.stderr if result.stderr else result.stdout
            if "❌ Нет видео" in error_output:
                error_msg = "❌ Нет видео для загрузки"
            elif "❌ titles.txt пуст" in error_output:
                error_msg = "❌ Нет заголовков для видео"
            elif "NoSuchWindowException" in error_output:
                error_msg = "❌ Ошибка браузера: окно было закрыто"
            else:
                # Извлекаем основную ошибку
                lines = error_output.split('\n')
                for line in lines:
                    if "❌" in line or "Exception" in line or "Error" in line:
                        error_msg = f"❌ Ошибка загрузки: {line.strip()}"
                        break
                else:
                    error_msg = "❌ Неизвестная ошибка при загрузке видео"
            
            print(error_msg)
            # Не отправляем в Telegram, так как final_upload.py уже отправил
            # send_telegram_message(error_msg)
            
    except Exception as e:
        error_msg = f"❌ Критическая ошибка: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

if __name__ == "__main__":
    main()