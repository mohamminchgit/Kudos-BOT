#!/usr/bin/env python3
"""
🚀 Bot Runner - رانر خودکار ربات کودوز

این اسکریپت ربات را به صورت دائمی اجرا می‌کند و در صورت خرابی،
آن را مجدداً راه‌اندازی می‌کند.

ویژگی‌ها:
- مانیتورینگ وضعیت ربات
- ری‌استارت خودکار در صورت خرابی
- لاگ‌گیری کامل
- تایم‌اوت هوشمند
- پاکسازی session‌های معلق
"""

import os
import sys
import time
import signal
import subprocess
import logging
import threading
from datetime import datetime
from pathlib import Path
import psutil
import json

# تنظیم مسیر
BOT_DIR = Path(__file__).parent.absolute()
BOT_SCRIPT = BOT_DIR / "bot.py"
LOG_DIR = BOT_DIR / "logs"
RUNNER_LOG = LOG_DIR / "runner.log"

# ایجاد پوشه لاگ
LOG_DIR.mkdir(exist_ok=True)

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RUNNER_LOG, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BotRunner:
    def __init__(self):
        self.bot_process = None
        self.is_running = False
        self.restart_count = 0
        self.last_restart = None
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # تنظیمات
        self.RESTART_DELAY = 5  # ثانیه
        self.HEALTH_CHECK_INTERVAL = 10  # ثانیه - کاهش فاصله بررسی
        self.MAX_RESTARTS_PER_HOUR = 20  # افزایش تعداد مجاز ری‌استارت
        self.PROCESS_TIMEOUT = 5  # ثانیه برای تایم‌اوت
        self.PING_INTERVAL = 120  # هر 2 دقیقه یک بار ارسال پینگ به پروسه
        
        # مدیریت signal
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """مدیریت سیگنال‌های خروج"""
        logger.info(f"🛑 دریافت سیگنال {signum}. در حال توقف رانر...")
        self.stop_runner()
        
    def cleanup_zombie_processes(self):
        """پاکسازی پروسه‌های معلق و session‌های باز"""
        try:
            # پیدا کردن پروسه‌های python که bot.py را اجرا می‌کنند
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if (proc.info['name'] and 'python' in proc.info['name'].lower() and 
                        proc.info['cmdline'] and 'bot.py' in ' '.join(proc.info['cmdline'])):
                        
                        logger.warning(f"🧹 پاکسازی پروسه معلق: PID {proc.info['pid']}")
                        proc.kill()
                        proc.wait(timeout=3)
                        killed_count += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    continue
                    
            if killed_count > 0:
                logger.info(f"🧹 تعداد {killed_count} پروسه معلق پاکسازی شد")
                time.sleep(2)  # فرصت برای پاکسازی کامل
                
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی پروسه‌ها: {e}")
    
    def start_bot(self):
        """شروع ربات"""
        try:
            # پاکسازی قبل از شروع
            self.cleanup_zombie_processes()
            
            logger.info("🚀 در حال شروع ربات...")
            
            # اجرای ربات
            self.bot_process = subprocess.Popen(
                [sys.executable, str(BOT_SCRIPT)],
                cwd=BOT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # انتظار کوتاه برای اطمینان از شروع
            time.sleep(3)
            
            if self.bot_process.poll() is None:
                logger.info(f"✅ ربات با موفقیت شروع شد. PID: {self.bot_process.pid}")
                self.is_running = True
                self.restart_count += 1
                self.last_restart = datetime.now()
                return True
            else:
                stdout, stderr = self.bot_process.communicate()
                logger.error(f"❌ ربات نتوانست شروع شود:")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ خطا در شروع ربات: {e}")
            return False
    
    def stop_bot(self):
        """توقف ربات"""
        if self.bot_process:
            try:
                logger.info("🛑 در حال توقف ربات...")
                
                # ابتدا سعی در توقف مهربانانه
                self.bot_process.terminate()
                
                try:
                    self.bot_process.wait(timeout=self.PROCESS_TIMEOUT)
                    logger.info("✅ ربات با موفقیت متوقف شد")
                except subprocess.TimeoutExpired:
                    # اگر پاسخ نداد، به زور متوقف کن
                    logger.warning("⚠️ ربات پاسخ نداد. در حال kill کردن...")
                    self.bot_process.kill()
                    self.bot_process.wait()
                    logger.info("✅ ربات به زور متوقف شد")
                    
            except Exception as e:
                logger.error(f"❌ خطا در توقف ربات: {e}")
            finally:
                self.bot_process = None
                self.is_running = False
    
    def is_bot_healthy(self):
        """بررسی سلامت ربات"""
        if not self.bot_process:
            return False
            
        # بررسی اینکه پروسه هنوز زنده است
        if self.bot_process.poll() is not None:
            return False
            
        # بررسی اینکه پروسه واقعاً کار می‌کند (نه zombie)
        try:
            proc = psutil.Process(self.bot_process.pid)
            if proc.status() == psutil.STATUS_ZOMBIE:
                logger.warning("⚠️ ربات به حالت zombie رفته")
                return False
                
            # بررسی مصرف CPU برای تشخیص حالت خواب یا قفل شدن
            try:
                cpu_percent = proc.cpu_percent(interval=0.5)
                memory_percent = proc.memory_percent()
                
                # اگر مصرف CPU خیلی پایین باشد، ممکن است به خواب رفته باشد
                if cpu_percent < 0.1:
                    # بررسی زمان آخرین پینگ در فایل وضعیت
                    status_file = BOT_DIR / "runner_status.json"
                    if status_file.exists():
                        try:
                            with open(status_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                if 'last_ping' in data:
                                    last_ping = data['last_ping']
                                    current_time = time.time()
                                    # اگر بیش از 5 دقیقه از آخرین پینگ گذشته باشد، نیاز به ری‌استارت است
                                    if (current_time - last_ping) > 300:
                                        logger.warning("⚠️ ربات احتمالاً به خواب رفته است (عدم پاسخ به پینگ)")
                                        return False
                        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                            logger.error(f"❌ خطا در خواندن فایل وضعیت: {e}")
                
                logger.debug(f"📊 وضعیت ربات: CPU: {cpu_percent:.1f}%, RAM: {memory_percent:.1f}%")
            except Exception as e:
                logger.error(f"❌ خطا در بررسی مصرف منابع: {e}")
                
        except psutil.NoSuchProcess:
            return False
            
        return True
    
    def should_restart(self):
        """بررسی اینکه آیا باید ری‌استارت کرد"""
        # محدودیت تعداد ری‌استارت در ساعت
        if self.last_restart:
            hours_since_restart = (datetime.now() - self.last_restart).total_seconds() / 3600
            if hours_since_restart < 1 and self.restart_count >= self.MAX_RESTARTS_PER_HOUR:
                logger.error(f"❌ تعداد ری‌استارت بیش از حد مجاز ({self.MAX_RESTARTS_PER_HOUR} در ساعت)")
                return False
        
        return True
    
    def monitor_bot(self):
        """مانیتورینگ مداوم ربات"""
        logger.info("👁️ شروع مانیتورینگ ربات...")
        
        last_ping_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # بررسی سلامت بات
                if not self.is_bot_healthy():
                    logger.warning("⚠️ ربات سالم نیست!")
                    
                    if self.is_running:
                        logger.info("🔄 در حال ری‌استارت ربات...")
                        self.stop_bot()
                        
                        if self.should_restart():
                            time.sleep(self.RESTART_DELAY)
                            if not self.start_bot():
                                logger.error("❌ نتوانست ربات را مجدداً شروع کند")
                        else:
                            logger.error("❌ نمی‌توان ری‌استارت کرد. رانر متوقف می‌شود.")
                            break
                            
                else:
                    # ربات سالم است
                    if not self.is_running:
                        self.is_running = True
                        
                    # ارسال سیگنال ping به پروسه برای جلوگیری از به خواب رفتن
                    current_time = time.time()
                    if (current_time - last_ping_time) >= self.PING_INTERVAL:
                        self._ping_bot_process()
                        last_ping_time = current_time
                        
                # انتظار قبل از بررسی بعدی
                self.stop_event.wait(self.HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ خطا در مانیتورینگ: {e}")
                self.stop_event.wait(5)
                
    def _ping_bot_process(self):
        """ارسال پینگ به پروسه بات برای جلوگیری از به خواب رفتن"""
        try:
            if self.bot_process and self.bot_process.poll() is None:
                logger.debug("🔔 ارسال پینگ به پروسه بات...")
                
                # بررسی وجود فایل وضعیت
                status_file = BOT_DIR / "runner_status.json"
                if status_file.exists():
                    # بروزرسانی تایم‌استمپ در فایل وضعیت
                    try:
                        with open(status_file, 'r+', encoding='utf-8') as f:
                            data = json.load(f)
                            data['last_ping'] = time.time()
                            f.seek(0)
                            f.truncate()
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        logger.debug("✅ پینگ با موفقیت ارسال شد")
                    except Exception as e:
                        logger.error(f"❌ خطا در بروزرسانی فایل وضعیت: {e}")
                else:
                    # ایجاد فایل وضعیت
                    with open(status_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'running': self.is_running,
                            'restart_count': self.restart_count,
                            'last_restart': self.last_restart.isoformat() if self.last_restart else None,
                            'pid': self.bot_process.pid if self.bot_process else None,
                            'last_ping': time.time()
                        }, f, indent=2, ensure_ascii=False)
                    logger.debug("✅ فایل وضعیت ایجاد و پینگ ثبت شد")
        except Exception as e:
            logger.error(f"❌ خطا در ارسال پینگ به پروسه بات: {e}")
            
    def get_status(self):
        """دریافت وضعیت فعلی"""
        status = {
            'running': self.is_running,
            'restart_count': self.restart_count,
            'last_restart': self.last_restart.isoformat() if self.last_restart else None,
            'pid': self.bot_process.pid if self.bot_process else None
        }
        return status
    
    def save_status(self):
        """ذخیره وضعیت در فایل"""
        try:
            status_file = BOT_DIR / "runner_status.json"
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(self.get_status(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ خطا در ذخیره وضعیت: {e}")
    
    def start_runner(self):
        """شروع رانر"""
        logger.info("🎯 شروع Bot Runner...")
        logger.info(f"📁 پوشه کاری: {BOT_DIR}")
        logger.info(f"📝 فایل لاگ: {RUNNER_LOG}")
        
        # شروع ربات
        if not self.start_bot():
            logger.error("❌ نتوانست ربات را شروع کند. خروج از رانر.")
            return False
        
        # شروع مانیتورینگ در thread جداگانه
        self.monitor_thread = threading.Thread(target=self.monitor_bot, daemon=True)
        self.monitor_thread.start()
        
        try:
            # حلقه اصلی
            while not self.stop_event.is_set():
                self.save_status()
                self.stop_event.wait(30)  # هر 30 ثانیه وضعیت را ذخیره کن
                
        except KeyboardInterrupt:
            logger.info("👋 درخواست توقف از کاربر...")
        
        return True
    
    def stop_runner(self):
        """توقف رانر"""
        logger.info("🛑 در حال توقف رانر...")
        
        self.stop_event.set()
        self.stop_bot()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("✅ رانر با موفقیت متوقف شد")

def main():
    """تابع اصلی"""
    print("🤖 Bot Runner - رانر خودکار ربات کودوز")
    print("=" * 50)
    
    # بررسی وجود فایل ربات
    if not BOT_SCRIPT.exists():
        print(f"❌ فایل ربات یافت نشد: {BOT_SCRIPT}")
        sys.exit(1)
    
    # ایجاد رانر
    runner = BotRunner()
    
    try:
        success = runner.start_runner()
        if success:
            print("✅ رانر با موفقیت اجرا شد")
        else:
            print("❌ رانر نتوانست اجرا شود")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        sys.exit(1)
    finally:
        runner.stop_runner()

if __name__ == "__main__":
    main()
