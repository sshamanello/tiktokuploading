# Video Uploader v2.0 🎬

Модернизированная система автоматической загрузки видео в социальные сети с улучшенной архитектурой, планировщиком задач и веб-интерфейсом.

## 🚀 Новые возможности

### ✨ Ключевые улучшения
- **Архитектура с разделением ответственности** - модульная структура с четким разделением функций
- **Планировщик задач** - очереди загрузки, приоритеты, retry механизмы
- **Веб-интерфейс** - современный GUI с real-time мониторингом
- **Мультиплатформенность** - готовность к добавлению Instagram, YouTube и других платформ
- **Улучшенное логирование** - структурированные логи с цветным выводом
- **Конфигурация** - гибкая настройка через YAML файлы и переменные окружения
- **Надежность** - retry механизмы, обработка ошибок, graceful shutdown

### 🎯 Поддерживаемые платформы
- ✅ **TikTok** - полная поддержка загрузки
- 🚧 **Instagram** - заготовка архитектуры (в разработке)
- 📋 **YouTube, Twitter** - планируется

## 📁 Структура проекта

```
tiktokupload/
├── src/
│   ├── core/                   # Базовые компоненты
│   │   ├── config_manager.py   # Управление конфигурацией
│   │   ├── file_manager.py     # Работа с файлами
│   │   ├── logger.py           # Система логирования
│   │   ├── platform_base.py    # Базовые классы платформ
│   │   ├── retry_manager.py    # Retry механизмы
│   │   └── scheduler.py        # Планировщик задач
│   ├── platforms/              # Платформы для загрузки
│   │   ├── tiktok_uploader.py  # TikTok загрузчик
│   │   └── instagram_uploader.py # Instagram заготовка
│   ├── gui/                    # Веб-интерфейс
│   │   ├── templates/          # HTML шаблоны
│   │   ├── static/             # CSS/JS файлы
│   │   └── web_interface.py    # FastAPI приложение
│   └── uploader_app.py         # Основное приложение
├── main.py                     # Точка входа
├── config.yaml                 # Конфигурация
├── requirements_new.txt        # Новые зависимости
└── README_v2.md               # Эта документация
```

## 🛠 Установка

### 1. Подготовка окружения

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements_new.txt
```

### 2. Настройка конфигурации

Скопируйте `config.yaml` и настройте под свои нужды:

```yaml
# Основные настройки
videos_dir: "./VideosDirPath"
uploaded_dir: "./uploaded"  
titles_file: "./titles.txt"

# TikTok настройки
tiktok:
  enabled: true
  cookies_path: "./CookiesDir/tiktok_session.cookie"
  
# Telegram уведомления
telegram_enabled: true
telegram_token: "YOUR_BOT_TOKEN"
telegram_chat_id: "YOUR_CHAT_ID"
```

### 3. Переменные окружения (опционально)

Создайте файл `.env`:
```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id
TIKTOK_COOKIES_PATH=./CookiesDir/session.cookie
PROXY=host:port
PROXY_USER=username  
PROXY_PASS=password
```

## 🎮 Использование

### Веб-интерфейс (рекомендуется)

```bash
# Запуск с GUI (по умолчанию)
python main.py

# Кастомный хост и порт
python main.py --host 0.0.0.0 --port 8080

# Debug режим
python main.py --debug
```

Откройте http://127.0.0.1:8080 в браузере.

### Командная строка

```bash
# Разовая загрузка
python main.py --upload video.mp4 --platform tiktok --title "Мое видео"

# Пакетная загрузка (5 видео)
python main.py --batch --platform tiktok --max-videos 5

# Фоновый режим без GUI
python main.py --no-gui
```

### Программное использование

```python
import asyncio
from src.uploader_app import UploaderApp

async def example():
    app = UploaderApp("config.yaml")
    await app.start()
    
    # Разовая загрузка
    result = app.upload_single_video(
        platform_name="tiktok",
        video_path=Path("video.mp4"),
        title="Test upload"
    )
    
    # Планирование загрузки
    task_id = app.schedule_upload(
        platform_name="tiktok", 
        video_path=Path("video.mp4"),
        scheduled_time=datetime.now() + timedelta(hours=1)
    )
    
    await app.stop()

asyncio.run(example())
```

## 📊 Веб-интерфейс возможности

### Dashboard
- 📈 Статистика загрузок в реальном времени
- 📋 Мониторинг очереди задач
- 🎯 Быстрая загрузка видео
- ⏰ Планирование загрузок

### API Endpoints
- `GET /api/status` - статус приложения
- `GET /api/videos` - список видео
- `GET /api/tasks` - список задач
- `POST /api/upload` - немедленная загрузка
- `POST /api/schedule` - планирование загрузки
- `POST /api/batch-schedule` - пакетное планирование
- `DELETE /api/tasks/{id}` - отмена задачи
- `WebSocket /ws` - real-time уведомления

## ⚙️ Конфигурация

### Основные секции

```yaml
# Файлы и папки
videos_dir: "./VideosDirPath"
uploaded_dir: "./uploaded"
titles_file: "./titles.txt"

# Логирование
log_level: "INFO"
log_file: "./logs/uploader.log"

# Планировщик
scheduler_enabled: true
max_concurrent_uploads: 2

# Платформы
tiktok:
  enabled: true
  retry_attempts: 3
  upload_delay: 5
  rate_limit: 10

instagram:
  enabled: false  # Пока не реализовано
```

### Переменные окружения

Все настройки из config.yaml можно переопределить через переменные окружения:
- `VIDEOS_DIR` → `videos_dir`
- `TELEGRAM_BOT_TOKEN` → `telegram_token`
- `TIKTOK_ENABLED` → `tiktok.enabled`

## 📝 Логирование

### Уровни логирования
- `DEBUG` - детальная отладочная информация
- `INFO` - общая информация о работе
- `WARNING` - предупреждения
- `ERROR` - ошибки
- `CRITICAL` - критические ошибки

### Файлы логов
```
logs/
├── uploader.log        # Основной лог
└── uploader.log.1      # Ротация логов
```

## 🔄 Планировщик задач

### Возможности
- ⏰ **Планирование по времени** - загрузка в определенное время
- 🎯 **Приоритеты** - URGENT, HIGH, NORMAL, LOW
- 🔄 **Retry механизмы** - автоматические повторы при ошибках
- 📊 **Мониторинг** - отслеживание статуса всех задач
- 💾 **Персистентность** - сохранение состояния между перезапусками

### Статусы задач
- `PENDING` - ожидает выполнения
- `SCHEDULED` - запланировано на будущее
- `RUNNING` - выполняется
- `COMPLETED` - завершено успешно
- `FAILED` - завершено с ошибкой
- `CANCELLED` - отменено пользователем

## 🔧 Разработка

### Добавление новой платформы

1. Создайте класс-наследник от `Platform`:

```python
from src.core.platform_base import Platform

class YouTubeUploader(Platform):
    def authenticate(self) -> bool:
        # Реализация аутентификации
        pass
    
    def upload_video(self, metadata) -> UploadResult:
        # Реализация загрузки
        pass
```

2. Зарегистрируйте в `UploaderApp`:

```python
self.platforms['youtube'] = YouTubeUploader(config, logger)
```

### Архитектурные принципы

1. **Разделение ответственности** - каждый модуль отвечает за свою область
2. **Dependency Injection** - зависимости передаются через конструктор
3. **Абстракция платформ** - единый интерфейс для всех платформ
4. **Конфигурируемость** - все настройки вынесены в конфигурацию
5. **Наблюдаемость** - подробное логирование и метрики

## 🚨 Troubleshooting

### Частые проблемы

**WebDriver не запускается:**
```bash
# Обновите Chrome и установите актуальную версию
pip install --upgrade undetected-chromedriver
```

**Ошибки прав доступа:**
```bash
# Проверьте права на папки
chmod -R 755 VideosDirPath uploaded
```

**Проблемы с прокси:**
```bash
# Проверьте настройки в config.yaml или .env
# Протестируйте прокси отдельно
```

**Не работают уведомления Telegram:**
```bash
# Проверьте токен бота и chat_id
# Убедитесь что бот добавлен в чат
```

## 📈 Производительность

### Рекомендации
- Используйте SSD для папок с видео
- Настройте `max_concurrent_uploads` в зависимости от мощности ПК
- Включите прокси для обхода rate limiting
- Регулярно очищайте папку `uploaded`

### Мониторинг
- Веб-интерфейс показывает статистику в реальном времени
- Логи содержат время выполнения операций
- Планировщик отслеживает нагрузку

## 🛣 Roadmap

### v2.1 (планируется)
- ✅ Instagram поддержка
- 📊 Подробная аналитика
- 🔗 API webhooks
- 📱 Mobile-responsive GUI

### v2.2 (планируется)
- 🎥 YouTube поддержка
- 🐦 Twitter/X поддержка
- 🔍 Advanced video processing
- 🤖 AI-генерация заголовков

### v3.0 (в планах)
- ☁️ Cloud deployment
- 👥 Multi-user support
- 📊 Business analytics
- 🔐 Enterprise security

## 🤝 Вклад в проект

Приветствуются:
- 🐛 Отчеты об ошибках
- 💡 Предложения новых функций
- 🔧 Pull requests
- 📚 Улучшения документации

## 📄 Лицензия

MIT License - свободное использование и модификация.

## 🙏 Благодарности

- Selenium WebDriver
- FastAPI framework
- TailwindCSS
- Alpine.js
- Все контрибьюторы проекта

---

**Наслаждайтесь автоматизированной загрузкой видео! 🎬✨**