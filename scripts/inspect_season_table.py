import sqlite3
import config
import traceback

def inspect_season_table():
    """بررسی جدول season و ارتباط آن با transactions"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        print("🔍 بررسی جدول season...")
        
        # بررسی ساختار جدول season
        c.execute("PRAGMA table_info(season)")
        columns = c.fetchall()
        
        print("📋 ستون‌های جدول season:")
        column_names = []
        for col in columns:
            column_names.append(col[1])
            print(f"  • {col[1]} ({col[2]})")
        
        # بررسی داده‌های جدول season
        c.execute("SELECT * FROM season ORDER BY id")
        seasons = c.fetchall()
        
        print(f"\n📊 فصل‌های موجود ({len(seasons)}):")
        for season in seasons:
            status = "✅ فعال" if season['is_active'] == 1 else "❌ غیرفعال"
            print(f"  • فصل {season['id']}: {season['name']} - {status}")
        
        # بررسی فصل فعال
        c.execute("SELECT id, name FROM season WHERE is_active = 1")
        active_season = c.fetchone()
        
        if active_season:
            print(f"\n🔔 فصل فعال: {active_season['name']} (ID: {active_season['id']})")
        else:
            print("\n⚠️ هیچ فصل فعالی وجود ندارد!")
        
        # بررسی تراکنش‌ها بر اساس فصل
        print("\n📈 آمار تراکنش‌ها بر اساس فصل:")
        c.execute("""
            SELECT s.id, s.name, COUNT(t.transaction_id) as transaction_count
            FROM season s
            LEFT JOIN transactions t ON s.id = t.season_id
            GROUP BY s.id
            ORDER BY s.id
        """)
        season_stats = c.fetchall()
        
        for stat in season_stats:
            print(f"  • فصل {stat['id']} ({stat['name']}): {stat['transaction_count']} تراکنش")
        
        # بررسی تراکنش‌های بدون فصل
        c.execute("SELECT COUNT(*) as count FROM transactions WHERE season_id IS NULL")
        null_season_count = c.fetchone()['count']
        
        if null_season_count > 0:
            print(f"\n⚠️ تعداد {null_season_count} تراکنش بدون فصل (season_id IS NULL) وجود دارد!")
            
            # اصلاح تراکنش‌های بدون فصل
            active_season_id = active_season['id'] if active_season else 1
            print(f"🔧 در حال تنظیم فصل {active_season_id} برای تراکنش‌های بدون فصل...")
            c.execute("UPDATE transactions SET season_id = ? WHERE season_id IS NULL", (active_season_id,))
            conn.commit()
            print(f"✅ فصل {active_season_id} برای تراکنش‌های بدون فصل تنظیم شد")
        else:
            print("\n✅ همه تراکنش‌ها دارای مقدار فصل هستند")
        
        # بررسی یک نمونه از کوئری‌های مشکل‌دار
        print("\n🧪 تست کوئری زاویه دید دیگران با شرط فصل:")
        
        # 1. اولین کوئری: بررسی دلایل امتیازدهی
        try:
            test_user_id = 0
            test_season_id = active_season['id'] if active_season else 1
            
            # پیدا کردن یک کاربر با تراکنش
            c.execute("SELECT DISTINCT touser FROM transactions LIMIT 1")
            user_row = c.fetchone()
            if user_row:
                test_user_id = user_row['touser']
            
            season_condition = f"AND t.season_id = {test_season_id}"
            
            # تست کوئری اول
            sql_query = f"""
                SELECT t.reason, t.amount, u.name AS from_name, t.season_id, s.name AS season_name
                FROM transactions t
                JOIN users u ON t.user_id = u.user_id
                LEFT JOIN season s ON t.season_id = s.id
                WHERE t.touser = ? {season_condition}
                ORDER BY t.created_at DESC
                LIMIT 2
            """
            
            print(f"🔍 کوئری 1 (برای کاربر {test_user_id}, فصل {test_season_id}):")
            print(f"SQL: {sql_query}")
            
            c.execute(sql_query, (test_user_id,))
            results = c.fetchall()
            
            print(f"  • تعداد نتایج: {len(results)}")
            for i, result in enumerate(results):
                print(f"  • نتیجه {i+1}: {dict(result)}")
            
            print("✅ کوئری 1 با موفقیت اجرا شد")
        except Exception as e:
            print(f"❌ خطا در اجرای کوئری 1: {e}")
            traceback.print_exc()
        
        # 2. دومین کوئری: بررسی رای‌های ترین‌ها
        try:
            # تست کوئری دوم
            sql_query = f"""
                SELECT tq.text AS question, u.name AS voter_name, s.name AS season_name
                FROM top_votes tv
                JOIN top_questions tq ON tv.question_id = tq.question_id
                JOIN users u ON tv.user_id = u.user_id
                JOIN season s ON tv.season_id = s.id
                WHERE tv.voted_for_user_id = ? {season_condition}
                ORDER BY tv.vote_time DESC
                LIMIT 2
            """
            
            print(f"\n🔍 کوئری 2 (برای کاربر {test_user_id}, فصل {test_season_id}):")
            print(f"SQL: {sql_query}")
            
            c.execute(sql_query, (test_user_id,))
            results = c.fetchall()
            
            print(f"  • تعداد نتایج: {len(results)}")
            for i, result in enumerate(results):
                print(f"  • نتیجه {i+1}: {dict(result)}")
            
            print("✅ کوئری 2 با موفقیت اجرا شد")
        except Exception as e:
            print(f"❌ خطا در اجرای کوئری 2: {e}")
            traceback.print_exc()
        
        conn.close()
        print("\n🎉 بررسی جدول season با موفقیت به پایان رسید")
        
    except Exception as e:
        print(f"❌ خطا در بررسی جدول season: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    inspect_season_table() 