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
from config import DB_PATH, SEASON_ID, ADMIN_USER_ID

# همیشه دیتابیس را باز کن (چه وجود داشته باشد چه نه)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# تابعی برای بررسی وجود ستون در جدول
def column_exists(table_name, column_name):
    c.execute(f"PRAGMA table_info({table_name})")
    columns = c.fetchall()
    for column in columns:
        if column[1] == column_name:
            return True
    return False

# تابعی برای اضافه کردن ستون به جدول در صورت عدم وجود
def add_column_if_not_exists(table_name, column_name, column_type):
    if not column_exists(table_name, column_name):
        try:
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            conn.commit()
            print(f"Column {column_name} added to {table_name}")
        except sqlite3.OperationalError as e:
            print(f"Error adding column {column_name} to {table_name}: {e}")

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
    name TEXT NOT NULL,
    balance INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 0,
    start_date TEXT DEFAULT CURRENT_TIMESTAMP,
    end_date TEXT,
    description TEXT
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

# جدول رای‌های ترین‌ها - اصلاح شده با ستون vote_time
c.execute('''
CREATE TABLE IF NOT EXISTS top_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    voted_for_user_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    vote_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, question_id, season_id)
)
''')

# جدول جامع سوالات ترین‌ها
c.execute('''
CREATE TABLE IF NOT EXISTS master_top_questions (
    master_question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
''')

# بررسی و اضافه کردن ستون‌های مورد نیاز
try:
    # بررسی و اضافه کردن ستون vote_time در جدول top_votes اگر وجود ندارد
    add_column_if_not_exists("top_votes", "vote_time", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
except Exception as e:
    print(f"Error checking columns: {e}")

# بررسی و اضافه کردن ادمین گاد
try:
    # بررسی آیا ادمین گاد وجود دارد
    c.execute("SELECT user_id FROM admins WHERE user_id=? AND role='god'", (ADMIN_USER_ID,))
    admin_exists = c.fetchone()
    
    if not admin_exists:
        # اضافه کردن ادمین گاد به دیتابیس
        c.execute("INSERT OR REPLACE INTO admins (user_id, role, permissions) VALUES (?, 'god', NULL)", (ADMIN_USER_ID,))
        conn.commit()
        print(f"Admin with ID {ADMIN_USER_ID} added as 'god' admin.")
    else:
        print(f"Admin with ID {ADMIN_USER_ID} already exists as 'god' admin.")
except Exception as e:
    print(f"Error checking/adding god admin: {e}")

# اضافه کردن کاربر ادمین گاد به جدول users در صورتی که وجود نداشته باشد
try:
    c.execute("SELECT user_id FROM users WHERE user_id=?", (ADMIN_USER_ID,))
    user_exists = c.fetchone()
    
    if not user_exists:
        # اضافه کردن کاربر ادمین به جدول users
        c.execute("INSERT INTO users (user_id, username, name, balance) VALUES (?, 'admin', 'Admin', 100)", (ADMIN_USER_ID,))
        conn.commit()
        print(f"Admin user with ID {ADMIN_USER_ID} added to users table.")
    else:
        print(f"Admin user with ID {ADMIN_USER_ID} already exists in users table.")
except Exception as e:
    print(f"Error checking/adding admin user: {e}")

conn.commit()
conn.close()
print("Database and tables checked/created. All necessary columns have been added.") 