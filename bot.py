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

# لیست دسترسی‌های ادمین (مطابق با گزینه‌های پنل مدیریت)
ADMIN_PERMISSIONS = [
    ("admin_users", "مدیریت کاربران"),
    ("admin_transactions", "مدیریت تراکنش"),
    ("admin_stats", "آمار و گزارشات"),
    ("manage_admins", "مدیریت ادمین‌ها"),
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
        [InlineKeyboardButton("🎯 امتیازدهی به دیگران", callback_data="tovote^")],
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
        # ارسال پیام به کاربر
        await update.message.reply_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با ادمین ارتباط بگیرید:\n"
            f"👤 @{config.SUPPORT_USERNAME.split('/')[-1]}"
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
                keyboard = [[InlineKeyboardButton("» مشاهده در کانال👁", url=f"https://t.me/c/{channel_id_num}/{channel_message.message_id}")]]
                
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
        keyboard.append([InlineKeyboardButton("» بازگشت به منوی اصلی", callback_data="userpanel^")])
        await query.answer()
        await query.edit_message_text(
            "🔐 <b>پنل مدیریت ادمین</b>\n\n"
            "به پنل مدیریت خوش آمدید. از این بخش می‌توانید کاربران و تراکنش‌ها را مدیریت کنید و آمار سیستم را مشاهده نمایید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
        
    elif data == "admin_users^":
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
        if "admin_users" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        await query.answer()
        # در اینجا می‌توانید لیست کاربران را نمایش دهید
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        keyboard = [
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        await query.edit_message_text(
            f"👥 <b>مدیریت کاربران</b>\n\n"
            f"تعداد کل کاربران: {user_count}\n\n"
            f"این بخش در حال توسعه است...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
        
    elif data == "admin_transactions^":
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
        if "admin_transactions" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        await query.answer()
        # در اینجا می‌توانید آمار تراکنش‌ها را نمایش دهید
        c.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
        result = c.fetchone()
        transaction_count = result[0] or 0
        total_amount = result[1] or 0
        keyboard = [
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        await query.edit_message_text(
            f"💰 <b>مدیریت تراکنش‌ها</b>\n\n"
            f"تعداد کل تراکنش‌ها: {transaction_count}\n"
            f"مجموع امتیازات: {total_amount}\n\n"
            f"این بخش در حال توسعه است...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
        
    elif data == "admin_stats^":
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
        if "admin_stats" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        await query.answer()
        # در اینجا می‌توانید آمار کلی سیستم را نمایش دهید
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
        result = c.fetchone()
        transaction_count = result[0] or 0
        total_amount = result[1] or 0
        keyboard = [
            [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
        ]
        await query.edit_message_text(
            f"📊 <b>آمار و گزارشات</b>\n\n"
            f"تعداد کل کاربران: {user_count}\n"
            f"تعداد کل تراکنش‌ها: {transaction_count}\n"
            f"مجموع امتیازات: {total_amount}\n\n"
            f"این بخش در حال توسعه است...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    elif data == "manage_admins^":
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
        if "manage_admins" not in allowed:
            await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
            return
        if not is_god_admin(user.id):
            await query.answer("دسترسی فقط برای ادمین گاد مجاز است.", show_alert=True)
            return
        admins = get_admins()
        msg = "لیست ادمین‌ها:\n"
        for a in admins:
            msg += f"\n{a[0]} | نقش: {a[1]} | دسترسی: {a[2]}"
        keyboard = [
            [InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin^")],
            [InlineKeyboardButton("✏️ ویرایش دسترسی", callback_data="edit_admin^")],
            [InlineKeyboardButton("❌ حذف ادمین", callback_data="remove_admin^")],
            [InlineKeyboardButton("بازگشت", callback_data="userpanel^")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    elif data == "add_admin^":
        context.user_data['admin_action'] = 'add'
        await query.edit_message_text("لطفاً آیدی عددی کاربر را ارسال کنید:")
    elif data.startswith("set_role^"):
        role = data.split('^')[1]
        context.user_data['pending_role'] = role
        context.user_data['pending_permissions'] = []
        context.user_data['admin_action'] = 'select_permissions'
        await query.edit_message_text(
            "دسترسی‌های مورد نظر را انتخاب کنید:",
            reply_markup=build_permissions_keyboard(context.user_data['pending_permissions'])
        )
        return
    elif data.startswith("toggleperm^"):
        if not is_god_admin(user.id):
            await query.answer("دسترسی فقط برای ادمین گاد مجاز است.", show_alert=True)
            return
        perm = data.split("^")[1]
        selected = context.user_data.get('pending_permissions', [])
        if perm in selected:
            selected.remove(perm)
        else:
            selected.append(perm)
        context.user_data['pending_permissions'] = selected
        await query.edit_message_text(
            "دسترسی‌های مورد نظر را انتخاب کنید:",
            reply_markup=build_permissions_keyboard(selected)
        )
        return
    elif data == "confirm_add_admin^":
        if not is_god_admin(user.id):
            await query.answer("دسترسی فقط برای ادمین گاد مجاز است.", show_alert=True)
            return
        new_admin_id = context.user_data.get('new_admin_id')
        role = context.user_data.get('pending_role')
        permissions = ",".join(context.user_data.get('pending_permissions', []))
        add_admin(new_admin_id, role, permissions)
        await query.edit_message_text("ادمین جدید اضافه شد.")
        try:
            await context.bot.send_message(new_admin_id, f"شما به عنوان ادمین ({role}) به ربات اضافه شدید. دسترسی‌ها: {permissions}")
        except:
            pass
        context.user_data['admin_action'] = None
        context.user_data['new_admin_id'] = None
        context.user_data['pending_role'] = None
        context.user_data['pending_permissions'] = None
        return
    elif is_god_admin(user.id) and context.user_data.get('admin_action'):
        action = context.user_data['admin_action']
        if action == 'add':
            try:
                new_admin_id = int(data.split('^')[1])
                context.user_data['new_admin_id'] = new_admin_id
                keyboard = [
                    [InlineKeyboardButton("ادمین معمولی", callback_data="set_role^admin")],
                    [InlineKeyboardButton("ادمین گاد", callback_data="set_role^god")]
                ]
                await update.message.reply_text("نقش ادمین را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
                # مرحله بعدی با دکمه set_role^ انجام می‌شود
                return
            except:
                await update.message.reply_text("آیدی عددی معتبر نیست.")
                context.user_data['admin_action'] = None
                return
        elif action == 'edit':
            try:
                edit_admin_id = int(data.split('^')[1])
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
            update_admin_permissions(edit_admin_id, data)
            await update.message.reply_text("دسترسی ادمین به‌روزرسانی شد.")
            context.user_data['admin_action'] = None
            context.user_data['edit_admin_id'] = None
            return
        elif action == 'remove':
            try:
                remove_admin_id = int(data.split('^')[1])
                remove_admin(remove_admin_id)
                await update.message.reply_text("ادمین حذف شد.")
            except:
                await update.message.reply_text("آیدی عددی معتبر نیست.")
            context.user_data['admin_action'] = None
            return
    # پردازش تأیید یا رد کاربر
    elif data.startswith("approve_user^"):
        if user.id != config.ADMIN_USER_ID:
            await query.answer("شما دسترسی به این بخش ندارید!")
            return
            
        await query.answer()
        user_id = int(data.split("^")[1])
        
        # دریافت اطلاعات کاربر از تلگرام
        try:
            bot = context.bot
            chat_member = await bot.get_chat_member(chat_id=user_id, user_id=user_id)
            target_user = chat_member.user
            
            # افزودن کاربر به دیتابیس
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            if not c.fetchone():
                c.execute("INSERT INTO users (user_id, username, name) VALUES (?, ?, ?)", 
                         (user_id, target_user.username, target_user.full_name))
                conn.commit()
                
                # ارسال پیام به کاربر
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>درخواست دسترسی شما تأیید شد</b>\n\n"
                         f"اکنون می‌توانید از {config.BOT_NAME} استفاده کنید.\n"
                         f"برای شروع، دستور /start را ارسال کنید.",
                    parse_mode="HTML"
                )
                
                # اطلاع به ادمین
                await query.edit_message_text(
                    f"✅ کاربر {target_user.full_name} با موفقیت به سیستم اضافه شد و به او اطلاع داده شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
                )
            else:
                await query.edit_message_text(
                    f"⚠️ کاربر {target_user.full_name} قبلاً در سیستم ثبت شده است.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
                )
        except Exception as e:
            logger.error(f"Error approving user: {e}")
            await query.edit_message_text(
                f"❌ خطا در تأیید کاربر: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
            )
    
    elif data.startswith("reject_user^"):
        if user.id != config.ADMIN_USER_ID:
            await query.answer("شما دسترسی به این بخش ندارید!")
            return
            
        await query.answer()
        user_id = int(data.split("^")[1])
        
        try:
            bot = context.bot
            chat_member = await bot.get_chat_member(chat_id=user_id, user_id=user_id)
            target_user = chat_member.user
            
            # ارسال پیام به کاربر
            await bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>درخواست دسترسی شما رد شد</b>\n\n"
                     f"متأسفانه درخواست شما برای دسترسی به {config.BOT_NAME} توسط ادمین رد شد.",
                parse_mode="HTML"
            )
            
            # اطلاع به ادمین
            await query.edit_message_text(
                f"❌ درخواست کاربر {target_user.full_name} رد شد و به او اطلاع داده شد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
            )
        except Exception as e:
            logger.error(f"Error rejecting user: {e}")
            await query.edit_message_text(
                f"❌ خطا در رد کاربر: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
            )
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
    
    # بررسی تأیید کاربر
    is_approved = is_user_approved(user.id)
    if not is_approved:
        # ارسال پیام به کاربر
        await update.message.reply_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با ادمین ارتباط بگیرید:\n"
            f"👤 @{config.SUPPORT_USERNAME.split('/')[-1]}"
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