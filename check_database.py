#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def check_database():
    db_path = "kudosbot.db"
    
    if not os.path.exists(db_path):
        print("❌ دیتابیس وجود ندارد!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # بررسی جداول موجود
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print("✅ جداول موجود در دیتابیس:")
        for table in tables:
            print(f"  - {table}")
            
            # نمایش تعداد رکوردها
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"    تعداد رکورد: {count}")
        
        print("\n" + "="*50)
        
        # بررسی وجود کاربران
        if 'users' in tables:
            cursor.execute("SELECT user_id, name FROM users LIMIT 5")
            users = cursor.fetchall()
            print("👥 نمونه کاربران:")
            for user in users:
                print(f"  - {user[1]} (ID: {user[0]})")
        
        # بررسی فصل فعال
        if 'season' in tables:
            cursor.execute("SELECT id, name, is_active FROM season WHERE is_active=1")
            active_season = cursor.fetchone()
            if active_season:
                print(f"🏆 فصل فعال: {active_season[1]} (ID: {active_season[0]})")
            else:
                print("❌ هیچ فصل فعالی وجود ندارد")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ خطا در بررسی دیتابیس: {e}")

if __name__ == "__main__":
    check_database()
