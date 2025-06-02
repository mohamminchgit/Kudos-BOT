import sqlite3
import config
import sys

def add_season_id_column():
    """اضافه کردن ستون season_id به جدول transactions در صورت عدم وجود"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        print("🔍 بررسی ستون season_id در جدول transactions...")
        
        # بررسی وجود ستون season_id
        c.execute("PRAGMA table_info(transactions)")
        columns = c.fetchall()
        column_names = [col[1] for col in columns]
        
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
        
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ خطا در اضافه کردن ستون season_id: {e}")
        return False

def show_sql_commands():
    """نمایش دستورات SQL لازم برای اضافه کردن ستون season_id"""
    print("\n📝 دستورات SQL برای اضافه کردن ستون season_id به جدول transactions:")
    print("ALTER TABLE transactions ADD COLUMN season_id INTEGER DEFAULT 1;")
    print("UPDATE transactions SET season_id = 1 WHERE season_id IS NULL;")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--show-sql':
        show_sql_commands()
    else:
        result = add_season_id_column()
        
        if result:
            print("\n🎉 عملیات با موفقیت انجام شد!")
            print("\n💡 برای مشاهده دستورات SQL، از پارامتر '--show-sql' استفاده کنید:")
            print("python fix_db.py --show-sql")
        else:
            print("\n❌ عملیات با خطا مواجه شد!")
            print("\n💡 دستورات SQL مورد نیاز:")
            show_sql_commands() 