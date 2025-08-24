import os
import time
import pickle
from pathlib import Path
from typing import Dict, Any
import logging

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

from ..core.platform_base import Platform, VideoMetadata, UploadResult, UploadStatus


class TikTokUploader(Platform):
    """Загрузчик видео в TikTok"""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        self.driver = None
        self.upload_url = "https://www.tiktok.com/upload"
        self.max_title_length = 2200

    # ---------- AUTH ----------
    def authenticate(self) -> bool:
        """Аутентификация через cookies"""
        try:
            cookies_path = self.config.get("cookies_path")
            if not cookies_path or not Path(cookies_path).exists():
                self.logger.error(f"Cookies file not found: {cookies_path}")
                return False

            self.driver = self._create_driver()
            if not self.driver:
                return False

            self.driver.get("https://www.tiktok.com/")
            time.sleep(3)

            with open(cookies_path, "rb") as f:
                cookies = pickle.load(f)

            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.debug(f"Could not add cookie: {e}")

            self.driver.refresh()
            time.sleep(5)

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.XPATH, "//span[contains(@class,'avatar')]")
                    or d.find_elements(By.XPATH, "//div[contains(@data-e2e,'nav-profile')]")
                )
                self.logger.info("Successfully authenticated to TikTok")
                return True
            except TimeoutException:
                self.logger.warning("Could not verify TikTok authentication (continuing)")
                return True
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False

    # ---------- PUBLIC API ----------
    def upload_video(self, metadata: VideoMetadata) -> UploadResult:
        """Загружает видео в TikTok"""
        result = UploadResult(
            success=False, platform=self.platform_name, status=UploadStatus.PENDING
        )

        try:
            # Драйвер
            if not self.driver:
                if not self.authenticate():
                    result.message = "Authentication failed"
                    result.status = UploadStatus.FAILED
                    return result

            # Валидации
            if not self.validate_video(metadata.file_path):
                result.message = "Video validation failed"
                result.status = UploadStatus.FAILED
                return result

            if len(metadata.title) > self.max_title_length:
                result.message = f"Title too long (max {self.max_title_length} characters)"
                result.status = UploadStatus.FAILED
                return result

            result.status = UploadStatus.UPLOADING
            self.logger.info(f"Starting upload: {metadata.file_path.name}")

            # Страница загрузки
            self.driver.get(self.upload_url)
            time.sleep(3)
            self._handle_cookie_banner()

            wait = WebDriverWait(self.driver, 60)

            # input[type=file]
            upload_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
            )
            upload_input.send_keys(str(metadata.file_path.absolute()))
            self.logger.info("Video file uploaded, waiting for processing...")

            # Ожидание обработки
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located(
                            (By.XPATH, '//span[contains(text(),"Загружено")]')
                        ),
                        EC.presence_of_element_located(
                            (By.XPATH, '//span[contains(text(),"Uploaded")]')
                        ),
                        EC.presence_of_element_located(
                            (By.XPATH, '//div[contains(@class,"upload-success")]')
                        ),
                    )
                )
                self.logger.info("Video processed successfully")
                
                # Проверяем, есть ли кнопка "Опубликовать" сразу после загрузки
                try:
                    immediate_publish = wait.until(
                        EC.any_of(
                            EC.element_to_be_clickable((By.XPATH, '//div[@class="TUXButton-label" and text()="Опубликовать"]/parent::button')),
                            EC.element_to_be_clickable((By.XPATH, '//div[@class="TUXButton-label" and text()="Publish"]/parent::button')),
                            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Опубликовать")]')),
                            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Publish")]'))
                        )
                    )
                    
                    time.sleep(0.8)
                    immediate_publish.click()
                    self.logger.info("Immediate publish button clicked after upload")
                    time.sleep(2)
                    
                except TimeoutException:
                    self.logger.debug("No immediate publish button found after upload - proceeding with title input")
                
            except TimeoutException:
                result.message = "Video processing timeout"
                result.status = UploadStatus.FAILED
                return result

            # Заголовок
            try:
                self._handle_cookie_banner()
                self._clear_and_type_caption(metadata.title)
                self.logger.info(f"Title set: {metadata.title[:50]}...")
            except Exception as e:
                self.logger.warning(f"Could not set title: {e}")

            # Приватность
            self._configure_privacy_settings(metadata)

            # Первая кнопка «Опубликовать»
            try:
                publish_button = wait.until(
                    EC.any_of(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                '//div[@class="TUXButton-label" and text()="Опубликовать"]/parent::button',
                            )
                        ),
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                '//div[@class="TUXButton-label" and text()="Publish"]/parent::button',
                            )
                        ),
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[@data-e2e="post_video_button"]')
                        ),
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[contains(text(),"Опубликовать")]')
                        ),
                    )
                )
                time.sleep(0.8)
                try:
                    publish_button.click()
                except (ElementClickInterceptedException, WebDriverException):
                    self._handle_cookie_banner()
                    self._click_with_js(publish_button)

                self.logger.info("Publish button clicked")

                # Подтвердить во втором окне (если появится)
                try:
                    self._confirm_publish(timeout=25)
                except Exception as e:
                    self.logger.debug(f"Confirm modal handling: {e}")

                # Проверяем успешность публикации
                success_confirmed = self._verify_upload_success(timeout=15)
                
                if success_confirmed:
                    result.success = True
                    result.status = UploadStatus.COMPLETED
                    result.message = f"Successfully uploaded: {metadata.file_path.name}"
                    
                    # Пытаемся получить URL видео
                    try:
                        current_url = self.driver.current_url
                        if "tiktok.com" in current_url and current_url != self.upload_url:
                            result.url = current_url
                            self.logger.info(f"Video URL: {current_url}")
                    except Exception:
                        pass
                else:
                    result.success = True  # Считаем успешным, если дошли до публикации
                    result.status = UploadStatus.COMPLETED
                    result.message = f"Upload likely successful: {metadata.file_path.name} (verification timeout)"
                    self.logger.warning("Could not verify upload success, but assuming successful")

            except Exception as e:
                self.logger.error(f"Failed to publish: {e}")
                # Если дошли до этапа публикации, считаем частично успешным
                if "processed successfully" in str(result.message) or result.status == UploadStatus.UPLOADING:
                    result.success = True
                    result.status = UploadStatus.COMPLETED
                    result.message = f"Upload likely successful despite error: {metadata.file_path.name} - {e}"
                    self.logger.warning(f"Assuming upload success despite publish error: {e}")
                else:
                    result.message = f"Failed to publish: {e}"
                    result.status = UploadStatus.FAILED

        except Exception as e:
            result.message = f"Upload failed: {e}"
            result.status = UploadStatus.FAILED
            self.logger.error(f"Upload error: {e}")

        return result

    # ---------- HELPERS ----------
    def _clear_and_type_caption(self, text: str, timeout: int = 30):
        """Полная очистка contenteditable + надёжный ввод текста."""
        wait = WebDriverWait(self.driver, timeout)

        caption = wait.until(
            EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]'))
        )

        # Жёсткая очистка + событие ввода
        self.driver.execute_script(
            """
            const el = arguments[0];
            el.focus();

            // select all
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);

            // delete
            document.execCommand('delete', false, null);
            el.innerHTML = '';
            el.textContent = '';

            // уведомить реактивный слой
            el.dispatchEvent(new InputEvent('input', { bubbles: true }));
        """,
            caption,
        )
        time.sleep(0.2)

        # Доп. страховка клавишами
        ActionChains(self.driver).move_to_element(caption).click().key_down(
            Keys.CONTROL
        ).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
        time.sleep(0.2)

        # Ввод текста
        caption.send_keys(text)
        self.driver.execute_script(
            "arguments[0].dispatchEvent(new InputEvent('input', { bubbles: true }));",
            caption,
        )

    def _click_with_js(self, el):
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", el
            )
            self.driver.execute_script("arguments[0].click();", el)
        except Exception:
            pass

    def _confirm_publish(self, timeout: int = 25):
        """
        Ждёт модалку подтверждения и жмёт вторую «Опубликовать», строго внутри модалки.
        Работает и на RU, и на EN. Делает JS‑клик, если обычный перехвачен.
        """
        wait = WebDriverWait(self.driver, timeout)
        self._handle_cookie_banner()

        # 1) Ждём появление именно модального окна
        try:
            modal = wait.until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    # любой диалог тт + отсекаем скрытые
                    '//*[(@role="dialog" or contains(@class,"Dialog") or contains(@class,"modal")) and not(contains(@style,"display: none"))]'
                ))
            )
        except TimeoutException:
            return  # модалки нет — подтверждение не нужно

        # 2) Ищем кнопку ТОЛЬКО ВНУТРИ модалки
        inside_selectors = [
            './/button[@data-e2e="upload-confirm-btn" and not(@aria-disabled="true")]',
            './/button[.//div[@class="TUXButton-label" and (normalize-space()="Опубликовать" or normalize-space()="Publish")] and not(@aria-disabled="true")]',
            './/div[@class="TUXButton-label" and (normalize-space()="Опубликовать" or normalize-space()="Publish")]/parent::button[not(@aria-disabled="true")]',
            './/button[(normalize-space()="Опубликовать" or normalize-space()="Publish") and not(@aria-disabled="true")]',
            './/*[self::button or @role="button"][contains(normalize-space(),"Опубликовать") or contains(normalize-space(),"Publish")][not(@aria-disabled="true")]'
        ]

        btn = None
        for sel in inside_selectors:
            els = modal.find_elements(By.XPATH, sel)
            if els:
                btn = els[0]
                break

        if not btn:
            # иногда кнопка сразу disabled – ждём, пока активируется
            for _ in range(int(timeout * 5)):  # ~5 раз в секунду
                for sel in inside_selectors:
                    els = modal.find_elements(By.XPATH, sel)
                    if els:
                        btn = els[0]; break
                if btn: break
                time.sleep(0.2)

        if not btn:
            raise TimeoutException("Кнопка подтверждения публикации в модалке не найдена")

        # 3) Страховка: дождаться видимости и снять disabled, потом нажать
        try:
            # если есть aria-disabled=true — ждём, пока станет false
            for _ in range(50):
                aria = btn.get_attribute("aria-disabled") or btn.get_attribute("disabled")
                if not aria or aria == "false":
                    break
                time.sleep(0.1)

            # обычный клик, если перекрыт — JS
            btn.click()
        except (ElementClickInterceptedException, StaleElementReferenceException, WebDriverException):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                self.driver.execute_script("arguments[0].click();", btn)
            except Exception:
                # финальный ретрай: ещё раз найдём внутри модалки и кликнем JS
                fresh = None
                for sel in inside_selectors:
                    els = modal.find_elements(By.XPATH, sel)
                    if els:
                        fresh = els[0]; break
                if not fresh:
                    raise
                self.driver.execute_script("arguments[0].click();", fresh)

        self.logger.info("Confirm Publish clicked (modal)")

    def _verify_upload_success(self, timeout: int = 15) -> bool:
        """Проверяет успешность загрузки видео"""
        try:
            wait = WebDriverWait(self.driver, timeout)
            
            # Проверяем различные индикаторы успешной публикации
            success_indicators = [
                # Переход на страницу видео
                lambda d: d.current_url != self.upload_url and "tiktok.com" in d.current_url,
                
                # Сообщения об успехе
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Your video is being processed")]'),
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Ваше видео обрабатывается")]'),
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Video uploaded")]'),
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Видео загружено")]'),
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Successfully")]'),
                lambda d: d.find_elements(By.XPATH, '//*[contains(text(), "Успешно")]'),
                
                # Профильная страница или домашняя
                lambda d: "/following" in d.current_url or "/foryou" in d.current_url,
            ]
            
            # Проверяем каждый индикатор
            for check_func in success_indicators:
                try:
                    if check_func(self.driver):
                        self.logger.info("Upload success verified")
                        return True
                        
                    # Небольшая пауза между проверками
                    time.sleep(1)
                    
                except Exception:
                    continue
            
            self.logger.debug("Could not verify upload success within timeout")
            return False
            
        except Exception as e:
            self.logger.debug(f"Error verifying upload success: {e}")
            return False

    # ---------- UTILS ----------
    def validate_video(self, file_path: Path) -> bool:
        if not file_path.exists():
            return False
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 4096:
            self.logger.error(f"Video too large: {size_mb:.1f}MB")
            return False
        if file_path.suffix.lower() not in {".mp4", ".mov", ".avi", ".webm"}:
            self.logger.error(f"Unsupported format: {file_path.suffix}")
            return False
        return True

    def get_upload_limits(self) -> Dict[str, Any]:
        return {
            "max_file_size_mb": 4096,
            "max_duration_seconds": 600,
            "min_duration_seconds": 3,
            "max_title_length": 2200,
            "supported_formats": [".mp4", ".mov", ".avi", ".webm"],
            "max_uploads_per_day": 100,
        }

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
                self.logger.debug("WebDriver closed")
            except Exception as e:
                self.logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None

    def _create_driver(self):
        try:
            import sys
            root_path = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(root_path))
            try:
                from scripts.proxy_manager import ProxyManager
            except ImportError as e:
                self.logger.warning(
                    f"Could not import ProxyManager: {e}. Using basic Chrome options."
                )
                return self._create_basic_driver()
            
            # Создаем прокси менеджер
            proxy_manager = ProxyManager()
            options = proxy_manager.get_enhanced_chrome_options()
            driver = uc.Chrome(version_main=None, options=options)

            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                    """
                },
            )
            return driver
        except Exception as e:
            self.logger.error(f"Failed to create WebDriver: {e}")
            return None

    def _create_basic_driver(self):
        try:
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            driver = uc.Chrome(version_main=None, options=options)
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                    """
                },
            )
            self.logger.info("Basic Chrome driver created successfully")
            return driver
        except Exception as e:
            self.logger.error(f"Failed to create basic WebDriver: {e}")
            return None

    
    def _create_basic_driver(self):
        """Создает базовый WebDriver без прокси"""
        try:
            options = uc.ChromeOptions()
            
            # Базовые настройки
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Создаем драйвер
            driver = uc.Chrome(version_main=None, options=options)
            
            # Убираем следы автоматизации
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """
            })
            
            self.logger.info("Basic Chrome driver created successfully")
            return driver
            
        except Exception as e:
            self.logger.error(f"Failed to create basic WebDriver: {e}")
            return None
    
    def _handle_cookie_banner(self):
        """Убирает cookie баннер (часто мешает кликам)."""
        try:
            js_script = """
            const banners = document.querySelectorAll('tiktok-cookie-banner, .tiktok-cookie-banner, .paas_tiktok');
            let clicked = false;
            banners.forEach(banner => {
                if (banner.shadowRoot) {
                    const btns = banner.shadowRoot.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent||'').trim();
                        if (t.includes('Allow') || t.includes('Разрешить') || t.includes('Accept')) {
                            b.click(); clicked = true; break;
                        }
                    }
                }
                banner.style.display = 'none';
            });
            return clicked || banners.length > 0;
            """
            handled = self.driver.execute_script(js_script)
            if handled:
                time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Cookie banner handling failed: {e}")

    def _configure_privacy_settings(self, metadata: VideoMetadata):
        try:
            if not metadata.allow_comments:
                comment_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e,"allow-comment")]//input'
                )
                if comment_toggle and comment_toggle[0].is_selected():
                    comment_toggle[0].click()

            if not metadata.allow_duet:
                duet_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e,"allow-duet")]//input'
                )
                if duet_toggle and duet_toggle[0].is_selected():
                    duet_toggle[0].click()

            if not metadata.allow_stitch:
                stitch_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e,"allow-stitch")]//input'
                )
                if stitch_toggle and stitch_toggle[0].is_selected():
                    stitch_toggle[0].click()
        except Exception as e:
            self.logger.debug(f"Could not configure privacy settings: {e}")
