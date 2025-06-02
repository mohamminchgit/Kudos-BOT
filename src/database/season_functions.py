"""
توابع مربوط به مدیریت فصل‌ها و سوالات ترین‌ها
"""
import sqlite3
import logging
from .models import db_manager
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

logger = logging.getLogger(__name__)

def get_active_season():
    """دریافت فصل فعال"""
    try:
        result = db_manager.execute_query(
            "SELECT id, name, balance FROM season WHERE is_active=1 LIMIT 1", 
            fetchone=True
        )
        return result
    except sqlite3.OperationalError:
        # در صورت عدم وجود ستون created_at یا جدول
        logger.warning("مشکل در دسترسی به جدول season - استفاده از مقادیر پیش‌فرض")
        return (config.SEASON_ID, config.SEASON_NAME, 10)  # مقادیر پیش‌فرض

def get_all_seasons():
    """دریافت همه فصل‌ها"""
    try:
        result = db_manager.execute_query(
            "SELECT id, name, balance, is_active FROM season ORDER BY id DESC"
        )
        if not result:
            logger.info("No seasons found in the database!")
        return result
    except Exception as e:
        logger.error(f"Error in get_all_seasons: {e}")
        return []

def add_season(name, balance, description=''):
    """افزودن فصل جدید"""
    try:
        result = db_manager.execute_query(
            "INSERT INTO season (name, balance, description, is_active) VALUES (?, ?, ?, 0)", 
            (name, balance, description), 
            commit=True
        )
        if result:
            # دریافت ID آخرین رکورد اضافه شده
            conn = db_manager.get_connection()
            return conn.lastrowid
        return None
    except sqlite3.OperationalError as e:
        logger.error(f"خطا در افزودن فصل جدید: {e}")
        return None

def update_season(season_id, name=None, balance=None, description=None):
    """بروزرسانی فصل"""
    if name is not None:
        db_manager.execute_query(
            "UPDATE season SET name=? WHERE id=?", 
            (name, season_id), 
            commit=True
        )
    if balance is not None:
        db_manager.execute_query(
            "UPDATE season SET balance=? WHERE id=?", 
            (balance, season_id), 
            commit=True
        )
    if description is not None:
        db_manager.execute_query(
            "UPDATE season SET description=? WHERE id=?", 
            (description, season_id), 
            commit=True
        )
    return True

def end_season(season_id):
    """پایان فصل"""
    try:
        return db_manager.execute_query(
            "UPDATE season SET is_active=0 WHERE id=?", 
            (season_id,), 
            commit=True
        )
    except sqlite3.OperationalError as e:
        logger.error(f"خطا در پایان دادن به فصل: {e}")
        return False

# توابع مربوط به سوالات ترین‌ها
def get_all_top_questions():
    """دریافت همه سوالات ترین‌ها"""
    return db_manager.execute_query(
        "SELECT question_id, text, is_active FROM top_questions ORDER BY question_id DESC"
    )

def get_top_questions_for_season(season_id):
    """دریافت همه سوالات ترین‌های یک فصل خاص"""
    return db_manager.execute_query(
        "SELECT question_id, text, is_active FROM top_questions WHERE season_id=? ORDER BY question_id DESC", 
        (season_id,)
    )

def add_master_top_question(text):
    """سوال را به لیست جامع سوالات ترین‌ها اضافه می‌کند، در صورت عدم وجود."""
    try:
        return db_manager.execute_query(
            "INSERT OR IGNORE INTO master_top_questions (text) VALUES (?)", 
            (text,), 
            commit=True
        )
    except Exception as e:
        logger.error(f"Error adding to master_top_questions: {e}")
        return False

def add_season_top_question(season_id, question_text, is_active=1):
    """یک سوال ترین‌ها را برای فصل مشخص شده اضافه می‌کند"""
    if not add_master_top_question(question_text):
        return None 
    
    try:
        result = db_manager.execute_query("""
            INSERT INTO top_questions (text, is_active, season_id)
            VALUES (?, ?, ?)
        """, (question_text, is_active, season_id), commit=True)
        
        if result:
            conn = db_manager.get_connection()
            return conn.lastrowid
        return None
    except Exception as e:
        logger.error(f"Error adding season top question for season {season_id}: {e}")
        return None

def update_top_question(question_id, text=None, is_active=None):
    """بروزرسانی سوال ترین‌ها"""
    if text is not None and is_active is not None:
        return db_manager.execute_query(
            "UPDATE top_questions SET text=?, is_active=? WHERE question_id=?", 
            (text, is_active, question_id), 
            commit=True
        )
    elif text is not None:
        return db_manager.execute_query(
            "UPDATE top_questions SET text=? WHERE question_id=?", 
            (text, question_id), 
            commit=True
        )
    elif is_active is not None:
        return db_manager.execute_query(
            "UPDATE top_questions SET is_active=? WHERE question_id=?", 
            (is_active, question_id), 
            commit=True
        )
    return True

def delete_top_question(question_id):
    """حذف سوال ترین‌ها"""
    return db_manager.execute_query(
        "DELETE FROM top_questions WHERE question_id=?", 
        (question_id,), 
        commit=True
    )
