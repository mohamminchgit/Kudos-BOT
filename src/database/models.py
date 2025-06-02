"""
مدل‌های پایگاه داده برای ربات کادوس
"""
import sqlite3
import logging
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """کلاس مدیریت پایگاه داده"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()
    
    def _init_db(self):
        """ایجاد جداول مورد نیاز"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # ایجاد جدول جامع سوالات ترین‌ها
        c.execute('''
        CREATE TABLE IF NOT EXISTS master_top_questions (
            master_question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # ایجاد جدول تنظیمات
        c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # بررسی وجود تنظیم نمایش کاربران
        c.execute("SELECT value FROM settings WHERE key='show_all_users'")
        result = c.fetchone()
        if result is None:
            # اضافه کردن تنظیم پیش‌فرض
            c.execute(
                "INSERT INTO settings (key, value, description) VALUES (?, ?, ?)",
                ('show_all_users', '1', 'نمایش لیست همه کاربران در منوی امتیازدهی')
            )
            logger.info("تنظیم پیش‌فرض نمایش کاربران اضافه شد")
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """ایجاد و برگرداندن اتصال به دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_query(self, query, params=None, fetchone=False, commit=False):
        """اجرای کوئری SQL با یک اتصال جدید"""
        conn = None
        try:
            conn = self.get_connection()
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

# سنگلتون برای استفاده در کل برنامه
db_manager = DatabaseManager()

# لیست دسترسی‌های ادمین
ADMIN_PERMISSIONS = [
    ("admin_users", "مدیریت کاربران"),
    ("admin_transactions", "مدیریت تراکنش"),
    ("admin_stats", "آمار و گزارشات"),
    ("manage_admins", "مدیریت ادمین‌ها"),
    ("manage_questions", "مدیریت سوالات ترین‌ها"),
]
