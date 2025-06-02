"""
Handler اصلی کامند start
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config و سایر ماژول‌ها
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.user_functions import get_or_create_user, is_user_approved
from ..utils.ui_helpers_new import main_menu_keyboard
from .admin_handlers import check_channel_membership

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کامند /start"""
    user = update.effective_user
    
    # بررسی عضویت در کانال
    is_member = await check_channel_membership(user.id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=config.CHANNEL_LINK)],
                   [InlineKeyboardButton("✅ عضو شدم", callback_data="joinedch^")]]
        await update.message.reply_text(
            f"کاربر گرامی، برای استفاده از {config.BOT_NAME} ابتدا باید عضو کانال رسمی ما شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی آیا کاربر تایید شده است
    if not is_user_approved(user.id):
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
