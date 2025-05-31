import json
import logging
import sqlite3
import asyncio
import config
import sys
import codecs
import os # برای حذف فایل موقت کارت هدیه
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import NetworkError, Conflict, TimedOut, TelegramError
from telegram.request import HTTPXRequest

# وارد کردن ماژول کارت هدیه
import giftcard
# وارد کردن ماژول راهنما
import help

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

# ایجاد جداول مورد نیاز در صورت عدم وجود
def init_db():
    # جداول ترین‌ها در db_init.py ساخته می‌شوند
    pass

# اجرای تابع ایجاد دیتابیس
init_db()

# در بخش ایجاد جداول در db_init.py این کد را اضافه کنید:

# ایجاد جدول جامع سوالات ترین‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS master_top_questions (
    master_question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')

# لیست دسترسی‌های ادمین (مطابق با گزینه‌های پنل مدیریت)
ADMIN_PERMISSIONS = [
    ("admin_users", "مدیریت کاربران"),
    ("admin_transactions", "مدیریت تراکنش"),
    ("admin_stats", "آمار و گزارشات"),
    ("manage_admins", "مدیریت ادمین‌ها"),
    ("manage_questions", "مدیریت سوالات ترین‌ها"),
]

def get_or_create_user(user):
    c.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    return c.fetchone() is not None

def is_user_approved(user_id):
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return c.fetchone() is not None

def add_user(user):
    c.execute("INSERT INTO users (user_id, username, name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
    conn.commit()

def main_menu_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("🎁 ارسال کارت هدیه", callback_data="giftcard_start^"),
        InlineKeyboardButton("🎯 امتیازدهی به دیگران", callback_data="tovote^")]
    ]
    
    # دریافت فصل فعال
    active_season = get_active_season()
    
    # اضافه کردن دکمه ترین‌ها فقط اگر فصل فعالی وجود داشته باشد
    if active_season:
        season_id = active_season[0]
        season_name = active_season[1]
        
        # بررسی آیا کاربر در فصل جاری به سوالات ترین‌ها پاسخ داده است
        has_voted_all = False
        if user_id:
            c.execute("""
                SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
            """, (season_id,))
            total_questions = c.fetchone()[0]
            
            c.execute("""
                SELECT COUNT(*) FROM top_votes 
                WHERE user_id=? AND season_id=?
            """, (user_id, season_id))
            user_votes = c.fetchone()[0]
            
            has_voted_all = user_votes >= total_questions
        
        # اضافه کردن دکمه ترین‌ها با متن مناسب
        if has_voted_all:
            keyboard.append([InlineKeyboardButton(f"🏆 نتایج ترین‌های {season_name}", callback_data="top_results^")])
        else:
            keyboard.append([InlineKeyboardButton(f"🏆 ترین‌های {season_name}!", callback_data="top_vote^")])
    
    keyboard += [
        [InlineKeyboardButton("» پروفایل شما", callback_data="userprofile^"), InlineKeyboardButton("ردپای امتیازات", callback_data="historypoints^")],
        [InlineKeyboardButton("» راهنما", callback_data="help^"), InlineKeyboardButton("» پشتیبانی", url=config.SUPPORT_USERNAME)]
    ]
    
    # اضافه کردن دکمه پنل ادمین برای کاربران ادمین
    if user_id:
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            role, permissions = row
            if role == 'god' or permissions:
                keyboard.append([InlineKeyboardButton("🔐 پنل ادمین", callback_data="admin_panel^")])
    
    return InlineKeyboardMarkup(keyboard)

def get_all_users(exclude_id=None):
    if exclude_id:
        c.execute("SELECT user_id, name FROM users WHERE user_id != ?", (exclude_id,))
    else:
        c.execute("SELECT user_id, name FROM users")
    return c.fetchall()

def get_user_profile(user_id):
    c.execute("""
        SELECT u.*, 
            (SELECT SUM(t.amount) 
             FROM transactions t
             WHERE t.touser = u.user_id) AS total_received
        FROM users u
        WHERE u.user_id=?
    """, (user_id,))
    return c.fetchone()

def get_user_transactions(user_id, given=True, offset=0, limit=3, season_id=None):
    """دریافت تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND t.season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params + [limit, offset]
        c.execute(f"""
            SELECT t.amount, t.touser, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, params)
    else:
        params = [user_id] + params + [limit, offset]
        c.execute(f"""
            SELECT t.amount, t.user_id, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, params)
    return c.fetchall()

def count_user_transactions(user_id, given=True, season_id=None):
    """شمارش تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params
        c.execute(f"""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE user_id=?{season_filter}
        """, params)
    else:
        params = [user_id] + params
        c.execute(f"""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE touser=?{season_filter}
        """, params)
    return c.fetchone()[0]

def get_scoreboard():
    c.execute("""
        SELECT touser, SUM(amount) as total, u.name 
        FROM transactions t 
        LEFT JOIN users u ON t.touser = u.user_id 
        GROUP BY touser 
        ORDER BY total DESC LIMIT 10
    """)
    return c.fetchall()

def get_active_season():
    """دریافت فصل فعال"""
    try:
        c.execute("SELECT id, name, balance FROM season WHERE is_active=1 LIMIT 1")
        return c.fetchone()
    except sqlite3.OperationalError:
        # در صورت عدم وجود ستون created_at یا جدول
        logger.warning("مشکل در دسترسی به جدول season - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض

def get_all_seasons():
    """دریافت همه فصل‌ها"""
    print("Executing get_all_seasons function...")
    try:
        c.execute("SELECT id, name, balance, is_active FROM season ORDER BY id DESC")
        result = c.fetchall()
        print(f"get_all_seasons result: {result}")
        if not result:
            print("No seasons found in the database!")
        return result
    except Exception as e:
        print(f"Error in get_all_seasons: {e}")
        import traceback
        print(traceback.format_exc())
        return []

def get_all_top_questions():
    """دریافت همه سوالات ترین‌ها"""
    c.execute("SELECT question_id, text, is_active FROM top_questions ORDER BY question_id DESC")
    return c.fetchall()

def get_top_questions_for_season(season_id):
    """دریافت همه سوالات ترین‌های یک فصل خاص"""
    c.execute("SELECT question_id, text, is_active FROM top_questions WHERE season_id=? ORDER BY question_id DESC", (season_id,))
    return c.fetchall()

def add_master_top_question(text):
    """سوال را به لیست جامع سوالات ترین‌ها اضافه می‌کند، در صورت عدم وجود."""
    try:
        c.execute("INSERT OR IGNORE INTO master_top_questions (text) VALUES (?)", (text,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding to master_top_questions: {e}")
        return False

def add_season_top_question(season_id, question_text, is_active=1):
    """یک سوال ترین‌ها را برای فصل مشخص شده اضافه می‌کند و همچنین آن را به لیست جامع سوالات اضافه می‌کند."""
    if not add_master_top_question(question_text):
        # اگر نتوانست به مستر لیست اضافه کند (مثلا خطای دیتابیس)، ادامه نده
        return None 
    try:
        c.execute("""
            INSERT INTO top_questions (text, is_active, season_id)
            VALUES (?, ?, ?)
        """, (question_text, is_active, season_id))
        conn.commit()
        return c.lastrowid
    except Exception as e:
        logger.error(f"Error adding season top question for season {season_id}: {e}")
        return None

def update_top_question(question_id, text=None, is_active=None):
    """بروزرسانی سوال ترین‌ها"""
    if text is not None and is_active is not None:
        c.execute("UPDATE top_questions SET text=?, is_active=? WHERE question_id=?", (text, is_active, question_id))
    elif text is not None:
        c.execute("UPDATE top_questions SET text=? WHERE question_id=?", (text, question_id))
    elif is_active is not None:
        c.execute("UPDATE top_questions SET is_active=? WHERE question_id=?", (is_active, question_id))
    conn.commit()
    return True

def delete_top_question(question_id):
    """حذف سوال ترین‌ها"""
    c.execute("DELETE FROM top_questions WHERE question_id=?", (question_id,))
    conn.commit()
    return True

def add_season(name, balance, description=''):
    """افزودن فصل جدید"""
    try:
        c.execute("INSERT INTO season (name, balance, description, is_active) VALUES (?, ?, ?, 0)", 
                 (name, balance, description))
        conn.commit()
        return c.lastrowid
    except sqlite3.OperationalError as e:
        logger.error(f"خطا در افزودن فصل جدید: {e}")
        return None

def update_season(season_id, name=None, balance=None, description=None):
    """بروزرسانی فصل"""
    if name is not None:
        c.execute("UPDATE season SET name=? WHERE id=?", (name, season_id))
    if balance is not None:
        c.execute("UPDATE season SET balance=? WHERE id=?", (balance, season_id))
    if description is not None:
        c.execute("UPDATE season SET description=? WHERE id=?", (description, season_id))
    conn.commit()
    return True

def end_season(season_id):
    """پایان فصل"""
    try:
        c.execute("UPDATE season SET is_active=0 WHERE id=?", (season_id,))
        conn.commit()
        return True
    except sqlite3.OperationalError as e:
        logger.error(f"خطا در پایان دادن به فصل: {e}")
        return False

def delete_season(season_id):
    """حذف فصل"""
    # بررسی اینکه فصل فعال نباشد
    c.execute("SELECT is_active FROM season WHERE id=?", (season_id,))
    result = c.fetchone()
    if not result or result[0] == 1:
        return False
    
    c.execute("DELETE FROM season WHERE id=?", (season_id,))
    conn.commit()
    return True

def activate_season(season_id):
    """فعال‌سازی فصل"""
    try:
        # غیرفعال کردن همه فصل‌های فعال قبلی
        c.execute("UPDATE season SET is_active=0 WHERE is_active=1")
        
        # فعال کردن فصل مورد نظر
        c.execute("UPDATE season SET is_active=1 WHERE id=?", (season_id,))
        
        # دریافت اعتبار فصل
        c.execute("SELECT balance FROM season WHERE id=?", (season_id,))
        balance = c.fetchone()[0]
        
        # اعطای اعتبار به همه کاربران
        c.execute("UPDATE users SET balance=?", (balance,))
        
        conn.commit()
        return balance
    except sqlite3.OperationalError as e:
        logger.error(f"خطا در فعال‌سازی فصل: {e}")
        return 10  # مقدار پیش‌فرض

def get_user_season_stats(user_id, season_id):
    """دریافت آمار کاربر در یک فصل خاص"""
    stats = {
        'received_count': 0,
        'received_amount': 0,
        'given_count': 0,
        'given_amount': 0,
        'top_votes': [],
        'rank': 0,
        'total_users': 0
    }
    
    # دریافت آمار تراکنش‌های دریافتی
    c.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM transactions
        WHERE touser=? AND season_id=?
    """, (user_id, season_id))
    result = c.fetchone()
    if result:
        stats['received_count'] = result[0] or 0
        stats['received_amount'] = result[1] or 0
    
    # دریافت آمار تراکنش‌های داده شده
    c.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM transactions
        WHERE user_id=? AND season_id=?
    """, (user_id, season_id))
    result = c.fetchone()
    if result:
        stats['given_count'] = result[0] or 0
        stats['given_amount'] = result[1] or 0
    
    # دریافت رتبه کاربر در فصل
    c.execute("""
        WITH UserRanks AS (
            SELECT 
                touser, 
                SUM(amount) as total,
                RANK() OVER (ORDER BY SUM(amount) DESC) as rank
            FROM transactions 
            WHERE season_id=?
            GROUP BY touser
        )
        SELECT rank, (SELECT COUNT(DISTINCT touser) FROM transactions WHERE season_id=?)
        FROM UserRanks 
        WHERE touser=?
    """, (season_id, season_id, user_id))
    rank_result = c.fetchone()
    if rank_result:
        stats['rank'] = rank_result[0]
        stats['total_users'] = rank_result[1]
    
    # دریافت آمار ترین‌های کاربر
    c.execute("""
        SELECT q.text, COUNT(v.vote_id) as vote_count, GROUP_CONCAT(u.name, ', ') as voters
        FROM top_votes v
        JOIN top_questions q ON v.question_id = q.question_id
        JOIN users u ON v.user_id = u.user_id
        WHERE v.voted_for_user_id=? AND v.season_id=?
        GROUP BY q.question_id
    """, (user_id, season_id))
    top_votes = c.fetchall()
    if top_votes:
        stats['top_votes'] = [(row[0], row[1], row[2]) for row in top_votes]
    
    return stats

def get_season_scoreboard(season_id):
    """دریافت تابلوی امتیازات یک فصل خاص"""
    c.execute("""
        SELECT touser, SUM(amount) as total, u.name 
        FROM transactions t 
        LEFT JOIN users u ON t.touser = u.user_id 
        WHERE t.season_id=?
        GROUP BY touser 
        ORDER BY total DESC LIMIT 10
    """, (season_id,))
    return c.fetchall()

def has_user_voted_all_top_questions(user_id):
    """بررسی آیا کاربر به همه سوالات ترین‌ها پاسخ داده است"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        return False
    
    season_id = active_season[0]
    
    # دریافت تعداد سوالات فعال
    c.execute("""
        SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
    """, (season_id,))
    total_questions = c.fetchone()[0]
    
    if total_questions == 0:
        return True
    
    # دریافت تعداد رأی‌های کاربر
    c.execute("""
        SELECT COUNT(*) FROM top_votes 
        WHERE user_id=? AND season_id=?
    """, (user_id, season_id))
    user_votes = c.fetchone()[0]
    
    return user_votes >= total_questions

def get_user_top_votes(user_id):
    """دریافت رأی‌های کاربر برای ترین‌ها"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        return []
    
    season_id = active_season[0]
    
    c.execute("""
        SELECT q.text, u.name, v.voted_for_user_id
        FROM top_votes v
        JOIN top_questions q ON v.question_id = q.question_id
        JOIN users u ON v.voted_for_user_id = u.user_id
        WHERE v.user_id=? AND v.season_id=?
        ORDER BY v.vote_id ASC
    """, (user_id, season_id))
    
    return c.fetchall()

def get_next_unanswered_question(user_id):
    """دریافت اولین سوال پاسخ داده نشده برای کاربر"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        return None
    
    season_id = active_season[0]
    
    # دریافت سوالاتی که کاربر به آنها پاسخ نداده است
    c.execute("""
        SELECT q.question_id, q.text
        FROM top_questions q
        LEFT JOIN top_votes v ON q.question_id = v.question_id AND v.user_id = ?
        WHERE q.is_active = 1
        AND q.season_id = ?
        AND v.vote_id IS NULL
        ORDER BY q.question_id ASC
        LIMIT 1
    """, (user_id, season_id))
    
    result = c.fetchone()
    return (result[0], result[1]) if result else None

def save_top_vote(user_id, question_id, voted_for):
    """ذخیره رأی کاربر برای ترین‌ها"""
    try:
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            return False
        
        season_id = active_season[0]
        
        # بررسی آیا کاربر قبلاً به این سوال پاسخ داده است
        c.execute("""
            SELECT vote_id FROM top_votes 
            WHERE user_id=? AND question_id=? AND season_id=?
        """, (user_id, question_id, season_id))
        
        existing_vote = c.fetchone()
        
        if existing_vote:
            # اگر قبلاً رأی داده، آن را بروز کنید
            c.execute("""
                UPDATE top_votes 
                SET voted_for_user_id=?, vote_time=datetime('now')
                WHERE vote_id=?
            """, (voted_for, existing_vote[0]))
        else:
            # اگر رأی جدید است، آن را اضافه کنید
            c.execute("""
                INSERT INTO top_votes (user_id, question_id, voted_for_user_id, season_id, vote_time)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (user_id, question_id, voted_for, season_id))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"خطا در ذخیره رأی: {e}")
        return False

def get_top_results_for_question(question_id):
    """دریافت نتایج برای یک سوال خاص ترین‌ها"""
    c.execute("""
        SELECT v.voted_for_user_id, COUNT(v.vote_id) as vote_count, u.name
        FROM top_votes v
        JOIN users u ON v.voted_for_user_id = u.user_id
        WHERE v.question_id = ?
        GROUP BY v.voted_for_user_id
        ORDER BY vote_count DESC
        LIMIT 10
    """, (question_id,))
    
    return c.fetchall()

def get_active_top_questions():
    """دریافت سوالات فعال ترین‌ها"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        return []
    
    season_id = active_season[0]
    
    c.execute("""
        SELECT question_id, text
        FROM top_questions
        WHERE is_active = 1 AND season_id = ?
        ORDER BY question_id ASC
    """, (season_id,))
    
    return c.fetchall()

# تابع ایجاد دکمه‌های شیشه‌ای برای صفحه‌بندی
def create_glass_buttons(page, total_pages, callback_prefix):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ صفحه قبل", callback_data=f"{callback_prefix}^{page-1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("صفحه بعد ➡️", callback_data=f"{callback_prefix}^{page+1}"))
    return buttons

async def check_channel_membership(user_id, context):
    try:
        bot = context.bot
        logger.info(f"Checking membership for user {user_id} in channel {config.CHANNEL_ID}")
        chat_member = await bot.get_chat_member(chat_id=config.CHANNEL_ID, user_id=user_id)
        logger.info(f"User {user_id} membership status: {chat_member.status}")
        is_member = chat_member.status in ['member', 'administrator', 'creator', 'restricted']
        return is_member
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_approved = is_user_approved(user.id)
    
    # بررسی عضویت در کانال
    is_member = await check_channel_membership(user.id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await update.message.reply_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی تأیید کاربر
    if not is_approved:
        # ارسال پیام به کاربر با دکمه شیشه‌ای برای پشتیبانی
        keyboard = [[InlineKeyboardButton(f"👤 پشتیبانی", url=f"{config.SUPPORT_USERNAME.strip('@')}")]]
        await update.message.reply_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با پشتیبان تماس بگیرید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # ارسال نوتیفیکیشن به ادمین
        admin_keyboard = [
            [InlineKeyboardButton("✅ تأیید کاربر", callback_data=f"approve_user^{user.id}")],
            [InlineKeyboardButton("❌ رد کاربر", callback_data=f"reject_user^{user.id}")]
        ]
        
        try:
            bot = context.bot
            await bot.send_message(
                chat_id=config.ADMIN_USER_ID,
                text=f"🔔 <b>درخواست دسترسی جدید</b>\n\n"
                     f"👤 نام: {user.full_name}\n"
                     f"🆔 شناسه: {user.id}\n"
                     f"👤 یوزرنیم: @{user.username or 'ندارد'}",
                reply_markup=InlineKeyboardMarkup(admin_keyboard),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending notification to admin: {e}")
        
        return
    
    await update.message.reply_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard(user.id)
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    get_or_create_user(user)
    data = query.data
    
    # بررسی عضویت در کانال برای تمام کالبک‌ها
    is_member = await check_channel_membership(user.id, context)
    if not is_member and not data.startswith("joinedch^"):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await query.edit_message_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی وجود فصل فعال برای اکثر دکمه‌ها
    # لیست دکمه‌هایی که نیاز به فصل فعال ندارند
    excluded_buttons = ["help^", "userpanel^", "userprofile^", "historypoints^", "joinedch^", 
                        "admin_panel^", "approve_user^", "reject_user^", "season_archive^",
                        "manage_seasons^", "add_season^", "toggle_season^", "edit_season^", "delete_season^",
                        "edit_season_name^", "edit_season_balance^", "edit_season_desc^",
                        "skip_season_description^", "manage_top_questions^", "add_top_question^",
                        "edit_top_question^", "delete_top_question^"]
    
    # استثنا برای دکمه‌هایی که با پیشوند خاصی شروع می‌شوند
    excluded_prefixes = ["Scoreboard^", "receivedpoints^", "givenpoints^", "admin_", "manage_", 
                        "edit_season", "delete_season", "toggle_season", "edit_question", "toggle_question"]
    
    needs_active_season = True
    for button in excluded_buttons:
        if data == button:
            needs_active_season = False
            break
    
    for prefix in excluded_prefixes:
        if data.startswith(prefix):
            needs_active_season = False
            break
    
    # اگر کاربر ادمین است، نیازی به فصل فعال ندارد
    c.execute("SELECT role FROM admins WHERE user_id=?", (user.id,))
    admin_role = c.fetchone()
    if admin_role:
        needs_active_season = False
    
    if needs_active_season:
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            await query.edit_message_text(
                "⚠️ <b>هیچ فصل فعالی وجود ندارد!</b>\n\n"
                "در حال حاضر هیچ فصل فعالی در سیستم تعریف نشده است. لطفاً منتظر باشید تا ادمین‌های سیستم "
                "یک فصل جدید را فعال کنند. سپس می‌توانید از امکانات ربات استفاده نمایید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به منو", callback_data="userpanel^")]]),
                parse_mode="HTML"
            )
            return
    
    if data == "help^":
        await query.answer()
        # استفاده از ماژول help برای نمایش صفحه اصلی راهنما
        help_data = help.get_help_text("main")
        await query.edit_message_text(
            help_data["text"],
            reply_markup=InlineKeyboardMarkup(help_data["buttons"]),
            parse_mode="HTML"
        )
    elif data.startswith("help_"):
        await query.answer()
        # استفاده از ماژول help برای نمایش بخش‌های مختلف راهنما
        help_data = help.handle_help_callback(data)
        await query.edit_message_text(
            f"<b>{help_data['title']}</b>\n\n{help_data['text']}",
            reply_markup=InlineKeyboardMarkup(help_data["buttons"]),
            parse_mode="HTML"
        )
    elif data == "userpanel^":
        await query.answer()
        await query.edit_message_text(
            f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
            reply_markup=main_menu_keyboard(user.id)
        )
    elif data == "userprofile^":
        await query.answer()
        profile = get_user_profile(user.id)
        if profile:
            total_received = profile[5] or 0
            await query.edit_message_text(
                f"👤 پروفایل شما\n\nنام: {profile[2]}\nیوزرنیم: @{profile[1] or 'ندارد'}\nاعتبار فعلی: {profile[3]}\nمجموع امتیازات دریافتی: {total_received}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
        else:
            await query.edit_message_text("پروفایل یافت نشد.", reply_markup=main_menu_keyboard(user.id))
    elif data == "historypoints^":
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("تابلوی امتیازات 🏆", callback_data="Scoreboard^")],
            [InlineKeyboardButton("امتیازهای شما 🎯", callback_data="receivedpoints^"), 
             InlineKeyboardButton("امتیازهایی که دادید 💬", callback_data="givenpoints^")],
            [InlineKeyboardButton("🗂 آرشیو فصل‌ها", callback_data="season_archive")],
            [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
        ]
        await query.edit_message_text(
            f"تاریخچه امتیازات شما\n\nدر این بخش می‌توانید امتیازهایی که به دیگران داده‌اید و امتیازهایی که از دیگران دریافت کرده‌اید را همراه با وضعیت آن‌ها مشاهده کنید.\n\nلطفاً از گزینه‌های زیر، انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "joinedch^":
        await query.answer()
        await query.edit_message_text(
            f"📌 شما با موفقیت به کانال {config.BOT_NAME} پیوستید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» دریافت منو", callback_data="userpanel^")]])
        )
    elif data == "tovote^":
        await query.answer()
        users = get_all_users(exclude_id=user.id)
        if not users:
            await query.edit_message_text("هیچ کاربر دیگری برای امتیازدهی وجود ندارد!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            # اگر فصل فعالی وجود نداشت، از مقدار پیش‌فرض استفاده کن
            season_id = config.SEASON_ID
            season_name = config.SEASON_NAME
        else:
            season_id = active_season[0]
            season_name = active_season[1]
        
        keyboard = []
        row = []
        for i, u in enumerate(users):
            row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"voteuser^{u[0]}"))
            if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
                if len(row) == 1 and i == len(users) - 1:  # اگر آخرین آیتم تنها در ردیف باشد
                    keyboard.append(row)
                elif len(row) == 2:
                    keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
        
        # دریافت موجودی کاربر
        c.execute("SELECT balance FROM users WHERE user_id=?", (user.id,))
        balance = c.fetchone()[0]
        
        await query.edit_message_text(
            f"#{season_name}\n\n"
            f"تو {balance} امتیاز داری که می‌تونی به دوستات بدی 🎁\n\n"
            f"از بین افراد زیر، به کی می‌خوای امتیاز بدی؟ 🤔",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("voteuser^"):
        await query.answer()
        touser_id = int(data.split("^")[1])
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        profile = get_user_profile(user.id)
        if not profile or profile[3] < 1:
            await query.edit_message_text("اعتبار کافی برای امتیازدهی ندارید!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # انتخاب مقدار امتیاز - تمام مقادیر ممکن را نمایش می‌دهیم
        max_score = profile[3]  # حداکثر امتیاز برابر با موجودی کاربر
        
        # ایجاد دکمه‌های امتیازدهی، 3 دکمه در هر ردیف
        keyboard = []
        row = []
        for i in range(1, max_score + 1):
            row.append(InlineKeyboardButton(str(i), callback_data=f"givepoint^{touser_id}^{i}"))
            if len(row) == 3 or i == max_score:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
        
        await query.edit_message_text(
            f"شما در حال امتیاز دادن به {touser_name} هستید!\n\n"
            f"درحال حاضر شما {max_score} امتیاز دارید که میتوانید استفاده کنید.\n\n"
            f"لطفا مقدار امتیازی که میخواهید بدهید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("givepoint^"):
        await query.answer()
        parts = data.split("^")
        touser_id = int(parts[1])
        amount = int(parts[2])
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        # درخواست دلیل امتیازدهی
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]]
        
        # ذخیره اطلاعات در context.user_data
        context.user_data['pending_transaction'] = {
            'touser_id': touser_id,
            'amount': amount,
            'touser_name': touser_name  # ذخیره نام کاربر مقصد
        }
        
        await query.edit_message_text(
            f"شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"  
            f"دلیل:\n-----------------\n\n"  
            f"لطفاً دلیل امتیازدهی را بنویسید و ارسال کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # تغییر وضعیت کاربر به حالت انتظار برای دریافت دلیل
        context.user_data['waiting_for_reason'] = True
    elif data.startswith("Confirm^"):
        await query.answer()
        parts = data.split("^")
        touser_id = int(parts[1])
        amount = int(parts[2])
        reason = parts[3] if len(parts) > 3 else "-"
        
        profile = get_user_profile(user.id)
        if not profile or profile[3] < amount:
            await query.edit_message_text("اعتبار کافی ندارید!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            # اگر فصل فعالی وجود نداشت، از مقدار پیش‌فرض استفاده کن
            season_id = config.SEASON_ID
        else:
            season_id = active_season[0]
        
        # دریافت نام کاربر فرستنده از دیتابیس
        c.execute("SELECT name FROM users WHERE user_id=?", (user.id,))
        sender_result = c.fetchone()
        sender_name = sender_result[0] if sender_result else "کاربر"
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        # ثبت تراکنش و کم کردن اعتبار
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
        c.execute("INSERT INTO transactions (user_id, touser, amount, season_id, reason) VALUES (?, ?, ?, ?, ?)", 
                 (user.id, touser_id, amount, season_id, reason))
        conn.commit()
        
        # دریافت آخرین شناسه تراکنش درج شده
        c.execute("SELECT last_insert_rowid()")
        transaction_id = c.fetchone()[0]
        
        # دریافت تاریخ و زمان شمسی و فارسی
        import jdatetime
        # نگاشت دستی روزها و ماه‌های فارسی
        fa_weekdays = {
            'Saturday': 'شنبه',
            'Sunday': 'یکشنبه',
            'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه',
            'Wednesday': 'چهارشنبه',
            'Thursday': 'پنجشنبه',
            'Friday': 'جمعه',
        }
        fa_months = {
            'Farvardin': 'فروردین',
            'Ordibehesht': 'اردیبهشت',
            'Khordad': 'خرداد',
            'Tir': 'تیر',
            'Mordad': 'مرداد',
            'Shahrivar': 'شهریور',
            'Mehr': 'مهر',
            'Aban': 'آبان',
            'Azar': 'آذر',
            'Dey': 'دی',
            'Bahman': 'بهمن',
            'Esfand': 'اسفند',
        }
        now = jdatetime.datetime.now()
        weekday_en = now.strftime("%A")
        month_en = now.strftime("%B")
        weekday = fa_weekdays.get(weekday_en, weekday_en)
        month = fa_months.get(month_en, month_en)
        day = now.day
        year = now.year
        fa_date = f"{weekday} {day} {month} {year}"
        current_time = f"⏰ {fa_date}"
        
        try:
            # ارسال پیام به کانال
            bot = context.bot
            # دکمه شیشه‌ای برای امتیاز دادن در ربات
            vote_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 امتیاز دادن در ربات", url=f"https://t.me/{bot.username}?start=start")]
            ])
            channel_message = await bot.send_message(
                chat_id=config.CHANNEL_ID,
                text=f"{sender_name} {amount} امتیاز به {touser_name} داد و نوشت : \n\n"
                     f"💬 {reason}\n\n"
                     f"{current_time}",
                reply_markup=vote_keyboard
            )
            
            # بروزرسانی message_id در دیتابیس
            if channel_message:
                c.execute("UPDATE transactions SET message_id = ? WHERE transaction_id = ?", 
                         (channel_message.message_id, transaction_id))
                conn.commit()
                
                # ارسال پیام به کاربر دریافت‌کننده
                channel_id_num = config.CHANNEL_ID.replace("-100", "")
                keyboard = [[InlineKeyboardButton("مشاهده در کانال", url=f"https://t.me/c/{channel_id_num}/{channel_message.message_id}")]]
                
                try:
                    await bot.send_message(
                        chat_id=touser_id,
                        text=f"🎉 {sender_name} {amount} امتیاز بهت داد و نوشت : \n\n"
                             f"💬 {reason}\n\n"
                             f"{current_time}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to user {touser_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error sending message to channel: {e}")
        
        # اطلاع به کاربر فرستنده
        await query.edit_message_text(
            f"✅ {amount} امتیاز به {touser_name} داده شد!\n\n"  
            f"دلیل: {reason}",
            reply_markup=main_menu_keyboard(user.id)
        )
    elif data.startswith("givenpoints^"):
        await query.answer()
        parts = data.split("^")
        
        # اگر بخش سوم وجود داشت، یعنی فصل خاصی انتخاب شده است
        if len(parts) > 2 and parts[2].isdigit():
            season_id = int(parts[2])
            try:
                page = int(parts[1]) if parts[1].isdigit() else 0
            except:
                page = 0
                
            # دریافت اطلاعات فصل
            c.execute("SELECT name FROM season WHERE id=?", (season_id,))
            season_row = c.fetchone()
            season_name = season_row[0] if season_row else "نامشخص"
            
            # دریافت تعداد کل تراکنش‌های این فصل
            total_transactions = count_user_transactions(user.id, given=True, season_id=season_id)
            total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
            
            # دریافت تراکنش‌های صفحه فعلی برای این فصل
            given = get_user_transactions(user.id, given=True, offset=page*3, limit=3, season_id=season_id)
            
            msg = f"✨ <b>امتیازهایی که در فصل {season_name} دادید</b> ✨\n\n"
            if given:
                for transaction in given:
                    amount = transaction[0]
                    touser_name = transaction[2]
                    reason = transaction[3] or '-'
                    created_at = transaction[4]
                    message_id = transaction[5]  # شناسه پیام در کانال
                    # اضافه کردن لینک به پیام کانال
                    link_text = "[لینک]"
                    if message_id:
                        channel_id_num = config.CHANNEL_ID.replace("-100", "")
                        link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                    msg += f"✅ شما {amount} امتیاز به {touser_name} دادید: {link_text}\n"
                    msg += f"📄 {reason}\n\n"
                    msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
            else:
                msg += "- در این فصل هنوز امتیازی به کسی نداده‌اید.\n\n"
                
            # ایجاد دکمه‌های شیشه‌ای
            nav_buttons = create_glass_buttons(page, max(1, total_pages), f"givenpoints^{season_id}")
            keyboard = [nav_buttons] if nav_buttons else []
            keyboard.append([InlineKeyboardButton("» بازگشت", callback_data=f"season_archive^{season_id}")])
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return
        
        # در غیر این صورت، فصل جاری را نمایش می‌دهیم
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
            
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!")
            return
            
        season_id = active_season[0]
        season_name = active_season[1]
        
        # دریافت تعداد کل تراکنش‌های فصل جاری
        total_transactions = count_user_transactions(user.id, given=True, season_id=season_id)
        total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
        
        # دریافت تراکنش‌های صفحه فعلی برای فصل جاری
        given = get_user_transactions(user.id, given=True, offset=page*3, limit=3, season_id=season_id)
        
        msg = f"✨ <b>امتیازهایی که در فصل {season_name} دادید</b> ✨\n\n"
        if given:
            for transaction in given:
                amount = transaction[0]
                touser_name = transaction[2]
                reason = transaction[3] or '-'
                created_at = transaction[4]
                message_id = transaction[5]  # شناسه پیام در کانال
                # اضافه کردن لینک به پیام کانال
                link_text = "[لینک]"
                if message_id:
                    channel_id_num = config.CHANNEL_ID.replace("-100", "")
                    link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                msg += f"✅ شما {amount} امتیاز به {touser_name} دادید: {link_text}\n"
                msg += f"📄 {reason}\n\n"
                msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
        else:
            msg += "- در این فصل هنوز امتیازی به کسی نداده‌اید.\n\n"
            
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "givenpoints")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("receivedpoints^"):
        await query.answer()
        parts = data.split("^")
        
        # اگر بخش سوم وجود داشت، یعنی فصل خاصی انتخاب شده است
        if len(parts) > 2 and parts[2].isdigit():
            season_id = int(parts[2])
            try:
                page = int(parts[1]) if parts[1].isdigit() else 0
            except:
                page = 0
                
            # دریافت اطلاعات فصل
            c.execute("SELECT name FROM season WHERE id=?", (season_id,))
            season_row = c.fetchone()
            season_name = season_row[0] if season_row else "نامشخص"
            
            # دریافت تعداد کل تراکنش‌های این فصل
            total_transactions = count_user_transactions(user.id, given=False, season_id=season_id)
            total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
            
            # دریافت تراکنش‌های صفحه فعلی برای این فصل
            received = get_user_transactions(user.id, given=False, offset=page*3, limit=3, season_id=season_id)
            
            msg = f"✨ <b>امتیازهایی که در فصل {season_name} دریافت کردید</b> ✨\n\n"
            if received:
                for transaction in received:
                    amount = transaction[0]
                    from_name = transaction[2]
                    reason = transaction[3] or '-'
                    created_at = transaction[4]
                    message_id = transaction[5]  # شناسه پیام در کانال
                    # اضافه کردن لینک به پیام کانال
                    link_text = "[لینک]"
                    if message_id:
                        channel_id_num = config.CHANNEL_ID.replace("-100", "")
                        link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                    msg += f"✅ {from_name} به شما {amount} امتیاز داد: {link_text}\n"
                    msg += f"📄 {reason}\n\n"
                    msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
            else:
                msg += "- در این فصل هنوز امتیازی دریافت نکرده‌اید.\n\n"
                
            # ایجاد دکمه‌های شیشه‌ای
            nav_buttons = create_glass_buttons(page, max(1, total_pages), f"receivedpoints^{season_id}")
            keyboard = [nav_buttons] if nav_buttons else []
            keyboard.append([InlineKeyboardButton("» بازگشت", callback_data=f"season_archive^{season_id}")])
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return
        
        # در غیر این صورت، فصل جاری را نمایش می‌دهیم
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
            
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!")
            return
            
        season_id = active_season[0]
        season_name = active_season[1]
        
        # دریافت تعداد کل تراکنش‌های فصل جاری
        total_transactions = count_user_transactions(user.id, given=False, season_id=season_id)
        total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
        
        # دریافت تراکنش‌های صفحه فعلی برای فصل جاری
        received = get_user_transactions(user.id, given=False, offset=page*3, limit=3, season_id=season_id)
        
        msg = f"✨ <b>امتیازهایی که در فصل {season_name} دریافت کردید</b> ✨\n\n"
        if received:
            for transaction in received:
                amount = transaction[0]
                from_name = transaction[2]
                reason = transaction[3] or '-'
                created_at = transaction[4]
                message_id = transaction[5]  # شناسه پیام در کانال
                # اضافه کردن لینک به پیام کانال
                link_text = "[لینک]"
                if message_id:
                    channel_id_num = config.CHANNEL_ID.replace("-100", "")
                    link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                msg += f"✅ {from_name} به شما {amount} امتیاز داد: {link_text}\n"
                msg += f"📄 {reason}\n\n"
                msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
        else:
            msg += "- در این فصل هنوز امتیازی دریافت نکرده‌اید.\n\n"
            
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "receivedpoints")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("Scoreboard^"):
        await query.answer()
        parts = data.split("^")
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
        # دریافت تابلوی امتیازات
        board = get_scoreboard()
        total_items = len(board)
        total_pages = (total_items + 9) // 10  # تقسیم به صفحات 10 تایی
        # انتخاب آیتم‌های صفحه فعلی
        start_idx = page * 10
        end_idx = min(start_idx + 10, total_items)
        current_page_items = board[start_idx:end_idx]
        msg = "🏆 <b>تابلوی امتیازات برتر</b> 🏆\n\n"
        for i, row in enumerate(current_page_items):
            rank = i + start_idx + 1
            medal = ""
            if rank == 1:
                medal = "🥇 "
            elif rank == 2:
                medal = "🥈 "
            elif rank == 3:
                medal = "🥉 "
            user_name = row[2] or "کاربر"
            total_points = row[1]
            # برجسته کردن کاربر جاری
            if row[0] == user.id:
                user_name = f"<tg-spoiler>{user_name}</tg-spoiler>"
            msg += f"{rank}- {medal}{user_name}: <b>{total_points}</b> امتیاز\n\n"
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "Scoreboard")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    # پنل ادمین
    elif data == "admin_panel^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row:
            await query.answer("شما دسترسی به این بخش ندارید!")
            return
        role, permissions = row
        allowed = []
        if role == 'god':
            allowed = [p[0] for p in ADMIN_PERMISSIONS]
        elif permissions:
            allowed = [p.strip() for p in permissions.split(",") if p.strip()]
        keyboard = []
        if "admin_users" in allowed:
            keyboard.append([InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users^")])
        if "admin_transactions" in allowed:
            keyboard.append([InlineKeyboardButton("💰 مدیریت تراکنش‌ها", callback_data="admin_transactions^")])
        if "admin_stats" in allowed:
            keyboard.append([InlineKeyboardButton("📊 آمار و گزارشات", callback_data="admin_stats^")])
        if "manage_admins" in allowed:
            keyboard.append([InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="manage_admins^")])
        # Add new broadcast button
        if "admin_users" in allowed:  # Using same permission as user management
            keyboard.append([InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast_menu^")])
        # اضافه کردن بخش مدیریت ترین‌ها
        if "manage_questions" in allowed:
            keyboard.append([InlineKeyboardButton("🏆 مدیریت سوالات ترین‌ها", callback_data="manage_top_questions^")])
        # اضافه کردن بخش مدیریت فصل‌ها
        if "manage_questions" in allowed:  # با همان دسترسی مدیریت سوالات
            keyboard.append([InlineKeyboardButton("🔄 مدیریت فصل‌ها", callback_data="manage_seasons^")])
        keyboard.append([InlineKeyboardButton("» بازگشت به منوی اصلی", callback_data="userpanel^")])
        await query.answer()
        await query.edit_message_text(
            "🔐 <b>پنل مدیریت ادمین</b>\n\n"
            "به پنل مدیریت خوش آمدید. از این بخش می‌توانید کاربران و تراکنش‌ها را مدیریت کنید و آمار سیستم را مشاهده نمایید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    
    # بخش مدیریت سوالات ترین‌ها
    elif data == "manage_top_questions^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        role, permissions = row
        allowed = []
        if role == 'god':
            allowed = [p[0] for p in ADMIN_PERMISSIONS]
        elif permissions:
            allowed = [p.strip() for p in permissions.split(",") if p.strip()]
        if "manage_questions" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد! ابتدا یک فصل را فعال کنید.", show_alert=True)
            await query.edit_message_text(
                "مدیریت سوالات ترین‌ها",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]])
            )
            return
            
        # دریافت سوالات فصل فعال به جای همه سوالات
        season_id = active_season[0]
        season_name = active_season[1]
        questions = get_top_questions_for_season(season_id)
            
        msg = f"🏆 <b>مدیریت سوالات ترین‌های فصل {season_name}</b>\n\n"
        
        if questions:
            for i, q in enumerate(questions):
                status = "✅ فعال" if q[2] == 1 else "❌ غیرفعال"
                msg += f"{i+1}. {q[1]} - <i>{status}</i>\n"
        else:
            msg += "هیچ سوالی برای این فصل تعریف نشده است."
            
        keyboard = [
            [InlineKeyboardButton("➕ افزودن سوال جدید", callback_data="add_top_question^")],
            [InlineKeyboardButton("✏️ ویرایش سوال", callback_data="edit_top_question^")],
            [InlineKeyboardButton("❌ حذف سوال", callback_data="delete_top_question^")],
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
        
    elif data == "add_season^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        context.user_data['admin_action'] = 'add_season'
        context.user_data['season_step'] = 'name'
        context.user_data['current_question_number'] = 1 # برای شمارش سوالات ترین ها
        context.user_data['season_questions'] = [] # برای ذخیره سوالات ترین ها
        
        await query.edit_message_text(
            "نام فصل جدید را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
        )
        return
        
    elif data.startswith("edit_season^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        parts = data.split("^")
        
        if len(parts) == 1:
            # نمایش لیست فصل‌ها برای انتخاب
            seasons = get_all_seasons()
            
            if not seasons:
                await query.answer("هیچ فصلی تعریف نشده است!", show_alert=True)
                # به جای فراخوانی مستقیم menu_callback، مستقیماً به منوی مدیریت فصل‌ها برمی‌گردیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
            
            keyboard = []
            for s in seasons:
                keyboard.append([InlineKeyboardButton(f"{s[1]}", callback_data=f"edit_season^{s[0]}")])
            keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")])
            
            await query.edit_message_text(
                "لطفاً فصل مورد نظر برای ویرایش را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # نمایش لیست فصل‌ها برای انتخاب
        seasons = get_all_seasons()
        keyboard = []
        for s in seasons:
            keyboard.append([InlineKeyboardButton(f"{s[1]}", callback_data=f"edit_season^{s[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")])
        
        await query.edit_message_text(
            "لطفاً فصل مورد نظر برای ویرایش را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    elif data.startswith("edit_season_name^"):
        season_id = int(data.split("^")[1])
        context.user_data['edit_season_id'] = season_id
        context.user_data['admin_action'] = 'edit_season_name'
        
        c.execute("SELECT name FROM season WHERE id=?", (season_id,))
        current_name = c.fetchone()[0]
        
        await query.edit_message_text(
            f"لطفاً نام جدید برای فصل را وارد کنید:\n\n"
            f"نام فعلی: {current_name}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data=f"edit_season^{season_id}")]])
        )
        return
        
    elif data.startswith("edit_season_balance^"):
        season_id = int(data.split("^")[1])
        context.user_data['edit_season_id'] = season_id
        context.user_data['admin_action'] = 'edit_season_balance'
        
        c.execute("SELECT balance FROM season WHERE id=?", (season_id,))
        current_balance = c.fetchone()[0]
        
        await query.edit_message_text(
            f"لطفاً اعتبار جدید برای فصل را وارد کنید:\n\n"
            f"اعتبار فعلی: {current_balance}\n\n"
            f"⚠️ توجه: این مقدار اعتباری است که در صورت فعال‌سازی فصل به همه کاربران داده می‌شود.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data=f"edit_season^{season_id}")]])
        )
        return
        
    elif data.startswith("edit_season_desc^"):
        season_id = int(data.split("^")[1])
        context.user_data['edit_season_id'] = season_id
        context.user_data['admin_action'] = 'edit_season_desc'
        
        c.execute("SELECT description FROM season WHERE id=?", (season_id,))
        current_desc = c.fetchone()[0] or "بدون توضیحات"
        
        await query.edit_message_text(
            f"لطفاً توضیحات جدید برای فصل را وارد کنید:\n\n"
            f"توضیحات فعلی: {current_desc}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data=f"edit_season^{season_id}")]])
        )
        return
        
    elif data.startswith("toggle_season^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            season_id = int(data.split("^")[1])
            
            c.execute("SELECT is_active, name, balance FROM season WHERE id=?", (season_id,))
            result = c.fetchone()
            
            if not result:
                await query.answer("فصل مورد نظر یافت نشد!", show_alert=True)
                # به جای فراخوانی مستقیم menu_callback، مستقیماً به صفحه مدیریت فصل‌ها برمی‌گردیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")]])
                )
                return
                
            is_active, name, balance = result
            
            if is_active == 1:
                # غیرفعال کردن فصل
                end_season(season_id)
                await query.answer(f"فصل {name} غیرفعال شد.")
                # به جای فراخوانی مستقیم menu_callback، مستقیماً داده را تغییر می‌دهیم
                data = "manage_seasons^"
                # ادامه اجرای همین تابع با داده جدید
                # دوباره منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
            else:
                # فعال کردن فصل
                season_balance = activate_season(season_id)
                
                # ارسال پیام به کانال - فقط یک بار
                try:
                    bot = context.bot
                    channel_message = f"🎉 <b>فصل جدید آغاز شد!</b> 🎉\n\n"
                    channel_message += f"نام فصل: <b>{name}</b>\n"
                    channel_message += f"اعتبار فصل: <b>{balance}</b>\n\n"
                    
                    c.execute("SELECT description FROM season WHERE id=?", (season_id,))
                    desc = c.fetchone()[0]
                    if desc:
                        channel_message += f"<b>توضیحات:</b>\n{desc}\n\n"
                    
                    channel_message += "اکنون می‌توانید وارد ربات شوید و از اعتبار خود برای امتیازدهی استفاده کنید."
                    
                    # دکمه شیشه‌ای برای ورود به ربات
                    keyboard = [[InlineKeyboardButton("🎯 ورود به ربات", url=f"https://t.me/{bot.username}?start=start")]]
                    
                    await bot.send_message(
                        chat_id=config.CHANNEL_ID,
                        text=channel_message,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending message to channel: {e}")
                
                await query.answer(f"فصل {name} فعال شد و به همه کاربران {balance} اعتبار داده شد.")
                
                # به جای فراخوانی مستقیم menu_callback، مستقیماً منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
        
        # نمایش لیست فصل‌ها برای انتخاب
        seasons = get_all_seasons()
        keyboard = []
        for s in seasons:
            status = "✅ فعال" if s[3] == 1 else "❌ غیرفعال"
            keyboard.append([InlineKeyboardButton(f"{s[1]} - {status}", callback_data=f"toggle_season^{s[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")])
        
        await query.edit_message_text(
            "لطفاً فصل مورد نظر برای فعال/غیرفعال کردن را انتخاب کنید:\n\n"
            "⚠️ توجه: با فعال کردن یک فصل، فصل قبلی غیرفعال می‌شود.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    elif data.startswith("delete_season^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            season_id = int(data.split("^")[1])
            
            c.execute("SELECT is_active FROM season WHERE id=?", (season_id,))
            result = c.fetchone()
            
            if not result:
                await query.answer("فصل مورد نظر یافت نشد!", show_alert=True)
                # به جای فراخوانی مستقیم menu_callback، مستقیماً منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
                
            if result[0] == 1:
                await query.answer("نمی‌توان فصل فعال را حذف کرد!", show_alert=True)
                # به جای فراخوانی مستقیم menu_callback، مستقیماً منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
            
            # حذف فصل
            if delete_season(season_id):
                await query.answer("فصل با موفقیت حذف شد.")
                # به جای فراخوانی مستقیم menu_callback، مستقیماً منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
            else:
                await query.answer("خطا در حذف فصل!")
                # به جای فراخوانی مستقیم menu_callback، مستقیماً منوی مدیریت فصل‌ها را نمایش می‌دهیم
                await query.edit_message_text(
                    "مدیریت فصل‌ها",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                        [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                        [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                        [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
                    ])
                )
                return
        
        # نمایش لیست فصل‌های غیرفعال برای انتخاب
        c.execute("SELECT id, name FROM season WHERE is_active=0")
        inactive_seasons = c.fetchall()
        
        if not inactive_seasons:
            await query.answer("هیچ فصل غیرفعالی برای حذف وجود ندارد!", show_alert=True)
            # به جای فراخوانی مستقیم menu_callback، مستقیماً به منوی مدیریت فصل‌ها برمی‌گردیم
            await query.edit_message_text(
                "مدیریت فصل‌ها",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
                    [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
                    [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
                    [InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")]
                ])
            )
            return
        
        keyboard = []
        for s in inactive_seasons:
            keyboard.append([InlineKeyboardButton(f"{s[1]}", callback_data=f"delete_season^{s[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_seasons^")])
        
        await query.edit_message_text(
            "⚠️ لطفاً فصل مورد نظر برای حذف را انتخاب کنید:\n"
            "توجه: این عملیات غیرقابل بازگشت است!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data.startswith("season_archive"):
        parts = data.split("^")
        print(f"season_archive callback called with data: {data}, parts: {parts}")
        
        # دریافت لیست تمام فصل‌ها
        if len(parts) == 1:
            print("Getting all seasons...")
            try:
                # دریافت فصل‌ها به صورت مستقیم با کرسر جدید
                cursor = conn.cursor()
                print("Executing SQL query to get seasons...")
                cursor.execute("SELECT id, name, balance, is_active FROM season ORDER BY id DESC")
                print("SQL query executed successfully")
                seasons = cursor.fetchall()
                print(f"seasons found directly from DB: {seasons}")
                
                if not seasons:
                    print("No seasons found in database")
                    await query.edit_message_text(
                        "هیچ فصلی تعریف نشده است!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
                    )
                    return
                
                # ساخت دکمه‌ها با روش ساده‌تر
                keyboard = []
                for season in seasons:
                    season_id = season[0]
                    season_name = season[1]
                    is_active = season[3]
                    status = "🟢 فعال" if is_active == 1 else "🔴 تمام شده"
                    button_text = f"{season_name} - {status}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=f"season_archive^{season_id}")])
                
                # اضافه کردن دکمه بازگشت
                keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
                
                print(f"Created keyboard with {len(keyboard)} buttons")
                for idx, kb in enumerate(keyboard):
                    print(f"  Button {idx}: {kb[0].text}, callback_data={kb[0].callback_data}")
                
                # ارسال پیام با کیبورد
                try:
                    print("Trying to edit message text...")
                    await query.edit_message_text(
                        "🗂 <b>آرشیو فصل‌ها</b>\n\n"
                        "لطفاً فصل مورد نظر را انتخاب کنید:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                    print("Message edited successfully")
                except Exception as e:
                    print(f"Error editing message: {e}")
                    import traceback
                    traceback_str = traceback.format_exc()
                    print(traceback_str)
                    
                    # اگر خطا مربوط به ناتغییر بودن پیام باشد، سعی می‌کنیم یک پیام جدید ارسال کنیم
                    if "message is not modified" in str(e):
                        print("Message not modified error detected, trying to answer callback query...")
                        await query.answer("لیست فصل‌ها به‌روز شد")
                    else:
                        # اگر خطای دیگری رخ داد، سعی می‌کنیم با ارسال یک پیام آن را به کاربر اطلاع دهیم
                        try:
                            await query.answer("خطا در نمایش فصل‌ها. لطفاً دوباره تلاش کنید.")
                        except:
                            pass
                    
                return
                
            except Exception as e:
                print(f"Error in season_archive: {e}")
                import traceback
                print(traceback.format_exc())
                
                # سعی می‌کنیم حداقل یک پاسخ به کاربر بدهیم
                try:
                    await query.answer(f"خطا: {str(e)[:200]}")
                except:
                    pass
                
                try:
                    await query.edit_message_text(
                        "خطایی در بازیابی فصل‌ها رخ داد. لطفاً بعداً دوباره امتحان کنید.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
                    )
                except Exception as e2:
                    print(f"Error showing error message: {e2}")
                
                return
            
        # نمایش اطلاعات یک فصل خاص
        elif len(parts) > 1 and parts[1].isdigit():
            season_id = int(parts[1])
            
            c.execute("SELECT name FROM season WHERE id=?", (season_id,))
            season_row = c.fetchone()
            
            if not season_row:
                await query.answer("فصل مورد نظر یافت نشد!")
                # به جای فراخوانی مستقیم menu_callback، به منوی آرشیو فصل‌ها برمی‌گردیم
                await query.edit_message_text(
                    "🗂 <b>آرشیو فصل‌ها</b>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="season_archive")]]),
                    parse_mode="HTML"
                )
                return
            
            season_name = season_row[0]
            
            # دریافت 10 نفر برتر فصل
            scoreboard = get_season_scoreboard(season_id)
            
            # دریافت آمار کاربر در این فصل
            stats = get_user_season_stats(user.id, season_id)
            
            msg = f"🏆 <b>آرشیو فصل {season_name}</b>\n\n"
            
            # نمایش 10 نفر برتر
            msg += "<b>🥇 نفرات برتر:</b>\n\n"
            
            if scoreboard:
                for i, (user_id, total, name) in enumerate(scoreboard):
                    medal = ""
                    if i == 0:
                        medal = "🥇 "
                    elif i == 1:
                        medal = "🥈 "
                    elif i == 2:
                        medal = "🥉 "
                        
                    # برجسته کردن کاربر جاری
                    if user_id == user.id:
                        name = f"<tg-spoiler>{name}</tg-spoiler>"
                        
                    msg += f"{i+1}- {medal}{name}: <b>{total}</b> امتیاز\n"
            else:
                msg += "هیچ امتیازی در این فصل ثبت نشده است.\n"
                
            msg += "\n" + "-" * 30 + "\n\n"
            
            # نمایش آمار کاربر
            msg += f"<b>📊 آمار من در فصل {season_name}:</b>\n\n"
            
            if stats['rank'] > 0:
                msg += f"• رتبه شما: <b>{stats['rank']}</b> از {stats['total_users']} کاربر\n"
            msg += f"• تعداد امتیازهای دریافتی: {stats['received_count']} (مجموع: {stats['received_amount']})\n"
            msg += f"• تعداد امتیازهای داده شده: {stats['given_count']} (مجموع: {stats['given_amount']})\n\n"
            
            # نمایش ترین‌های کاربر
            if stats['top_votes']:
                msg += "<b>🏆 ترین‌های من از نظر دیگران:</b>\n\n"
                
                for q_text, vote_count, voters in stats['top_votes']:
                    msg += f"• {q_text} ({vote_count} رأی)\n"
                    msg += f"  از نظر: {voters}\n\n"
            
            # اضافه کردن دکمه‌های مشاهده امتیازهای دریافتی و داده شده در این فصل
            keyboard = [
                [InlineKeyboardButton("👁 امتیازهای دریافتی", callback_data=f"receivedpoints^0^{season_id}")],
                [InlineKeyboardButton("👁 امتیازهای داده شده", callback_data=f"givenpoints^0^{season_id}")],
                [InlineKeyboardButton("🏆 نتایج ترین‌های فصل", callback_data=f"season_top_results^{season_id}")],
                [InlineKeyboardButton("» بازگشت", callback_data="season_archive")]
            ]
            
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    elif data.startswith("manage_permissions^"):
        if len(data.split("^")) == 1:
            # اگر هیچ کاربری انتخاب نشده
            c.execute("SELECT user_id, role, permissions FROM admins")
            admins = c.fetchall()
            
            keyboard = []
            for admin_id, role, perms in admins:
                c.execute("SELECT name FROM users WHERE user_id=?", (admin_id,))
                name_row = c.fetchone()
                name = name_row[0] if name_row else f"کاربر {admin_id}"
                keyboard.append([InlineKeyboardButton(f"{name} ({role})", callback_data=f"manage_permissions^{admin_id}")])
            
            keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="adminpanel^")])
            
            await query.edit_message_text(
                "لطفاً ادمینی که می‌خواهید دسترسی‌های آن را مدیریت کنید انتخاب نمایید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # اگر کاربر انتخاب شده
        admin_id = int(data.split("^")[1])
        
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (admin_id,))
        admin_info = c.fetchone()
        
        if not admin_info:
            await query.answer("ادمین مورد نظر یافت نشد!")
            # به جای فراخوانی مستقیم menu_callback، به منوی اصلی ادمین برمی‌گردیم
            await query.edit_message_text(
                "مدیریت دسترسی‌ها",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_permissions^")]])
            )
            return
        
        role, current_permissions = admin_info
        current_permissions = current_permissions.split(",") if current_permissions else []
        
        keyboard = build_permissions_keyboard(current_permissions)
        keyboard.append([InlineKeyboardButton("» ذخیره تغییرات", callback_data=f"save_permissions^{admin_id}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_permissions^")])
        
        c.execute("SELECT name FROM users WHERE user_id=?", (admin_id,))
        name_row = c.fetchone()
        name = name_row[0] if name_row else f"کاربر {admin_id}"
        
        await query.edit_message_text(
            f"مدیریت دسترسی‌های {name} ({role}):\n\n"
            "دسترسی‌های مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data.startswith("manage_top_votes^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        
        keyboard = [
            [InlineKeyboardButton("➕ افزودن سؤال جدید", callback_data="add_top_question^")],
            [InlineKeyboardButton("✏️ ویرایش سؤالات", callback_data="edit_top_questions^")],
            [InlineKeyboardButton("📊 مشاهده نتایج", callback_data="view_top_results^")],
            [InlineKeyboardButton("» بازگشت", callback_data="adminpanel^")]
        ]
        
        await query.edit_message_text(
            "🏆 مدیریت رای‌گیری ترین‌ها\n\n"
            "در این بخش می‌توانید سؤالات ترین‌ها را مدیریت کنید و نتایج را مشاهده نمایید.\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data.startswith("add_top_question^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        # بررسی وجود فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد! ابتدا یک فصل را فعال کنید.", show_alert=True)
            await query.edit_message_text(
                "مدیریت سوالات ترین‌ها",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]])
            )
            return
            
        context.user_data['admin_action'] = 'add_top_question'
        await query.edit_message_text(
            f"لطفاً متن سوال جدید برای فصل «{active_season[1]}» را وارد کنید:\n\n"
            f"مثال: بهترین همکارت کیه؟",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_top_questions^")]])
        )
        return
        
    elif data.startswith("edit_top_question^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            return
            
        season_id = active_season[0]
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            question_id = int(data.split("^")[1])
            
            # بررسی آیا سوال مربوط به فصل فعال است
            c.execute("SELECT text, is_active FROM top_questions WHERE question_id=? AND season_id=?", (question_id, season_id))
            question = c.fetchone()
            
            if question:
                context.user_data['edit_question_id'] = question_id
                context.user_data['admin_action'] = 'edit_top_question'
                status = "فعال" if question[1] == 1 else "غیرفعال"
                
                keyboard = [
                    [InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"edit_question_text^{question_id}")],
                    [InlineKeyboardButton("🔄 تغییر وضعیت", callback_data=f"toggle_question_status^{question_id}")],
                    [InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]
                ]
                
                await query.edit_message_text(
                    f"ویرایش سوال:\n\n"
                    f"متن فعلی: {question[0]}\n"
                    f"وضعیت: {status}\n\n"
                    f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
        
        # نمایش لیست سوالات فصل فعال برای انتخاب
        questions = get_top_questions_for_season(season_id)
        keyboard = []
        for q in questions:
            keyboard.append([InlineKeyboardButton(f"{q[1]}", callback_data=f"edit_top_question^{q[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")])
        
        await query.edit_message_text(
            f"لطفاً سوال مورد نظر از فصل «{active_season[1]}» برای ویرایش را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    elif data.startswith("edit_question_text^"):
        question_id = int(data.split("^")[1])
        context.user_data['edit_question_id'] = question_id
        context.user_data['admin_action'] = 'edit_question_text'
        
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            return
            
        season_id = active_season[0]
        
        # بررسی آیا سوال مربوط به فصل فعال است
        c.execute("SELECT text FROM top_questions WHERE question_id=? AND season_id=?", (question_id, season_id))
        result = c.fetchone()
        
        if not result:
            await query.answer("سوال مورد نظر در فصل فعال یافت نشد!", show_alert=True)
            return
            
        current_text = result[0]
        
        await query.edit_message_text(
            f"لطفاً متن جدید برای سوال زیر را وارد کنید:\n\n"
            f"متن فعلی: {current_text}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data=f"edit_top_question^{question_id}")]])
        )
        return
        
    elif data.startswith("toggle_question_status^"):
        question_id = int(data.split("^")[1])
        
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            return
            
        season_id = active_season[0]
        
        # بررسی آیا سوال مربوط به فصل فعال است
        c.execute("SELECT is_active FROM top_questions WHERE question_id=? AND season_id=?", (question_id, season_id))
        result = c.fetchone()
        
        if not result:
            await query.answer("سوال مورد نظر در فصل فعال یافت نشد!", show_alert=True)
            return
            
        current_status = result[0]
        new_status = 0 if current_status == 1 else 1
        
        c.execute("UPDATE top_questions SET is_active=? WHERE question_id=?", (new_status, question_id))
        conn.commit()
        
        status_text = "فعال" if new_status == 1 else "غیرفعال"
        await query.answer(f"وضعیت سوال به {status_text} تغییر یافت.")
        
        # به جای فراخوانی بازگشتی menu_callback، مستقیماً به صفحه ویرایش سوال برگشت می‌دهیم
        c.execute("SELECT text, is_active FROM top_questions WHERE question_id=?", (question_id,))
        question = c.fetchone()
        
        if question:
            status = "فعال" if question[1] == 1 else "غیرفعال"
            
            keyboard = [
                [InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"edit_question_text^{question_id}")],
                [InlineKeyboardButton("🔄 تغییر وضعیت", callback_data=f"toggle_question_status^{question_id}")],
                [InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]
            ]
            
            await query.edit_message_text(
                f"ویرایش سوال:\n\n"
                f"متن فعلی: {question[0]}\n"
                f"وضعیت: {status}\n\n"
                f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # اگر سوال پیدا نشد، به صفحه مدیریت سوالات برگشت می‌دهیم
            await query.edit_message_text(
                "سوال مورد نظر یافت نشد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]])
            )
        return
        
    elif data.startswith("delete_top_question^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            return
            
        season_id = active_season[0]
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            question_id = int(data.split("^")[1])
            
            # بررسی آیا سوال مربوط به فصل فعال است
            c.execute("SELECT * FROM top_questions WHERE question_id=? AND season_id=?", (question_id, season_id))
            if not c.fetchone():
                await query.answer("سوال مورد نظر در فصل فعال یافت نشد!", show_alert=True)
                return
            
            # حذف سوال
            c.execute("DELETE FROM top_questions WHERE question_id=?", (question_id,))
            conn.commit()
            
            await query.answer("سوال با موفقیت حذف شد.")
            # بازگشت به صفحه مدیریت سوالات
            await query.edit_message_text(
                "سوال با موفقیت حذف شد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]])
            )
            return
        
        # نمایش لیست سوالات فصل فعال برای انتخاب
        questions = get_top_questions_for_season(season_id)
        keyboard = []
        for q in questions:
            keyboard.append([InlineKeyboardButton(f"{q[1]}", callback_data=f"delete_top_question^{q[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")])
        
        await query.edit_message_text(
            f"⚠️ لطفاً سوال مورد نظر از فصل «{active_season[1]}» برای حذف را انتخاب کنید:\n"
            "توجه: این عملیات غیرقابل بازگشت است!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data.startswith("admin_topq_toggle^"):
        # بدون فراخوانی بازگشتی menu_callback
        await query.answer()
        question_id = int(data.split("^")[1])
        
        # دریافت وضعیت فعلی سوال
        c.execute("SELECT is_active FROM top_questions WHERE question_id=?", (question_id,))
        current_status = c.fetchone()[0]
        
        # تغییر وضعیت سوال
        new_status = 0 if current_status == 1 else 1
        update_top_question(question_id, None, new_status)
        
        # تعیین متن وضعیت برای نمایش
        status_text = "فعال" if new_status == 1 else "غیرفعال"
        
        # پاسخ به کاربر
        await query.answer(f"وضعیت سوال به {status_text} تغییر یافت.")
        
        # نمایش مجدد لیست سوالات با وضعیت به‌روز شده
        questions = get_all_top_questions()
        
        text = "⚡️ <b>مدیریت سوالات ترین‌ها</b>\n\n"
        keyboard = []
        
        for q in questions:
            status = "🟢 فعال" if q[2] == 1 else "🔴 تمام شده:"
            text += f"شناسه {q[0]}: {q[1]} - {status}\n\n"
            keyboard.append([
                InlineKeyboardButton(f"{'غیرفعال کردن' if q[2] == 1 else 'فعال کردن'} سوال {q[0]}", 
                                    callback_data=f"admin_topq_toggle^{q[0]}")
            ])
        
        keyboard.append([InlineKeyboardButton("افزودن سوال جدید", callback_data="admin_topq_add^")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    elif data.startswith("skip_season_description^"):
        # اگر کاربر از وارد کردن توضیحات صرف نظر کرد
        season_name = context.user_data.get('season_name')
        season_balance = context.user_data.get('season_balance')
        season_description = "" # توضیحات خالی
        
        # ذخیره توضیحات خالی و آماده سازی برای دریافت سوالات
        context.user_data['season_description'] = ""
        context.user_data['season_step'] = 'question_1'
        context.user_data['season_questions'] = []
        
        await query.edit_message_text(
            f"فصل «{season_name}» بدون توضیحات ثبت شد.\n\n"
            f"اکنون لطفاً ۵ سوال اصلی «ترین‌ها» را برای این فصل وارد کنید.\n\n"
            f"سوال ۱ از ۵: لطفاً متن اولین سوال را وارد کنید (مثال: خوش‌اخلاق‌ترین همکار کیست؟)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
        )
        
        await query.answer() # اضافه کردن query.answer()
        return
    elif data.startswith("manage_permissions^"):
        if len(data.split("^")) == 1:
            # اگر هیچ کاربری انتخاب نشده
            c.execute("SELECT user_id, role, permissions FROM admins")
            admins = c.fetchall()
            
            keyboard = []
            for admin_id, role, perms in admins:
                c.execute("SELECT name FROM users WHERE user_id=?", (admin_id,))
                name_row = c.fetchone()
                name = name_row[0] if name_row else f"کاربر {admin_id}"
                keyboard.append([InlineKeyboardButton(f"{name} ({role})", callback_data=f"manage_permissions^{admin_id}")])
            
            keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="adminpanel^")])
            
            await query.edit_message_text(
                "لطفاً ادمینی که می‌خواهید دسترسی‌های آن را مدیریت کنید انتخاب نمایید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # اگر کاربر انتخاب شده
        admin_id = int(data.split("^")[1])
        
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (admin_id,))
        admin_info = c.fetchone()
        
        if not admin_info:
            await query.answer("ادمین مورد نظر یافت نشد!")
            # به جای فراخوانی مستقیم menu_callback، به منوی اصلی ادمین برمی‌گردیم
            await query.edit_message_text(
                "مدیریت دسترسی‌ها",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="manage_permissions^")]])
            )
            return
        
        role, current_permissions = admin_info
        current_permissions = current_permissions.split(",") if current_permissions else []
        
        keyboard = build_permissions_keyboard(current_permissions)
        keyboard.append([InlineKeyboardButton("» ذخیره تغییرات", callback_data=f"save_permissions^{admin_id}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_permissions^")])
        
        c.execute("SELECT name FROM users WHERE user_id=?", (admin_id,))
        name_row = c.fetchone()
        name = name_row[0] if name_row else f"کاربر {admin_id}"
        
        await query.edit_message_text(
            f"مدیریت دسترسی‌های {name} ({role}):\n\n"
            "دسترسی‌های مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data == "manage_seasons^": # اضافه کردن این بلوک
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("➕ ایجاد فصل جدید", callback_data="add_season^")],
            [InlineKeyboardButton("🔄 فعال/غیرفعال کردن فصل", callback_data="toggle_season^")],
            [InlineKeyboardButton("✏️ ویرایش فصل", callback_data="edit_season^")],
            [InlineKeyboardButton("🗑 حذف فصل", callback_data="delete_season^")],
            [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
        ]
        await query.edit_message_text(
            "🔄 <b>مدیریت فصل‌ها</b>\n\n"
            "از این بخش می‌توانید فصل‌های مختلف ربات را مدیریت کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    elif data == "top_vote^":
        await process_next_top_question(update, context)
    elif data.startswith("top_select^"):
        await query.answer()
        parts = data.split("^")
        question_id = int(parts[1])
        voted_for = int(parts[2])
        
        # ذخیره رأی کاربر
        if save_top_vote(user.id, question_id, voted_for):
            # ادامه به سوال بعدی
            await process_next_top_question(update, context)
        else:
            await query.edit_message_text(
                "خطا در ثبت رأی شما. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
    elif data == "top_results^":
        await query.answer()
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            season_id = config.SEASON_ID
            season_name = config.SEASON_NAME
        else:
            season_id = active_season[0]
            season_name = active_season[1]
        
        # دریافت سوالات فعال
        questions = get_active_top_questions()
        
        if not questions:
            await query.edit_message_text(
                f"هیچ سوالی برای فصل {season_name} تعریف نشده است.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
            return
            
        # ساخت متن نتایج
        result_text = f"🏆 <b>نتایج ترین‌های فصل {season_name}</b>\n\n"
        
        for q_id, q_text in questions:
            result_text += f"<b>{q_text}</b>\n"
            
            # دریافت نتایج برای این سوال
            top_results = get_top_results_for_question(q_id)
            
            if top_results:
                for i, (voted_for, count, name) in enumerate(top_results[:3]):
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                    result_text += f"{medal} {name}: {count} رأی\n"
            else:
                result_text += "هنوز رأیی ثبت نشده است.\n"
                
            result_text += "\n" + "-" * 30 + "\n\n"
            
        await query.edit_message_text(
            result_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
            parse_mode="HTML"
        )
    elif data.startswith("approve_user^"):
        await query.answer()
        user_id = int(data.split("^")[1])
        
        # بررسی آیا کاربر قبلاً در دیتابیس موجود است
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        existing_user = c.fetchone()
        
        if not existing_user:
            # دریافت اطلاعات کاربر از تلگرام برای نمایش به ادمین
            try:
                chat_member = await context.bot.get_chat_member(chat_id=user_id, user_id=user_id)
                user_name = chat_member.user.full_name
                user_username = chat_member.user.username
                
                # ذخیره اطلاعات کاربر در context برای استفاده بعدی
                context.user_data['pending_approval'] = {
                    'user_id': user_id,
                    'username': user_username,
                    'telegram_name': user_name
                }
                
                # درخواست نام کاربر از ادمین
                await query.edit_message_text(
                    f"کاربر {user_name} با یوزرنیم @{user_username or 'ندارد'} در حال تایید است.\n\n"
                    f"لطفاً نام واقعی کاربر را وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_approval^")]])
                )
                
                # تنظیم وضعیت انتظار برای دریافت نام
                context.user_data['waiting_for_name'] = True
                
            except Exception as e:
                logger.error(f"Error approving user: {e}")
                await query.edit_message_text(f"خطا در تایید کاربر: {e}")
        else:
            # اگر کاربر قبلاً در دیتابیس باشد
            await query.edit_message_text(f"این کاربر قبلاً در سیستم ثبت شده است!")
    elif data.startswith("reject_user^"):
        await query.answer()
        user_id = int(data.split("^")[1])
        
        try:
            # ارسال پیام به کاربر
            await context.bot.send_message(
                chat_id=user_id,
                text=f"کاربر گرامی، متاسفانه درخواست دسترسی شما به {config.BOT_NAME} تایید نشد. ❌\n\n"
                     f"در صورت نیاز به اطلاعات بیشتر با پشتیبانی تماس بگیرید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("پشتیبانی", url=config.SUPPORT_USERNAME)]])
            )
            
            # پاسخ به ادمین
            await query.edit_message_text(
                f"❌ درخواست کاربر رد شد و به ایشان اطلاع داده شد."
            )
            
        except Exception as e:
            logger.error(f"Error rejecting user: {e}")
            await query.edit_message_text(f"خطا در رد درخواست کاربر: {e}")
    elif data.startswith("cancel_approval^"):
        await query.answer()
        # پاک کردن داده‌های مربوط به تایید
        context.user_data.pop('pending_approval', None)
        context.user_data.pop('waiting_for_name', None)
        
        await query.edit_message_text(
            "فرآیند تایید کاربر لغو شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]])
        )
    elif data.startswith("broadcast_menu^"):
        await query.answer()
        # بررسی دسترسی کاربر
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "admin_users" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        # نمایش منوی ارسال پیام همگانی
        keyboard = [
            [InlineKeyboardButton("ارسال پیام به همه کاربران", callback_data="broadcast_all^")],
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        
        await query.edit_message_text(
            "📢 <b>ارسال پیام همگانی</b>\n\n"
            "با استفاده از این بخش می‌توانید پیامی را به تمام کاربران ربات ارسال کنید.\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    elif data == "broadcast_all^":
        await query.answer()
        # بررسی دسترسی کاربر
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "admin_users" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        
        # آماده‌سازی کاربر برای دریافت متن پیام همگانی
        context.user_data['admin_action'] = 'broadcast'
        
        await query.edit_message_text(
            "📝 <b>ارسال پیام همگانی</b>\n\n"
            "لطفاً متن پیامی که می‌خواهید به تمام کاربران ارسال شود را وارد کنید:\n\n"
            "<i>نکته: می‌توانید از فرمت HTML استفاده کنید. برای مثال: &lt;b&gt;متن پررنگ&lt;/b&gt;</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="broadcast_menu^")]]),
            parse_mode="HTML"
        )
    elif data.startswith("season_top_results^"):
        await query.answer()
        season_id = int(data.split("^")[1])
        
        # دریافت اطلاعات فصل
        c.execute("SELECT name FROM season WHERE id=?", (season_id,))
        season_row = c.fetchone()
        
        if not season_row:
            await query.answer("فصل مورد نظر یافت نشد!")
            await query.edit_message_text(
                "فصل مورد نظر یافت نشد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="season_archive")]])
            )
            return
            
        season_name = season_row[0]
        
        # دریافت سوالات ترین‌های این فصل
        c.execute("""
            SELECT question_id, text
            FROM top_questions
            WHERE season_id = ?
            ORDER BY question_id ASC
        """, (season_id,))
        
        questions = c.fetchall()
        
        if not questions:
            await query.edit_message_text(
                f"هیچ سوالی برای فصل {season_name} تعریف نشده است.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data=f"season_archive^{season_id}")]])
            )
            return
            
        # ساخت متن نتایج
        result_text = f"🏆 <b>نتایج ترین‌های فصل {season_name}</b>\n\n"
        
        for q_id, q_text in questions:
            result_text += f"<b>{q_text}</b>\n"
            
            # دریافت نتایج برای این سوال
            c.execute("""
                SELECT v.voted_for_user_id, COUNT(v.vote_id) as vote_count, u.name
                FROM top_votes v
                JOIN users u ON v.voted_for_user_id = u.user_id
                WHERE v.question_id = ? AND v.season_id = ?
                GROUP BY v.voted_for_user_id
                ORDER BY vote_count DESC
                LIMIT 3
            """, (q_id, season_id))
            
            top_results = c.fetchall()
            
            if top_results:
                for i, (voted_for, count, name) in enumerate(top_results):
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                    result_text += f"{medal} {name}: {count} رأی\n"
            else:
                result_text += "هیچ رأیی ثبت نشده است.\n"
                
            result_text += "\n" + "-" * 30 + "\n\n"
            
        await query.edit_message_text(
            result_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data=f"season_archive^{season_id}")]]),
            parse_mode="HTML"
        )
    elif data.startswith("giftcard_start^"):
        await query.answer()
        users = get_all_users(exclude_id=user.id)
        if not users:
            await query.edit_message_text("هیچ کاربر دیگری برای ارسال کارت هدیه وجود ندارد!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # اضافه کردن توضیحات برای بخش کارت هدیه
        welcome_message = "🎁 ارسال کارت هدیه 💌\n\n"
        welcome_message += "با استفاده از این بخش می‌توانید یک کارت هدیه زیبا با پیام دلخواه خود برای دوستانتان ارسال کنید.\n\n"
        welcome_message += "✅ این سرویس کاملاً رایگان است و نیازی به اعتبار ندارد.\n"
        welcome_message += "✅ کارت هدیه‌های شما به صورت خصوصی ارسال می‌شود و در کانال عمومی منتشر نمی‌شود.\n\n"
        welcome_message += "✨ روش استفاده:\n"
        welcome_message += "۱. ابتدا کاربر مورد نظر خود را از لیست زیر انتخاب کنید\n"
        welcome_message += "۲. متن پیام خود را تایپ کنید\n"
        welcome_message += "۳. کارت هدیه شما به صورت خودکار طراحی و ارسال می‌شود\n\n"
        welcome_message += "👥 لطفاً کاربر مورد نظر را انتخاب کنید:"
        
        keyboard = []
        row = []
        for i, u in enumerate(users):
            row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"giftcard_selectuser^{u[0]}"))
            if len(row) == 2 or i == len(users) - 1:
                if len(row) == 1 and i == len(users) - 1:
                    keyboard.append(row)
                elif len(row) == 2:
                    keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
        await query.edit_message_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("giftcard_selectuser^"):
        await query.answer()
        receiver_id = int(data.split("^")[1])
        
        c.execute("SELECT name FROM users WHERE user_id=?", (receiver_id,))
        result = c.fetchone()
        receiver_name = result[0] if result else "کاربر"
        
        context.user_data['gift_card_receiver_id'] = receiver_id
        context.user_data['gift_card_receiver_name'] = receiver_name
        context.user_data['waiting_for_gift_card_message'] = True
        
        await query.edit_message_text(
            f"شما در حال ارسال کارت هدیه به {receiver_name} هستید.\n\n"
            f"لطفاً متن دلخواه خود را برای کارت هدیه بنویسید و ارسال کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="giftcard_start^")]])
        )
    else:
        await query.answer("در حال توسعه ...")

# تابع بررسی مدیر اصلی
def is_god_admin(user_id):
    c.execute("SELECT role FROM admins WHERE user_id=?", (user_id,))
    admin = c.fetchone()
    return admin is not None and admin[0] == 'god'

async def process_next_top_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش سوال بعدی در رأی‌گیری ترین‌ها"""
    query = update.callback_query
    user = query.from_user
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        # اگر فصل فعالی وجود نداشت، از مقدار پیش‌فرض استفاده کن
        season_id = config.SEASON_ID
        season_name = config.SEASON_NAME
    else:
        season_id = active_season[0]
        season_name = active_season[1]
    
    # دریافت سوال بعدی
    next_question = get_next_unanswered_question(user.id)
    
    if not next_question:
        # اگر همه سوالات پاسخ داده شده‌اند، نمایش خلاصه رأی‌های کاربر
        user_votes = get_user_top_votes(user.id)
        summary = f"🎉 <b>تبریک!</b>\n\nشما به تمام سوالات ترین‌های فصل {season_name} پاسخ دادید.\n\n<b>رأی‌های شما:</b>\n\n"
        
        for q_text, voted_name, _ in user_votes:
            summary += f"🔹 {q_text}\n"
            summary += f"✓ رأی شما: {voted_name}\n\n"
        
        keyboard = [[InlineKeyboardButton("» مشاهده نتایج", callback_data="top_results^")]]
        
        await query.edit_message_text(
            summary,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
        
    question_id, question_text = next_question
    
    # دریافت لیست کاربران برای رأی‌دهی (به جز خود کاربر)
    users = get_all_users(exclude_id=user.id)
    keyboard = []
    row = []
    for i, u in enumerate(users):
        row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"top_select^{question_id}^{u[0]}"))
        if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
            if len(row) == 1 and i == len(users) - 1:  # اگر آخرین آیتم تنها در ردیف باشد
                keyboard.append(row)
            elif len(row) == 2:
                keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
    
    await query.edit_message_text(
        f"🏆 <b>ترین‌های فصل {season_name}</b>\n\n"
        f"<b>سوال {len(get_user_top_votes(user.id))+1}:</b> {question_text}\n\n"
        f"لطفاً یکی از همکاران خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های متنی دریافتی از کاربران"""
    user = update.effective_user
    message_text = update.message.text # تغییر نام متغیر برای جلوگیری از تداخل
    
    # بررسی آیا کاربر منتظر دریافت دلیل امتیازدهی است
    if context.user_data.get('waiting_for_reason'):
        # دریافت اطلاعات ذخیره شده
        pending_transaction = context.user_data.get('pending_transaction', {})
        touser_id = pending_transaction.get('touser_id')
        amount = pending_transaction.get('amount')
        touser_name = pending_transaction.get('touser_name', 'کاربر')
        
        # پاک کردن وضعیت انتظار
        context.user_data.pop('waiting_for_reason', None)
        context.user_data.pop('pending_transaction', None)
        
        if not touser_id or not amount:
            await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
            return
        
        # تنظیم دکمه تأیید
        keyboard = [
            [InlineKeyboardButton("✅ تأیید", callback_data=f"Confirm^{touser_id}^{amount}^{message_text}")],
            [InlineKeyboardButton("❌ لغو", callback_data="tovote^")]
        ]
        
        await update.message.reply_text(
            f"در حال ارسال {amount} امتیاز به {touser_name}\n\n"
            f"📝 دلیل: {message_text}\n\n"
            f"آیا تأیید می‌کنید؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif context.user_data.get('waiting_for_gift_card_message'):
        receiver_id = context.user_data.get('gift_card_receiver_id')
        receiver_name = context.user_data.get('gift_card_receiver_name', 'کاربر')
        sender_id = user.id
        
        # دریافت نام فرستنده از دیتابیس
        c.execute("SELECT name FROM users WHERE user_id=?", (sender_id,))
        sender_result = c.fetchone()
        sender_name = sender_result[0] if sender_result else "یک دوست"

        # پاک کردن وضعیت انتظار
        context.user_data.pop('waiting_for_gift_card_message', None)
        context.user_data.pop('gift_card_receiver_id', None)
        context.user_data.pop('gift_card_receiver_name', None)

        if not receiver_id:
            await update.message.reply_text("خطا در پردازش کارت هدیه. لطفاً دوباره تلاش کنید.")
            return

        gift_message = message_text.strip()
        if not gift_message:
            await update.message.reply_text(
                "متن کارت هدیه نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 کارت هدیه", callback_data="giftcard_start^")]])
            )
            return

        # ایجاد تصویر کارت هدیه
        image_path = giftcard.create_gift_card_image(sender_name, receiver_name, gift_message)

        if image_path:
            caption = f"🎁 یک کارت هدیه از طرف {sender_name} برای شما! 💌\n\nمتن پیام:\n{gift_message}"
            god_admin_caption = f"🎁 کارت هدیه ارسالی:\n\nاز: {sender_name} (ID: {sender_id})\nبه: {receiver_name} (ID: {receiver_id})\n\nمتن پیام:\n{gift_message}"
            
            try:
                # ارسال به گیرنده
                with open(image_path, 'rb') as photo_file:
                    await context.bot.send_photo(chat_id=receiver_id, photo=InputFile(photo_file), caption=caption)
                
                # ارسال به ادمین گاد
                if hasattr(config, 'GOD_ADMIN_ID') and config.GOD_ADMIN_ID:
                    with open(image_path, 'rb') as photo_file_admin: # دوباره باز کردن فایل
                        await context.bot.send_photo(chat_id=config.GOD_ADMIN_ID, photo=InputFile(photo_file_admin), caption=god_admin_caption)
                else:
                    logger.warning("GOD_ADMIN_ID در config.py تعریف نشده یا خالی است. کارت هدیه به ادمین ارسال نشد.")

                await update.message.reply_text(
                    f"کارت هدیه شما با موفقیت برای {receiver_name} ارسال شد! ✅",
                    reply_markup=main_menu_keyboard(user.id)
                )
            except Exception as e:
                logger.error(f"خطا در ارسال کارت هدیه: {e}")
                await update.message.reply_text("متاسفانه در ارسال کارت هدیه خطایی رخ داد.")
            finally:
                # حذف فایل موقت تصویر
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e_remove:
                        logger.error(f"خطا در حذف فایل موقت کارت هدیه {image_path}: {e_remove}")
        else:
            await update.message.reply_text("متاسفانه در ایجاد تصویر کارت هدیه خطایی رخ داد. لطفاً مطمئن شوید فایل قالب و فونت به درستی در سرور موجود است.")
        return
    # بررسی آیا ادمین در حال وارد کردن نام کاربر برای تایید است
    if context.user_data.get('waiting_for_name'):
        # دریافت اطلاعات کاربر در حال تایید
        pending_approval = context.user_data.get('pending_approval', {})
        user_id = pending_approval.get('user_id')
        username = pending_approval.get('username')
        telegram_name = pending_approval.get('telegram_name')
        
        # پاک کردن وضعیت انتظار
        context.user_data.pop('waiting_for_name', None)
        context.user_data.pop('pending_approval', None)
        
        if not user_id:
            await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
            return
        
        real_name = message_text.strip()
        if not real_name:
            await update.message.reply_text(
                "نام وارد شده معتبر نیست. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]])
            )
            return
        
        try:
            # اضافه کردن کاربر به دیتابیس با نام واقعی
            c.execute("INSERT INTO users (user_id, username, name, balance) VALUES (?, ?, ?, ?)", 
                     (user_id, username, real_name, 10))  # اعتبار اولیه 10
            conn.commit()
            
            # دریافت فصل فعال
            active_season = get_active_season()
            season_name = ""
            if active_season:
                season_name = f" - فصل {active_season[1]}"
                
            # ارسال پیام به کاربر با نام واقعی
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{real_name} عزیز، درخواست دسترسی شما به {config.BOT_NAME}{season_name} تایید شد! ✅\n\n"
                     f"می‌توانید اکنون از خدمات ربات استفاده کنید. برای شروع دستور /start را ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 ورود به ربات", url=f"https://t.me/{context.bot.username}?start=start")]])
            )
            
            # پاسخ به ادمین
            await update.message.reply_text(
                f"✅ کاربر {real_name} (با نام تلگرام {telegram_name}) با موفقیت تایید شد و اکنون می‌تواند از ربات استفاده کند.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
            )
            
        except Exception as e:
            logger.error(f"Error approving user with custom name: {e}")
            await update.message.reply_text(
                f"خطا در تایید کاربر: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]])
            )
            
        return
    
    # پردازش سایر حالت‌های انتظار برای دریافت ورودی
    # بررسی آیا کاربر در حال افزودن سوال ترین‌ها است
    if context.user_data.get('admin_action') == 'add_top_question':
        # پاک کردن وضعیت انتظار
        context.user_data.pop('admin_action', None)
        
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            await update.message.reply_text("خطا: هیچ فصل فعالی وجود ندارد!")
            return
            
        # افزودن سوال جدید
        c.execute("""
            INSERT INTO top_questions (text, is_active, season_id)
            VALUES (?, 1, ?)
        """, (message_text, active_season[0]))
        conn.commit()
        
        await update.message.reply_text(
            "سوال جدید با موفقیت اضافه شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به مدیریت سوالات", callback_data="manage_top_questions^")]])
        )
        return
    
    # بررسی آیا کاربر در حال افزودن فصل جدید است
    if context.user_data.get('admin_action') == 'add_season':
        season_step = context.user_data.get('season_step')
        
        if season_step == 'name':
            context.user_data['season_name'] = message_text
            context.user_data['season_step'] = 'balance'
            await update.message.reply_text(
                f"لطفاً اعتبار اولیه برای فصل «{message_text}» را وارد کنید (مثلاً: 10):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'balance':
            try:
                balance = int(message_text)
                if balance <= 0:
                    await update.message.reply_text(
                        "اعتبار باید یک عدد مثبت باشد. لطفاً دوباره وارد کنید:",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                    )
                    return
                context.user_data['season_balance'] = balance
                context.user_data['season_step'] = 'description'
                await update.message.reply_text(
                    "اختیاری: لطفاً توضیحات کوتاهی برای این فصل وارد کنید، یا دکمه «توضیحاتی ندارم» را بزنید:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 توضیحاتی ندارم", callback_data="skip_season_description^")],
                        [InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]
                    ])
                )
            except ValueError:
                await update.message.reply_text(
                    "اعتبار وارد شده نامعتبر است. لطفاً یک عدد وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
        elif season_step == 'description':
            context.user_data['season_description'] = message_text
            # آماده‌سازی برای دریافت سوالات ترین‌ها
            context.user_data['season_step'] = 'question_1'
            context.user_data['season_questions'] = []
            
            await update.message.reply_text(
                f"توضیحات فصل «{context.user_data.get('season_name')}» ثبت شد.\n\n"
                f"اکنون لطفاً ۵ سوال اصلی «ترین‌ها» را برای این فصل وارد کنید.\n\n"
                f"سوال ۱ از ۵: لطفاً متن اولین سوال را وارد کنید (مثال: خوش‌اخلاق‌ترین همکار کیست؟)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'question_1':
            if not message_text.strip():
                await update.message.reply_text(
                    "متن سوال نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
            
            context.user_data['season_questions'].append(message_text)
            context.user_data['season_step'] = 'question_2'
            
            await update.message.reply_text(
                "سوال ۲ از ۵: لطفاً متن دومین سوال را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'question_2':
            if not message_text.strip():
                await update.message.reply_text(
                    "متن سوال نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
            
            context.user_data['season_questions'].append(message_text)
            context.user_data['season_step'] = 'question_3'
            
            await update.message.reply_text(
                "سوال ۳ از ۵: لطفاً متن سومین سوال را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'question_3':
            if not message_text.strip():
                await update.message.reply_text(
                    "متن سوال نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
            
            context.user_data['season_questions'].append(message_text)
            context.user_data['season_step'] = 'question_4'
            
            await update.message.reply_text(
                "سوال ۴ از ۵: لطفاً متن چهارمین سوال را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'question_4':
            if not message_text.strip():
                await update.message.reply_text(
                    "متن سوال نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
            
            context.user_data['season_questions'].append(message_text)
            context.user_data['season_step'] = 'question_5'
            
            await update.message.reply_text(
                "سوال ۵ از ۵: لطفاً متن آخرین سوال را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
            )
            return
        elif season_step == 'question_5':
            if not message_text.strip():
                await update.message.reply_text(
                    "متن سوال نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_seasons^")]])
                )
                return
            
            context.user_data['season_questions'].append(message_text)
            
            # اطلاعات فصل و سوالات آماده ثبت است
            season_name = context.user_data.get('season_name')
            season_balance = context.user_data.get('season_balance')
            season_description = context.user_data.get('season_description')
            season_questions = context.user_data.get('season_questions')
            
            # ایجاد فصل جدید
            season_id = add_season(season_name, season_balance, season_description)
            
            if season_id:
                # افزودن سوالات به دیتابیس
                success_count = 0
                for question_text in season_questions:
                    if add_season_top_question(season_id, question_text):
                        success_count += 1
                
                await update.message.reply_text(
                    f"فصل «{season_name}» با موفقیت ایجاد شد!\n\n"
                    f"تعداد {success_count} سوال از ۵ سوال ترین‌ها ثبت شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به مدیریت فصل‌ها", callback_data="manage_seasons^")]])
                )
            else:
                await update.message.reply_text(
                    "خطا در ایجاد فصل جدید. لطفاً دوباره تلاش کنید.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به مدیریت فصل‌ها", callback_data="manage_seasons^")]])
                )
            
            # پاک کردن داده‌های موقت
            context.user_data.pop('admin_action', None)
            context.user_data.pop('season_step', None)
            context.user_data.pop('season_name', None)
            context.user_data.pop('season_balance', None)
            context.user_data.pop('season_description', None)
            context.user_data.pop('season_questions', None)
            
            return
    
    # بررسی آیا ادمین در حال ارسال پیام همگانی است
    elif context.user_data.get('admin_action') == 'broadcast':
        # پاک کردن وضعیت انتظار
        context.user_data.pop('admin_action', None)
        
        if not message_text.strip():
            await update.message.reply_text(
                "متن پیام نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="broadcast_menu^")]])
            )
            return
        
        # دریافت لیست تمام کاربران
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        
        if not users:
            await update.message.reply_text(
                "هیچ کاربری در سیستم یافت نشد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
            )
            return
        
        # شروع ارسال پیام به کاربران
        status_message = await update.message.reply_text(
            "⏳ در حال ارسال پیام همگانی...\n"
            "لطفاً صبر کنید..."
        )
        
        successful = 0
        failed = 0
        bot = context.bot
        
        # اضافه کردن دکمه به پیام (اختیاری)
        keyboard = None
        if bot.username:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 ورود به ربات", url=f"https://t.me/{bot.username}")]
            ])
        
        # ارسال پیام به تمام کاربران
        for user_row in users:
            try:
                await bot.send_message(
                    chat_id=user_row[0],
                    text=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                successful += 1
            except Exception as e:
                logger.error(f"خطا در ارسال پیام همگانی به کاربر {user_row[0]}: {e}")
                failed += 1
                
            # آپدیت پیام وضعیت هر 10 کاربر
            if (successful + failed) % 10 == 0:
                try:
                    await status_message.edit_text(
                        f"⏳ در حال ارسال پیام همگانی...\n"
                        f"موفق: {successful}\n"
                        f"ناموفق: {failed}\n"
                        f"پیشرفت: {successful + failed}/{len(users)}"
                    )
                except:
                    pass
        
        # آپدیت نهایی پیام وضعیت
        await status_message.edit_text(
            f"✅ ارسال پیام همگانی به پایان رسید!\n\n"
            f"✓ موفق: {successful}\n"
            f"❌ ناموفق: {failed}\n"
            f"📊 مجموع: {len(users)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
        )
        return
     
     # بررسی آیا کاربر در حال افزودن فصل جدید است

async def main():
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
    
    # افزودن هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # اجرای ربات
    print("ربات اجرا شد...")
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
    while True:
        try:
            # هر 5 دقیقه یک درخواست ساده به API تلگرام ارسال می‌کنیم
            logger.debug("ارسال درخواست keep-alive...")
            await bot.get_me()
            logger.debug("درخواست keep-alive با موفقیت انجام شد")
        except Exception as e:
            logger.warning(f"خطا در درخواست keep-alive: {e}")
        
        # انتظار برای 5 دقیقه
        await asyncio.sleep(300)

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