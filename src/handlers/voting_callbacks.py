"""
Handler های مربوط به سیستم رای‌گیری و امتیازدهی
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.models import db_manager
from ..database.user_functions import get_user_profile, get_all_users
from ..database.season_functions import get_active_season
from ..utils.ui_helpers_new import main_menu_keyboard

logger = logging.getLogger(__name__)

async def handle_voting_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش callback های مربوط به سیستم رای‌گیری و امتیازدهی"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data == "tovote^":
        await _handle_voting_menu(query, user.id, context)
    elif data.startswith("voteuser^") or data.startswith("vu^"):
        await _handle_select_user(query, user.id, data)
    elif data.startswith("givepoint^") or data.startswith("gp^"):
        await _handle_give_points(query, user.id, data, context)
    elif data.startswith("Confirm^"):
        await _handle_confirm_transaction(query, user.id, data, context)
    elif data.startswith("custom_points^"):
        await _handle_custom_points(query, user.id, data, context)

async def _handle_voting_menu(query, user_id, context):
    """نمایش منوی امتیازدهی"""
    await query.answer()
    
    # اضافه کردن گزارش برای اشکال‌زدایی
    logger.debug(f"درخواست منوی امتیازدهی از کاربر {user_id}")
    
    # بررسی آیا کاربر در سیستم تعریف شده است
    from ..database.models import db_manager
    
    # دریافت مستقیم اطلاعات کاربر با دستور SQL
    user_data = db_manager.execute_query(
        "SELECT user_id, name, balance FROM users WHERE user_id = ?", 
        (user_id,), 
        fetchone=True
    )
    
    # ثبت نتیجه برای اشکال‌زدایی
    logger.debug(f"نتیجه جستجوی کاربر {user_id}: {user_data}")
    
    if not user_data:
        logger.warning(f"کاربر {user_id} در سیستم یافت نشد")
        await query.edit_message_text(
            "⚠️ اطلاعات شما در سیستم یافت نشد. لطفاً با پشتیبانی تماس بگیرید.", 
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # استخراج موجودی کاربر
    balance = 0
    try:
        if len(user_data) > 2 and user_data[2] is not None:
            balance = int(user_data[2])
        logger.debug(f"موجودی کاربر {user_id}: {balance}")
    except (TypeError, ValueError) as e:
        logger.error(f"خطا در تبدیل موجودی کاربر {user_id}: {e}")
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
        season_name = config.SEASON_NAME
        logger.debug(f"فصل فعال یافت نشد، استفاده از مقادیر پیش‌فرض: {season_id}, {season_name}")
    else:
        season_id = active_season[0]
        season_name = active_season[1]
        logger.debug(f"فصل فعال: {season_id}, {season_name}")
    
    # بررسی تنظیمات نمایش کاربران
    show_all_users_result = db_manager.execute_query(
        "SELECT value FROM settings WHERE key='show_all_users'", 
        fetchone=True
    )
    show_all_users = show_all_users_result[0] if show_all_users_result else "0"
    logger.debug(f"تنظیم نمایش همه کاربران: {show_all_users}")
    
    # پاک کردن سایر حالت‌های فعال
    context.user_data.pop('top_vote_mode', None)
    context.user_data.pop('gift_card_mode', None)
    context.user_data.pop('waiting_for_gift_card_message', None)
    context.user_data.pop('waiting_for_reason', None)
    
    # ایجاد کیبورد با دکمه جستجو
    keyboard = [
        [InlineKeyboardButton("🔍 جستجوی کاربر", switch_inline_query_current_chat="")]
    ]
    
    # اگر نمایش همه کاربران فعال باشد، لیست کاربران را نیز نشان می‌دهیم
    if show_all_users == "1":
        # دریافت کاربران (به جز خود کاربر)
        users = get_all_users(exclude_id=user_id)
        logger.debug(f"تعداد کاربران یافت شده (به جز خود کاربر): {len(users) if users else 0}")
        
        if users:
            # اضافه کردن دکمه‌های کاربران
            row = []
            for i, u in enumerate(users):
                row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"vu^{u[0]}^0"))
                if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
                    keyboard.append(row)
                    row = []
    
    # اضافه کردن دکمه بازگشت
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
    
    # متن پیام بر اساس حالت نمایش
    if show_all_users == "1":
        message_text = (
            f"#{season_name}\n\n"
            f"تو {balance} امتیاز داری که می‌تونی به دوستات بدی 🎁\n\n"
            f"از بین افراد زیر، به کی می‌خوای امتیاز بدی؟ 🤔\n\n"
            f"برای جستجوی سریع‌تر می‌توانی از دکمه 🔍 جستجو استفاده کنی."
        )
    else:
        message_text = (
            f"#{season_name}\n\n"
            f"تو {balance} امتیاز داری که می‌تونی به دوستات بدی 🎁\n\n"
            f"برای پیدا کردن کاربر مورد نظر از دکمه 🔍 جستجو استفاده کن.\n"
            f"کافیه قسمتی از اسم شخص مورد نظر رو تایپ کنی و انتخابش کنی."
        )
    
    logger.debug(f"نمایش منوی امتیازدهی برای کاربر {user_id}")
    
    # ارسال پیام منوی امتیازدهی
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # ذخیره اطلاعات منوی امتیازدهی در context
    if hasattr(query, 'message') and query.message:
        context.user_data['voting_menu'] = {
            'chat_id': query.message.chat_id,
            'message_id': query.message.message_id,
            'season_name': season_name,
            'balance': balance
        }

async def _handle_select_user(query, user_id, data):
    """پردازش انتخاب کاربر برای امتیازدهی"""
    await query.answer()
    
    # بررسی آیا data شامل شناسه کاربر و شماره صفحه است
    parts = data.split("^")
    touser_id = int(parts[1])
    
    # پارامتر اختیاری شماره صفحه
    page = 0
    if len(parts) > 2 and parts[2].isdigit():
        page = int(parts[2])
    
    # دریافت اطلاعات کاربر مقصد
    target_user = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (touser_id,), 
        fetchone=True
    )
    touser_name = target_user[0] if target_user else "کاربر"
    
    # بستن سایر پنل‌های فعال
    if hasattr(query, 'message') and query.message:
        if query.message.chat.type == 'private':
            # پاک کردن پیام‌های قبلی اگر در چت خصوصی هستیم
            try:
                if 'previous_panel_message_id' in query.bot.application.user_data.get(user_id, {}):
                    prev_msg_id = query.bot.application.user_data[user_id]['previous_panel_message_id']
                    await query.bot.delete_message(chat_id=query.message.chat_id, message_id=prev_msg_id)
            except Exception as e:
                logger.error(f"خطا در پاک کردن پیام قبلی: {e}")
    
    # بررسی موجودی کاربر
    profile = get_user_profile(user_id)
    if not profile or profile[3] < 1:
        await query.edit_message_text(
            "اعتبار کافی برای امتیازدهی ندارید!", 
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # انتخاب مقدار امتیاز
    max_score = min(profile[3], 100)  # حداکثر امتیاز برابر با موجودی کاربر (حداکثر 100)
    
    # تعداد دکمه در هر صفحه و تعداد صفحات
    buttons_per_page = 25  # 5 ردیف با 5 دکمه در هر ردیف
    total_pages = (max_score + buttons_per_page - 1) // buttons_per_page
    
    # محاسبه شروع و پایان دکمه‌ها برای صفحه فعلی
    start_button = page * buttons_per_page + 1
    end_button = min(start_button + buttons_per_page - 1, max_score)
    
    # ایجاد دکمه‌های امتیازدهی
    keyboard = []
    
    # نمایش دکمه‌های امتیاز برای صفحه فعلی
    row = []
    for i in range(start_button, end_button + 1):
        # استفاده از فرمت کوتاه‌تر برای callback_data
        row.append(InlineKeyboardButton(str(i), callback_data=f"gp^{touser_id}^{i}"))
        if len(row) == 5:  # هر ردیف 5 دکمه داشته باشد
            keyboard.append(row)
            row = []
    if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
        keyboard.append(row)
    
    # اضافه کردن دکمه‌های ناوبری صفحات
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« قبلی", callback_data=f"vu^{touser_id}^{page-1}"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"vu^{touser_id}^{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # اضافه کردن دکمه بازگشت
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
    
    # ایجاد متن پیام بر اساس صفحه فعلی
    page_info = f" (صفحه {page+1} از {total_pages})" if total_pages > 1 else ""
    
    try:
        message = await query.edit_message_text(
            f"شما در حال امتیاز دادن به {touser_name} هستید!{page_info}\n\n"
            f"درحال حاضر شما {profile[3]} امتیاز دارید که میتوانید استفاده کنید.\n\n"
            f"لطفا مقدار امتیازی که میخواهید بدهید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # ذخیره شناسه پیام برای امکان پاک کردن بعدی
        if hasattr(query, 'message') and query.message:
            query.bot.application.user_data.setdefault(user_id, {})['previous_panel_message_id'] = message.message_id
            
    except Exception as e:
        logger.error(f"خطا در نمایش دکمه‌های امتیاز: {e}")
        await query.edit_message_text(
            "متأسفانه در نمایش دکمه‌های امتیاز خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=main_menu_keyboard(user_id)
        )

async def _handle_give_points(query, user_id, data, context):
    """پردازش انتخاب مقدار امتیاز و درخواست دلیل"""
    await query.answer()
    parts = data.split("^")
    
    # پاک کردن سایر حالت‌های فعال
    context.user_data.pop('top_vote_mode', None)
    context.user_data.pop('gift_card_mode', None)
    context.user_data.pop('waiting_for_gift_card_message', None)
    
    # تشخیص فرمت کوتاه یا کامل
    prefix = parts[0]
    if prefix == "gp":  # فرمت کوتاه
        touser_id = int(parts[1])
        amount = int(parts[2])
    else:  # فرمت کامل givepoint^
        touser_id = int(parts[1])
        amount = int(parts[2])
    
    # دریافت اطلاعات کاربر مقصد
    target_user = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (touser_id,), 
        fetchone=True
    )
    touser_name = target_user[0] if target_user else "کاربر"
    
    # درخواست دلیل امتیازدهی
    keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]]
    
    # ذخیره اطلاعات در context.user_data
    context.user_data['voting_target_user_id'] = touser_id
    context.user_data['voting_amount'] = amount
    context.user_data['pending_transaction'] = {
        'touser_id': touser_id,
        'amount': amount,
        'touser_name': touser_name
    }
    
    try:
        await query.edit_message_text(
            f"شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"  
            f"دلیل:\n-----------------\n\n"  
            f"لطفاً دلیل امتیازدهی را بنویسید و ارسال کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # تغییر وضعیت کاربر به حالت انتظار برای دریافت دلیل
        context.user_data['waiting_for_reason'] = True
        
        # نمایش هشدار به کاربر برای ادامه فرآیند
        await query.answer("لطفاً دلیل امتیازدهی را بنویسید", show_alert=True)
    except Exception as e:
        logger.error(f"خطا در درخواست دلیل امتیازدهی: {e}")
        await query.edit_message_text(
            "متأسفانه در پردازش درخواست خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=main_menu_keyboard(user_id)
        )

async def _handle_confirm_transaction(query, user_id, data, context):
    """پردازش تایید نهایی تراکنش"""
    await query.answer()
    parts = data.split("^")
    touser_id = int(parts[1])
    amount = int(parts[2])
    reason = parts[3] if len(parts) > 3 else "-"
    
    # بررسی موجودی کاربر
    profile = get_user_profile(user_id)
    if not profile or profile[3] < amount:
        await query.edit_message_text(
            "اعتبار کافی ندارید!",
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
    else:
        season_id = active_season[0]
    
    # دریافت نام کاربر فرستنده و مقصد
    sender_info = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (user_id,), 
        fetchone=True
    )
    sender_name = sender_info[0] if sender_info else "کاربر"
    
    target_info = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (touser_id,), 
        fetchone=True
    )
    touser_name = target_info[0] if target_info else "کاربر"
    
    try:
        # ایجاد یک connection جدید و شروع تراکنش 
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        try:
            # کم کردن اعتبار از فرستنده
            c.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?", 
                (amount, user_id)
            )
            
            # ثبت تراکنش
            c.execute(
                "INSERT INTO transactions (user_id, touser, amount, season_id, reason) VALUES (?, ?, ?, ?, ?)", 
                (user_id, touser_id, amount, season_id, reason)
            )
            
            # افزایش مجموع امتیازات دریافتی کاربر مقصد
            c.execute(
                "UPDATE users SET total_received = total_received + ? WHERE user_id = ?", 
                (amount, touser_id)
            )
            
            # کامیت کردن تراکنش
            conn.commit()
            logger.info(f"تراکنش {amount} امتیاز از {user_id} به {touser_id} با موفقیت انجام شد")
            
        except Exception as db_error:
            # در صورت بروز خطا، rollback انجام می‌دهیم
            conn.rollback()
            logger.error(f"خطا در تراکنش دیتابیس: {db_error}")
            raise db_error
        finally:
            # بستن اتصال دیتابیس
            conn.close()
        
        # ارسال پیام اطلاع‌رسانی به کاربر گیرنده
        try:
            await context.bot.send_message(
                chat_id=touser_id,
                text=f"🎉 شما {amount} امتیاز از {sender_name} دریافت کردید!\n\n"
                     f"دلیل: {reason}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("مشاهده پروفایل", callback_data="userprofile^")]
                ])
            )
        except Exception as e:
            logger.error(f"Error sending notification to user {touser_id}: {e}")
        
        # ارسال پیام به کانال (اگر تنظیم شده باشد)
        try:
            if hasattr(config, 'CHANNEL_ID') and config.CHANNEL_ID:
                await context.bot.send_message(
                    chat_id=config.CHANNEL_ID,
                    text=f"🎯 {sender_name} به {touser_name} {amount} امتیاز داد!\n\n"
                         f"💬 دلیل: {reason}",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Error sending message to channel: {e}")
        
        # اطلاع به کاربر فرستنده
        await query.edit_message_text(
            f"✅ {amount} امتیاز به {touser_name} داده شد!\n\n"  
            f"دلیل: {reason}",
            reply_markup=main_menu_keyboard(user_id)
        )
        
        # پاک کردن اطلاعات تراکنش از context
        context.user_data.pop('pending_transaction', None)
        context.user_data.pop('waiting_for_reason', None)
        
    except Exception as e:
        logger.error(f"Error in transaction: {e}")
        await query.edit_message_text(
            "خطا در انجام تراکنش! لطفاً دوباره تلاش کنید.",
            reply_markup=main_menu_keyboard(user_id)
        )

async def _handle_custom_points(query, user_id, data, context):
    """پردازش وارد کردن مقدار دلخواه امتیاز"""
    await query.answer()
    touser_id = int(data.split("^")[1])
    
    # دریافت اطلاعات کاربر مقصد
    target_user = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (touser_id,), 
        fetchone=True
    )
    touser_name = target_user[0] if target_user else "کاربر"
    
    # بررسی موجودی کاربر
    profile = get_user_profile(user_id)
    if not profile or profile[3] < 1:
        await query.edit_message_text(
            "اعتبار کافی برای امتیازدهی ندارید!", 
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    max_score = profile[3]
    
    # ذخیره اطلاعات در کانتکست
    context.user_data['custom_points'] = {
        'touser_id': touser_id,
        'touser_name': touser_name,
        'max_score': max_score
    }
    context.user_data['waiting_for_custom_points'] = True
    
    await query.edit_message_text(
        f"شما در حال امتیاز دادن به {touser_name} هستید!\n\n"
        f"درحال حاضر شما {max_score} امتیاز دارید.\n\n"
        f"لطفاً مقدار امتیاز دلخواه خود را به صورت عدد وارد کنید (بین 1 تا {max_score}):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data=f"voteuser^{touser_id}")]])
    )
