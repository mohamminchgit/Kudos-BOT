# راهنمای افزودن کاربران به دیتابیس:

# برای افزودن لیست کاربران (مثلاً از یک آرایه JSON)، می‌توانید از کد زیر استفاده کنید:

# import sqlite3
# import json
# from config import DB_PATH

# with open('users.json', encoding='utf-8') as f:
#     users = json.load(f)

# conn = sqlite3.connect(DB_PATH)
# c = conn.cursor()
# for user in users:
#     c.execute('''
#         INSERT OR REPLACE INTO users (user_id, username, name, balance, birthday, created_at)
#         VALUES (?, ?, ?, ?, ?, ?)
#     ''', (
#         user['user_id'],
#         user.get('username'),
#         user['name'],
#         user['balance'],
#         user.get('birthday'),
#         user.get('created_at')
#     ))
# conn.commit()
# conn.close()
# print('Users imported.')

import sqlite3
import os
from config import DB_PATH, SEASON_ID

# همیشه دیتابیس را باز کن (چه وجود داشته باشد چه نه)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# جدول کاربران
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    balance INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    birthday TEXT
)
''')

# جدول تراکنش‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    touser INTEGER,
    amount INTEGER,
    season_id INTEGER,
    message_id INTEGER,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# جدول فصل‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS season (
    id INTEGER PRIMARY KEY,
    name TEXT
)
''')

# جدول ادمین‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL, -- god یا admin
    permissions TEXT -- رشته‌ای از دسترسی‌ها (مثلاً: add_user,view_stats,...)
)
''')

# جدول سوالات ترین‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS top_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    season_id INTEGER,
    is_active INTEGER DEFAULT 1
)
''')

# جدول رای‌های ترین‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS top_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    voted_for_user_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, question_id, season_id)
)
''')

# اضافه کردن سوالات پیش‌فرض ترین‌ها اگر جدول خالی است
c.execute("SELECT COUNT(*) FROM top_questions")
if c.fetchone()[0] == 0:
    default_questions = [
        "مشتاق‌ترین همکارت کیه؟",
        "اجتماعی‌ترین همکارت کیه؟",
        "خوش‌بین‌ترین همکارت کیه؟",
        "با احساس‌ترین همکارت کیه؟",
        "رقابتی‌ترین همکارت کیه؟"
    ]
    for q in default_questions:
        c.execute("INSERT INTO top_questions (text, season_id) VALUES (?, ?)", (q, SEASON_ID))

conn.commit()
conn.close()
print("Database and tables checked/created.") 