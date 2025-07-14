# TikTok Video Uploader

Скрипт для автоматической загрузки видео на TikTok с помощью Selenium.

## Функции

- Загружает любое видео из папки `VideosDirPath`
- Использует заголовки из `titles.txt` и удаляет использованные
- Перемещает загруженные видео в папку `uploaded`
- Использует cookie из `CookiesDir`
- Обходит баннер cookies
- Отправляет уведомление в Telegram после выполнения

## Установка

```bash
pip install -r requirements.txt
