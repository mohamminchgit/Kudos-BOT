import json
import logging
import sqlite3
import asyncio
import config
import sys
import codecs
import os
import importlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, InlineQueryHandler
from telegram.error import NetworkError, Conflict, TimedOut, TelegramError
from telegram.request import HTTPXRequest
import time

# وارد کردن هندلرهای مدولار جدید
from src.handlers.start_handler import start
from src.handlers.callback_handler import menu_callback
from src.handlers.message_handler import handle_message
from src.handlers.inline_handler import handle_inline_query

# وارد کردن ماژول راهنما
from src.services import help

# وارد کردن ماژول هوش مصنوعی برای سازگاری با کد قدیمی (موقتاً غیرفعال)
try:
    from src.services import ai
    AI_MODULE_AVAILABLE = True
    logging.info("ماژول هوش مصنوعی فعال شده است.")
except ImportError:
    logging.error("ماژول هوش مصنوعی (ai.py) یافت نشد. برخی از قابلیت‌های مرتبط غیرفعال خواهند شد.")
    AI_MODULE_AVAILABLE = False

# تنظیم لاگر با پشتیبانی از UTF-8
if sys.platform == 'win32':
    # تنظیم لاگر برای ویندوز با پشتیبانی از UTF-8
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # فایل لاگ با انکودینگ UTF-8
    file_handler = logging.FileHandler("bot.log", encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # خروجی کنسول با UTF-8
    console_handler = logging.StreamHandler(codecs.getwriter('utf-8')(sys.stdout.buffer))
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
else:
    # تنظیم لاگر برای سیستم‌های غیر ویندوز
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)

# اتصال به دیتابیس
conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# تابع کمکی برای دریافت اتصال به دیتابیس
def get_db_connection():
    """ایجاد و برگرداندن اتصال به دیتابیس"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# تابع برای اجرای کوئری با connection جدید (برای جلوگیری از مشکل با اتصال اصلی)
def execute_db_query(query, params=None, fetchone=False, commit=False):
    """اجرای کوئری SQL با یک اتصال جدید
    
    Args:
        query (str): کوئری SQL
        params (tuple, optional): پارامترهای کوئری
        fetchone (bool, optional): آیا فقط یک نتیجه برگرداند
        commit (bool, optional): آیا تغییرات را کامیت کند
    
    Returns:
        list or dict: نتیجه کوئری
    """
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
            
        if commit:
            conn.commit()
            return True
            
        if fetchone:
            return c.fetchone()
        else:
            return c.fetchall()
            
    except Exception as e:
        logger.error(f"خطا در اجرای کوئری: {e}")
        return None
    finally:
        if conn:
            conn.close()

async def main():
    """تابع اصلی ربات"""
    # تنظیم پارامترهای اتصال و زمان انتظار
    request_kwargs = {
        'http_version': '1.1',
        'read_timeout': 60,
        'write_timeout': 60,
        'connect_timeout': 30,
        'pool_timeout': 30
    }
    
    # ایجاد و پیکربندی برنامه با تنظیمات شبکه
    app = Application.builder().token(config.BOT_TOKEN)\
        .request(HTTPXRequest(**request_kwargs))\
        .get_updates_request(HTTPXRequest(**request_kwargs))\
        .build()
    
    # افزودن مدیریت خطا
    app.add_error_handler(error_handler)
    
    # افزودن هندلرها با هندلرهای مدولار جدید
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # اضافه کردن هندلر برای inline query
    app.add_handler(InlineQueryHandler(handle_inline_query))
      # اجرای ربات
    print("Bot started successfully...")
    logger.info("ربات با موفقیت راه‌اندازی شد")
    
    await app.initialize()
    await app.start()
    
    # راه‌اندازی سیستم دریافت به‌روزرسانی‌ها با مدیریت خطا
    await app.updater.start_polling(
        poll_interval=2.0,  # کاهش فاصله زمانی بین درخواست‌ها
        timeout=15,  # کاهش مدت زمان timeout برای تشخیص سریعتر قطعی اتصال
        bootstrap_retries=5,  # تعداد تلاش‌های مجدد در هنگام راه‌اندازی
        allowed_updates=Update.ALL_TYPES,  # دریافت همه نوع به‌روزرسانی
        drop_pending_updates=False  # دریافت به‌روزرسانی‌های معلق
    )
    
    # راه‌اندازی وظیفه keep-alive
    asyncio.create_task(keep_alive(app.bot))
    
    try:
        # حلقه بی‌نهایت برای نگه داشتن برنامه در حال اجرا
        logger.info("ربات در حال کار است")
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        # در صورت قطع برنامه، ربات را به درستی متوقف می‌کنیم
        logger.info("دستور توقف ربات دریافت شد")
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
    finally:
        # بستن ربات
        logger.info("در حال بستن ربات...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("ربات با موفقیت بسته شد")

async def keep_alive(bot):
    """ارسال درخواست‌های منظم برای حفظ اتصال"""
    ping_count = 0
    ping_interval = 120  # هر 2 دقیقه یک بار پینگ
    update_status_interval = 5  # هر 5 پینگ یکبار بروزرسانی فایل وضعیت
    
    while True:
        try:
            # ارسال یک درخواست ساده به API تلگرام
            logger.debug("ارسال درخواست keep-alive...")
            await bot.get_me()
            logger.debug("درخواست keep-alive با موفقیت انجام شد")
            
            # بروزرسانی فایل وضعیت برای ارتباط با bot_runner
            ping_count += 1
            if ping_count % update_status_interval == 0:
                try:
                    import json
                    import time
                    import os
                    
                    status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner_status.json")
                    
                    # خواندن و بروزرسانی فایل وضعیت
                    try:
                        if os.path.exists(status_path):
                            with open(status_path, 'r+', encoding='utf-8') as f:
                                data = json.load(f)
                                data['last_bot_ping'] = time.time()
                                data['bot_alive'] = True
                                f.seek(0)
                                f.truncate()
                                json.dump(data, f, indent=2, ensure_ascii=False)
                        else:
                            with open(status_path, 'w', encoding='utf-8') as f:
                                json.dump({
                                    'bot_alive': True,
                                    'last_bot_ping': time.time()
                                }, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        logger.warning(f"خطا در بروزرسانی فایل وضعیت: {e}")
                except Exception as file_error:
                    logger.warning(f"خطا در مدیریت فایل وضعیت: {file_error}")
                    
        except Exception as e:
            logger.warning(f"خطا در درخواست keep-alive: {e}")
        
        # انتظار برای اجرای مجدد
        await asyncio.sleep(ping_interval)

async def error_handler(update, context):
    """مدیریت خطاهای ربات"""
    # استخراج اطلاعات خطا
    error = context.error
    
    # ثبت خطا در لاگ
    logger.error(f"خطا در پردازش به‌روزرسانی: {error}")
    logger.error(f"اطلاعات خطا: {context.error.__class__.__name__}: {context.error}")
    
    # مدیریت خطاهای شبکه
    if isinstance(error, (NetworkError, Conflict, TimedOut, TelegramError)):
        logger.warning(f"خطای شبکه تشخیص داده شد: {error}")
        
        # سعی می‌کنیم مجدداً متصل شویم
        try:
            # در صورت نیاز، می‌توانید اینجا کد خاصی برای بازیابی اضافه کنید
            pass
        except Exception as reconnect_error:
            logger.error(f"خطا در اتصال مجدد: {reconnect_error}")
    
    # اطلاع‌رسانی به کاربران در صورت لزوم
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "متأسفانه خطایی رخ داده است. لطفاً دوباره تلاش کنید."
            )
        except Exception as notify_error:
            logger.error(f"خطا در اطلاع‌رسانی به کاربر: {notify_error}")

if __name__ == "__main__":
    asyncio.run(main())
