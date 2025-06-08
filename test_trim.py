import sqlite3

def test_trim_function():
    try:
        # ایجاد یک دیتابیس موقت در حافظه
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # ایجاد جدول تست
        cursor.execute("""
            CREATE TABLE test_users (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        
        # افزودن داده‌های تست با فاصله اضافی
        test_data = [
            (1, "نام عادی"),
            (2, " نام با فاصله ابتدا"),
            (3, "نام با فاصله انتها "),
            (4, " نام با فاصله ابتدا و انتها ")
        ]
        
        cursor.executemany("INSERT INTO test_users (id, name) VALUES (?, ?)", test_data)
        conn.commit()
        
        # تست تابع TRIM
        print("نتایج جستجو با استفاده از تابع TRIM:")
        try:
            cursor.execute("SELECT id, name, TRIM(name) AS trimmed_name FROM test_users")
            results = cursor.fetchall()
            
            for row in results:
                print(f"ID: {row[0]}, اصلی: '{row[1]}', بعد از TRIM: '{row[2]}'")
                
            # تست جستجو با TRIM
            search_query = "نام"
            print(f"\nنتایج جستجو برای '{search_query}' با استفاده از TRIM:")
            cursor.execute("SELECT id, name FROM test_users WHERE TRIM(name) LIKE ?", (f"%{search_query}%",))
            search_results = cursor.fetchall()
            
            for row in search_results:
                print(f"ID: {row[0]}, نام: '{row[1]}'")
                
            print("\nتست TRIM با موفقیت انجام شد!")
        except Exception as e:
            print(f"خطا در اجرای TRIM: {e}")
            
            # تست با راه حل جایگزین
            print("\nاستفاده از راه حل جایگزین بدون TRIM:")
            # استفاده از روش جایگزین با strip() در پایتون
            cursor.execute("SELECT id, name FROM test_users")
            results = cursor.fetchall()
            
            filtered_results = []
            search_query = "نام"
            for row in results:
                name = row[1].strip()
                if search_query in name:
                    filtered_results.append(row)
                    print(f"ID: {row[0]}, اصلی: '{row[1]}', بعد از strip(): '{name}'")
            
            print(f"\nتعداد {len(filtered_results)} نتیجه با استفاده از strip() پایتون یافت شد.")
        
        conn.close()
        
    except Exception as e:
        print(f"خطا در اجرای تست: {e}")

if __name__ == "__main__":
    test_trim_function() 