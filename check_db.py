#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import config
import sys
import codecs

# در ویندوز، تنظیم خروجی با UTF-8
if sys.platform == 'win32':
    # تغییر کدپیج کنسول به UTF-8
    import os
    os.system('chcp 65001 > nul')
    
    # تنظیم خروجی با UTF-8
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

# اتصال به دیتابیس
conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# نمایش جداول موجود
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t['name'] for t in c.fetchall()]
print("Tables in database:", tables)

# بررسی ساختار جدول‌های مورد نیاز
for table in tables:
    print(f"\nStructure of table '{table}':")
    c.execute(f"PRAGMA table_info({table})")
    columns = c.fetchall()
    for col in columns:
        print(f"  {col['name']} ({col['type']})")

# بررسی محتوای جداول مهم
print("\n--- Season Table ---")
try:
    c.execute("SELECT * FROM season")
    seasons = c.fetchall()
    for s in seasons:
        print(f"  ID: {s['id']}, Name: {s['name']}, Is Active: {s['is_active']}")
except:
    try:
        c.execute("SELECT * FROM seasons")
        seasons = c.fetchall()
        for s in seasons:
            print(f"  ID: {s['season_id']}, Name: {s['name']}, Is Active: {s['is_active']}")
    except:
        print("  No season table found or error accessing it")

print("\n--- Top Questions Table ---")
try:
    c.execute("SELECT * FROM top_questions LIMIT 5")
    questions = c.fetchall()
    for q in questions:
        print(f"  ID: {q['question_id']}, Text: {q['text'][:30]}..., Season ID: {q['season_id']}, Is Active: {q['is_active']}")
    
    c.execute("SELECT COUNT(*) FROM top_questions")
    count = c.fetchone()[0]
    print(f"  Total questions: {count}")
except:
    print("  Error accessing top_questions table")

print("\n--- Top Votes Table ---")
try:
    c.execute("SELECT COUNT(*) FROM top_votes")
    count = c.fetchone()[0]
    print(f"  Total votes: {count}")
    
    c.execute("SELECT DISTINCT season_id FROM top_votes")
    seasons = [s[0] for s in c.fetchall()]
    print(f"  Season IDs in votes: {seasons}")
except:
    print("  Error accessing top_votes table")

# بستن اتصال
conn.close()

print("\nDatabase check completed!") 