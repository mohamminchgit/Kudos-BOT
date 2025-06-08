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
        # حذف فاصله‌های اضافی از ابتدا و انتهای رشته جستجو
        search_query = search_query.strip()
        logger.debug(f"جستجو برای کاربر با نام: '{search_query}'")
        
        # ابتدا همه کاربران را دریافت می‌کنیم
        if exclude_id is not None:
            all_users = db_manager.execute_query("""
                SELECT user_id, name FROM users 
                WHERE user_id != ? 
                ORDER BY name
            """, (exclude_id,))
        else:
            all_users = db_manager.execute_query("""
                SELECT user_id, name FROM users 
                ORDER BY name
            """)
        
        # اطمینان از اینکه نتایج خالی نیست
        if all_users is None:
            logger.error(f"نتیجه دریافت همه کاربران برگشت None")
            return []
        
        # فیلتر کردن کاربران بر اساس نام (با حذف فاصله‌های اضافی)
        filtered_users = []
        for user in all_users:
            if search_query.lower() in user[1].strip().lower():
                filtered_users.append(user)
                if len(filtered_users) >= limit:
                    break
        
        # چاپ تعداد نتایج برای اشکال‌زدایی
        logger.debug(f"تعداد {len(filtered_users)} کاربر برای جستجوی '{search_query}' یافت شد")
        
        # لاگ کردن نام‌های یافت شده برای اشکال‌زدایی
        for user in filtered_users:
            logger.debug(f"کاربر یافت شده: شناسه={user[0]}, نام='{user[1]}', نام بعد از strip='{user[1].strip()}'")
        
        return filtered_users
        
    except Exception as e:
        logger.error(f"خطا در جستجوی کاربران: {e}")
        return []
