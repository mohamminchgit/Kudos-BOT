# -*- coding: utf-8 -*-
"""
ماژول توابع کمکی برای مدیریت اتصال دیتابیس
این ماژول شامل توابعی برای مدیریت اتصال به دیتابیس و عملیات پایه روی آن است
"""

import sqlite3
import logging
import config
import traceback

# تنظیم لاگر
logger = logging.getLogger(__name__)

def get_db_connection():
    """ایجاد و برگرداندن اتصال به دیتابیس"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

def get_or_create_user(user):
    """بررسی وجود کاربر و در صورت نیاز ایجاد آن"""
    result = execute_db_query("SELECT * FROM users WHERE user_id=?", (user.id,), fetchone=True)
    return result is not None

def is_user_approved(user_id):
    """بررسی آیا کاربر در سیستم تایید شده است"""
    return execute_db_query("SELECT * FROM users WHERE user_id=?", (user_id,), fetchone=True) is not None

def add_user(user):
    """اضافه کردن کاربر جدید به سیستم"""
    return execute_db_query(
        "INSERT INTO users (user_id, username, name, balance, is_approved) VALUES (?, ?, ?, 10, 1)", 
        (user.id, user.username, user.full_name), 
        commit=True
    )

def get_user_by_id(user_id):
    """دریافت اطلاعات کاربر بر اساس شناسه"""
    return execute_db_query("SELECT * FROM users WHERE user_id=?", (user_id,), fetchone=True)

def get_all_users(exclude_id=None):
    """دریافت لیست همه کاربران"""
    if exclude_id:
        return execute_db_query("SELECT user_id, name FROM users WHERE user_id != ?", (exclude_id,))
    else:
        return execute_db_query("SELECT user_id, name FROM users")

def get_active_season():
    """دریافت فصل فعال"""
    try:
        result = execute_db_query("SELECT id, name, balance FROM season WHERE is_active=1 LIMIT 1", fetchone=True)
        if result:
            return result
        logger.warning("هیچ فصل فعالی یافت نشد - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض
    except Exception as e:
        logger.warning(f"مشکل در دسترسی به جدول season: {e} - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض

def get_all_seasons():
    """دریافت همه فصل‌ها"""
    try:
        result = execute_db_query("SELECT id, name, balance, is_active FROM season ORDER BY id DESC")
        if not result:
            logger.warning("هیچ فصلی در دیتابیس یافت نشد!")
        return result or []
    except Exception as e:
        logger.error(f"خطا در دریافت فصل‌ها: {e}")
        return []

def get_user_profile(user_id):
    """دریافت پروفایل کاربر"""
    return execute_db_query("""
        SELECT u.*, 
            (SELECT SUM(t.amount) 
             FROM transactions t
             WHERE t.touser = u.user_id) AS total_received
        FROM users u
        WHERE u.user_id=?
    """, (user_id,), fetchone=True)

def is_user_approved(user_id):
    """بررسی آیا کاربر در سیستم تایید شده است"""
    return execute_db_query("SELECT * FROM users WHERE user_id=?", (user_id,), fetchone=True) is not None

def get_user_by_id(user_id):
    """دریافت اطلاعات کاربر بر اساس شناسه"""
    return execute_db_query("SELECT * FROM users WHERE user_id=?", (user_id,), fetchone=True)

def get_active_season():
    """دریافت فصل فعال"""
    try:
        result = execute_db_query("SELECT id, name, balance FROM season WHERE is_active=1 LIMIT 1", fetchone=True)
        if result:
            return result
        logger.warning("هیچ فصل فعالی یافت نشد - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض
    except Exception as e:
        logger.warning(f"مشکل در دسترسی به جدول season: {e} - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض

def get_all_seasons():
    """دریافت همه فصل‌ها"""
    return execute_db_query("SELECT * FROM season ORDER BY is_active DESC, id DESC")

def get_user_profile(user_id):
    """دریافت پروفایل کاربر"""
    return execute_db_query("""
        SELECT u.*, 
            (SELECT SUM(amount) FROM transactions WHERE touser = u.user_id) as total_received
        FROM users u 
        WHERE u.user_id = ?
    """, (user_id,), fetchone=True)

def get_user_transactions(user_id, given=True, offset=0, limit=3, season_id=None):
    """دریافت تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND t.season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params + [limit, offset]
        query = f"""
            SELECT t.amount, t.touser, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """
    else:
        params = [user_id] + params + [limit, offset]
        query = f"""
            SELECT t.amount, t.user_id, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """
    
    return execute_db_query(query, params)

def count_user_transactions(user_id, given=True, season_id=None):
    """شمارش تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params
        query = f"SELECT COUNT(*) FROM transactions WHERE user_id=?{season_filter}"
    else:
        params = [user_id] + params
        query = f"SELECT COUNT(*) FROM transactions WHERE touser=?{season_filter}"
    
    result = execute_db_query(query, params, fetchone=True)
    return result[0] if result else 0

def get_scoreboard(season_id=None):
    """دریافت تابلوی امتیازات با امکان فیلتر بر اساس فصل"""
    if season_id is not None:
        return execute_db_query("""
            SELECT touser, SUM(amount) as total, u.name 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.season_id=?
            GROUP BY touser 
            ORDER BY total DESC LIMIT 10
        """, (season_id,))
    else:
        return execute_db_query("""
            SELECT touser, SUM(amount) as total, u.name 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            GROUP BY touser 
            ORDER BY total DESC LIMIT 10
        """)

def add_transaction(user_id, touser_id, amount, season_id, reason, message_id=None):
    """اضافه کردن یک تراکنش جدید"""
    # کم کردن از موجودی کاربر فرستنده
    execute_db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", 
                    (amount, user_id), commit=True)
    
    # اضافه کردن تراکنش
    return execute_db_query("""
        INSERT INTO transactions (user_id, touser, amount, season_id, reason, message_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, touser_id, amount, season_id, reason, message_id), commit=True)

# توابع مدیریت ترین‌ها
def get_all_top_questions():
    """دریافت همه سوالات ترین‌ها"""
    return execute_db_query("SELECT question_id, text, is_active FROM top_questions ORDER BY question_id DESC")

def get_top_questions_for_season(season_id):
    """دریافت همه سوالات ترین‌های یک فصل خاص"""
    return execute_db_query("SELECT question_id, text, is_active FROM top_questions WHERE season_id=? ORDER BY question_id DESC", (season_id,))

def add_season_top_question(season_id, question_text, is_active=1):
    """یک سوال ترین‌ها را برای فصل مشخص شده اضافه می‌کند"""
    # اول سوال را به master list اضافه کن
    execute_db_query("INSERT OR IGNORE INTO master_top_questions (text) VALUES (?)", (question_text,), commit=True)
    
    # حالا سوال را برای فصل اضافه کن
    result = execute_db_query("""
        INSERT INTO top_questions (text, is_active, season_id)
        VALUES (?, ?, ?)
    """, (question_text, is_active, season_id), commit=True)
    
    if result:
        # دریافت آیدی سوال اضافه شده
        conn = get_db_connection()
        return conn.lastrowid
    return None

def update_top_question(question_id, text=None, is_active=None):
    """بروزرسانی سوال ترین‌ها"""
    if text is not None and is_active is not None:
        return execute_db_query("UPDATE top_questions SET text=?, is_active=? WHERE question_id=?", 
                               (text, is_active, question_id), commit=True)
    elif text is not None:
        return execute_db_query("UPDATE top_questions SET text=? WHERE question_id=?", 
                               (text, question_id), commit=True)
    elif is_active is not None:
        return execute_db_query("UPDATE top_questions SET is_active=? WHERE question_id=?", 
                               (is_active, question_id), commit=True)
    return False

def delete_top_question(question_id):
    """حذف سوال ترین‌ها"""
    return execute_db_query("DELETE FROM top_questions WHERE question_id=?", (question_id,), commit=True)

def has_user_voted_all_top_questions(user_id):
    """بررسی آیا کاربر به همه سوالات ترین‌ها پاسخ داده است"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        return False
    
    season_id = active_season[0]
    
    # دریافت تعداد سوالات فعال
    total_questions_result = execute_db_query("""
        SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
    """, (season_id,), fetchone=True)
    total_questions = total_questions_result[0] if total_questions_result else 0
    
    if total_questions == 0:
        return True
    
    # دریافت تعداد رأی‌های کاربر
    user_votes_result = execute_db_query("""
        SELECT COUNT(*) FROM top_votes 
        WHERE user_id=? AND season_id=?
    """, (user_id, season_id), fetchone=True)
    user_votes = user_votes_result[0] if user_votes_result else 0
    
    return user_votes >= total_questions

# توابع مدیریت فصل‌ها
def add_season(name, balance, description=''):
    """افزودن فصل جدید"""
    try:
        result = execute_db_query("INSERT INTO season (name, balance, description, is_active) VALUES (?, ?, ?, 0)", 
                                (name, balance, description), commit=True)
        if result:
            conn = get_db_connection()
            return conn.lastrowid
        return None
    except Exception as e:
        logger.error(f"خطا در افزودن فصل جدید: {e}")
        return None

def update_season(season_id, name=None, balance=None, description=None):
    """بروزرسانی فصل"""
    if name is not None:
        execute_db_query("UPDATE season SET name=? WHERE id=?", (name, season_id), commit=True)
    if balance is not None:
        execute_db_query("UPDATE season SET balance=? WHERE id=?", (balance, season_id), commit=True)
    if description is not None:
        execute_db_query("UPDATE season SET description=? WHERE id=?", (description, season_id), commit=True)
    return True

def end_season(season_id):
    """پایان فصل"""
    try:
        return execute_db_query("UPDATE season SET is_active=0 WHERE id=?", (season_id,), commit=True)
    except Exception as e:
        logger.error(f"خطا در پایان دادن به فصل: {e}")
        return False

def delete_season(season_id):
    """حذف فصل"""
    # بررسی اینکه فصل فعال نباشد
    result = execute_db_query("SELECT is_active FROM season WHERE id=?", (season_id,), fetchone=True)
    if not result or result[0] == 1:
        return False
    
    return execute_db_query("DELETE FROM season WHERE id=?", (season_id,), commit=True)

def activate_season(season_id):
    """فعال‌سازی فصل"""
    try:
        # غیرفعال کردن همه فصل‌های فعال قبلی
        execute_db_query("UPDATE season SET is_active=0 WHERE is_active=1", commit=True)
        
        # فعال کردن فصل مورد نظر
        execute_db_query("UPDATE season SET is_active=1 WHERE id=?", (season_id,), commit=True)
        
        # دریافت اعتبار فصل
        balance_result = execute_db_query("SELECT balance FROM season WHERE id=?", (season_id,), fetchone=True)
        balance = balance_result[0] if balance_result else 10
        
        # اعطای اعتبار به همه کاربران
        execute_db_query("UPDATE users SET balance=?", (balance,), commit=True)
        
        return balance
    except Exception as e:
        logger.error(f"خطا در فعال‌سازی فصل: {e}")
        return 10  # مقدار پیش‌فرض
