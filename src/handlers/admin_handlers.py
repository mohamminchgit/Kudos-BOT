"""
Handler های مربوط به عملیات ادمین
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.models import db_manager
from ..database.user_functions import get_or_create_user

logger = logging.getLogger(__name__)

async def check_channel_membership(user_id, context):
    """بررسی عضویت کاربر در کانال"""
    try:
        logger.info(f"Checking membership for user {user_id} in channel {config.CHANNEL_ID}")
        
        # بررسی عضویت در کانال
        member = await context.bot.get_chat_member(config.CHANNEL_ID, user_id)
        is_member = member.status in ['member', 'administrator', 'creator']
        
        logger.info(f"User {user_id} membership status: {member.status}")
        return is_member
        
    except TelegramError as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

def is_admin(user_id):
    """بررسی آیا کاربر ادمین است"""
    result = db_manager.execute_query(
        "SELECT role, permissions FROM admins WHERE user_id=?", 
        (user_id,), 
        fetchone=True
    )
    return result is not None

def get_admin_permissions(user_id):
    """دریافت دسترسی‌های ادمین"""
    result = db_manager.execute_query(
        "SELECT role, permissions FROM admins WHERE user_id=?", 
        (user_id,), 
        fetchone=True
    )
    
    if not result:
        return [], ""
    
    role, permissions = result
    
    if role == 'god':
        from ..database.models import ADMIN_PERMISSIONS
        return [p[0] for p in ADMIN_PERMISSIONS], role
    elif permissions:
        return [p.strip() for p in permissions.split(",") if p.strip()], role
    else:
        return [], role

async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, approved: bool):
    """پردازش تایید یا رد کاربر"""
    query = update.callback_query
    
    if approved:
        # ذخیره اطلاعات کاربر برای دریافت نام واقعی
        try:
            user_info = await context.bot.get_chat(user_id)
            context.user_data['pending_approval'] = {
                'user_id': user_id,
                'username': user_info.username,
                'telegram_name': user_info.full_name
            }
            context.user_data['waiting_for_name'] = True
            
            await query.edit_message_text(
                f"👤 <b>تایید کاربر</b>\n\n"
                f"شناسه: {user_id}\n"
                f"نام تلگرام: {user_info.full_name}\n"
                f"یوزرنیم: @{user_info.username or 'ندارد'}\n\n"
                f"لطفاً نام واقعی این کاربر را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("» لغو", callback_data="cancel_approval^")]
                ]),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await query.edit_message_text(f"خطا در دریافت اطلاعات کاربر: {e}")
    else:
        # رد کاربر
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"متأسفانه درخواست دسترسی شما به {config.BOT_NAME} رد شد.\n\n"
                     f"برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("پشتیبانی", url=config.SUPPORT_USERNAME)]])
            )
            
            await query.edit_message_text(
                f"❌ درخواست کاربر رد شد و به ایشان اطلاع داده شد."
            )
            
        except Exception as e:
            logger.error(f"Error rejecting user: {e}")
            await query.edit_message_text(f"خطا در رد درخواست کاربر: {e}")

async def handle_broadcast_message(context: ContextTypes.DEFAULT_TYPE, message_text: str, sender_id: int):
    """ارسال پیام همگانی به تمام کاربران"""
    users = db_manager.execute_query("SELECT user_id FROM users")
    success_count = 0
    fail_count = 0
    
    for user in users:
        user_id = user[0]
        if user_id == sender_id:  # عدم ارسال به خود فرستنده
            continue
            
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>پیام همگانی</b>\n\n{message_text}",
                parse_mode="HTML"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Error sending broadcast to user {user_id}: {e}")
            fail_count += 1
    
    return success_count, fail_count

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """هندل کردن callback های مربوط به ادمین
    
    Returns:
        bool: True اگر callback پردازش شد، False در غیر این صورت
    """
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # بررسی دسترسی ادمین
    if not is_admin(user_id):
        await query.answer("❌ شما دسترسی ادمین ندارید.", show_alert=True)
        return True
    
    try:
        if data == "admin_panel^":
            # نمایش پنل ادمین با استفاده از کیبورد تعریف شده در ui_helpers_new
            from ..utils.ui_helpers_new import create_admin_panel_keyboard
            admin_keyboard = create_admin_panel_keyboard(user_id)
            
            if not admin_keyboard:
                await query.answer("شما دسترسی ادمین ندارید.", show_alert=True)
                return True
                
            await query.edit_message_text(
                "👨‍💼 <b>پنل مدیریت</b>\n\n"
                "به پنل مدیریت خوش آمدید. لطفاً گزینه‌ی مورد نظر خود را انتخاب کنید:",
                parse_mode="HTML",
                reply_markup=admin_keyboard
            )
            return True
            
        elif data.startswith("approve_user^"):
            parts = data.split("^")
            if len(parts) >= 2:
                target_user_id = int(parts[1])
                await handle_user_approval(update, context, target_user_id, True)
            return True
            
        elif data.startswith("reject_user^"):
            parts = data.split("^")
            if len(parts) >= 2:
                target_user_id = int(parts[1])
                await handle_user_approval(update, context, target_user_id, False)
            return True
            
        elif data == "broadcast^":
            # راهنمای ارسال پیام همگانی
            await query.edit_message_text(
                "📢 <b>ارسال پیام همگانی</b>\n\n"
                "برای ارسال پیام همگانی، متن پیام خود را در پیام بعدی ارسال کنید.\n\n"
                "📝 نکته: پیام شما به تمام کاربران ثبت‌نام شده ارسال خواهد شد.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel^")]])
            )
            
            # تنظیم state برای دریافت پیام همگانی
            context.user_data['waiting_for_broadcast'] = True
            return True
            
        elif data == "toggle_show_users^":
            # تغییر وضعیت نمایش کاربران در جستجو
            await _handle_toggle_show_users(query, user_id)
            return True
            
        elif data == "admin_users^" or data == "admin_transactions^" or data == "admin_stats^" or data == "manage_admins^" or data == "broadcast_menu^" or data == "manage_top_questions^" or data == "manage_seasons^":
            # این کالبک‌ها هنوز در حال توسعه هستند
            await query.answer("این بخش در حال توسعه است و به زودی آماده خواهد شد.", show_alert=True)
            return True
    
    except Exception as e:
        logger.error(f"Error handling admin callback {data}: {e}")
        await query.answer("❌ خطا در پردازش درخواست ادمین.", show_alert=True)
    
    return False

async def _handle_toggle_show_users(query, user_id):
    """تغییر وضعیت نمایش کاربران در جستجو"""
    from ..database.models import db_manager
    
    # بررسی وضعیت فعلی
    result = db_manager.execute_query(
        "SELECT value FROM settings WHERE key='show_all_users'", 
        fetchone=True
    )
    
    current_value = result[0] if result else "0"
    new_value = "0" if current_value == "1" else "1"
    
    # آپدیت وضعیت در دیتابیس
    if result:
        db_manager.execute_query(
            "UPDATE settings SET value=? WHERE key='show_all_users'", 
            (new_value,), 
            commit=True
        )
    else:
        db_manager.execute_query(
            "INSERT INTO settings (key, value) VALUES ('show_all_users', ?)", 
            (new_value,), 
            commit=True
        )
    
    # نمایش پیام موفقیت
    status_text = "فعال" if new_value == "1" else "غیرفعال"
    await query.answer(f"نمایش لیست کاربران {status_text} شد.", show_alert=True)
    
    # به‌روزرسانی پنل ادمین
    from ..utils.ui_helpers_new import create_admin_panel_keyboard
    admin_keyboard = create_admin_panel_keyboard(user_id)
    
    await query.edit_message_text(
        "👨‍💼 <b>پنل مدیریت</b>\n\n"
        f"نمایش لیست کاربران با موفقیت {status_text} شد.\n"
        "به پنل مدیریت خوش آمدید. لطفاً گزینه‌ی مورد نظر خود را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=admin_keyboard
    )
