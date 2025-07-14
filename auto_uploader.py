import os
from tiktok_uploader.tiktok import upload_video
from tiktok_uploader.Config import Config

# Настройки
COOKIES_NAME = "toptrailer82"
VIDEO_FOLDER = "./VideosDirPath"
UPLOADED_FOLDER = "./uploaded"
TITLES_FILE = "titles.txt"

Config.load("./config.txt")
os.makedirs(UPLOADED_FOLDER, exist_ok=True)

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

def upload_one_video():
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".mov"))]

    if not videos:
        print("[!] Нет видео для загрузки.")
        return

    video = videos[0]
    video_path = os.path.join(VIDEO_FOLDER, video)

    try:
        title = get_next_title()

        # ВНИМАНИЕ: в оригинальной функции видео ищется в папке videos_dir из config.txt
        # Поэтому нужно, чтобы config.videos_dir = "videos_to_post"

        print(f"⏫ Загружаем: {video} | Заголовок: {title}")
        upload_video(
            session_user=COOKIES_NAME,
            video=video,  # НЕ полный путь, а имя файла
            title=title
        )

        os.rename(video_path, os.path.join(UPLOADED_FOLDER, video))
        print(f"[✔] Успешно загружено и перемещено.")

    except Exception as e:
        print(f"[✖] Ошибка при загрузке {video}: {e}")

if __name__ == "__main__":
    upload_one_video()
