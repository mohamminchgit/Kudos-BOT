import sqlite3
import sys

def check_user(search_name):
    try:
        conn = sqlite3.connect('kudosbot.db')
        cursor = conn.cursor()
        
        # جستجوی کاربر با نام مشابه
        cursor.execute("SELECT user_id, name, username, balance FROM users WHERE name LIKE ?", (f'%{search_name}%',))
        users = cursor.fetchall()
        
        if not users:
            print(f"هیچ کاربری با نام مشابه '{search_name}' یافت نشد.")
        else:
            print(f"تعداد {len(users)} کاربر با نام مشابه '{search_name}' یافت شد:")
            for user in users:
                print(f"شناسه: {user[0]}, نام: {user[1]}, یوزرنیم: {user[2]}, موجودی: {user[3]}")
        
        # همچنین کاربر با نام دقیق را بررسی کنیم
        cursor.execute("SELECT user_id, name, username, balance FROM users WHERE name = ?", (search_name,))
        exact_user = cursor.fetchone()
        
        if exact_user:
            print(f"\nکاربر با نام دقیق '{search_name}' یافت شد:")
            print(f"شناسه: {exact_user[0]}, نام: {exact_user[1]}, یوزرنیم: {exact_user[2]}, موجودی: {exact_user[3]}")
        else:
            print(f"\nهیچ کاربری با نام دقیق '{search_name}' یافت نشد.")
            
        # بررسی ساختار جدول users
        print("\nستون‌های جدول users:")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"شماره: {col[0]}, نام: {col[1]}, نوع: {col[2]}")
            
        conn.close()
    except Exception as e:
        print(f"خطا در بررسی دیتابیس: {e}")

if __name__ == "__main__":
    search_name = "مصطفی طحان"
    if len(sys.argv) > 1:
        search_name = sys.argv[1]
    
    print(f"در حال جستجوی کاربر با نام: '{search_name}'")
    check_user(search_name) 