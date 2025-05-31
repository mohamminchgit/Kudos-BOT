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

print("آغاز اصلاح دیتابیس...")

# اتصال به دیتابیس
conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# دریافت فصل فعال
c.execute("SELECT * FROM season WHERE is_active=1")
active_season = c.fetchone()

if not active_season:
    print("خطا: هیچ فصل فعالی یافت نشد!")
    conn.close()
    exit(1)

active_season_id = active_season['id']
active_season_name = active_season['name']

print(f"فصل فعال: {active_season_name} (ID: {active_season_id})")

# بررسی سوالات با season_id نادرست
c.execute("""
    SELECT COUNT(*) as count FROM top_questions 
    WHERE season_id != ?
""", (active_season_id,))

wrong_season_questions_count = c.fetchone()['count']

if wrong_season_questions_count > 0:
    print(f"\n{wrong_season_questions_count} سوال با season_id نادرست یافت شد.")
    
    # نمایش سوالات با season_id نادرست
    c.execute("""
        SELECT * FROM top_questions
        WHERE season_id != ?
    """, (active_season_id,))
    
    wrong_questions = c.fetchall()
    for q in wrong_questions:
        print(f"  سوال {q['question_id']}: \"{q['text'][:50]}...\", فصل فعلی: {q['season_id']}")
    
    # پرسش از کاربر برای اصلاح
    answer = input("\nآیا می‌خواهید همه سوالات را به فصل فعال منتقل کنید؟ (y/n): ")
    
    if answer.lower() == 'y':
        # انتقال سوالات به فصل فعال
        c.execute("""
            UPDATE top_questions
            SET season_id = ?
            WHERE season_id != ?
        """, (active_season_id, active_season_id))
        
        conn.commit()
        print(f"{wrong_season_questions_count} سوال به فصل فعال منتقل شد.")
        
        # اصلاح رای‌ها متناسب با سوالات
        c.execute("""
            UPDATE top_votes
            SET season_id = ?
            WHERE season_id != ?
        """, (active_season_id, active_season_id))
        
        conn.commit()
        print("season_id رأی‌ها نیز اصلاح شد.")
else:
    print("همه سوالات در فصل فعال صحیح هستند.")

# بررسی سوالات غیرفعال
c.execute("""
    SELECT COUNT(*) as count FROM top_questions 
    WHERE is_active = 0 AND season_id = ?
""", (active_season_id,))

inactive_questions_count = c.fetchone()['count']

if inactive_questions_count > 0:
    print(f"\n{inactive_questions_count} سوال غیرفعال در فصل فعال یافت شد.")
    
    # پرسش از کاربر برای فعال کردن سوالات
    answer = input("آیا می‌خواهید همه سوالات فصل فعال را فعال کنید؟ (y/n): ")
    
    if answer.lower() == 'y':
        # فعال کردن همه سوالات فصل فعال
        c.execute("""
            UPDATE top_questions
            SET is_active = 1
            WHERE season_id = ?
        """, (active_season_id,))
        
        conn.commit()
        print(f"{inactive_questions_count} سوال فعال شد.")

# بررسی نهایی
c.execute("SELECT COUNT(*) as count FROM top_questions WHERE season_id = ? AND is_active = 1", (active_season_id,))
active_questions_count = c.fetchone()['count']

print(f"\nوضعیت نهایی: {active_questions_count} سوال فعال در فصل {active_season_name}")

# بستن اتصال
conn.close()

print("\nعملیات اصلاح دیتابیس با موفقیت انجام شد.") 