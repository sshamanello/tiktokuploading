"""
Instagram Autoposter using instagrapi
-------------------------------------
Назначение:
- Безопасный логин (сессия + device settings) и автопролонгация сессии
- Загрузка: фото, видео в ленту, Reels, карусель
- REST-слой (FastAPI) для интеграции с внешним пайплайном (например, автозагрузчик TikTok)
- CLI для ручного запуска (python instagram_uploader.py --type reel --media path.mp4 --caption "...")

Требования:
- Python 3.10+
- pip install instagrapi fastapi uvicorn[standard] python-multipart pydantic[dotenv] requests
- (опционально) pip install tenacity

Переменные окружения (.env):
- IG_USERNAME=your_login
- IG_PASSWORD=your_password
- IG_PROXY=    # опционально: http://user:pass@host:port или socks5://...
- IG_SESSION_PATH=./.ig_session.json
- IG_DEVICE_SEED=shhamanello-01   # любой стабильный идентификатор устройства
- IG_2FA_CODE=                    # используйте при 2FA (одноразово)

Запуск REST:
- uvicorn instagram_uploader:app --host 0.0.0.0 --port 8090 --reload

Безопасность:
- НЕ храните пароль в репозитории, используйте переменные окружения/secret manager
- Для прод: прикрутите ограничение доступа к REST (IP allowlist, reverse-proxy auth)
"""
from __future__ import annotations

import os
import io
import sys
import json
import time
import random
import logging
from pathlib import Path
from typing import List, Optional, Literal, Union

import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from instagrapi import Client
from instagrapi.exceptions import (LoginRequired, TwoFactorRequired, ChallengeRequired,
                                   PleaseWaitFewMinutes, RateLimitError)
try:
    from instagrapi.exceptions import Throttled
except Exception:
    class Throttled(Exception):
        pass

# ---------------------------------
# Конфиг и утилиты
# ---------------------------------

class Settings(BaseSettings):
    IG_USERNAME: str
    IG_PASSWORD: str
    IG_PROXY: Optional[str] = None
    IG_SESSION_PATH: str = "./.ig_session.json"
    IG_DEVICE_SEED: str = "device-seed"
    IG_2FA_CODE: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("ig")

SESSION_PATH = Path(settings.IG_SESSION_PATH)


def _human_delay(a: float = 1.0, b: float = 2.5) -> None:
    time.sleep(random.uniform(a, b))


def _download_to_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


# ---------------------------------
# Клиент Instagram (instagrapi)
# ---------------------------------

from __future__ import annotations

import json
import os
import logging
import random
import time
from pathlib import Path
from typing import Optional, Union, List

from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired,
    TwoFactorRequired,
    ChallengeRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
)
try:  # совместимость со старыми/новыми версиями instagrapi
    from instagrapi.exceptions import Throttled  # type: ignore
except Exception:  # noqa: BLE001 - универсальная заглушка
    class Throttled(Exception):
        pass

log = logging.getLogger("ig")


class IGClient:
    """Надёжная обёртка вокруг instagrapi.Client с хранением сессии и безопасной инициализацией.

    Ожидается, что в settings есть поля:
      - IG_USERNAME, IG_PASSWORD (обяз.)
      - IG_PROXY (опц.)
      - IG_SESSION_PATH (опц., путь к json)
      - IG_2FA_CODE (опц., для одноразового 2FA)
    """

    def __init__(self, settings):
        self.settings = settings
        self.session_path = Path(getattr(settings, "IG_SESSION_PATH", "./.ig_session.json"))

        # 1) Пытаемся загрузить валидные сохранённые настройки
        settings_dict = self._safe_read_session()
        if settings_dict is not None:
            self.cl = self._safe_init_client(settings=settings_dict)
            log.info("Загружены сохранённые настройки клиента")
        else:
            # 2) Инициализируем пустым, но валидным набором настроек
            self.cl = self._safe_init_client(settings={"device_settings": {}})
            log.info("Создан новый клиент с пустыми device_settings")

        # Прокси после init
        proxy = getattr(settings, "IG_PROXY", None)
        if proxy:
            try:
                self.cl.set_proxy(proxy)
            except Exception as e:  # pragma: no cover
                log.warning(f"Не удалось установить прокси: {e}")

    # -----------------------------
    # Вспомогательные методы
    # -----------------------------
    def _human_delay(self, a: float = 0.9, b: float = 2.3) -> None:
        time.sleep(random.uniform(a, b))

    def _safe_init_client(self, settings: dict | None = None) -> Client:
        """Создаёт Client, гарантируя корректный формат settings."""
        if not isinstance(settings, dict):
            settings = {}
        ds = settings.get("device_settings")
        if isinstance(ds, str):
            settings["device_settings"] = {}
        elif ds is None:
            settings["device_settings"] = {}
        try:
            return Client(settings=settings)
        except ValueError:
            # Если settings кривые — стартуем с пустыми
            return Client(settings={"device_settings": {}})

    def _safe_read_session(self) -> Optional[dict]:
        if not self.session_path.exists():
            return None
        try:
            raw = self.session_path.read_text(encoding="utf-8")
            if not raw.strip().startswith("{"):
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            # Нормализуем device_settings
            if isinstance(data.get("device_settings"), str):
                data["device_settings"] = {}
            return data
        except Exception as e:
            log.warning(f"Не удалось прочитать сессию: {e}")
            return None

    def _save_session(self) -> None:
        try:
            data = self.cl.get_settings()
            if isinstance(data.get("device_settings"), str):
                data["device_settings"] = {}
            self.session_path.write_text(json.dumps(data), encoding="utf-8")
            log.info(f"Сессия сохранена в {self.session_path}")
        except Exception as e:  # pragma: no cover
            log.warning(f"Не удалось сохранить сессию: {e}")

    def _session_alive(self) -> bool:
        try:
            # Если пользователь залогинен — user_id установлен
            if getattr(self.cl, "user_id", None):
                self.cl.get_timeline_feed()
                return True
            return False
        except Exception:
            return False

    # -----------------------------
    # Аутентификация
    # -----------------------------
    def login(self) -> None:
        """Логин с переиспользованием сессии и обработкой 2FA/Challenge."""
        # 1) Повторное использование существующей сессии
        if self._session_alive():
            log.info("Сессия активна, логин не требуется")
            return

        # 2) Полный логин
        try:
            log.info("Выполняю логин по паролю…")
            self.cl.login(self.settings.IG_USERNAME, self.settings.IG_PASSWORD)
            self._human_delay(0.8, 1.6)
            self._save_session()
            return
        except TwoFactorRequired:
            code = getattr(self.settings, "IG_2FA_CODE", None) or os.environ.get("IG_2FA_CODE")
            if not code:
                raise RuntimeError("Требуется 2FA код. Установите IG_2FA_CODE в окружении и повторите.")
            self.cl.two_factor_login(self.settings.IG_USERNAME, self.settings.IG_PASSWORD, code)
            self._human_delay(0.8, 1.6)
            self._save_session()
            return
        except ChallengeRequired as e:  # pragma: no cover
            raise RuntimeError(
                "Instagram запросил Challenge. Подтвердите вход в приложении/по почте и повторите."
            ) from e
        except Exception as e:  # pragma: no cover
            # В случае битых настроек пробуем сбросить и залогиниться с нуля
            log.warning(f"Первый логин не удался: {e}. Пробую сброс и повтор…")
            try:
                if self.session_path.exists():
                    self.session_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.cl = self._safe_init_client(settings={"device_settings": {}})
            proxy = getattr(self.settings, "IG_PROXY", None)
            if proxy:
                try:
                    self.cl.set_proxy(proxy)
                except Exception:
                    pass
            self.cl.login(self.settings.IG_USERNAME, self.settings.IG_PASSWORD)
            self._human_delay(0.8, 1.6)
            self._save_session()

    # -----------------------------
    # Публикации
    # -----------------------------
    def _ensure_login(self) -> None:
        if not self._session_alive():
            self.login()

    @staticmethod
    def _to_path(tmp_name: str, media: Union[str, bytes]) -> Path:
        if isinstance(media, str) and media.startswith("http"):
            # отложенный импорт, чтобы не тянуть requests глобально, если не надо
            import requests  # noqa: WPS433
            r = requests.get(media, timeout=60)
            r.raise_for_status()
            p = Path(tmp_name)
            p.write_bytes(r.content)
            return p
        if isinstance(media, bytes):
            p = Path(tmp_name)
            p.write_bytes(media)
            return p
        return Path(media)

    def upload_photo(self, media: Union[str, bytes], caption: str = "") -> dict:
        self._ensure_login()
        self._human_delay()
        path = self._to_path("/tmp/ig_photo.jpg", media)
        res = self.cl.photo_upload(path, caption)
        return {"status": "ok", "type": "photo", "media_id": getattr(res, "pk", None) or res.dict().get("pk")}

    def upload_video(
        self,
        media: Union[str, bytes],
        caption: str = "",
        cover: Optional[Union[str, bytes]] = None,
    ) -> dict:
        self._ensure_login()
        self._human_delay()
        video_path = self._to_path("/tmp/ig_video.mp4", media)
        thumb_path = None
        if cover is not None:
            thumb_path = self._to_path("/tmp/ig_thumb.jpg", cover)
        res = self.cl.video_upload(video_path, caption=caption, thumbnail=thumb_path)
        return {"status": "ok", "type": "video", "media_id": getattr(res, "pk", None) or res.dict().get("pk")}

    def upload_reel(
        self,
        media: Union[str, bytes],
        caption: str = "",
        cover: Optional[Union[str, bytes]] = None,
    ) -> dict:
        self._ensure_login()
        self._human_delay()
        video_path = self._to_path("/tmp/ig_reel.mp4", media)
        thumb_path = None
        if cover is not None:
            thumb_path = self._to_path("/tmp/ig_reel_thumb.jpg", cover)
        res = self.cl.clip_upload(video_path, caption=caption, thumbnail=thumb_path)
        return {"status": "ok", "type": "reel", "media_id": getattr(res, "pk", None) or res.dict().get("pk")}

    def upload_album(self, media_list: List[Union[str, bytes]], caption: str = "") -> dict:
        self._ensure_login()
        self._human_delay()
        paths: List[Path] = []
        for i, m in enumerate(media_list):
            paths.append(self._to_path(f"/tmp/ig_album_{i}.jpg", m))
        res = self.cl.album_upload(paths, caption)
        return {"status": "ok", "type": "album", "media_id": getattr(res, "pk", None) or res.dict().get("pk")}

# ---------------------------------
# FastAPI слой
# ---------------------------------

app = FastAPI(title="Instagram Autoposter")
ig = IGClient(settings)


class PublishBody(BaseModel):
    type: Literal["photo", "video", "reel", "album"]
    caption: Optional[str] = ""
    media: Optional[str] = None               # локальный путь ИЛИ URL
    cover: Optional[str] = None               # путь/URL для превью (video/reel)
    media_list: Optional[List[str]] = None    # для album


@app.post("/instagram/publish")
async def publish_json(body: PublishBody):
    try:
        if body.type == "photo":
            assert body.media, "media обязателен"
            res = ig.upload_photo(body.media, body.caption or "")
        elif body.type == "video":
            assert body.media, "media обязателен"
            res = ig.upload_video(body.media, body.caption or "", body.cover)
        elif body.type == "reel":
            assert body.media, "media обязателен"
            res = ig.upload_reel(body.media, body.caption or "", body.cover)
        elif body.type == "album":
            assert body.media_list and len(body.media_list) >= 2, "media_list: минимум 2 элемента"
            res = ig.upload_album(body.media_list, body.caption or "")
        else:
            return JSONResponse({"error": "unknown type"}, status_code=400)
        return res
    except (PleaseWaitFewMinutes, Throttled, RateLimitError) as e:
        log.warning(f"Rate limit: {e}")
        return JSONResponse({"error": "rate_limited", "detail": str(e)}, status_code=429)
    except (LoginRequired,) as e:
        log.error(f"LoginRequired: {e}")
        # Пробуем ре-логин и повторить? Здесь отдаём ошибку, чтобы вызывающая система решила, что делать
        return JSONResponse({"error": "login_required", "detail": str(e)}, status_code=401)
    except AssertionError as e:
        return JSONResponse({"error": "bad_request", "detail": str(e)}, status_code=400)
    except Exception as e:
        log.exception("Unhandled error")
        return JSONResponse({"error": "unknown", "detail": str(e)}, status_code=500)


# Файл-аплоад (multipart/form-data) — удобно слать из других сервисов
@app.post("/instagram/upload")
async def publish_file(
    type: Literal["photo", "video", "reel", "album"] = Form(...),
    caption: Optional[str] = Form("") ,
    files: List[UploadFile] = File(...),
):
    try:
        if type == "album":
            # Сохраняем все во временные файлы и грузим как карусель
            paths = []
            for i, f in enumerate(files):
                p = Path(f"/tmp/ig_album_up_{i}")
                p.write_bytes(await f.read())
                paths.append(str(p))
            res = ig.upload_album(paths, caption or "")
        else:
            # Берём первый файл
            data = await files[0].read()
            if type == "photo":
                res = ig.upload_photo(data, caption or "")
            elif type == "video":
                res = ig.upload_video(data, caption or "")
            elif type == "reel":
                res = ig.upload_reel(data, caption or "")
            else:
                return JSONResponse({"error": "unknown type"}, status_code=400)
        return res
    except Exception as e:
        log.exception("upload error")
        return JSONResponse({"error": "unknown", "detail": str(e)}, status_code=500)


# ---------------------------------
# CLI
# ---------------------------------

import argparse

def _cli():
    parser = argparse.ArgumentParser(description="Instagram autoposter")
    parser.add_argument("--type", choices=["photo", "video", "reel", "album"], required=True)
    parser.add_argument("--media", nargs="*", help="Путь/URL (для album можно несколько)")
    parser.add_argument("--caption", default="")
    parser.add_argument("--cover", default=None, help="Путь/URL превью для видео/реилс")
    args = parser.parse_args()

    igc = IGClient(settings)

    if args.type == "album":
        if not args.media or len(args.media) < 2:
            print("Для album укажите минимум 2 файла/URL", file=sys.stderr)
            sys.exit(2)
        print(igc.upload_album(args.media, args.caption))
    elif args.type == "photo":
        assert args.media and len(args.media) == 1
        print(igc.upload_photo(args.media[0], args.caption))
    elif args.type == "video":
        assert args.media and len(args.media) == 1
        print(igc.upload_video(args.media[0], args.caption, args.cover))
    elif args.type == "reel":
        assert args.media and len(args.media) == 1
        print(igc.upload_reel(args.media[0], args.caption, args.cover))


if __name__ == "__main__":
    _cli()
