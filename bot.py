import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sqlite3
import config

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# اتصال به دیتابیس
conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
c = conn.cursor()

# ایجاد جداول مورد نیاز در صورت عدم وجود
def init_db():
    # جداول ترین‌ها در db_init.py ساخته می‌شوند
    pass

# اجرای تابع ایجاد دیتابیس
init_db()

# لیست دسترسی‌های ادمین (مطابق با گزینه‌های پنل مدیریت)
ADMIN_PERMISSIONS = [
    ("admin_users", "مدیریت کاربران"),
    ("admin_transactions", "مدیریت تراکنش"),
    ("admin_stats", "آمار و گزارشات"),
    ("manage_admins", "مدیریت ادمین‌ها"),
    ("manage_questions", "مدیریت سوالات ترین‌ها"),
]

def get_or_create_user(user):
    c.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    return c.fetchone() is not None

def is_user_approved(user_id):
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return c.fetchone() is not None

def add_user(user):
    c.execute("INSERT INTO users (user_id, username, name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
    conn.commit()

def main_menu_keyboard(user_id=None):
    keyboard = [
        [InlineKeyboardButton("🎯 امتیازدهی به دیگران", callback_data="tovote^")]
    ]
    
    # بررسی آیا کاربر در فصل جاری به سوالات ترین‌ها پاسخ داده است
    has_voted_all = False
    if user_id:
        c.execute("""
            SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
        """, (config.SEASON_ID,))
        total_questions = c.fetchone()[0]
        
        c.execute("""
            SELECT COUNT(*) FROM top_votes 
            WHERE user_id=? AND season_id=?
        """, (user_id, config.SEASON_ID))
        user_votes = c.fetchone()[0]
        
        has_voted_all = user_votes >= total_questions
    
    # اضافه کردن دکمه ترین‌ها با متن مناسب
    if has_voted_all:
        keyboard.append([InlineKeyboardButton("🏆 نتایج ترین‌های فصل", callback_data="top_results^")])
    else:
        keyboard.append([InlineKeyboardButton("🏆 ترین‌های فصل!", callback_data="top_vote^")])
    
    keyboard += [
        [InlineKeyboardButton("» پروفایل شما", callback_data="userprofile^"), InlineKeyboardButton("ردپای امتیازات", callback_data="historypoints^")],
        [InlineKeyboardButton("» راهنما", callback_data="help^"), InlineKeyboardButton("» پشتیبانی", url=config.SUPPORT_USERNAME)]
    ]
    
    # اضافه کردن دکمه پنل ادمین برای کاربران ادمین
    if user_id:
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            role, permissions = row
            if role == 'god' or permissions:
                keyboard.append([InlineKeyboardButton("🔐 پنل ادمین", callback_data="admin_panel^")])
    
    return InlineKeyboardMarkup(keyboard)

def get_all_users(exclude_id=None):
    if exclude_id:
        c.execute("SELECT user_id, name FROM users WHERE user_id != ?", (exclude_id,))
    else:
        c.execute("SELECT user_id, name FROM users")
    return c.fetchall()

def get_user_profile(user_id):
    c.execute("""
        SELECT u.*, 
            (SELECT SUM(t.amount) 
             FROM transactions t
             WHERE t.touser = u.user_id) AS total_received
        FROM users u
        WHERE u.user_id=?
    """, (user_id,))
    return c.fetchone()

def get_user_transactions(user_id, given=True, offset=0, limit=3):
    if given:
        c.execute("""
            SELECT t.amount, t.touser, u.name, t.reason, t.created_at, t.message_id, t.transaction_id 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id=? 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
    else:
        c.execute("""
            SELECT t.amount, t.user_id, u.name, t.reason, t.created_at, t.message_id, t.transaction_id
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser=? 
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
    return c.fetchall()

def count_user_transactions(user_id, given=True):
    if given:
        c.execute("""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE user_id=?
        """, (user_id,))
    else:
        c.execute("""
            SELECT COUNT(*) 
            FROM transactions 
            WHERE touser=?
        """, (user_id,))
    return c.fetchone()[0]

def get_scoreboard():
    c.execute("""
        SELECT touser, SUM(amount) as total, u.name 
        FROM transactions t 
        LEFT JOIN users u ON t.touser = u.user_id 
        GROUP BY touser 
        ORDER BY total DESC LIMIT 10
    """)
    return c.fetchall()

# تابع ایجاد دکمه‌های شیشه‌ای برای صفحه‌بندی
def create_glass_buttons(page, total_pages, callback_prefix):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ صفحه قبل", callback_data=f"{callback_prefix}^{page-1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("صفحه بعد ➡️", callback_data=f"{callback_prefix}^{page+1}"))
    return buttons

async def check_channel_membership(user_id, context):
    try:
        bot = context.bot
        logger.info(f"Checking membership for user {user_id} in channel {config.CHANNEL_ID}")
        chat_member = await bot.get_chat_member(chat_id=config.CHANNEL_ID, user_id=user_id)
        logger.info(f"User {user_id} membership status: {chat_member.status}")
        is_member = chat_member.status in ['member', 'administrator', 'creator', 'restricted']
        return is_member
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_approved = is_user_approved(user.id)
    
    # بررسی عضویت در کانال
    is_member = await check_channel_membership(user.id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await update.message.reply_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی تأیید کاربر
    if not is_approved:
        # ارسال پیام به کاربر با دکمه شیشه‌ای برای پشتیبانی
        keyboard = [[InlineKeyboardButton(f"👤 پشتیبانی", url=f"{config.SUPPORT_USERNAME.strip('@')}")]]
        await update.message.reply_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با پشتیبان تماس بگیرید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # ارسال نوتیفیکیشن به ادمین
        admin_keyboard = [
            [InlineKeyboardButton("✅ تأیید کاربر", callback_data=f"approve_user^{user.id}")],
            [InlineKeyboardButton("❌ رد کاربر", callback_data=f"reject_user^{user.id}")]
        ]
        
        try:
            bot = context.bot
            await bot.send_message(
                chat_id=config.ADMIN_USER_ID,
                text=f"🔔 <b>درخواست دسترسی جدید</b>\n\n"
                     f"👤 نام: {user.full_name}\n"
                     f"🆔 شناسه: {user.id}\n"
                     f"👤 یوزرنیم: @{user.username or 'ندارد'}",
                reply_markup=InlineKeyboardMarkup(admin_keyboard),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending notification to admin: {e}")
        
        return
    
    await update.message.reply_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard(user.id)
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    get_or_create_user(user)
    data = query.data
    
    # بررسی عضویت در کانال برای تمام کالبک‌ها
    is_member = await check_channel_membership(user.id, context)
    if not is_member and not data.startswith("joinedch^"):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await query.edit_message_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    if data == "help^":
        await query.answer()
        await query.edit_message_text(
            f"📌 راهنمای استفاده از {config.BOT_NAME}\n\n[... به زودی ...]",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
        )
    elif data == "userpanel^":
        await query.answer()
        await query.edit_message_text(
            f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
            reply_markup=main_menu_keyboard(user.id)
        )
    elif data == "userprofile^":
        await query.answer()
        profile = get_user_profile(user.id)
        if profile:
            total_received = profile[5] or 0
            await query.edit_message_text(
                f"👤 پروفایل شما\n\nنام: {profile[2]}\nیوزرنیم: @{profile[1] or 'ندارد'}\nاعتبار فعلی: {profile[3]}\nمجموع امتیازات دریافتی: {total_received}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
        else:
            await query.edit_message_text("پروفایل یافت نشد.", reply_markup=main_menu_keyboard(user.id))
    elif data == "historypoints^":
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("تابلوی امتیازات 🏆", callback_data="Scoreboard^")],
            [InlineKeyboardButton("امتیازهای شما 🎯", callback_data="receivedpoints^"), 
             InlineKeyboardButton("امتیازهایی که دادید 💬", callback_data="givenpoints^")],
            [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
        ]
        await query.edit_message_text(
            f"تاریخچه امتیازات شما\n\nدر این بخش می‌توانید امتیازهایی که به دیگران داده‌اید و امتیازهایی که از دیگران دریافت کرده‌اید را همراه با وضعیت آن‌ها مشاهده کنید.\n\nلطفاً از گزینه‌های زیر، انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "joinedch^":
        await query.answer()
        await query.edit_message_text(
            f"📌 شما با موفقیت به کانال {config.BOT_NAME} پیوستید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» دریافت منو", callback_data="userpanel^")]])
        )
    elif data == "tovote^":
        await query.answer()
        users = get_all_users(exclude_id=user.id)
        if not users:
            await query.edit_message_text("هیچ کاربر دیگری برای امتیازدهی وجود ندارد!", reply_markup=main_menu_keyboard(user.id))
            return
        
        keyboard = []
        row = []
        for i, u in enumerate(users):
            row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"voteuser^{u[0]}"))
            if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
                if len(row) == 1 and i == len(users) - 1:  # اگر آخرین آیتم تنها در ردیف باشد
                    keyboard.append(row)
                elif len(row) == 2:
                    keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
        
        # دریافت موجودی کاربر
        c.execute("SELECT balance FROM users WHERE user_id=?", (user.id,))
        balance = c.fetchone()[0]
        
        await query.edit_message_text(
            f"#{config.SEASON_NAME}\n\n"
            f"تو {balance} امتیاز داری که می‌تونی به دوستات بدی 🎁\n\n"
            f"از بین افراد زیر، به کی می‌خوای امتیاز بدی؟ 🤔",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("voteuser^"):
        await query.answer()
        touser_id = int(data.split("^")[1])
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        profile = get_user_profile(user.id)
        if not profile or profile[3] < 1:
            await query.edit_message_text("اعتبار کافی برای امتیازدهی ندارید!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # انتخاب مقدار امتیاز - تمام مقادیر ممکن را نمایش می‌دهیم
        max_score = profile[3]  # حداکثر امتیاز برابر با موجودی کاربر
        
        # ایجاد دکمه‌های امتیازدهی، 3 دکمه در هر ردیف
        keyboard = []
        row = []
        for i in range(1, max_score + 1):
            row.append(InlineKeyboardButton(str(i), callback_data=f"givepoint^{touser_id}^{i}"))
            if len(row) == 3 or i == max_score:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
        
        await query.edit_message_text(
            f"شما در حال امتیاز دادن به {touser_name} هستید!\n\n"
            f"درحال حاضر شما {max_score} امتیاز دارید که میتوانید استفاده کنید.\n\n"
            f"لطفا مقدار امتیازی که میخواهید بدهید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("givepoint^"):
        await query.answer()
        parts = data.split("^")
        touser_id = int(parts[1])
        amount = int(parts[2])
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        # درخواست دلیل امتیازدهی
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]]
        
        # ذخیره اطلاعات در context.user_data
        context.user_data['pending_transaction'] = {
            'touser_id': touser_id,
            'amount': amount,
            'touser_name': touser_name  # ذخیره نام کاربر مقصد
        }
        
        await query.edit_message_text(
            f"شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"  
            f"دلیل:\n-----------------\n\n"  
            f"لطفاً دلیل امتیازدهی را بنویسید و ارسال کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # تغییر وضعیت کاربر به حالت انتظار برای دریافت دلیل
        context.user_data['waiting_for_reason'] = True
    elif data.startswith("Confirm^"):
        await query.answer()
        parts = data.split("^")
        touser_id = int(parts[1])
        amount = int(parts[2])
        reason = parts[3] if len(parts) > 3 else "-"
        
        profile = get_user_profile(user.id)
        if not profile or profile[3] < amount:
            await query.edit_message_text("اعتبار کافی ندارید!", reply_markup=main_menu_keyboard(user.id))
            return
        
        # دریافت نام کاربر فرستنده از دیتابیس
        c.execute("SELECT name FROM users WHERE user_id=?", (user.id,))
        sender_result = c.fetchone()
        sender_name = sender_result[0] if sender_result else "کاربر"
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        result = c.fetchone()
        touser_name = result[0] if result else "کاربر"
        
        # ثبت تراکنش و کم کردن اعتبار
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
        c.execute("INSERT INTO transactions (user_id, touser, amount, season_id, reason) VALUES (?, ?, ?, ?, ?)", 
                 (user.id, touser_id, amount, config.SEASON_ID, reason))
        conn.commit()
        
        # دریافت آخرین شناسه تراکنش درج شده
        c.execute("SELECT last_insert_rowid()")
        transaction_id = c.fetchone()[0]
        
        # دریافت تاریخ و زمان شمسی و فارسی
        import jdatetime
        # نگاشت دستی روزها و ماه‌های فارسی
        fa_weekdays = {
            'Saturday': 'شنبه',
            'Sunday': 'یکشنبه',
            'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه',
            'Wednesday': 'چهارشنبه',
            'Thursday': 'پنجشنبه',
            'Friday': 'جمعه',
        }
        fa_months = {
            'Farvardin': 'فروردین',
            'Ordibehesht': 'اردیبهشت',
            'Khordad': 'خرداد',
            'Tir': 'تیر',
            'Mordad': 'مرداد',
            'Shahrivar': 'شهریور',
            'Mehr': 'مهر',
            'Aban': 'آبان',
            'Azar': 'آذر',
            'Dey': 'دی',
            'Bahman': 'بهمن',
            'Esfand': 'اسفند',
        }
        now = jdatetime.datetime.now()
        weekday_en = now.strftime("%A")
        month_en = now.strftime("%B")
        weekday = fa_weekdays.get(weekday_en, weekday_en)
        month = fa_months.get(month_en, month_en)
        day = now.day
        year = now.year
        fa_date = f"{weekday} {day} {month} {year}"
        current_time = f"⏰ {fa_date}"
        
        try:
            # ارسال پیام به کانال
            bot = context.bot
            # دکمه شیشه‌ای برای امتیاز دادن در ربات
            vote_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 امتیاز دادن در ربات", url=f"https://t.me/{bot.username}?start=start")]
            ])
            channel_message = await bot.send_message(
                chat_id=config.CHANNEL_ID,
                text=f"{sender_name} {amount} امتیاز به {touser_name} داد و نوشت : \n\n"
                     f"💬 {reason}\n\n"
                     f"{current_time}",
                reply_markup=vote_keyboard
            )
            
            # بروزرسانی message_id در دیتابیس
            if channel_message:
                c.execute("UPDATE transactions SET message_id = ? WHERE transaction_id = ?", 
                         (channel_message.message_id, transaction_id))
                conn.commit()
                
                # ارسال پیام به کاربر دریافت‌کننده
                channel_id_num = config.CHANNEL_ID.replace("-100", "")
                keyboard = [[InlineKeyboardButton("مشاهده در کانال", url=f"https://t.me/c/{channel_id_num}/{channel_message.message_id}")]]
                
                try:
                    await bot.send_message(
                        chat_id=touser_id,
                        text=f"🎉 {sender_name} {amount} امتیاز بهت داد و نوشت : \n\n"
                             f"💬 {reason}\n\n"
                             f"{current_time}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to user {touser_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error sending message to channel: {e}")
        
        # اطلاع به کاربر فرستنده
        await query.edit_message_text(
            f"✅ {amount} امتیاز به {touser_name} داده شد!\n\n"  
            f"دلیل: {reason}",
            reply_markup=main_menu_keyboard(user.id)
        )
    elif data.startswith("givenpoints^"):
        await query.answer()
        parts = data.split("^")
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
        # دریافت تعداد کل تراکنش‌ها
        total_transactions = count_user_transactions(user.id, given=True)
        total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
        # دریافت تراکنش‌های صفحه فعلی
        given = get_user_transactions(user.id, given=True, offset=page*3, limit=3)
        msg = "✨ <b>امتیازهایی که دادید</b> ✨\n\n"
        if given:
            for transaction in given:
                amount = transaction[0]
                touser_name = transaction[2]
                reason = transaction[3] or '-'
                created_at = transaction[4]
                message_id = transaction[5]  # شناسه پیام در کانال
                # اضافه کردن لینک به پیام کانال
                link_text = "[لینک]"
                if message_id:
                    channel_id_num = config.CHANNEL_ID.replace("-100", "")
                    link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                msg += f"✅ شما {amount} امتیاز به {touser_name} دادید: {link_text}\n"
                msg += f"📄 {reason}\n\n"
                msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
        else:
            msg += "- هنوز امتیازی به کسی نداده‌اید.\n\n"
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "givenpoints")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("receivedpoints^"):
        await query.answer()
        parts = data.split("^")
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
        # دریافت تعداد کل تراکنش‌ها
        total_transactions = count_user_transactions(user.id, given=False)
        total_pages = (total_transactions + 2) // 3  # تقسیم به صفحات 3 تایی
        # دریافت تراکنش‌های صفحه فعلی
        received = get_user_transactions(user.id, given=False, offset=page*3, limit=3)
        msg = "✨ <b>امتیازهایی که دریافت کردید</b> ✨\n\n"
        if received:
            for transaction in received:
                amount = transaction[0]
                from_name = transaction[2]
                reason = transaction[3] or '-'
                created_at = transaction[4]
                message_id = transaction[5]  # شناسه پیام در کانال
                # اضافه کردن لینک به پیام کانال
                link_text = "[لینک]"
                if message_id:
                    channel_id_num = config.CHANNEL_ID.replace("-100", "")
                    link_text = f'<a href="https://t.me/c/{channel_id_num}/{message_id}">[لینک]</a>'
                msg += f"✅ {from_name} به شما {amount} امتیاز داد: {link_text}\n"
                msg += f"📄 {reason}\n\n"
                msg += f"🕒 {created_at}\n\n" + "-" * 30 + "\n\n"
        else:
            msg += "- هنوز امتیازی دریافت نکرده‌اید.\n\n"
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "receivedpoints")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif data.startswith("Scoreboard^"):
        await query.answer()
        parts = data.split("^")
        try:
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except:
            page = 0
        # دریافت تابلوی امتیازات
        board = get_scoreboard()
        total_items = len(board)
        total_pages = (total_items + 9) // 10  # تقسیم به صفحات 10 تایی
        # انتخاب آیتم‌های صفحه فعلی
        start_idx = page * 10
        end_idx = min(start_idx + 10, total_items)
        current_page_items = board[start_idx:end_idx]
        msg = "🏆 <b>تابلوی امتیازات برتر</b> 🏆\n\n"
        for i, row in enumerate(current_page_items):
            rank = i + start_idx + 1
            medal = ""
            if rank == 1:
                medal = "🥇 "
            elif rank == 2:
                medal = "🥈 "
            elif rank == 3:
                medal = "🥉 "
            user_name = row[2] or "کاربر"
            total_points = row[1]
            # برجسته کردن کاربر جاری
            if row[0] == user.id:
                user_name = f"<tg-spoiler>{user_name}</tg-spoiler>"
            msg += f"{rank}- {medal}{user_name}: <b>{total_points}</b> امتیاز\n\n"
        # ایجاد دکمه‌های شیشه‌ای
        nav_buttons = create_glass_buttons(page, max(1, total_pages), "Scoreboard")
        keyboard = [nav_buttons] if nav_buttons else []
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    # پنل ادمین
    elif data == "admin_panel^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row:
            await query.answer("شما دسترسی به این بخش ندارید!")
            return
        role, permissions = row
        allowed = []
        if role == 'god':
            allowed = [p[0] for p in ADMIN_PERMISSIONS]
        elif permissions:
            allowed = [p.strip() for p in permissions.split(",") if p.strip()]
        keyboard = []
        if "admin_users" in allowed:
            keyboard.append([InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users^")])
        if "admin_transactions" in allowed:
            keyboard.append([InlineKeyboardButton("💰 مدیریت تراکنش‌ها", callback_data="admin_transactions^")])
        if "admin_stats" in allowed:
            keyboard.append([InlineKeyboardButton("📊 آمار و گزارشات", callback_data="admin_stats^")])
        if "manage_admins" in allowed:
            keyboard.append([InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="manage_admins^")])
        # Add new broadcast button
        if "admin_users" in allowed:  # Using same permission as user management
            keyboard.append([InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast_menu^")])
        # اضافه کردن بخش مدیریت ترین‌ها
        if "manage_questions" in allowed:
            keyboard.append([InlineKeyboardButton("🏆 مدیریت سوالات ترین‌ها", callback_data="manage_top_questions^")])
        keyboard.append([InlineKeyboardButton("» بازگشت به منوی اصلی", callback_data="userpanel^")])
        await query.answer()
        await query.edit_message_text(
            "🔐 <b>پنل مدیریت ادمین</b>\n\n"
            "به پنل مدیریت خوش آمدید. از این بخش می‌توانید کاربران و تراکنش‌ها را مدیریت کنید و آمار سیستم را مشاهده نمایید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    
    # بخش مدیریت سوالات ترین‌ها
    elif data == "manage_top_questions^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        role, permissions = row
        allowed = []
        if role == 'god':
            allowed = [p[0] for p in ADMIN_PERMISSIONS]
        elif permissions:
            allowed = [p.strip() for p in permissions.split(",") if p.strip()]
        if "manage_questions" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        questions = get_all_top_questions()
        msg = "🏆 <b>مدیریت سوالات ترین‌ها</b>\n\n"
        
        if questions:
            for i, q in enumerate(questions):
                status = "✅ فعال" if q[2] == 1 else "❌ غیرفعال"
                msg += f"{i+1}. {q[1]} - <i>{status}</i>\n"
        else:
            msg += "هیچ سوالی تعریف نشده است."
            
        keyboard = [
            [InlineKeyboardButton("➕ افزودن سوال جدید", callback_data="add_top_question^")],
            [InlineKeyboardButton("✏️ ویرایش سوال", callback_data="edit_top_question^")],
            [InlineKeyboardButton("❌ حذف سوال", callback_data="delete_top_question^")],
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return
        
    elif data == "add_top_question^":
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        context.user_data['admin_action'] = 'add_top_question'
        await query.edit_message_text(
            "لطفاً متن سوال جدید را وارد کنید:\n\n"
            "مثال: بهترین همکارت کیه؟",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="manage_top_questions^")]])
        )
        return
        
    elif data.startswith("edit_top_question^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            question_id = int(data.split("^")[1])
            c.execute("SELECT text, is_active FROM top_questions WHERE question_id=?", (question_id,))
            question = c.fetchone()
            
            if question:
                context.user_data['edit_question_id'] = question_id
                context.user_data['admin_action'] = 'edit_top_question'
                status = "فعال" if question[1] == 1 else "غیرفعال"
                
                keyboard = [
                    [InlineKeyboardButton("✏️ ویرایش متن", callback_data=f"edit_question_text^{question_id}")],
                    [InlineKeyboardButton("🔄 تغییر وضعیت", callback_data=f"toggle_question_status^{question_id}")],
                    [InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")]
                ]
                
                await query.edit_message_text(
                    f"ویرایش سوال:\n\n"
                    f"متن فعلی: {question[0]}\n"
                    f"وضعیت: {status}\n\n"
                    f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
        
        # نمایش لیست سوالات برای انتخاب
        questions = get_all_top_questions()
        keyboard = []
        for q in questions:
            keyboard.append([InlineKeyboardButton(f"{q[1]}", callback_data=f"edit_top_question^{q[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")])
        
        await query.edit_message_text(
            "لطفاً سوال مورد نظر برای ویرایش را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    elif data.startswith("edit_question_text^"):
        question_id = int(data.split("^")[1])
        context.user_data['edit_question_id'] = question_id
        context.user_data['admin_action'] = 'edit_question_text'
        
        c.execute("SELECT text FROM top_questions WHERE question_id=?", (question_id,))
        current_text = c.fetchone()[0]
        
        await query.edit_message_text(
            f"لطفاً متن جدید برای سوال زیر را وارد کنید:\n\n"
            f"متن فعلی: {current_text}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data=f"edit_top_question^{question_id}")]])
        )
        return
        
    elif data.startswith("toggle_question_status^"):
        question_id = int(data.split("^")[1])
        
        c.execute("SELECT is_active FROM top_questions WHERE question_id=?", (question_id,))
        current_status = c.fetchone()[0]
        new_status = 0 if current_status == 1 else 1
        
        c.execute("UPDATE top_questions SET is_active=? WHERE question_id=?", (new_status, question_id))
        conn.commit()
        
        status_text = "فعال" if new_status == 1 else "غیرفعال"
        await query.answer(f"وضعیت سوال به {status_text} تغییر یافت.")
        
        # بازگشت به صفحه ویرایش سوال
        return await menu_callback(update, context)
        
    elif data.startswith("delete_top_question^"):
        c.execute("SELECT role, permissions FROM admins WHERE user_id=?", (user.id,))
        row = c.fetchone()
        if not row or (row[0] != 'god' and "manage_questions" not in row[1].split(",")):
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
            
        if len(data.split("^")) > 1 and data.split("^")[1].isdigit():
            question_id = int(data.split("^")[1])
            
            # حذف سوال
            c.execute("DELETE FROM top_questions WHERE question_id=?", (question_id,))
            conn.commit()
            
            await query.answer("سوال با موفقیت حذف شد.")
            return await menu_callback(update, context)
        
        # نمایش لیست سوالات برای انتخاب
        questions = get_all_top_questions()
        keyboard = []
        for q in questions:
            keyboard.append([InlineKeyboardButton(f"{q[1]}", callback_data=f"delete_top_question^{q[0]}")])
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="manage_top_questions^")])
        
        await query.edit_message_text(
            "⚠️ لطفاً سوال مورد نظر برای حذف را انتخاب کنید:\n"
            "توجه: این عملیات غیرقابل بازگشت است!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    elif data == "broadcast_menu^":
        keyboard = [
            [InlineKeyboardButton("📝 پیام همگانی دلخواه", callback_data="custom_broadcast^")],
            [InlineKeyboardButton("⭐️ پیام به کاربران بدون رای", callback_data="inactive_users_broadcast^")],
            [InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]
        ]
        await query.edit_message_text(
            "📢 <b>بخش پیام همگانی</b>\n\n"
            "لطفاً نوع پیام همگانی را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data == "custom_broadcast^":
        context.user_data['admin_action'] = 'custom_broadcast'
        await query.edit_message_text(
            "📝 لطفاً متن پیام همگانی خود را ارسال کنید:\n\n"
            "می‌توانید از فرمت HTML استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="broadcast_menu^")]])
        )

    elif data == "inactive_users_broadcast^":
        # Get users who haven't voted yet
        c.execute("""
            SELECT u.user_id FROM users u 
            LEFT JOIN transactions t ON u.user_id = t.user_id 
            WHERE t.user_id IS NULL
        """)
        inactive_users = c.fetchall()
        
        if not inactive_users:
            await query.answer("کاربر بدون رای وجود ندارد!", show_alert=True)
            return
            
        broadcast_text = (
            "👋 سلام دوست عزیز,\n\n"
            "تا حالا به کسی در سیمرغ امتیاز دادی؟ اگر نه، می‌تونی از طریق ربات و گزینه «امتیازدهی به دیگران» وارد بشی و با چند کلیک ساده، از همکارایی که برات ارزشمند بودن قدردانی کنی.\n\n"
            "🌟 حتی یه امتیاز کوچیک هم می‌تونه کلی انرژی مثبت منتقل کنه!\n"
            "ممنون که همراه مایی 💙"
        )
        
        sent_count = 0
        failed_count = 0
        
        for user_id in inactive_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id[0],
                    text=broadcast_text,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id[0]}: {e}")
                failed_count += 1
                
        await query.edit_message_text(
            f"✅ پیام به کاربران بدون رای ارسال شد\n\n"
            f"✓ ارسال موفق: {sent_count}\n"
            f"❌ ارسال ناموفق: {failed_count}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="broadcast_menu^")]])
        )
    elif data == "top_vote^":
        # بررسی آیا کاربر قبلاً به همه سوالات پاسخ داده است
        if has_user_voted_all_top_questions(user.id):
            return await menu_callback(update, context)
        
        # بررسی آیا کاربر قبلاً هیچ سوالی را پاسخ نداده است (یعنی اولین بار است)
        c.execute("SELECT COUNT(*) FROM top_votes WHERE user_id=? AND season_id=?", (user.id, config.SEASON_ID))
        first_time = c.fetchone()[0] == 0
        
        if first_time:
            # ارائه توضیحات و نمایش دکمه شروع
            keyboard = [[InlineKeyboardButton("👈 شروع رأی‌گیری", callback_data="start_top_vote^")],
                       [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]
            
            await query.edit_message_text(
                f"🏆 <b>ترین‌های فصل {config.SEASON_NAME}</b>\n\n"
                f"به بخش «ترین‌ها» خوش آمدید!\n\n"
                f"در این بخش شما به سؤالاتی درباره ویژگی‌های همکارانتان پاسخ می‌دهید.\n"
                f"برای هر سؤال، می‌توانید یکی از همکارانتان را انتخاب کنید.\n\n"
                f"<b>نکات مهم:</b>\n"
                f"• شما فقط یک بار می‌توانید به هر سؤال پاسخ دهید.\n"
                f"• بعد از پاسخ به همه سؤالات، نتایج کلی را مشاهده خواهید کرد.\n"
                f"• رأی‌های شما به صورت عمومی در کانال منتشر خواهد شد.\n\n"
                f"آیا آماده‌اید؟",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
        
        # ادامه روند معمول برای دریافت سوال بعدی
        return await process_next_top_question(update, context)
        
    # شروع رأی‌گیری بعد از دیدن توضیحات
    elif data == "start_top_vote^":
        return await process_next_top_question(update, context)
    
    # انتخاب کاربر برای ترین‌ها
    elif data.startswith("top_select^"):
        parts = data.split("^")
        question_id = int(parts[1])
        voted_for_user_id = int(parts[2])
        
        # دریافت اطلاعات سوال و کاربر انتخاب شده
        c.execute("SELECT text FROM top_questions WHERE question_id=?", (question_id,))
        question = c.fetchone()
        
        c.execute("SELECT name FROM users WHERE user_id=?", (voted_for_user_id,))
        user_name = c.fetchone()[0]
        
        if not question:
            await query.answer("سوال مورد نظر یافت نشد!")
            return await menu_callback(update, context)
            
        # ثبت رأی
        if save_top_vote(user.id, question_id, voted_for_user_id):
            await query.answer(f"رأی شما با موفقیت ثبت شد!")
            
            # بررسی آیا سوال بعدی وجود دارد
            next_question = get_next_unanswered_question(user.id)
            
            if next_question:
                # اگر سوال بعدی وجود دارد، مستقیماً به صفحه سوال بعدی برو
                question_id, question_text = next_question
                
                # دریافت لیست کاربران برای رأی‌دهی (به جز خود کاربر)
                users = get_all_users(exclude_id=user.id)
                keyboard = []
                row = []
                for i, u in enumerate(users):
                    row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"top_select^{question_id}^{u[0]}"))
                    if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
                        if len(row) == 1 and i == len(users) - 1:  # اگر آخرین آیتم تنها در ردیف باشد
                            keyboard.append(row)
                        elif len(row) == 2:
                            keyboard.append(row)
                        row = []
                
                keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
                
                await query.edit_message_text(
                    f"🏆 <b>ترین‌های فصل {config.SEASON_NAME}</b>\n\n"
                    f"<b>سوال:</b> {question_text}\n\n"
                    f"لطفاً یکی از همکاران خود را انتخاب کنید:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            else:
                # اگر همه سوالات پاسخ داده شده‌اند، نمایش خلاصه رأی‌های کاربر
                user_votes = get_user_top_votes(user.id)
                summary = f"🎉 <b>تبریک!</b>\n\nشما به تمام سوالات ترین‌های فصل {config.SEASON_NAME} پاسخ دادید.\n\n<b>رأی‌های شما:</b>\n\n"
                
                for q_text, voted_name, _ in user_votes:
                    summary += f"🔹 {q_text}\n"
                    summary += f"✓ رأی شما: {voted_name}\n\n"
                
                keyboard = [[InlineKeyboardButton("» مشاهده نتایج", callback_data="top_results^")]]
                
                await query.edit_message_text(
                    summary,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
                
                # ارسال پیام به کانال
                try:
                    bot = context.bot
                    channel_message = f"🏆 <b>ترین‌های فصل {config.SEASON_NAME}</b>\n\n"
                    channel_message += f"از نظر <b>{user.full_name}</b>:\n\n"
                    
                    for q_text, voted_name, _ in user_votes:
                        channel_message += f"🔹 {q_text} <b>{voted_name}</b>\n\n"
                    
                    await bot.send_message(
                        chat_id=config.CHANNEL_ID,
                        text=channel_message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending message to channel: {e}")
                
        else:
            await query.answer("خطا در ثبت رأی!")
            # در صورت خطا، به منوی اصلی برگرد
            return await menu_callback(update, context)
        return
    
    # نمایش نتایج ترین‌ها
    elif data == "top_results^":
        # دریافت سوالات فعال
        questions = get_active_top_questions()
        
        if not questions:
            await query.edit_message_text(
                "هیچ سوال فعالی برای نمایش نتایج وجود ندارد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
            return
            
        msg = f"🏆 <b>نتایج ترین‌های فصل {config.SEASON_NAME}</b>\n\n"
        
        # نمایش نتایج برای هر سوال
        for q_id, q_text in questions:
            results = get_top_results_for_question(q_id)
            
            msg += f"<b>🔹 {q_text}</b>\n"
            
            if results:
                for i, (user_id, vote_count, name) in enumerate(results):
                    medal = ""
                    if i == 0:
                        medal = "🥇 "
                    elif i == 1:
                        medal = "🥈 "
                    elif i == 2:
                        medal = "🥉 "
                        
                    msg += f"{medal}{name}: {vote_count} رأی\n"
            else:
                msg += "هنوز رأیی ثبت نشده است.\n"
                
            msg += "\n"
            
        # دریافت رأی‌های کاربر
        user_votes = get_user_top_votes(user.id)
        
        if user_votes:
            msg += "<b>👤 رأی‌های شما:</b>\n\n"
            
            for q_text, voted_name, _ in user_votes:
                msg += f"🔹 {q_text}\n"
                msg += f"✓ رأی شما: {voted_name}\n\n"
        
        keyboard = [[InlineKeyboardButton("» بازگشت به منوی اصلی", callback_data="userpanel^")]]
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    else:
        await query.answer("در حال توسعه ...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    
    # ویزارد مدیریت ادمین‌ها
    if is_god_admin(user.id) and context.user_data.get('admin_action'):
        action = context.user_data['admin_action']
        if action == 'add':
            try:
                new_admin_id = int(message)
                context.user_data['new_admin_id'] = new_admin_id
                keyboard = [
                    [InlineKeyboardButton("ادمین معمولی", callback_data="set_role^admin")],
                    [InlineKeyboardButton("ادمین گاد", callback_data="set_role^god")]
                ]
                await update.message.reply_text("نقش ادمین را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            except:
                await update.message.reply_text("آیدی عددی معتبر نیست.")
                context.user_data['admin_action'] = None
                return
        elif action == 'edit':
            try:
                edit_admin_id = int(message)
                context.user_data['edit_admin_id'] = edit_admin_id
                await update.message.reply_text("دسترسی جدید را به صورت کاما جدا وارد کنید (مثلاً: add_user,view_stats):")
                context.user_data['admin_action'] = 'edit_permissions'
                return
            except:
                await update.message.reply_text("آیدی عددی معتبر نیست.")
                context.user_data['admin_action'] = None
                return
        elif action == 'edit_permissions':
            edit_admin_id = context.user_data.get('edit_admin_id')
            update_admin_permissions(edit_admin_id, message)
            await update.message.reply_text("دسترسی ادمین به‌روزرسانی شد.")
            context.user_data['admin_action'] = None
            context.user_data['edit_admin_id'] = None
            return
        elif action == 'remove':
            try:
                remove_admin_id = int(message)
                remove_admin(remove_admin_id)
                await update.message.reply_text("ادمین حذف شد.")
            except:
                await update.message.reply_text("آیدی عددی معتبر نیست.")
            context.user_data['admin_action'] = None
            return
        # مدیریت سوالات ترین‌ها
        elif action == 'add_top_question':
            question_text = message.strip()
            
            if not question_text:
                await update.message.reply_text("متن سوال نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.")
                return
                
            add_top_question(question_text)
            
            await update.message.reply_text(
                f"✅ سوال جدید با موفقیت اضافه شد:\n\n{question_text}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» مدیریت سوالات", callback_data="manage_top_questions^")]])
            )
            
            context.user_data['admin_action'] = None
            return
            
        elif action == 'edit_question_text':
            question_id = context.user_data.get('edit_question_id')
            new_text = message.strip()
            
            if not new_text:
                await update.message.reply_text("متن سوال نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.")
                return
                
            c.execute("SELECT is_active FROM top_questions WHERE question_id=?", (question_id,))
            is_active = c.fetchone()[0]
            
            update_top_question(question_id, new_text, is_active)
            
            await update.message.reply_text(
                f"✅ سوال با موفقیت ویرایش شد:\n\n{new_text}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» مدیریت سوالات", callback_data="manage_top_questions^")]])
            )
            
            context.user_data['admin_action'] = None
            context.user_data['edit_question_id'] = None
            return
    
    # بررسی تأیید کاربر
    is_approved = is_user_approved(user.id)
    if not is_approved:
        # ارسال پیام به کاربر
        await update.message.reply_text(
            f"برای اخذ دسترسی با پشتیبانی تماس بگیرید.\n\n"
            f"آیدی پشتیبانی: {config.SUPPORT_USERNAME}",
            reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 پشتیبانی", url=f"https://t.me/{config.SUPPORT_USERNAME.strip('@')}")]
            ])
        )
        return
    
    # اگر کاربر در حالت انتظار برای دلیل امتیازدهی است
    if context.user_data.get('waiting_for_reason'):
        pending = context.user_data.get('pending_transaction')
        if pending:
            touser_id = pending['touser_id']
            amount = pending['amount']
            touser_name = pending.get('touser_name', 'کاربر')
            reason = message
            
            # ایجاد دکمه‌های تأیید یا لغو
            keyboard = [
                [
                    InlineKeyboardButton("✏️ ویرایش", callback_data=f"voteuser^{touser_id}"),
                    InlineKeyboardButton("✅ تأیید", callback_data=f"Confirm^{touser_id}^{amount}^{reason}")
                ],
                [InlineKeyboardButton("❌ انصراف", callback_data="tovote^")]
            ]
            
            await update.message.reply_text(
                f"شما قصد دارید به {touser_name} {amount} امتیاز بدهید.\n\n"
                f"---------------------------------\n"
                f"دلیل : {reason}\n"
                f"---------------------------------\n\n"
                f"اگر متن مناسب است، روی دکمه «تأیید» کلیک کنید تا امتیاز ثبت شود.\n"
                f"در غیر این صورت، می‌توانید پیام خود را ویرایش کنید.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # پاک کردن وضعیت انتظار
            context.user_data['waiting_for_reason'] = False
            return
    
    # اگر پیام با دستور شروع نشده باشد، منوی اصلی را فقط زمانی نمایش بده که هیچ اکشن مدیریتی فعال نباشد
    if not context.user_data.get('admin_action'):
        await update.message.reply_text(
            f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
            reply_markup=main_menu_keyboard(user.id)
        )
    
    # Handle custom broadcast
    if context.user_data.get('admin_action') == 'custom_broadcast':
        broadcast_text = update.message.text
        
        # Get all users
        c.execute("SELECT user_id FROM users")
        all_users = c.fetchall()
        
        sent_count = 0
        failed_count = 0
        
        progress_message = await update.message.reply_text("در حال ارسال پیام همگانی...")
        
        for user_id in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id[0],
                    text=broadcast_text,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id[0]}: {e}")
                failed_count += 1
        
        await progress_message.edit_text(
            f"✅ پیام همگانی ارسال شد\n\n"
            f"✓ ارسال موفق: {sent_count}\n"
            f"❌ ارسال ناموفق: {failed_count}"
        )
        
        context.user_data['admin_action'] = None
        return

# توابع کمکی برای مدیریت ادمین‌ها

def is_god_admin(user_id):
    c.execute("SELECT role FROM admins WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row and row[0] == 'god'

def get_admins():
    c.execute("SELECT user_id, role, permissions FROM admins")
    return c.fetchall()

def add_admin(user_id, role, permissions):
    c.execute("INSERT OR REPLACE INTO admins (user_id, role, permissions) VALUES (?, ?, ?)", (user_id, role, permissions))
    conn.commit()

def remove_admin(user_id):
    c.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    conn.commit()

def update_admin_permissions(user_id, permissions):
    c.execute("UPDATE admins SET permissions=? WHERE user_id=?", (permissions, user_id))
    conn.commit()

def build_permissions_keyboard(selected_permissions):
    keyboard = []
    for perm, fa_title in ADMIN_PERMISSIONS:
        is_selected = perm in selected_permissions
        status = "✅" if is_selected else "❌"
        keyboard.append([
            InlineKeyboardButton(f"{fa_title}", callback_data="noop"),
            InlineKeyboardButton(f"{status}", callback_data=f"toggleperm^{perm}")
        ])
    keyboard.append([InlineKeyboardButton("➕ افزودن", callback_data="confirm_add_admin^")])
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="manage_admins^")])
    return InlineKeyboardMarkup(keyboard)

# بخش کمکی برای دریافت سوالات ترین‌ها
def get_active_top_questions():
    c.execute("""
        SELECT question_id, text FROM top_questions 
        WHERE is_active=1 AND season_id=?
        ORDER BY question_id
    """, (config.SEASON_ID,))
    return c.fetchall()

# بررسی آیا کاربر به همه سوالات ترین‌ها پاسخ داده است
def has_user_voted_all_top_questions(user_id):
    c.execute("""
        SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
    """, (config.SEASON_ID,))
    total_questions = c.fetchone()[0]
    
    c.execute("""
        SELECT COUNT(*) FROM top_votes 
        WHERE user_id=? AND season_id=?
    """, (user_id, config.SEASON_ID))
    user_votes = c.fetchone()[0]
    
    return user_votes >= total_questions

# دریافت سوال بعدی که کاربر هنوز به آن پاسخ نداده
def get_next_unanswered_question(user_id):
    c.execute("""
        SELECT q.question_id, q.text 
        FROM top_questions q 
        LEFT JOIN top_votes v ON q.question_id = v.question_id AND v.user_id = ? AND v.season_id = ?
        WHERE q.is_active=1 AND q.season_id=? AND v.vote_id IS NULL
        ORDER BY q.question_id
        LIMIT 1
    """, (user_id, config.SEASON_ID, config.SEASON_ID))
    return c.fetchone()

# ثبت رای ترین‌ها
def save_top_vote(user_id, question_id, voted_for_user_id):
    try:
        c.execute("""
            INSERT OR REPLACE INTO top_votes 
            (user_id, question_id, voted_for_user_id, season_id) 
            VALUES (?, ?, ?, ?)
        """, (user_id, question_id, voted_for_user_id, config.SEASON_ID))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving top vote: {e}")
        return False

# دریافت نتایج ترین‌ها برای یک سوال خاص
def get_top_results_for_question(question_id):
    c.execute("""
        SELECT v.voted_for_user_id, COUNT(*) as vote_count, u.name
        FROM top_votes v
        JOIN users u ON v.voted_for_user_id = u.user_id
        WHERE v.question_id = ? AND v.season_id = ?
        GROUP BY v.voted_for_user_id
        ORDER BY vote_count DESC
        LIMIT 5
    """, (question_id, config.SEASON_ID))
    return c.fetchall()

# دریافت رای‌های کاربر در ترین‌ها
def get_user_top_votes(user_id):
    c.execute("""
        SELECT q.text, u.name, v.vote_id
        FROM top_votes v
        JOIN top_questions q ON v.question_id = q.question_id
        JOIN users u ON v.voted_for_user_id = u.user_id
        WHERE v.user_id = ? AND v.season_id = ?
        ORDER BY q.question_id
    """, (user_id, config.SEASON_ID))
    return c.fetchall()

# مدیریت سوالات ترین‌ها (برای ادمین)
def get_all_top_questions():
    c.execute("""
        SELECT question_id, text, is_active 
        FROM top_questions 
        WHERE season_id=?
        ORDER BY question_id
    """, (config.SEASON_ID,))
    return c.fetchall()

def add_top_question(text):
    c.execute("""
        INSERT INTO top_questions (text, season_id, is_active) 
        VALUES (?, ?, 1)
    """, (text, config.SEASON_ID))
    conn.commit()

def update_top_question(question_id, text, is_active):
    c.execute("""
        UPDATE top_questions 
        SET text = ?, is_active = ? 
        WHERE question_id = ?
    """, (text, is_active, question_id))
    conn.commit()

def delete_top_question(question_id):
    c.execute("DELETE FROM top_questions WHERE question_id = ?", (question_id,))
    conn.commit()

async def process_next_top_question(update, context):
    query = update.callback_query
    user = query.from_user
    
    # دریافت سوال بعدی که کاربر به آن پاسخ نداده
    next_question = get_next_unanswered_question(user.id)
    
    if not next_question:
        await query.answer("هیچ سوال فعالی برای پاسخ وجود ندارد!")
        return await menu_callback(update, context)
        
    question_id, question_text = next_question
    
    # دریافت لیست کاربران برای رأی‌دهی (به جز خود کاربر)
    users = get_all_users(exclude_id=user.id)
    if not users:
        await query.edit_message_text(
            "هیچ کاربر دیگری برای رأی‌دهی وجود ندارد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
        )
        return
    
    keyboard = []
    row = []
    for i, u in enumerate(users):
        row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"top_select^{question_id}^{u[0]}"))
        if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
            if len(row) == 1 and i == len(users) - 1:  # اگر آخرین آیتم تنها در ردیف باشد
                keyboard.append(row)
            elif len(row) == 2:
                keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
    
    await query.edit_message_text(
        f"🏆 <b>ترین‌های فصل {config.SEASON_NAME}</b>\n\n"
        f"<b>سوال:</b> {question_text}\n\n"
        f"لطفاً یکی از همکاران خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return

async def main():
    # ایجاد و پیکربندی برنامه
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # اجرای ربات
    print("ربات اجرا شد...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # حلقه بی‌نهایت برای نگه داشتن برنامه در حال اجرا
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        # در صورت قطع برنامه، ربات را به درستی متوقف می‌کنیم
        pass
    finally:
        # بستن ربات
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())