# راهنمای افزودن کاربران به دیتابیس:
#
# برای افزودن لیست کاربران (مثلاً از یک آرایه JSON)، می‌توانید از کد زیر استفاده کنید:
#
# import sqlite3
# import json
# from config import DB_PATH
#
# with open('users.json', encoding='utf-8') as f:
#     users = json.load(f)
#
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
from config import DB_PATH

if os.path.exists(DB_PATH):
    print("Database already exists. No action taken.")
    exit(0)

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

conn.commit()
conn.close()
print("Database and tables created.") 