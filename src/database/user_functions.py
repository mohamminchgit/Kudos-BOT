"""
توابع مربوط به مدیریت کاربران
"""
import sqlite3
import logging
from .models import db_manager
from .db_utils import get_db_connection
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

logger = logging.getLogger(__name__)

def get_or_create_user(user):
    """بررسی یا ایجاد کاربر"""
    result = db_manager.execute_query(
        "SELECT * FROM users WHERE user_id=?", 
        (user.id,), 
        fetchone=True
    )
    return result is not None

def is_user_approved(user_id):
    """بررسی آیا کاربر تایید شده است"""
    result = db_manager.execute_query(
        "SELECT * FROM users WHERE user_id=?", 
        (user_id,), 
        fetchone=True
    )
    return result is not None

def add_user(user):
    """افزودن کاربر جدید"""
    return db_manager.execute_query(
        "INSERT INTO users (user_id, username, name) VALUES (?, ?, ?)", 
        (user.id, user.username, user.full_name), 
        commit=True
    )

def get_user_by_id(user_id):
    """دریافت کاربر بر اساس شناسه"""
    return db_manager.execute_query(
        "SELECT * FROM users WHERE user_id = ?", 
        (user_id,), 
        fetchone=True
    )

def get_all_users(exclude_id=None):
    """دریافت همه کاربران"""
    if exclude_id:
        return db_manager.execute_query(
            "SELECT user_id, name FROM users WHERE user_id != ?", 
            (exclude_id,)
        )
    else:
        return db_manager.execute_query("SELECT user_id, name FROM users")

def get_user_profile(user_id):
    """دریافت پروفایل کاربر شامل نام، موجودی و مجموع دریافتی"""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # دریافت اطلاعات کاربر
        c.execute("""
            SELECT u.name, u.user_id, us.season_id, u.balance, COALESCE(u.total_received, 0) as total_received
            FROM users u
            LEFT JOIN user_season us ON u.user_id = us.user_id AND us.season_id = (
                SELECT id FROM season WHERE is_active = 1
            )
            WHERE u.user_id = ?
        """, (user_id,))
        
        result = c.fetchone()
        
        if result:
            # اگر total_received NULL باشد، مقدار 0 را جایگزین می‌کنیم
            profile = list(result)
            if profile[4] is None:
                profile[4] = 0
                
                # همچنین مقدار را در دیتابیس به‌روزرسانی می‌کنیم
                c.execute("UPDATE users SET total_received = 0 WHERE user_id = ? AND total_received IS NULL", (user_id,))
                conn.commit()
            
            return profile
        else:
            # کاربر یافت نشد
            return None
    except Exception as e:
        logger.error(f"خطا در دریافت پروفایل کاربر: {e}")
        return None
    finally:
        conn.close()

def get_user_transactions(user_id, given=True, offset=0, limit=3, season_id=None):
    """دریافت تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND t.season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params + [limit, offset]
        return db_manager.execute_query(f"""
            SELECT t.amount, t.touser, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, params)
    else:
        params = [user_id] + params + [limit, offset]
        return db_manager.execute_query(f"""
            SELECT t.amount, t.user_id, u.name, t.reason, t.created_at, t.message_id, t.transaction_id, t.season_id
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser=?{season_filter} 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, params)

def count_user_transactions(user_id, given=True, season_id=None):
    """شمارش تراکنش‌های کاربر با امکان فیلتر بر اساس فصل"""
    season_filter = ""
    params = []
    
    if season_id is not None:
        season_filter = " AND season_id=?"
        params = [season_id]
        
    if given:
        params = [user_id] + params
        result = db_manager.execute_query(f"""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE user_id=?{season_filter}
        """, params, fetchone=True)
    else:
        params = [user_id] + params
        result = db_manager.execute_query(f"""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE touser=?{season_filter}
        """, params, fetchone=True)
    
    return result[0] if result else 0

def get_scoreboard(season_id=None):
    """دریافت تابلوی امتیازات با امکان فیلتر بر اساس فصل"""
    if season_id is not None:
        return db_manager.execute_query("""
            SELECT touser, SUM(amount) as total, u.name 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.season_id=?
            GROUP BY touser 
            ORDER BY total DESC LIMIT 10
        """, (season_id,))
    else:
        return db_manager.execute_query("""
            SELECT touser, SUM(amount) as total, u.name 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            GROUP BY touser 
            ORDER BY total DESC LIMIT 10
        """)

def search_users(search_query, limit=10, exclude_id=None):
    """جستجوی کاربران بر اساس نام
    
    Args:
        search_query (str): متن جستجو
        limit (int): حداکثر تعداد نتایج
        exclude_id (int): شناسه کاربری که باید از نتایج حذف شود (مثلاً خود کاربر)
    
    Returns:
        list: لیستی از کاربران یافت شده
    """
    try:
        if exclude_id is not None:
            results = db_manager.execute_query("""
                SELECT user_id, name FROM users 
                WHERE name LIKE ? AND user_id != ? 
                ORDER BY name LIMIT ?
            """, (f"%{search_query}%", exclude_id, limit))
        else:
            results = db_manager.execute_query("""
                SELECT user_id, name FROM users 
                WHERE name LIKE ? 
                ORDER BY name LIMIT ?
            """, (f"%{search_query}%", limit))
        
        # اطمینان از اینکه نتایج خالی نیست
        if results is None:
            logger.error(f"نتیجه جستجو برای '{search_query}' برگشت None")
            return []
            
        # چاپ تعداد نتایج برای اشکال‌زدایی
        logger.debug(f"تعداد {len(results)} کاربر برای جستجوی '{search_query}' یافت شد")
        return results
    except Exception as e:
        logger.error(f"خطا در جستجوی کاربران: {e}")
        return []
