# 🚀 Быстрый старт Video Uploader v2.0

## Минимальная установка (5 минут)

### 1. Установите зависимости
```bash
pip install -r requirements_minimal.txt
```

### 2. Автоматическая настройка
```bash
python setup_v2.py
```

### 3. Запуск
```bash
# Веб-интерфейс
python main.py

# Разовая загрузка  
python main.py --upload video.mp4

# Помощь
python main.py --help
```

## ⚠️ Если возникают ошибки

### Ошибка: "No module named..."
```bash
# Установите полные зависимости
pip install -r requirements_new.txt

# Или вручную
pip install fastapi uvicorn PyYAML selenium undetected-chromedriver
```

### Ошибка: "Chrome not found"
1. Установите Google Chrome
2. Или обновите: `pip install --upgrade undetected-chromedriver`

### Ошибка: "Config file not found"
```bash
# Скопируйте конфигурацию
cp config.yaml.example config.yaml
# или создайте новую через setup_v2.py
```

## 📋 Минимальная настройка

1. **Папки с видео**: поместите видео в `VideosDirPath/`
2. **Заголовки**: добавьте заголовки в `titles.txt`
3. **TikTok cookies**: экспортируйте cookies в `CookiesDir/`

## 🌐 Веб-интерфейс

После запуска `python main.py` откройте:
- http://127.0.0.1:8080

## 🆘 Поддержка

- Полная документация: `README_v2.md`
- Проблемы: запустите с флагом `--debug`
- Логи: папка `logs/`

---

**Готово! Теперь можно загружать видео! 🎬✨**