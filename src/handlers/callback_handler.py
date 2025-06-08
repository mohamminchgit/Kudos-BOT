"""
Handler اصلی برای پردازش callback query ها
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.user_functions import get_or_create_user
from ..database.season_functions import get_active_season
from ..database.models import db_manager
from ..utils.ui_helpers_new import main_menu_keyboard
from ..services import help
from .admin_handlers import check_channel_membership, is_admin, handle_admin_callbacks
from .user_callbacks import handle_user_callbacks
from .voting_callbacks import handle_voting_callbacks
from .gift_callbacks import handle_gift_callbacks
from .ai_callbacks import handle_ai_callbacks
from .letter_callbacks import handle_letter_callbacks

logger = logging.getLogger(__name__)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش اصلی callback query ها"""
    query = update.callback_query
    user = query.from_user
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
      # بررسی دسترسی کاربر - آیا کاربر در دیتابیس تایید شده است
    from ..database.user_functions import is_user_approved
    from ..handlers.admin_handlers import is_admin
    
    # ادمین‌ها نیاز به بررسی تایید ندارند
    if not is_admin(user.id) and not is_user_approved(user.id) and not data.startswith("joinedch^"):
        keyboard = [[InlineKeyboardButton(f"👤 پشتیبانی", url=f"https://t.me/{config.SUPPORT_USERNAME.strip('@')}")]]
        await query.edit_message_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با پشتیبان تماس بگیرید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # بررسی وجود فصل فعال برای اکثر دکمه‌ها
    if await _needs_active_season(data, user.id):
        active_season = get_active_season()
        if not active_season:
            await query.answer("هیچ فصل فعالی وجود ندارد!", show_alert=True)
            await query.edit_message_text(
                "⚠️ <b>هیچ فصل فعالی وجود ندارد!</b>\n\n"
                "در حال حاضر هیچ فصل فعالی در سیستم تعریف نشده است. لطفاً منتظر باشید تا ادمین‌های سیستم "
                "یک فصل جدید را فعال کنند. سپس می‌توانید از امکانات ربات استفاده نمایید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به منو", callback_data="userpanel^")]]),
                parse_mode="HTML"            )
            return
          # روتینگ callback ها به handler های مختلف
    if data.startswith(("help^", "help_")):
        await _handle_help_callbacks(query, data)
    elif data == "userpanel^":
        await _handle_main_menu(query, user.id)
    elif data.startswith(("userprofile^", "historypoints^", "receivedpoints^", "givenpoints^", "season_archive", "season_details^", "Scoreboard^")):
        await handle_user_callbacks(update, context)
    elif data.startswith(("admin_", "manage_", "approve_user^", "reject_user^", "broadcast_", "admin_panel^", "toggle_show_users^", "toggle_ai_features^")):
        await handle_admin_callbacks(update, context)
    elif data.startswith(("tovote^", "voteuser^", "givepoint^", "Confirm^", "vu^", "gp^", "improve_reason^", "custom_points^")):
        await handle_voting_callbacks(update, context)
    elif data.startswith(("letter_start^", "giftcard_")):
        await handle_gift_callbacks(update, context)
    elif data == "ai_chat^":
        # نمایش منوی دستیار هوشمند
        from .ai_callbacks import handle_ai_chat_menu
        await handle_ai_chat_menu(query, user.id)
    elif data.startswith(("ai_model^", "ai_profile^", "ai_perspective^", "ai_seasons_view^", "top_results^", "ai_analysis^", "top_vote^", "top_select^")):
        await handle_ai_callbacks(update, context, data)
    elif data == "joinedch^":
        await _handle_channel_join(query, user)
    else:
        # سایر callback های پیچیده که نیاز به پردازش خاص دارند
        await _handle_other_callbacks(update, context)

async def _needs_active_season(data: str, user_id: int) -> bool:
    """بررسی آیا callback نیاز به فصل فعال دارد"""
    # لیست دکمه‌هایی که نیاز به فصل فعال ندارند
    excluded_buttons = [
        "help^", "userpanel^", "userprofile^", "historypoints^", "joinedch^", 
        "admin_panel^", "approve_user^", "reject_user^", "season_archive^",
        "manage_seasons^", "add_season^", "toggle_season^", "edit_season^", "delete_season^",
        "edit_season_name^", "edit_season_balance^", "edit_season_desc^",
        "skip_season_description^", "manage_top_questions^", "add_top_question^",
        "edit_top_question^", "delete_top_question^", "letter_start^", "ai_chat^",
        "ai_profile^", "ai_seasons_view^", "ai_model^"
    ]
    
    # استثنا برای دکمه‌هایی که با پیشوند خاصی شروع می‌شوند
    excluded_prefixes = [
        "Scoreboard^", "receivedpoints^", "givenpoints^", "admin_", "manage_", 
        "edit_season", "delete_season", "toggle_season", "edit_question", "toggle_question",
        "giftcard_", "help_", "ai_profile", "ai_perspective", "ai_model", "season_details^", 
        "top_results^", "ai_analysis^", "top_vote^", "top_select^", "vu^", "gp^"
    ]
    
    # بررسی دکمه‌های استثنا
    if data in excluded_buttons:
        return False
    
    for prefix in excluded_prefixes:
        if data.startswith(prefix):
            return False
    
    # اگر کاربر ادمین است، نیازی به فصل فعال ندارد
    if is_admin(user_id):
        return False
    
    return True

async def _handle_help_callbacks(query, data):
    """پردازش callback های مربوط به راهنما"""
    await query.answer()
    
    if data == "help^":
        help_data = help.get_help_text("main")
        await query.edit_message_text(
            help_data["text"],
            reply_markup=InlineKeyboardMarkup(help_data["buttons"]),
            parse_mode="HTML"
        )
    elif data.startswith("help_"):
        help_data = help.handle_help_callback(data)
        await query.edit_message_text(
            f"<b>{help_data['title']}</b>\n\n{help_data['text']}",
            reply_markup=InlineKeyboardMarkup(help_data["buttons"]),
            parse_mode="HTML"
        )

async def _handle_main_menu(query, user_id):
    """پردازش بازگشت به منوی اصلی"""
    await query.answer()
    await query.edit_message_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard(user_id)
    )

async def _handle_channel_join(query, user):
    """پردازش تایید عضویت در کانال"""
    await query.answer()
    await query.edit_message_text(
        f"کاربر گرامی\nلطفا یکی از گزینه‌های زیر رو برای {config.BOT_NAME} انتخاب کنید :",
        reply_markup=main_menu_keyboard(user.id)
    )

async def _handle_other_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش سایر callback ها که در دسته‌بندی‌های اصلی قرار نمی‌گیرند"""
    query = update.callback_query
    data = query.data
    
    # این‌جا می‌توان callback های پیچیده‌تر را پردازش کرد
    # اما برای letter_start^ قبلاً پردازش شده است
    
    logger.warning(f"کالبک ناشناخته: {data}")
    await query.answer("این دکمه در حال حاضر فعال نیست. لطفاً دکمه دیگری را امتحان کنید.", show_alert=True)
