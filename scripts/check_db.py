import sqlite3
import os
import config

def check_database():
    """بررسی وضعیت دیتابیس و جداول موجود"""
    # بررسی وجود فایل دیتابیس
    if not os.path.exists(config.DB_PATH):
        print(f"❌ فایل دیتابیس {config.DB_PATH} وجود ندارد!")
        return
    
    print(f"✅ فایل دیتابیس {config.DB_PATH} یافت شد.")
    
    try:
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # دریافت لیست جداول موجود
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        
        if not tables:
            print("❌ هیچ جدولی در دیتابیس یافت نشد!")
            return
        
        print("===== جداول موجود در دیتابیس =====")
        for table in tables:
            print(f"- {table[0]}")
            
            # نمایش ساختار هر جدول
            try:
                c.execute(f"PRAGMA table_info({table[0]})")
                columns = c.fetchall()
                print(f"  ستون‌های جدول {table[0]}:")
                for column in columns:
                    print(f"    - {column[1]} ({column[2]})")
                print("")
            except sqlite3.Error as e:
                print(f"  خطا در دریافت ساختار جدول: {e}")
        
        # بررسی وجود جدول ai_user_perspectives
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_user_perspectives';")
        if c.fetchone():
            print("✅ جدول ai_user_perspectives وجود دارد.")
        else:
            print("❌ جدول ai_user_perspectives وجود ندارد!")
            
            # ایجاد جدول اگر وجود ندارد
            print("در حال ایجاد جدول ai_user_perspectives...")
            c.execute('''
                CREATE TABLE ai_user_perspectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    season_id INTEGER,
                    perspective_text TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("✅ جدول ai_user_perspectives با موفقیت ایجاد شد.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"❌ خطا در اتصال به دیتابیس: {e}")

def check_ai_perspectives_table():
    """بررسی وجود جدول ai_user_perspectives و ایجاد آن در صورت نیاز"""
    # بررسی وجود فایل دیتابیس
    if not os.path.exists(config.DB_PATH):
        print(f"❌ فایل دیتابیس {config.DB_PATH} وجود ندارد!")
        return False
    
    print(f"✅ فایل دیتابیس {config.DB_PATH} یافت شد.")
    
    try:
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # بررسی وجود جدول ai_user_perspectives
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_user_perspectives';")
        if c.fetchone():
            print("✅ جدول ai_user_perspectives وجود دارد.")
            return True
        else:
            print("❌ جدول ai_user_perspectives وجود ندارد!")
            
            # ایجاد جدول اگر وجود ندارد
            print("در حال ایجاد جدول ai_user_perspectives...")
            c.execute('''
                CREATE TABLE ai_user_perspectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    season_id INTEGER,
                    perspective_text TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            print("✅ جدول ai_user_perspectives با موفقیت ایجاد شد.")
            return True
    except sqlite3.Error as e:
        print(f"❌ خطا در اتصال به دیتابیس: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_ai_perspectives_table()
    print("مسیر دیتابیس:", config.DB_PATH) 