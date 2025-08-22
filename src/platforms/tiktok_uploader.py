import os
import time
import pickle
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import logging

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from ..core.platform_base import Platform, VideoMetadata, UploadResult, UploadStatus

class TikTokUploader(Platform):
    """Загрузчик видео в TikTok"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        super().__init__(config, logger)
        self.driver = None
        self.upload_url = "https://www.tiktok.com/upload"
        self.max_title_length = 2200
        
    def authenticate(self) -> bool:
        """Аутентификация через cookies"""
        try:
            cookies_path = self.config.get('cookies_path')
            if not cookies_path or not Path(cookies_path).exists():
                self.logger.error(f"Cookies file not found: {cookies_path}")
                return False
            
            # Создаем драйвер
            self.driver = self._create_driver()
            if not self.driver:
                return False
            
            # Переходим на TikTok и загружаем cookies
            self.driver.get("https://www.tiktok.com/")
            time.sleep(3)
            
            with open(cookies_path, "rb") as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.debug(f"Could not add cookie: {e}")
            
            # Обновляем страницу для применения cookies
            self.driver.refresh()
            time.sleep(5)
            
            # Проверяем, что мы авторизованы
            try:
                # Ищем элементы, которые появляются только у авторизованных пользователей
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.XPATH, "//span[contains(@class, 'avatar')]") or
                             d.find_elements(By.XPATH, "//div[contains(@data-e2e, 'nav-profile')]")
                )
                self.logger.info("Successfully authenticated to TikTok")
                return True
                
            except TimeoutException:
                self.logger.warning("Could not verify TikTok authentication")
                # Продолжаем, возможно аутентификация есть
                return True
                
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
    
    def upload_video(self, metadata: VideoMetadata) -> UploadResult:
        """Загружает видео в TikTok"""
        result = UploadResult(
            success=False,
            platform=self.platform_name,
            status=UploadStatus.PENDING
        )
        
        try:
            # Проверяем драйвер
            if not self.driver:
                if not self.authenticate():
                    result.message = "Authentication failed"
                    result.status = UploadStatus.FAILED
                    return result
            
            # Валидируем видео
            if not self.validate_video(metadata.file_path):
                result.message = "Video validation failed"
                result.status = UploadStatus.FAILED
                return result
            
            # Валидируем заголовок
            if len(metadata.title) > self.max_title_length:
                result.message = f"Title too long (max {self.max_title_length} characters)"
                result.status = UploadStatus.FAILED
                return result
            
            result.status = UploadStatus.UPLOADING
            self.logger.info(f"Starting upload: {metadata.file_path.name}")
            
            # Переходим на страницу загрузки
            self.driver.get(self.upload_url)
            time.sleep(3)
            
            # Убираем cookie баннер если есть
            self._handle_cookie_banner()
            
            # Находим input для файла
            wait = WebDriverWait(self.driver, 60)
            upload_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
            )
            
            # Загружаем файл
            upload_input.send_keys(str(metadata.file_path.absolute()))
            self.logger.info("Video file uploaded, waiting for processing...")
            
            # Ждем обработки видео
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Загружено")]')),
                        EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Uploaded")]')),
                        EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "upload-success")]'))
                    )
                )
                self.logger.info("Video processed successfully")
            except TimeoutException:
                result.message = "Video processing timeout"
                result.status = UploadStatus.FAILED
                return result
            
            # Добавляем заголовок
            try:
                caption_input = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//div[@contenteditable="true"]'))
                )
                
                # Очищаем поле и вводим заголовок
                ActionChains(self.driver).move_to_element(caption_input).click().perform()
                time.sleep(1)
                
                # Очищаем существующий текст
                caption_input.send_keys(Keys.CONTROL + "a")
                caption_input.send_keys(Keys.BACKSPACE)
                
                # Вводим новый заголовок
                caption_input.send_keys(metadata.title)
                
                self.logger.info(f"Title added: {metadata.title[:50]}...")
                
            except Exception as e:
                self.logger.warning(f"Could not set title: {e}")
            
            # Настройки конфиденциальности
            self._configure_privacy_settings(metadata)
            
            # Публикуем видео
            try:
                publish_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[@data-e2e="post_video_button"]'))
                )
                
                time.sleep(2)  # Небольшая пауза перед публикацией
                publish_button.click()
                
                self.logger.info("Publish button clicked")
                
                # Ждем подтверждения публикации
                time.sleep(10)
                
                result.success = True
                result.status = UploadStatus.COMPLETED
                result.message = f"Successfully uploaded: {metadata.file_path.name}"
                
                # Пытаемся получить URL видео (опционально)
                try:
                    current_url = self.driver.current_url
                    if "tiktok.com" in current_url and current_url != self.upload_url:
                        result.url = current_url
                except:
                    pass
                
            except Exception as e:
                result.message = f"Failed to publish: {e}"
                result.status = UploadStatus.FAILED
                
        except Exception as e:
            result.message = f"Upload failed: {e}"
            result.status = UploadStatus.FAILED
            self.logger.error(f"Upload error: {e}")
        
        return result
    
    def validate_video(self, file_path: Path) -> bool:
        """Проверяет совместимость видео с TikTok"""
        if not file_path.exists():
            return False
        
        # Проверяем размер файла (макс 4GB)
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 4096:
            self.logger.error(f"Video too large: {size_mb:.1f}MB")
            return False
        
        # Проверяем расширение
        allowed_extensions = {'.mp4', '.mov', '.avi', '.webm'}
        if file_path.suffix.lower() not in allowed_extensions:
            self.logger.error(f"Unsupported format: {file_path.suffix}")
            return False
        
        return True
    
    def get_upload_limits(self) -> Dict[str, Any]:
        """Возвращает лимиты TikTok"""
        return {
            'max_file_size_mb': 4096,
            'max_duration_seconds': 600,  # 10 minutes
            'min_duration_seconds': 3,
            'max_title_length': 2200,
            'supported_formats': ['.mp4', '.mov', '.avi', '.webm'],
            'max_uploads_per_day': 100  # приблизительно
        }
    
    def cleanup(self):
        """Очищает ресурсы"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.debug("WebDriver closed")
            except Exception as e:
                self.logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
    
    def _create_driver(self):
        """Создает WebDriver с оптимальными настройками"""
        try:
            # Импортируем proxy_manager из корневой папки
            import sys
            from pathlib import Path
            root_path = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(root_path))
            
            try:
                from proxy_manager import ProxyManager
            except ImportError as e:
                self.logger.warning(f"Could not import ProxyManager: {e}. Using basic Chrome options.")
                return self._create_basic_driver()
            
            # Создаем прокси менеджер
            proxy_manager = ProxyManager()
            
            # Получаем настройки Chrome
            options = proxy_manager.get_enhanced_chrome_options()
            
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
            
            return driver
            
        except Exception as e:
            self.logger.error(f"Failed to create WebDriver: {e}")
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
        """Убирает cookie баннер"""
        try:
            # JavaScript для обработки cookie баннера
            js_script = """
            const banners = document.querySelectorAll('tiktok-cookie-banner, .tiktok-cookie-banner, .paas_tiktok');
            banners.forEach(banner => {
                if (banner.shadowRoot) {
                    const acceptBtn = banner.shadowRoot.querySelector('button');
                    if (acceptBtn && (acceptBtn.textContent.includes('Allow') || acceptBtn.textContent.includes('Разрешить'))) {
                        acceptBtn.click();
                        return true;
                    }
                }
                banner.style.display = 'none';
            });
            return banners.length > 0;
            """
            
            result = self.driver.execute_script(js_script)
            if result:
                self.logger.debug("Cookie banner handled")
                time.sleep(2)
                
        except Exception as e:
            self.logger.debug(f"Cookie banner handling failed: {e}")
    
    def _configure_privacy_settings(self, metadata: VideoMetadata):
        """Настраивает приватность видео"""
        try:
            # Настройки комментариев
            if not metadata.allow_comments:
                comment_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e, "allow-comment")]//input'
                )
                if comment_toggle and comment_toggle[0].is_selected():
                    comment_toggle[0].click()
            
            # Настройки дуэтов
            if not metadata.allow_duet:
                duet_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e, "allow-duet")]//input'
                )
                if duet_toggle and duet_toggle[0].is_selected():
                    duet_toggle[0].click()
            
            # Настройки стежков
            if not metadata.allow_stitch:
                stitch_toggle = self.driver.find_elements(
                    By.XPATH, '//div[contains(@data-e2e, "allow-stitch")]//input'
                )
                if stitch_toggle and stitch_toggle[0].is_selected():
                    stitch_toggle[0].click()
            
        except Exception as e:
            self.logger.debug(f"Could not configure privacy settings: {e}")