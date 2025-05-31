#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os

output_file = 'db_check_output.txt'

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=== بررسی وضعیت دیتابیس ===\n")
    
    db_file = 'kudosbot.db'
    if not os.path.exists(db_file):
        f.write(f"خطا: فایل دیتابیس '{db_file}' وجود ندارد!\n")
        exit(1)
    
    f.write(f"فایل دیتابیس '{db_file}' پیدا شد. اندازه: {os.path.getsize(db_file) / 1024:.2f} کیلوبایت\n")
    
    try:
        # اتصال به دیتابیس
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # بررسی تمام جدول‌ها
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        f.write(f"\nتعداد جدول‌های موجود: {len(tables)}\n")
        for table in tables:
            table_name = table[0]
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = c.fetchone()[0]
            f.write(f"  {table_name}: {count} رکورد\n")
        
        # بررسی جدول season
        f.write("\n=== بررسی جدول season ===\n")
        try:
            c.execute("PRAGMA table_info(season)")
            columns = c.fetchall()
            f.write(f"ستون‌های جدول season: {[col[1] for col in columns]}\n")
            
            c.execute("SELECT * FROM season")
            seasons = c.fetchall()
            f.write(f"تعداد فصل‌ها: {len(seasons)}\n")
            for season in seasons:
                f.write(f"  {season}\n")
        except Exception as e:
            f.write(f"خطا در بررسی جدول season: {e}\n")
        
        # بررسی جدول transactions
        f.write("\n=== بررسی جدول transactions ===\n")
        try:
            c.execute("PRAGMA table_info(transactions)")
            columns = c.fetchall()
            f.write(f"ستون‌های جدول transactions: {[col[1] for col in columns]}\n")
            
            c.execute("SELECT COUNT(*) FROM transactions")
            count = c.fetchone()[0]
            f.write(f"تعداد تراکنش‌ها: {count}\n")
        except Exception as e:
            f.write(f"خطا در بررسی جدول transactions: {e}\n")
        
        # بستن اتصال
        conn.close()
        f.write("\nبررسی با موفقیت انجام شد.\n")
        
    except Exception as e:
        f.write(f"خطای کلی: {e}\n")

print(f"نتایج در فایل {output_file} ذخیره شد.") 