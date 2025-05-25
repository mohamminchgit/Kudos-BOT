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

def get_or_create_user(user):
    c.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
        conn.commit()

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎯 امتیازدهی به دیگران", callback_data="tovote^")],
        [InlineKeyboardButton("» پروفایل شما", callback_data="userprofile^"), InlineKeyboardButton("ردپای امتیازات", callback_data="historypoints^")],
        [InlineKeyboardButton("» راهنما", callback_data="help^"), InlineKeyboardButton("» پشتیبانی", url=config.SUPPORT_USERNAME)]
    ]
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

def get_user_transactions(user_id, given=True):
    if given:
        c.execute("""
            SELECT t.amount, t.touser, u.name, t.reason, t.created_at 
            FROM transactions t 
            LEFT JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id=? 
            ORDER BY t.created_at DESC LIMIT 10
        """, (user_id,))
    else:
        c.execute("""
            SELECT t.amount, t.user_id, u.name, t.reason, t.created_at 
            FROM transactions t 
            LEFT JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser=? 
            ORDER BY t.created_at DESC LIMIT 10
        """, (user_id,))
    return c.fetchall()

def get_scoreboard():
    c.execute("""
        SELECT touser, SUM(amount) as total, u.name 
        FROM transactions t 
        LEFT JOIN users u ON t.touser = u.user_id 
        GROUP BY touser 
        ORDER BY total DESC LIMIT 10
    """)
    return c.fetchall()

async def check_channel_membership(user_id):
    try:
        # استفاده از API تلگرام برای بررسی عضویت کاربر در کانال
        bot = Application.get_current().bot
        
        # اضافه کردن لاگ برای بررسی مقدار CHANNEL_ID
        logger.info(f"Checking membership for user {user_id} in channel {config.CHANNEL_ID}")
        
        # تلاش برای دریافت اطلاعات عضویت
        chat_member = await bot.get_chat_member(chat_id=config.CHANNEL_ID, user_id=user_id)
        
        # اضافه کردن لاگ برای بررسی وضعیت عضویت
        logger.info(f"User {user_id} membership status: {chat_member.status}")
        
        # بررسی وضعیت عضویت
        is_member = chat_member.status in ['member', 'administrator', 'creator', 'restricted']
        return is_member
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        # برای اهداف دیباگ، موقتاً همیشه True برمی‌گردانیم
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user)
    
    # بررسی عضویت در کانال
    is_member = await check_channel_membership(user.id)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await update.message.reply_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard()
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    get_or_create_user(user)
    data = query.data
    
    # بررسی عضویت در کانال برای تمام کالبک‌ها
    is_member = await check_channel_membership(user.id)
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
            reply_markup=main_menu_keyboard()
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
            await query.edit_message_text("پروفایل یافت نشد.", reply_markup=main_menu_keyboard())
    elif data == "historypoints^":
        await query.answer()
        keyboard = [
            [InlineKeyboardButton("تابلوی امتیازات 🏆", callback_data="Scoreboard^")],
            [InlineKeyboardButton("امتیازهای شما 🎯", callback_data="receivedpoints^"), 
             InlineKeyboardButton("امتیازهایی که دادید 💬", callback_data="givenpoints^")],
            [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
        ]
        await query.edit_message_text(
            f"📌 تاریخچه امتیازات شما\n\nدر این بخش می‌توانید امتیازهایی که به دیگران داده‌اید و امتیازهایی که از دیگران دریافت کرده‌اید را همراه با وضعیت آن‌ها مشاهده کنید.\n\nلطفاً از گزینه‌های زیر، انتخاب کنید:",
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
            await query.edit_message_text("هیچ کاربر دیگری برای امتیازدهی وجود ندارد!", reply_markup=main_menu_keyboard())
            return
        keyboard = [[InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"voteuser^{u[0]}")] for i, u in enumerate(users)]
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
        await query.edit_message_text("به کدام کاربر می‌خواهید امتیاز بدهید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("voteuser^"):
        await query.answer()
        touser_id = int(data.split("^")[1])
        profile = get_user_profile(user.id)
        if not profile or profile[3] < 1:
            await query.edit_message_text("اعتبار کافی برای امتیازدهی ندارید!", reply_markup=main_menu_keyboard())
            return
        # انتخاب مقدار امتیاز
        max_score = min(profile[3], 5)
        keyboard = [[InlineKeyboardButton(str(i), callback_data=f"givepoint^{touser_id}^{i}") for i in range(1, max_score+1)]]
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
        await query.edit_message_text(f"چه مقدار امتیاز می‌خواهید بدهید؟ (حداکثر {max_score})", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("givepoint^"):
        await query.answer()
        parts = data.split("^")
        touser_id = int(parts[1])
        amount = int(parts[2])
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        touser_name = c.fetchone()[0] if c.fetchone() else "کاربر"
        
        # درخواست دلیل امتیازدهی
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]]
        
        # ذخیره اطلاعات در context.user_data
        context.user_data['pending_transaction'] = {
            'touser_id': touser_id,
            'amount': amount
        }
        
        await query.edit_message_text(
            f"شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"  
            f"دلیل:\n-----------------\n\n"  
            f"لطفاً دلیل امتیازدهی را بنویسید و ارسال کنید یا روی دکمه بازگشت کلیک کنید.",
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
            await query.edit_message_text("اعتبار کافی ندارید!", reply_markup=main_menu_keyboard())
            return
        
        # ثبت تراکنش و کم کردن اعتبار
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user.id))
        c.execute("INSERT INTO transactions (user_id, touser, amount, season_id, reason) VALUES (?, ?, ?, ?, ?)", 
                 (user.id, touser_id, amount, config.SEASON_ID, reason))
        conn.commit()
        
        # دریافت اطلاعات کاربر مقصد
        c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
        touser_result = c.fetchone()
        touser_name = touser_result[0] if touser_result else "کاربر"
        
        await query.edit_message_text(
            f"✅ {amount} امتیاز به {touser_name} داده شد!\n\n"  
            f"دلیل: {reason}",
            reply_markup=main_menu_keyboard()
        )
    elif data == "givenpoints^":
        await query.answer()
        given = get_user_transactions(user.id, given=True)
        msg = "📊 امتیازهایی که دادید:\n\n"
        if given:
            for i, transaction in enumerate(given):
                msg += f"{i+1}- به {transaction[2]}: {transaction[0]} امتیاز\n   دلیل: {transaction[3] or '-'}\n   تاریخ: {transaction[4]}\n\n"
        else:
            msg += "- هنوز امتیازی به کسی نداده‌اید.\n\n"
        
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "receivedpoints^":
        await query.answer()
        received = get_user_transactions(user.id, given=False)
        msg = "📊 امتیازهایی که گرفتید:\n\n"
        if received:
            for i, transaction in enumerate(received):
                msg += f"{i+1}- از {transaction[2]}: {transaction[0]} امتیاز\n   دلیل: {transaction[3] or '-'}\n   تاریخ: {transaction[4]}\n\n"
        else:
            msg += "- هنوز امتیازی دریافت نکرده‌اید.\n\n"
        
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "Scoreboard^":
        await query.answer()
        board = get_scoreboard()
        msg = "🏆 رتبه‌بندی کاربران:\n\n"
        for i, row in enumerate(board):
            msg += f"{i+1}- {row[2]}: {row[1]} امتیاز\n"
        
        keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.answer("در حال توسعه ...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    
    # اگر کاربر در حالت انتظار برای دلیل امتیازدهی است
    if context.user_data.get('waiting_for_reason'):
        pending = context.user_data.get('pending_transaction')
        if pending:
            touser_id = pending['touser_id']
            amount = pending['amount']
            reason = message
            
            # دریافت اطلاعات کاربر مقصد
            c.execute("SELECT name FROM users WHERE user_id=?", (touser_id,))
            touser_result = c.fetchone()
            touser_name = touser_result[0] if touser_result else "کاربر"
            
            # ایجاد دکمه‌های تأیید یا لغو
            keyboard = [
                [InlineKeyboardButton("✅ تأیید و ارسال", callback_data=f"Confirm^{touser_id}^{amount}^{reason}")],
                [InlineKeyboardButton("❌ لغو", callback_data="tovote^")]
            ]
            
            await update.message.reply_text(
                f"خلاصه تراکنش:\n\n"  
                f"گیرنده: {touser_name}\n"  
                f"مقدار: {amount} امتیاز\n"  
                f"دلیل: {reason}\n\n"  
                f"آیا از ارسال این امتیاز اطمینان دارید؟",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # پاک کردن وضعیت انتظار
            context.user_data['waiting_for_reason'] = False
            return
    
    # اگر پیام با دستور شروع نشده باشد، منوی اصلی را نمایش می‌دهیم
    is_member = await check_channel_membership(user.id)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)]]
        await update.message.reply_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard()
    )

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