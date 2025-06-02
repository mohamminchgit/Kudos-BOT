"""
Handler های مربوط به تشکرنامه و نامه‌نگاری
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.user_functions import get_all_users
from ..database.db_utils import get_db_connection
from ..utils.ui_helpers_new import main_menu_keyboard
from ..services import giftcard
from ..database.models import db_manager

logger = logging.getLogger(__name__)

async def handle_gift_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش callback های مربوط به تشکرنامه و نامه‌نگاری"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data == "letter_start^":
        await _handle_letter_start(query, user.id)
    elif data.startswith("giftcard_selectuser^"):
        await _handle_select_user(query, user.id, data, context)
    else:
        await query.answer("این قابلیت در حال توسعه است.")

async def _handle_letter_start(query, user_id):
    """نمایش صفحه شروع ارسال تشکرنامه"""
    await query.answer()
    
    # دریافت لیست کاربران برای ارسال تشکرنامه (همه کاربران به جز خودش)
    users = get_all_users()
    if not users:
        await query.edit_message_text(
            "هیچ کاربری برای ارسال تشکر‌نامه وجود ندارد!", 
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # فیلتر کردن کاربر فعلی از لیست
    users = [u for u in users if u[0] != user_id]
    
    if not users:
        await query.edit_message_text(
            "هیچ کاربر دیگری برای ارسال تشکر‌نامه وجود ندارد!", 
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # بررسی تنظیمات نمایش کاربران
    show_all_users_result = db_manager.execute_query(
        "SELECT value FROM settings WHERE key='show_all_users'", 
        fetchone=True
    )
    show_all_users = show_all_users_result[0] if show_all_users_result else "0"
    
    # تنظیم وضعیت برای تشخیص حالت ارسال تشکرنامه در انتخاب کاربر با جستجو
    # دسترسی به context کاربر
    application = query.bot.application
    context = application.context_types.context.from_job_queue(application.job_queue)
    context.user_data = application.user_data.setdefault(user_id, {})
    
    # پاک کردن سایر وضعیت‌ها که ممکن است مزاحمت ایجاد کند
    context.user_data.pop('top_vote_mode', None)
    context.user_data.pop('waiting_for_reason', None)
    context.user_data.pop('waiting_for_gift_card_message', None)
    context.user_data.pop('voting_target_user_id', None)
    context.user_data.pop('voting_amount', None)
    
    # تنظیم حالت ارسال تشکرنامه
    context.user_data['gift_card_mode'] = True
    
    # اضافه کردن توضیحات برای بخش تشکر‌نامه
    welcome_message = "🎁 ارسال تشکر‌نامه 💌\n\n"
    welcome_message += "با استفاده از این بخش می‌توانید یک تشکر‌نامه زیبا با پیام دلخواه خود برای دوستانتان ارسال کنید.\n\n"
    welcome_message += "✅ این سرویس کاملاً رایگان است و نیازی به اعتبار ندارد.\n"
    welcome_message += "✅ تشکرنامه‌های شما شما به صورت خصوصی ارسال می‌شود و در کانال عمومی منتشر نمی‌شود.\n\n"
    welcome_message += "✨ روش استفاده:\n"
    welcome_message += "۱. ابتدا کاربر مورد نظر خود را از لیست زیر انتخاب کنید\n"
    welcome_message += "۲. متن پیام خود را تایپ کنید\n"
    welcome_message += "۳. تشکر‌نامه شما به صورت خودکار طراحی و ارسال می‌شود\n\n"
    
    keyboard = []
    
    # اضافه کردن دکمه جستجو با حالت اینلاین
    keyboard.append([
        InlineKeyboardButton("🔍 جستجوی کاربر", switch_inline_query_current_chat="")
    ])
    
    # اگر نمایش همه کاربران فعال باشد، لیست کاربران را نیز نشان می‌دهیم
    if show_all_users == "1":
        welcome_message += "👥 لطفاً کاربر مورد نظر را انتخاب کنید:"
        # اضافه کردن دکمه‌های کاربران
        row = []
        for i, u in enumerate(users):
            row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"giftcard_selectuser^{u[0]}"))
            if len(row) == 2 or i == len(users) - 1:
                if len(row) == 1 and i == len(users) - 1:
                    keyboard.append(row)
                elif len(row) == 2:
                    keyboard.append(row)
                row = []
    else:
        welcome_message += "👥 برای پیدا کردن کاربر مورد نظر از دکمه 🔍 جستجو استفاده کنید."
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
    
    await query.edit_message_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def _handle_select_user(query, user_id, data, context):
    """پردازش انتخاب کاربر برای ارسال تشکرنامه"""
    await query.answer()
    receiver_id = int(data.split("^")[1])
    
    # دریافت نام گیرنده از دیتابیس
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE user_id=?", (receiver_id,))
    result = cursor.fetchone()
    receiver_name = result[0] if result else "کاربر"
    conn.close()
    
    # پاک کردن سایر وضعیت‌ها که ممکن است مزاحمت ایجاد کند
    context.user_data.pop('top_vote_mode', None)
    context.user_data.pop('waiting_for_reason', None)
    context.user_data.pop('voting_target_user_id', None)
    context.user_data.pop('voting_amount', None)
    
    # ذخیره اطلاعات در context
    context.user_data['gift_card_mode'] = True
    context.user_data['gift_card_receiver_id'] = receiver_id
    context.user_data['gift_card_receiver_name'] = receiver_name
    context.user_data['waiting_for_gift_card_message'] = True
    
    await query.edit_message_text(
        f"شما در حال ارسال تشکر‌نامه به {receiver_name} هستید.\n\n"
        "لطفاً متن پیام تشکر‌نامه را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="letter_start^")]])
    )

async def handle_gift_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام تشکرنامه از کاربر"""
    if not context.user_data.get('waiting_for_gift_card_message'):
        return False  # این پیام برای تشکرنامه نیست
    
    user = update.message.from_user
    message_text = update.message.text
    
    receiver_id = context.user_data.get('gift_card_receiver_id')
    receiver_name = context.user_data.get('gift_card_receiver_name', 'کاربر')
    sender_id = user.id
    
    # دریافت نام فرستنده از دیتابیس
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE user_id=?", (sender_id,))
    sender_result = cursor.fetchone()
    sender_name = sender_result[0] if sender_result else "یک دوست"
    conn.close()

    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_gift_card_message', None)
    context.user_data.pop('gift_card_receiver_id', None)
    context.user_data.pop('gift_card_receiver_name', None)

    if not receiver_id:
        await update.message.reply_text("خطا در پردازش تشکر‌نامه. لطفاً دوباره تلاش کنید.")
        return True

    gift_message = message_text.strip()
    if not gift_message:
        await update.message.reply_text(
            "متن تشکر‌نامه نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 تشکر‌نامه", callback_data="letter_start^")]])
        )
        return True

    # شروع ارسال پیام به کاربران
    status_message = await update.message.reply_text(
        "⏳ در حال ایجاد و ارسال تشکر‌نامه...\n"
        "لطفاً صبر کنید..."
    )
    
    try:
        # ایجاد تصویر تشکر‌نامه
        image_path = giftcard.create_gift_card_image(sender_name, receiver_name, gift_message)
        
        if not image_path:
            logger.error("خطا در ایجاد تصویر تشکر‌نامه")
            await status_message.edit_text(
                "⚠️ متأسفانه در ایجاد تشکر‌نامه خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 تلاش مجدد", callback_data="letter_start^")]])
            )
            return True
            
        # ارسال تشکر‌نامه به گیرنده
        await context.bot.send_photo(
            chat_id=receiver_id,
            photo=open(image_path, 'rb'),
            caption=f"🎁 شما یک تشکر‌نامه از طرف {sender_name} دریافت کرده‌اید!"
        )
        
        # ارسال کپی به فرستنده
        await context.bot.send_photo(
            chat_id=sender_id,
            photo=open(image_path, 'rb'),
            caption=f"✅ تشکر‌نامه شما با موفقیت به {receiver_name} ارسال شد!"
        )
        
        await status_message.edit_text(
            f"✅ تشکر‌نامه با موفقیت به {receiver_name} ارسال شد!\n\n"
            "از این قابلیت می‌توانید هر زمان که بخواهید استفاده کنید.",
            reply_markup=main_menu_keyboard(sender_id)
        )
        
        # حذف فایل موقت
        try:
            os.remove(image_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"خطا در ارسال تشکر‌نامه: {e}")
        await status_message.edit_text(
            "⚠️ متأسفانه در ارسال تشکر‌نامه خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 تلاش مجدد", callback_data="letter_start^")]])
        )
    
    return True
