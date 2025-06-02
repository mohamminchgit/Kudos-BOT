import sqlite3
import config
import traceback

def check_and_fix_transactions_table():
    """بررسی و اصلاح ساختار جدول transactions"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        print("🔍 بررسی ساختار جدول transactions...")
        
        # بررسی ستون‌های موجود در جدول transactions
        c.execute("PRAGMA table_info(transactions)")
        columns = c.fetchall()
        
        # نمایش ستون‌های موجود
        print("📋 ستون‌های موجود در جدول transactions:")
        column_names = []
        for col in columns:
            column_names.append(col[1])
            print(f"  • {col[1]} ({col[2]})")
        
        # بررسی وجود ستون season_id
        if 'season_id' not in column_names:
            print("❌ ستون season_id در جدول transactions وجود ندارد!")
            print("🔧 در حال اضافه کردن ستون season_id...")
            
            # اضافه کردن ستون season_id
            c.execute("ALTER TABLE transactions ADD COLUMN season_id INTEGER DEFAULT 1")
            conn.commit()
            print("✅ ستون season_id با موفقیت به جدول transactions اضافه شد")
            
            # تنظیم مقدار پیش‌فرض برای ستون season_id
            active_season_id = config.SEASON_ID
            print(f"🔄 در حال تنظیم مقدار پیش‌فرض {active_season_id} برای ستون season_id...")
            c.execute("UPDATE transactions SET season_id = ? WHERE season_id IS NULL", (active_season_id,))
            conn.commit()
            print(f"✅ مقدار پیش‌فرض {active_season_id} برای ستون season_id تنظیم شد")
        else:
            print("✅ ستون season_id در جدول transactions وجود دارد")
        
        # نمایش نمونه‌ای از داده‌های جدول
        print("\n📊 نمونه داده‌های جدول transactions:")
        c.execute("SELECT * FROM transactions LIMIT 3")
        rows = c.fetchall()
        for row in rows:
            print(f"  • {row}")
        
        print("\n🧪 تست کوئری زاویه دید دیگران:")
        try:
            # اجرای کوئری زاویه دید دیگران با استفاده از season_id
            c.execute("""
                SELECT t.reason, t.amount, u.name AS from_name, t.season_id, s.name AS season_name
                FROM transactions t
                JOIN users u ON t.user_id = u.user_id
                LEFT JOIN season s ON t.season_id = s.id
                WHERE t.touser = ?
                ORDER BY t.created_at DESC
                LIMIT 3
            """, (rows[0][2],))  # استفاده از touser اولین تراکنش
            
            results = c.fetchall()
            print(f"  • تعداد نتایج: {len(results)}")
            for result in results:
                print(f"  • {result}")
            
            print("✅ کوئری زاویه دید دیگران با موفقیت اجرا شد")
        except Exception as e:
            print(f"❌ خطا در اجرای کوئری زاویه دید دیگران: {e}")
            traceback.print_exc()
        
        conn.close()
        print("\n🎉 بررسی و اصلاح جدول transactions با موفقیت به پایان رسید")
        print("\nدستور SQL برای اضافه کردن ستون season_id (در صورت نیاز):")
        print("ALTER TABLE transactions ADD COLUMN season_id INTEGER DEFAULT 1;")
        print("UPDATE transactions SET season_id = 1 WHERE season_id IS NULL;")
        
    except Exception as e:
        print(f"❌ خطا در بررسی جدول transactions: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_and_fix_transactions_table() 