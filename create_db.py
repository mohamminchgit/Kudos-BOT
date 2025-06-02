#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys
import os

# اضافه کردن مسیر پروژه به sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    # اگر config وجود نداشت، مقادیر پیش‌فرض
    class Config:
        DB_PATH = "kudosbot.db"
        SEASON_ID = 1
        ADMIN_USER_ID = 882730020
    config = Config()

def create_database():
    """ایجاد دیتابیس و جداول مورد نیاز"""
    print("🔧 در حال ایجاد دیتابیس...")
    
    # ایجاد دیتابیس
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()

    # جدول کاربران
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT,
        balance INTEGER DEFAULT 10,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        birthday TEXT,
        telegram_name TEXT,
        is_approved INTEGER DEFAULT 0
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
        balance INTEGER DEFAULT 10,
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
        role TEXT NOT NULL,
        permissions TEXT
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
    )
    ''')

    # جدول عضویت کاربران در فصل‌ها
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_season (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        season_id INTEGER NOT NULL,
        join_date INTEGER,
        balance INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # جدول نیازمند تأیید
    c.execute('''
    CREATE TABLE IF NOT EXISTS pending_approval (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول زاویه دید کاربران
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_perspectives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        season_id INTEGER NOT NULL,
        perspective TEXT,
        created_at TEXT,
        UNIQUE(user_id, season_id)
    )
    ''')
    
    # جدول پروفایل هوشمند کاربران
    c.execute('''
    CREATE TABLE IF NOT EXISTS user_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        profile_text TEXT,
        created_at TEXT
    )
    ''')

    # اضافه کردن ادمین اصلی
    try:
        # بررسی وجود ادمین
        c.execute("SELECT user_id FROM admins WHERE user_id=?", (config.ADMIN_USER_ID,))
        if not c.fetchone():
            c.execute("INSERT INTO admins (user_id, role, permissions) VALUES (?, 'god', NULL)", 
                     (config.ADMIN_USER_ID,))
            print(f"✅ ادمین اصلی (ID: {config.ADMIN_USER_ID}) اضافه شد")

        # اضافه کردن کاربر ادمین
        c.execute("SELECT user_id FROM users WHERE user_id=?", (config.ADMIN_USER_ID,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, username, name, balance, is_approved) VALUES (?, 'admin', 'Admin', 10, 1)", 
                     (config.ADMIN_USER_ID,))
            print(f"✅ کاربر ادمین (ID: {config.ADMIN_USER_ID}) اضافه شد")

    except Exception as e:
        print(f"❌ خطا در اضافه کردن ادمین: {e}")

    # ایجاد فصل پیش‌فرض
    try:
        c.execute("SELECT id FROM season WHERE id=?", (config.SEASON_ID,))
        if not c.fetchone():
            c.execute("INSERT INTO season (id, name, balance, is_active) VALUES (?, 'زمستان_1403', 10, 1)", 
                     (config.SEASON_ID,))
            print(f"✅ فصل پیش‌فرض ایجاد شد")
    except Exception as e:
        print(f"❌ خطا در ایجاد فصل: {e}")

    conn.commit()
    conn.close()
    print("✅ دیتابیس با موفقیت ایجاد شد!")

if __name__ == "__main__":
    create_database()
