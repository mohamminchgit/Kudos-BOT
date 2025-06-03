# 📊 مستندات دیتابیس ربات کودوز

## 🗄️ ساختار کلی دیتابیس

دیتابیس ربات کودوز بر پایه SQLite طراحی شده و شامل جداول مختلفی برای مدیریت کاربران، امتیازات، رای‌گیری‌ها و سایر عملکردهای ربات است.

## 📋 جداول اصلی

### 👥 1. جدول کاربران (users)
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    balance INTEGER DEFAULT 10,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    birthday TEXT,
    telegram_name TEXT,
    is_approved INTEGER DEFAULT 0,
    total_received INTEGER DEFAULT 0,
    join_date TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**توضیحات:**
- `user_id`: شناسه یکتای کاربر در تلگرام (Primary Key)
- `username`: نام کاربری تلگرام (@username)
- `name`: نام نمایشی کاربر
- `balance`: موجودی فعلی امتیازات کاربر
- `is_approved`: وضعیت تایید کاربر (0=منتظر تایید، 1=تایید شده)
- `total_received`: مجموع امتیازات دریافتی

### 🏆 2. جدول فصل‌ها (season)
```sql
CREATE TABLE season (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    balance INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 0,
    start_date TEXT DEFAULT CURRENT_TIMESTAMP,
    end_date TEXT,
    description TEXT
);
```

**توضیحات:**
- `id`: شناسه یکتای فصل
- `name`: نام فصل (مثل "زمستان_1403")
- `balance`: موجودی اولیه کاربران در این فصل
- `is_active`: فصل فعال (فقط یک فصل فعال)

### 🔗 3. جدول کاربر-فصل (user_season)
```sql
CREATE TABLE user_season (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    join_date INTEGER,
    balance INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);
```

**توضیحات:**
- رابطه many-to-many بین کاربران و فصل‌ها
- هر کاربر در هر فصل موجودی جداگانه دارد

### 💰 4. جدول تراکنش‌ها (transactions)
```sql
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    touser INTEGER,
    amount INTEGER,
    season_id INTEGER,
    message_id INTEGER,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```
**شامل:** تمامی انتقال امتیازات بین کاربران

### 5. جدول ادمین‌ها (admins)
```sql
CREATE TABLE admins (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    permissions TEXT
);
```
**شامل:** مدیریت دسترسی‌های ادمین‌ها

### 6. جدول سوالات ترین‌ها (top_questions)
```sql
CREATE TABLE top_questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    season_id INTEGER,
    is_active INTEGER DEFAULT 1
);
```
**شامل:** سوالات ترین‌ها برای هر فصل

### 7. جدول رأی‌گیری ترین‌ها (top_votes)
```sql
CREATE TABLE top_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    voted_for_user_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    vote_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, question_id, season_id)
);
```
**شامل:** رأی‌های داده شده در ترین‌ها

### 8. جدول انتظار تایید (pending_approval)
```sql
CREATE TABLE pending_approval (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**شامل:** کاربران در انتظار تایید ادمین

## جداول هوش مصنوعی

### 9. جدول پروفایل‌های کاربر (user_profiles)
```sql
CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    profile_text TEXT,
    created_at TEXT
);
```
**شامل:** پروفایل‌های هوشمند تولید شده توسط AI

### 10. جدول دیدگاه‌های کاربر (user_perspectives)
```sql
CREATE TABLE user_perspectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    perspective TEXT,
    created_at TEXT,
    UNIQUE(user_id, season_id)
);
```
**شامل:** تحلیل‌های AI از دیدگاه کاربران

### 11. جدول پروفایل‌های AI (ai_user_profiles)
```sql
CREATE TABLE ai_user_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    skills TEXT,
    strengths TEXT,
    personality TEXT,
    improvement_areas TEXT,
    team_perception TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```
**شامل:** تحلیل‌های جامع AI از مهارت‌ها و شخصیت کاربران

### 12. جدول دیدگاه‌های AI (ai_user_perspectives)
```sql
CREATE TABLE ai_user_perspectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    season_id INTEGER,
    perspective_text TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**شامل:** تحلیل‌های AI از نظرات کاربران

## جداول کمکی

### 13. جدول تنظیمات (settings)
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**شامل:** تنظیمات سیستمی ربات

### 14. جدول سوالات اصلی (master_top_questions)
```sql
CREATE TABLE master_top_questions (
    master_question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**شامل:** بانک سوالات ترین‌ها برای استفاده در فصل‌های مختلف

## 🔍 روابط بین جداول

### روابط کلیدی:
- `users.user_id` ← `user_season.user_id` (یک کاربر در چندین فصل)
- `season.id` ← `user_season.season_id` (یک فصل برای چندین کاربر)
- `users.user_id` ← `transactions.user_id` (کاربر فرستنده)
- `users.user_id` ← `transactions.touser` (کاربر گیرنده)
- `top_questions.question_id` ← `top_votes.question_id` (سوال رای‌گیری)
- `users.user_id` ← `top_votes.user_id` (رای دهنده)
- `users.user_id` ← `top_votes.voted_for_user_id` (کسی که رای گرفته)

## 🎯 مشخصات عملکردی

### 1. سیستم امتیازدهی
- هر کاربر موجودی اولیه 10 امتیاز دارد
- انتقال امتیاز بین کاربران ممکن است
- تراکنش‌ها ردیابی و ذخیره می‌شوند
- موجودی در هر فصل جداگانه مدیریت می‌شود

### 2. سیستم رای‌گیری ترین‌ها
- هر کاربر برای هر سوال فقط یک رای می‌تواند بدهد
- نتایج بر اساس تعداد رای‌ها محاسبه می‌شود
- **نکته مهم:** فیلد کلیدی `vote_id` است نه `id`

### 3. سیستم هوش مصنوعی
- تحلیل رفتار کاربران بر اساس تراکنش‌ها
- تولید پروفایل شخصیتی
- ارائه دیدگاه‌های کاربران به یکدیگر

### 4. سیستم مدیریت کاربران
- تایید کاربران جدید توسط ادمین
- مدیریت نقش‌ها و دسترسی‌ها
- ردیابی فعالیت‌های کاربران

## 🚨 نکات مهم و هشدارها

### 1. **نکات دیتابیس:**
- کلید اصلی جدول `top_votes` فیلد `vote_id` است
- هنگام JOIN با جدول votes از `v.vote_id` استفاده کنید
- محدودیت UNIQUE روی (`user_id`, `question_id`, `season_id`) در top_votes

### 2. **کارایی:**
- Index روی فیلدهای پرکاربرد تعریف شده
- استفاده از FOREIGN KEY برای تضمین یکپارچگی
- دسترسی‌های سطح پایین برای بهبود کارایی

### 3. **امنیت:**
- ولیدیشن داده‌ها در سطح اپلیکیشن
- محدودیت دسترسی بر اساس نقش کاربر
- لاگ تمامی عملیات حساس

### 4. **نگهداری:**
- پشتیبان‌گیری منظم از دیتابیس
- آرشیو داده‌های قدیمی
- مانیتورینگ سایز دیتابیس

## 📝 نمونه کوئری‌های مفید

### دریافت موجودی کاربر در فصل فعال:
```sql
SELECT us.balance 
FROM user_season us
JOIN season s ON us.season_id = s.id
WHERE us.user_id = ? AND s.is_active = 1;
```

### نتایج رای‌گیری:
```sql
SELECT 
    u.name,
    COUNT(v.vote_id) AS vote_count
FROM users u
LEFT JOIN top_votes v ON u.user_id = v.voted_for_user_id
WHERE v.question_id = ? AND v.season_id = ?
GROUP BY u.user_id, u.name
ORDER BY vote_count DESC;
```

### تراکنش‌های کاربر:
```sql
SELECT 
    t.*,
    u1.name AS sender_name,
    u2.name AS receiver_name
FROM transactions t
JOIN users u1 ON t.user_id = u1.user_id
JOIN users u2 ON t.touser = u2.user_id
WHERE t.user_id = ? OR t.touser = ?
ORDER BY t.created_at DESC;
```

## 🔧 راهنمای نصب دیتابیس

### 1. ایجاد دیتابیس جدید:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('kudos_bot.db')
# اجرای اسکریپت‌های CREATE TABLE
conn.close()
"
```

### 2. مایگریشن داده‌ها:
```bash
# اگر دیتابیس قدیمی دارید
python scripts/migrate_database.py
```

### 3. تست دیتابیس:
```bash
python -m pytest tests/test_database.py
```
