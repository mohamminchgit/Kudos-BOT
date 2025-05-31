import os
import sys
import time
import logging
import subprocess
import codecs
from datetime import datetime

# تنظیم لاگ گذاری با انکودینگ UTF-8
if sys.platform == 'win32':
    # در ویندوز، مطمئن می‌شویم که فایل لاگ با UTF-8 نوشته می‌شود
    log_handler = logging.FileHandler("bot_runner.log", 'a', encoding='utf-8')
    
    # برای خروجی کنسول در ویندوز، از utf-8 استفاده می‌کنیم
    # تغییر کدپیج کنسول به UTF-8
    os.system('chcp 65001 > nul')
    
    # مطمئن می‌شویم که stdout و stderr با UTF-8 کار می‌کنند
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    
    # ایجاد StreamHandler برای کنسول
    console_handler = logging.StreamHandler(sys.stdout)
else:
    # در سیستم‌های غیر ویندوز، معمولاً مشکل انکودینگ وجود ندارد
    log_handler = logging.FileHandler("bot_runner.log")
    console_handler = logging.StreamHandler()

# تنظیم فرمت لاگ
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# تنظیم لاگر
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

def kill_python_processes():
    """کشتن تمام فرآیندهای پایتون در حال اجرا"""
    try:
        logger.info("در حال متوقف کردن تمام فرآیندهای پایتون...")
        if sys.platform == 'win32':
            os.system('taskkill /f /im python.exe')
        else:
            os.system('pkill -f python')
        time.sleep(2)  # منتظر بمانید تا فرآیندها به طور کامل متوقف شوند
        logger.info("تمام فرآیندهای پایتون متوقف شدند")
    except Exception as e:
        logger.error(f"خطا در متوقف کردن فرآیندها: {e}")

def run_bot():
    """اجرای ربات و بازگرداندن کد خروجی"""
    try:
        logger.info("در حال راه‌اندازی ربات...")
        
        # در ویندوز، مطمئن می‌شویم که خروجی پروسس با UTF-8 خوانده می‌شود
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            process = subprocess.Popen(['python', 'bot.py'], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True,
                                      encoding='utf-8',
                                      startupinfo=startupinfo)
        else:
            process = subprocess.Popen(['python', 'bot.py'], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True)
        
        # منتظر خروجی فرآیند باشید
        stdout, stderr = process.communicate()
        
        if stderr:
            logger.error(f"خطا در اجرای ربات: {stderr}")
        
        return process.returncode
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        return 1

def main():
    """تابع اصلی برای اجرا و نظارت بر ربات"""
    max_restarts = 10
    restart_count = 0
    
    while restart_count < max_restarts:
        # ابتدا مطمئن شوید که هیچ نمونه‌ای از ربات در حال اجرا نیست
        kill_python_processes()
        
        # اجرای ربات
        start_time = datetime.now()
        exit_code = run_bot()
        end_time = datetime.now()
        run_duration = (end_time - start_time).total_seconds()
        
        if exit_code != 0:
            restart_count += 1
            logger.warning(f"ربات با کد خروجی {exit_code} متوقف شد. تلاش مجدد {restart_count}/{max_restarts}")
            
            # اگر ربات بیش از 1 ساعت اجرا شده بود، شمارشگر را ریست کنید
            if run_duration > 3600:
                restart_count = 0
                logger.info("شمارشگر راه‌اندازی مجدد ریست شد زیرا ربات بیش از یک ساعت اجرا شده بود")
            
            # قبل از تلاش مجدد کمی صبر کنید
            time.sleep(10)
        else:
            logger.info("ربات با موفقیت خاتمه یافت")
            break
    
    if restart_count >= max_restarts:
        logger.error("تعداد دفعات مجاز راه‌اندازی مجدد به پایان رسید. برنامه متوقف می‌شود.")

if __name__ == "__main__":
    logger.info("اسکریپت راه‌انداز ربات آغاز شد")
    main() 