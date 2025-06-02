import os
import sys
import psutil
import time
import subprocess

def kill_bot_processes():
    """کشتن همه فرایندهای پایتون که در حال اجرای بات هستند"""
    print("در حال جستجوی فرایندهای بات تلگرام...")
    bot_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # بررسی فرایندهای پایتون که bot.py را اجرا می‌کنند
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info['cmdline']
                if cmdline and any('bot.py' in cmd for cmd in cmdline):
                    bot_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # کشتن فرایندها
    if bot_processes:
        print(f"تعداد {len(bot_processes)} فرایند بات تلگرام یافت شد. در حال متوقف کردن...")
        for proc in bot_processes:
            try:
                proc.kill()
                print(f"فرایند با PID {proc.pid} متوقف شد.")
            except psutil.NoSuchProcess:
                pass
        
        # اطمینان از توقف همه فرایندها
        time.sleep(2)
        print("همه فرایندهای بات با موفقیت متوقف شدند.")
    else:
        print("هیچ فرایند بات تلگرامی در حال اجرا نیست.")
    
    return len(bot_processes)

def restart_bot():
    """راه‌اندازی مجدد بات تلگرام"""
    print("در حال راه‌اندازی مجدد بات تلگرام...")
    
    # اجرای بات در پس‌زمینه
    if sys.platform == 'win32':
        subprocess.Popen(['python', 'bot.py'], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(['python3', 'bot.py'], start_new_session=True)
    
    print("بات تلگرام با موفقیت راه‌اندازی مجدد شد.")

if __name__ == "__main__":
    # اول همه فرایندهای موجود را متوقف کن
    killed = kill_bot_processes()
    
    # اگر کاربر خواسته باشد، بات را دوباره راه‌اندازی کن
    if len(sys.argv) > 1 and sys.argv[1] == '--restart':
        restart_bot()
    elif killed > 0:
        answer = input("آیا می‌خواهید بات را مجدداً راه‌اندازی کنید؟ (y/n): ")
        if answer.lower() in ['y', 'yes', 'بله']:
            restart_bot()
    
    print("عملیات با موفقیت انجام شد.") 