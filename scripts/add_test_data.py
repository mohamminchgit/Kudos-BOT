import sqlite3
import random
import datetime
from datetime import timedelta
import config

# اتصال به دیتابیس
conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("شروع اضافه کردن داده‌های تستی به دیتابیس...")

# -------- افزودن کاربران تستی --------
# استفاده از شناسه ادمین اصلی از فایل config
GOD_ADMIN_ID = config.ADMIN_USER_ID

test_users = [
    (GOD_ADMIN_ID, config.ADMIN_USERNAME, config.ADMIN_NAME, 100),
    (1001, "user1", "محمد رضایی", 20),
    (1002, "user2", "علی حسینی", 15),
    (1003, "user3", "زهرا محمدی", 25),
    (1004, "user4", "فاطمه نوری", 18),
    (1005, "user5", "امیر کریمی", 22),
    (1006, "user6", "سارا احمدی", 30),
    (1007, "user7", "حسین نجفی", 12),
    (1008, "user8", "مریم موسوی", 28),
    (1009, "user9", "رضا جعفری", 17),
    (1010, "user10", "نیما صادقی", 24)
]

# پاک کردن داده‌های قبلی (اختیاری)
c.execute("DELETE FROM users WHERE user_id >= 1000 AND user_id <= 1100")
c.execute("DELETE FROM users WHERE user_id = ?", (GOD_ADMIN_ID,))

# افزودن کاربران تستی
print("افزودن کاربران تستی...")
for user in test_users:
    try:
        c.execute("INSERT OR IGNORE INTO users (user_id, username, name, balance) VALUES (?, ?, ?, ?)", user)
    except sqlite3.Error as e:
        print(f"خطا در افزودن کاربر {user[2]}: {e}")

conn.commit()
print(f"{len(test_users)} کاربر تستی اضافه شد.")

# -------- افزودن ادمین‌های تستی --------
test_admins = [
    (GOD_ADMIN_ID, "god", None),  # ادمین گاد با همه دسترسی‌ها
    (1001, "admin", "admin_users,admin_transactions,manage_admins"),
    (1002, "moderator", "admin_users,admin_stats")
]

# پاک کردن داده‌های قبلی (اختیاری)
c.execute("DELETE FROM admins WHERE user_id >= 1000 AND user_id <= 1100")
c.execute("DELETE FROM admins WHERE user_id = ?", (GOD_ADMIN_ID,))

# افزودن ادمین‌های تستی
print("افزودن ادمین‌های تستی...")
for admin in test_admins:
    try:
        c.execute("INSERT OR IGNORE INTO admins (user_id, role, permissions) VALUES (?, ?, ?)", admin)
    except sqlite3.Error as e:
        print(f"خطا در افزودن ادمین {admin[0]}: {e}")

conn.commit()
print(f"{len(test_admins)} ادمین تستی اضافه شد.")

# -------- افزودن فصل‌های تستی --------
test_seasons = [
    ("فصل بهار ۱۴۰۲", 10, "فصل بهاری با امتیازهای خوب", 0),
    ("فصل تابستان ۱۴۰۲", 15, "فصل تابستانی با امتیازهای عالی", 1),
    ("فصل پاییز ۱۴۰۲", 20, "فصل پاییزی (آینده)", 0)
]

# پاک کردن داده‌های قبلی (اختیاری)
c.execute("DELETE FROM season WHERE name LIKE '%فصل%'")

# افزودن فصل‌های تستی
print("افزودن فصل‌های تستی...")
season_ids = []
for season in test_seasons:
    try:
        c.execute("INSERT INTO season (name, balance, description, is_active) VALUES (?, ?, ?, ?)", season)
        season_ids.append(c.lastrowid)
    except sqlite3.Error as e:
        print(f"خطا در افزودن فصل {season[0]}: {e}")

conn.commit()
print(f"{len(test_seasons)} فصل تستی اضافه شد.")

# -------- افزودن سوالات ترین‌ها --------
test_questions = [
    "خوش‌اخلاق‌ترین همکار کیست؟",
    "با انگیزه‌ترین همکار کیست؟",
    "کمک‌کننده‌ترین همکار کیست؟",
    "منظم‌ترین همکار کیست؟",
    "خلاق‌ترین همکار کیست؟"
]

# پاک کردن داده‌های قبلی (اختیاری)
c.execute("DELETE FROM top_questions WHERE text IN ({})".format(','.join(['?']*len(test_questions))), test_questions)

# افزودن سوالات ترین‌ها برای هر فصل
print("افزودن سوالات ترین‌ها...")
question_ids = []
for season_id in season_ids:
    for question in test_questions:
        try:
            c.execute("INSERT INTO top_questions (text, is_active, season_id) VALUES (?, 1, ?)", 
                     (question, season_id))
            question_ids.append((c.lastrowid, season_id))
        except sqlite3.Error as e:
            print(f"خطا در افزودن سوال {question} برای فصل {season_id}: {e}")

conn.commit()
print(f"{len(question_ids)} سوال ترین‌ها اضافه شد.")

# -------- افزودن رأی‌های ترین‌ها --------
print("افزودن رأی‌های ترین‌ها...")
# اضافه کردن ادمین گاد به لیست کاربرانی که رأی می‌دهند
user_ids = [u[0] for u in test_users]

for user_id in user_ids:  # برای هر کاربر
    for question_id, season_id in question_ids:  # برای هر سوال در هر فصل
        # انتخاب تصادفی یک کاربر به عنوان رأی (به جز خود کاربر)
        voted_for = random.choice([u[0] for u in test_users if u[0] != user_id])
        # زمان رأی‌گیری تصادفی در 30 روز گذشته
        vote_time = (datetime.datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            c.execute("""
                INSERT INTO top_votes (user_id, question_id, voted_for_user_id, season_id, vote_time)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, question_id, voted_for, season_id, vote_time))
        except sqlite3.Error as e:
            print(f"خطا در افزودن رأی کاربر {user_id} برای سوال {question_id}: {e}")

conn.commit()
print("رأی‌های ترین‌ها اضافه شد.")

# -------- افزودن تراکنش‌های تستی --------
print("افزودن تراکنش‌های تستی...")
transaction_count = 0

# لیست دلایل تستی
reasons = [
    "کمک در انجام پروژه",
    "همکاری عالی در تیم",
    "ارائه ایده خلاقانه",
    "حل مشکل فنی",
    "پشتکار بالا در کار",
    "رسیدگی به مشکلات همکاران",
    "مدیریت خوب زمان",
    "انجام کار فراتر از وظایف",
    "کمک به آموزش همکاران جدید",
    "مشارکت فعال در جلسات"
]

# ایجاد تراکنش‌های تصادفی بین کاربران
for i in range(100):  # ایجاد 100 تراکنش تستی
    # انتخاب تصادفی فرستنده و گیرنده
    sender = random.choice(test_users)
    receiver = random.choice([u for u in test_users if u[0] != sender[0]])
    
    # انتخاب تصادفی مقدار و دلیل
    amount = random.randint(1, 5)
    reason = random.choice(reasons)
    
    # انتخاب تصادفی فصل
    season_id = random.choice(season_ids)
    
    # زمان تراکنش تصادفی در 60 روز گذشته
    created_at = (datetime.datetime.now() - timedelta(days=random.randint(0, 60))).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        c.execute("""
            INSERT INTO transactions (user_id, touser, amount, reason, season_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sender[0], receiver[0], amount, reason, season_id, created_at))
        transaction_count += 1
    except sqlite3.Error as e:
        print(f"خطا در افزودن تراکنش: {e}")

# ایجاد تراکنش‌های ادمین گاد
print("افزودن تراکنش‌های ادمین گاد...")
for i in range(20):  # 20 تراکنش از ادمین گاد به کاربران دیگر
    receiver = random.choice([u for u in test_users if u[0] != GOD_ADMIN_ID])
    amount = random.randint(1, 10)
    reason = f"تراکنش آزمایشی از ادمین گاد #{i+1}"
    season_id = random.choice(season_ids)
    created_at = (datetime.datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        c.execute("""
            INSERT INTO transactions (user_id, touser, amount, reason, season_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (GOD_ADMIN_ID, receiver[0], amount, reason, season_id, created_at))
        transaction_count += 1
    except sqlite3.Error as e:
        print(f"خطا در افزودن تراکنش ادمین گاد: {e}")

conn.commit()
print(f"{transaction_count} تراکنش تستی اضافه شد.")

print("افزودن داده‌های تستی به پایان رسید.")
conn.close() 