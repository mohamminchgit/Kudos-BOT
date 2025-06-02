import sqlite3
import config
import traceback

def check_database_structure():
    """بررسی ساختار دیتابیس"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        print("\n===== بررسی جداول دیتابیس =====")
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        
        print(f"تعداد جداول: {len(tables)}")
        for table in tables:
            print(f"- {table[0]}")
            # بررسی ساختار جدول
            c.execute(f"PRAGMA table_info({table[0]})")
            columns = c.fetchall()
            for col in columns:
                print(f"    • {col[1]} ({col[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"خطا در بررسی ساختار دیتابیس: {e}")
        traceback.print_exc()

def check_admins():
    """بررسی وضعیت ادمین‌ها در دیتابیس"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # بررسی وجود جدول admins
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admins'")
        if not c.fetchone():
            print("❌ جدول admins در دیتابیس وجود ندارد!")
            print("   در حال ایجاد جدول admins...")
            c.execute("""
                CREATE TABLE admins (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL,
                    permissions TEXT
                )
            """)
            conn.commit()
            print("✅ جدول admins با موفقیت ایجاد شد")
        
        print(f"\n===== بررسی ادمین اصلی =====")
        c.execute("SELECT * FROM admins WHERE user_id=?", (config.ADMIN_USER_ID,))
        admin = c.fetchone()
        
        if admin:
            print(f"✅ ادمین اصلی با شناسه {config.ADMIN_USER_ID} وجود دارد")
            print(f"   نقش: {admin['role']}")
            print(f"   دسترسی‌ها: {admin['permissions'] or 'دسترسی کامل (god)'}")
        else:
            print(f"❌ ادمین اصلی با شناسه {config.ADMIN_USER_ID} در دیتابیس یافت نشد!")
            print("   در حال افزودن ادمین اصلی...")
            c.execute("INSERT OR REPLACE INTO admins (user_id, role, permissions) VALUES (?, 'god', NULL)", (config.ADMIN_USER_ID,))
            conn.commit()
            print("✅ ادمین اصلی با موفقیت افزوده شد")
        
        print("\n===== بررسی وجود کاربر ادمین در جدول users =====")
        c.execute("SELECT * FROM users WHERE user_id=?", (config.ADMIN_USER_ID,))
        user = c.fetchone()
        
        if user:
            print(f"✅ کاربر ادمین با شناسه {config.ADMIN_USER_ID} در جدول users وجود دارد")
            print(f"   نام: {user['name']}")
            print(f"   یوزرنیم: {user['username']}")
        else:
            print(f"❌ کاربر ادمین با شناسه {config.ADMIN_USER_ID} در جدول users یافت نشد!")
            print("   در حال افزودن کاربر ادمین...")
            c.execute("INSERT INTO users (user_id, username, name, balance) VALUES (?, 'admin', 'Admin', 100)", (config.ADMIN_USER_ID,))
            conn.commit()
            print("✅ کاربر ادمین با موفقیت افزوده شد")
        
        print("\n===== لیست همه ادمین‌ها =====")
        c.execute("SELECT a.user_id, a.role, a.permissions, u.name FROM admins a LEFT JOIN users u ON a.user_id = u.user_id")
        admins = c.fetchall()
        
        for admin in admins:
            print(f"👤 شناسه: {admin['user_id']}, نام: {admin['name'] or 'نامشخص'}, نقش: {admin['role']}, دسترسی‌ها: {admin['permissions'] or 'دسترسی کامل (god)'}")
        
        conn.close()
        
    except Exception as e:
        print(f"خطا در بررسی ادمین‌ها: {e}")
        traceback.print_exc()

def check_transactions():
    """بررسی تراکنش‌ها برای مشکل زاویه دید دیگران"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        print("\n===== بررسی تراکنش‌ها =====")
        
        # دریافت یک نمونه تراکنش
        c.execute("SELECT * FROM transactions LIMIT 1")
        sample = c.fetchone()
        
        if sample:
            print(f"نمونه تراکنش: {dict(sample)}")
            
            # تست کوئری برای دیدگاه دیگران
            user_id = sample['touser']  # کاربری که می‌خواهیم دیدگاه دیگران درباره او را ببینیم
            
            print(f"\n===== تست کوئری زاویه دید دیگران برای کاربر {user_id} =====")
            
            try:
                # کوئری اصلاح شده در ai.py
                c.execute("""
                    SELECT t.reason, t.amount, u.name AS from_name, t.season_id, s.name AS season_name
                    FROM transactions t
                    JOIN users u ON t.user_id = u.user_id
                    LEFT JOIN season s ON t.season_id = s.id
                    WHERE t.touser = ?
                    ORDER BY t.created_at DESC
                    LIMIT 5
                """, (user_id,))
                
                reasons = c.fetchall()
                print(f"تعداد نتایج: {len(reasons)}")
                for reason in reasons:
                    print(f"- {reason['from_name']} ({reason['amount']} امتیاز): {reason['reason']} (فصل: {reason['season_name']})")
                
                # تست کوئری برای رای‌های ترین‌ها
                c.execute("""
                    SELECT tq.text AS question, u.name AS voter_name, s.name AS season_name
                    FROM top_votes tv
                    JOIN top_questions tq ON tv.question_id = tq.question_id
                    JOIN users u ON tv.user_id = u.user_id
                    JOIN season s ON tv.season_id = s.id
                    WHERE tv.voted_for_user_id = ?
                    ORDER BY tv.vote_time DESC
                    LIMIT 5
                """, (user_id,))
                
                top_votes = c.fetchall()
                print(f"\nتعداد رای‌های ترین‌ها: {len(top_votes)}")
                for vote in top_votes:
                    print(f"- {vote['voter_name']} به او برای '{vote['question']}' رای داده (فصل: {vote['season_name']})")
            
            except Exception as e:
                print(f"❌ خطا در اجرای کوئری: {e}")
                traceback.print_exc()
        else:
            print("هیچ تراکنشی در دیتابیس یافت نشد.")
        
        conn.close()
        
    except Exception as e:
        print(f"خطا در بررسی تراکنش‌ها: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_database_structure()
    check_admins()
    check_transactions() 