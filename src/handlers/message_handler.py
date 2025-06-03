"""
هندلر اصلی برای پردازش پیام‌های متنی و مدیریت وضعیت‌های مختلف کاربر
"""
import logging
import sys
import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..utils.ui_helpers_new import main_menu_keyboard

logger = logging.getLogger(__name__)

from ..database.db_utils import get_db_connection
from ..services.giftcard import create_gift_card_image
from ..services import ai

from .top_vote_handlers import _save_top_vote, _process_next_top_question

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش پیام‌های متنی ورودی"""
    message = update.message
    user = message.from_user
    text = message.text
    
    logger.debug(f"پیام جدید از {user.id}: {text[:20]}...")
    
    # بررسی پیام‌های خاص
    if not context.user_data:
        context.user_data = {}
    
    # بررسی پیام‌های مربوط به کالبک‌های اینلاین
    if text and text.startswith("voteuser^"):
        # پردازش انتخاب کاربر برای امتیازدهی
        logger.debug(f"تشخیص پیام انتخاب کاربر برای امتیازدهی: {text}")
        # استفاده از تابع موجود برای پردازش
        await handle_vote_user_selection(update, context, text)
        return
    
    if text and text.startswith("top_select^"):
        # پردازش انتخاب کاربر برای رای‌دهی ترین‌ها
        logger.debug(f"تشخیص پیام انتخاب کاربر برای رای‌دهی ترین‌ها: {text}")
        parts = text.split("^")
        if len(parts) == 3:
            question_id = int(parts[1])
            voted_for = int(parts[2])
            
            # تنظیم حالت رأی‌گیری ترین‌ها در داده‌های کاربر
            context.user_data['top_vote_mode'] = True
            context.user_data['current_question_id'] = question_id
            
            # نمایش پیام در حال پردازش
            processing_msg = await update.effective_chat.send_message(
                "در حال ثبت رأی شما...",
                reply_markup=None
            )
            
            # پاک کردن پیام اصلی
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"خطا در حذف پیام: {e}")
            
            # ذخیره رأی کاربر
            if await _save_top_vote(user.id, question_id, voted_for):
                # ادامه به سوال بعدی
                await _process_next_top_question(processing_msg, user.id, context)
            else:
                await processing_msg.edit_text(
                    "❌ خطا در ثبت رأی شما. ممکن است قبلاً به این سوال رأی داده باشید.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
                )
        return
        
    if text and text.startswith("giftcard_selectuser^"):
        # پردازش انتخاب کاربر برای ارسال تشکرنامه
        logger.debug(f"تشخیص پیام انتخاب کاربر برای ارسال تشکرنامه: {text}")
        # استخراج شناسه کاربر
        parts = text.split("^")
        if len(parts) == 2:
            user_id = int(parts[1])
            
            # به جای ایجاد CallbackQuery ساختگی، از روش دیگری استفاده می‌کنیم
            await update.effective_chat.send_message(
                "در حال پردازش...",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("منوی اصلی", callback_data="userpanel^")
                ]])
            )
            
            # استفاده از روش مستقیم برای پردازش انتخاب کاربر
            context.user_data['gift_card_mode'] = True
            context.user_data['gift_card_receiver_id'] = user_id
            
            # دریافت نام گیرنده از دیتابیس
            from ..database.models import db_manager
            target_user = db_manager.execute_query(
                "SELECT name FROM users WHERE user_id=?", 
                (user_id,), 
                fetchone=True
            )
            receiver_name = target_user[0] if target_user else "کاربر"
            context.user_data['gift_card_receiver_name'] = receiver_name
            context.user_data['waiting_for_gift_card_message'] = True
            
            # حذف پیام فعلی
            try:
                await update.message.delete()
            except Exception as e:
                logger.error(f"خطا در حذف پیام: {e}")
            
            # ارسال پیام جدید
            await update.effective_chat.send_message(
                f"شما در حال ارسال تشکر‌نامه به {receiver_name} هستید.\n\n"
                "لطفاً متن پیام تشکر‌نامه را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="letter_start^")]])
            )
        return
    
    if text and text.startswith("کاربر انتخاب شده:"):
        # پردازش پیام انتخاب کاربر از جستجوی اینلاین
        logger.debug(f"تشخیص پیام انتخاب کاربر از جستجوی اینلاین: {text}")
        await handle_inline_user_selection(update, context, text)
        return
    
    # بررسی وضعیت کاربر - اگر در انتظار دلیل امتیازدهی است
    if context.user_data.get('waiting_for_reason'):
        # پاک کردن سایر حالت‌های فعال
        context.user_data.pop('top_vote_mode', None)
        context.user_data.pop('gift_card_mode', None)
        context.user_data.pop('waiting_for_gift_card_message', None)
        
        logger.debug(f"کاربر {user.id} دلیل امتیازدهی را ارسال کرد")
        
        # دریافت اطلاعات تراکنش از کانتکست
        transaction_info = context.user_data.get('pending_transaction', {})
        touser_id = transaction_info.get('touser_id')
        amount = transaction_info.get('amount')
        touser_name = transaction_info.get('touser_name', 'کاربر')
        
        if not touser_id or not amount:
            await message.reply_text(
                "اطلاعات امتیازدهی ناقص است. لطفاً دوباره امتیازدهی را انجام دهید.",
                reply_markup=main_menu_keyboard(user.id)
            )
            # پاک کردن وضعیت انتظار
            context.user_data.pop('waiting_for_reason', None)
            context.user_data.pop('pending_transaction', None)
            return

        # حذف پیام کاربر برای تمیز کردن چت
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"خطا در حذف پیام کاربر: {e}")
        
        # دریافت دلیل امتیازدهی
        reason = text.strip()
        
        # ایجاد کیبورد تایید
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید", callback_data=f"Confirm^{touser_id}^{amount}^{reason}"),
                InlineKeyboardButton("❌ لغو", callback_data="tovote^")
            ]
        ]
        
        # ارسال پیام تایید - استفاده از ویرایش پیام قبلی به جای ارسال پیام جدید
        try:
            # اطلاعات پیام قبلی ذخیره شده
            voting_message = context.user_data.get('voting_message')
            
            if voting_message and 'chat_id' in voting_message and 'message_id' in voting_message:
                # ویرایش پیام قبلی
                await context.bot.edit_message_text(
                    chat_id=voting_message['chat_id'],
                    message_id=voting_message['message_id'],
                    text=f"✨ شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"
                         f"💬 دلیل: {reason}\n\n"
                         f"آیا تایید می‌کنید؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif 'voting_menu' in context.user_data and 'message_id' in context.user_data['voting_menu']:
                # ویرایش منوی امتیازدهی اگر وجود داشته باشد
                await context.bot.edit_message_text(
                    chat_id=context.user_data['voting_menu']['chat_id'],
                    message_id=context.user_data['voting_menu']['message_id'],
                    text=f"✨ شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"
                         f"💬 دلیل: {reason}\n\n"
                         f"آیا تایید می‌کنید؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # اگر هیچ پیام قبلی یافت نشد، پیام جدید ارسال می‌کنیم
                await message.reply_text(
                    f"✨ شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"
                    f"💬 دلیل: {reason}\n\n"
                    f"آیا تایید می‌کنید؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام تایید: {e}")
            await message.reply_text(
                "متأسفانه در پردازش درخواست خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(user.id)
            )
        
        # پاک کردن وضعیت انتظار
        context.user_data.pop('waiting_for_reason', None)
        context.user_data.pop('voting_message', None)  # پاک کردن اطلاعات پیام قبلی
        return

    # بررسی وضعیت کاربر - اگر در انتظار نام واقعی کاربر برای تایید است
    elif context.user_data.get('waiting_for_name'):
        logger.debug(f"ادمین {user.id} نام واقعی کاربر را ارسال کرد")
        
        # ارجاع به هندلر تایید کاربر توسط ادمین
        await handle_admin_user_approval(update, context, text)
        return

    # بررسی وضعیت کاربر - اگر در انتظار پیام همگانی است
    elif context.user_data.get('waiting_for_broadcast'):
        from ..handlers.admin_handlers import is_admin, handle_broadcast_message
        
        # بررسی دسترسی ادمین
        if not is_admin(user.id):
            await message.reply_text("شما دسترسی ادمین ندارید.")
            return
        
        logger.debug(f"ادمین {user.id} پیام همگانی را ارسال کرد")
        
        # پاک کردن وضعیت انتظار
        context.user_data.pop('waiting_for_broadcast', None)
        
        # حذف پیام ادمین
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"خطا در حذف پیام ادمین: {e}")
        
        # ارسال پیام "در حال ارسال..."
        status_msg = await update.effective_chat.send_message(
            "📤 در حال ارسال پیام همگانی...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel^")]])
        )
        
        # ارسال پیام همگانی
        success_count, fail_count = await handle_broadcast_message(context, text, user.id)
        
        # ویرایش پیام وضعیت
        await status_msg.edit_text(
            f"✅ <b>پیام همگانی ارسال شد</b>\n\n"
            f"موفق: {success_count} کاربر\n"
            f"ناموفق: {fail_count} کاربر\n\n"
            f"📝 متن پیام:\n{text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel^")]])
        )
        return

    # بررسی وضعیت کاربر - اگر در انتظار پیام AI است
    elif context.user_data.get('waiting_for_ai_prompt'):
        logger.debug(f"کاربر {user.id} پیام AI را ارسال کرد")
        
        # ارجاع به هندلر AI chat
        await handle_ai_chat_message(update, context, text)
        return

    # بررسی وضعیت کاربر - اگر در انتظار پیام تشکرنامه است
    elif context.user_data.get('waiting_for_gift_card_message'):
        # پاک کردن سایر حالت‌های فعال
        context.user_data.pop('top_vote_mode', None)
        context.user_data.pop('waiting_for_reason', None)
        
        logger.debug(f"کاربر {user.id} پیام تشکرنامه را ارسال کرد")
        
        # ارجاع به هندلر ارسال تشکرنامه
        from ..handlers.gift_callbacks import handle_gift_message
        handled = await handle_gift_message(update, context)
        return True

    # پردازش سایر پیام‌ها
    from ..database.user_functions import is_user_approved
    from ..handlers.admin_handlers import is_admin
    
    if not is_admin(user.id) and not is_user_approved(user.id):
        # کاربر تایید نشده است
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 پشتیبانی", url=f"https://t.me/{config.SUPPORT_USERNAME.strip('@')}")]
        ])
        await message.reply_text(
            f"کاربر گرامی، شما هنوز دسترسی به {config.BOT_NAME} ندارید.\n\n"
            f"برای اخذ دسترسی لطفاً با پشتیبان تماس بگیرید:",
            reply_markup=markup
        )
        return

    # نمایش منوی اصلی برای سایر پیام‌ها
    try:
        await message.reply_text(
            f"سلام {user.first_name}!\n"
            f"به {config.BOT_NAME} خوش آمدید!\n\n"
            f"لطفا از منوی زیر گزینه مورد نظر را انتخاب کنید:",
            reply_markup=main_menu_keyboard(user.id)
        )
    except Exception as e:
        logger.error(f"خطا در ارسال منوی اصلی: {e}")
        await message.reply_text(
            "متأسفانه در پردازش درخواست خطایی رخ داد. لطفاً دوباره تلاش کنید."
        )

async def handle_vote_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش انتخاب کاربر از طریق دکمه اینلاین با فرمت voteuser^user_id"""
    user = update.effective_user
    
    # استخراج شناسه کاربر از متن پیام
    parts = message_text.split("^")
    if len(parts) != 2:
        await update.message.reply_text("خطا در پردازش انتخاب کاربر")
        return
        
    try:
        touser_id = int(parts[1])
        
        # دریافت اطلاعات کاربر مقصد
        from ..database.models import db_manager
        target_user = db_manager.execute_query(
            "SELECT name FROM users WHERE user_id=?", 
            (touser_id,), 
            fetchone=True
        )
        
        if not target_user:
            await update.message.reply_text("کاربر مورد نظر یافت نشد. لطفاً دوباره تلاش کنید.")
            return
            
        touser_name = target_user[0]
        
        # پاک کردن پیام قبلی
        try:
            await update.message.delete()
        except Exception as e:
            logger.error(f"خطا در حذف پیام: {e}")
        
        # ذخیره اطلاعات کاربر انتخاب شده در context
        context.user_data['selected_user'] = {
            'user_id': touser_id,
            'name': touser_name
        }
        
        # بررسی اگر منوی امتیازدهی وجود دارد
        voting_menu = context.user_data.get('voting_menu')
        
        # بررسی موجودی کاربر
        from ..database.user_functions import get_user_profile
        profile = get_user_profile(user.id)
        if not profile or profile[3] < 1:
            if voting_menu:
                # ویرایش منوی موجود
                await context.bot.edit_message_text(
                    "اعتبار کافی برای امتیازدهی ندارید!",
                    chat_id=voting_menu['chat_id'],
                    message_id=voting_menu['message_id'],
                    reply_markup=main_menu_keyboard(user.id)
                )
            else:
                # ارسال پیام جدید
                await update.effective_chat.send_message(
                    "اعتبار کافی برای امتیازدهی ندارید!",
                    reply_markup=main_menu_keyboard(user.id)
                )
            return
        
        # انتخاب مقدار امتیاز
        max_score = min(profile[3], 100)  # حداکثر امتیاز برابر با موجودی کاربر (حداکثر 100)
        
        # تعداد دکمه در هر صفحه
        buttons_per_page = 25  # 5 ردیف با 5 دکمه در هر ردیف
        
        # ایجاد دکمه‌های امتیازدهی
        keyboard = []
        
        # نمایش دکمه‌های امتیاز برای صفحه اول
        row = []
        for i in range(1, min(max_score + 1, buttons_per_page + 1)):
            row.append(InlineKeyboardButton(str(i), callback_data=f"gp^{touser_id}^{i}"))
            if len(row) == 5:  # هر ردیف 5 دکمه داشته باشد
                keyboard.append(row)
                row = []
        if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
            keyboard.append(row)
        
        # اضافه کردن دکمه‌های ناوبری صفحات
        nav_buttons = []
        
        total_pages = (max_score + buttons_per_page - 1) // buttons_per_page
        if total_pages > 1:
            nav_buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"vu^{touser_id}^1"))
            keyboard.append(nav_buttons)
        
        # اضافه کردن دکمه بازگشت
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
        
        # ایجاد متن پیام
        page_info = f" (صفحه 1 از {total_pages})" if total_pages > 1 else ""
        
        # نمایش صفحه انتخاب امتیاز
        message_text = (
            f"شما در حال امتیاز دادن به {touser_name} هستید!{page_info}\n\n"
            f"درحال حاضر شما {profile[3]} امتیاز دارید که میتوانید استفاده کنید.\n\n"
            f"لطفا مقدار امتیازی که میخواهید بدهید را انتخاب کنید:"
        )
        
        # اگر منوی امتیازدهی قبلاً ذخیره شده، آن را ویرایش کنیم
        if voting_menu:
            try:
                await context.bot.edit_message_text(
                    message_text,
                    chat_id=voting_menu['chat_id'],
                    message_id=voting_menu['message_id'],
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            except Exception as e:
                logger.error(f"خطا در ویرایش منوی امتیازدهی: {e}")
                # در صورت خطا، پیام جدید ارسال می‌کنیم
        
        # ارسال پیام جدید
        await update.effective_chat.send_message(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"خطا در پردازش انتخاب کاربر: {e}")
        await update.effective_chat.send_message(
            "متأسفانه در پردازش انتخاب کاربر خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=main_menu_keyboard(user.id)
        )

async def handle_inline_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش انتخاب کاربر از طریق اینلاین"""
    user = update.effective_user
    
    # استخراج نام کاربر از متن پیام
    selected_name = message_text.replace("کاربر انتخاب شده:", "").strip()
    
    # یافتن کاربر بر اساس نام
    from ..database.models import db_manager
    selected_user = db_manager.execute_query(
        "SELECT user_id, name FROM users WHERE name = ?", 
        (selected_name,), 
        fetchone=True
    )
    
    if not selected_user:
        await update.message.reply_text(
            "❌ کاربر مورد نظر یافت نشد!",
            reply_markup=main_menu_keyboard(user.id)
        )
        return
    
    touser_id = selected_user[0]
    touser_name = selected_user[1]
    
    # پاک کردن پیام قبلی برای تمیزی گفتگو
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"خطا در حذف پیام: {e}")
    
    # بررسی حالت کاربر
    if context.user_data.get('top_vote_mode'):
        # در حالت رأی‌گیری ترین‌ها
        question_id = context.user_data.get('current_question_id')
        if not question_id:
            await update.effective_chat.send_message(
                "❌ خطا در پردازش انتخاب. لطفاً دوباره از منوی اصلی شروع کنید.",
                reply_markup=main_menu_keyboard(user.id)
            )
            return
        
        # پردازش رأی ترین‌ها
        
        # نمایش پیام موفقیت با آلرت
        msg = await update.effective_chat.send_message(
            f"✅ رأی شما به {touser_name} با موفقیت ثبت شد.",
            reply_markup=None
        )
        
        if await _save_top_vote(user.id, question_id, touser_id):
            # ادامه به سوال بعدی بعد از مکث کوتاه
            import asyncio
            await asyncio.sleep(1)
            await _process_next_top_question(msg, user.id, context)
        else:
            await msg.edit_text(
                "❌ خطا در ثبت رأی. ممکن است قبلاً به این سوال رأی داده باشید.",
                reply_markup=main_menu_keyboard(user.id)
            )
            
    elif context.user_data.get('gift_card_mode'):
        # در حالت ارسال تشکرنامه
        # ذخیره اطلاعات گیرنده
        context.user_data['gift_card_receiver_id'] = touser_id
        context.user_data['gift_card_receiver_name'] = touser_name
        context.user_data['waiting_for_gift_card_message'] = True
        
        # درخواست متن تشکرنامه
        await update.effective_chat.send_message(
            f"💌 <b>ارسال تشکر‌نامه به {touser_name}</b>\n\n"
            f"لطفاً متن تشکر‌نامه را بنویسید و ارسال کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="letter_start^")]]),
            parse_mode="HTML"
        )
    else:
        # در حالت امتیازدهی معمولی
        # بررسی موجودی کاربر
        from ..database.user_functions import get_user_profile
        profile = get_user_profile(user.id)
        if not profile or profile[3] < 1:
            await update.effective_chat.send_message(
                "❌ اعتبار کافی برای امتیازدهی ندارید!",
                reply_markup=main_menu_keyboard(user.id)
            )
            return
        
        # انتخاب مقدار امتیاز
        max_score = min(profile[3], 100)  # حداکثر امتیاز برابر با موجودی کاربر (حداکثر 100)
        
        # تعداد دکمه در هر صفحه
        buttons_per_page = 25  # 5 ردیف با 5 دکمه در هر ردیف
        
        # ایجاد دکمه‌های امتیازدهی
        keyboard = []
        
        # نمایش دکمه‌های امتیاز برای صفحه اول
        row = []
        for i in range(1, min(max_score + 1, buttons_per_page + 1)):
            row.append(InlineKeyboardButton(str(i), callback_data=f"gp^{touser_id}^{i}"))
            if len(row) == 5:  # هر ردیف 5 دکمه داشته باشد
                keyboard.append(row)
                row = []
        if row:  # اضافه کردن آخرین ردیف اگر کامل نشده باشد
            keyboard.append(row)
        
        # اضافه کردن دکمه‌های ناوبری صفحات
        nav_buttons = []
        
        total_pages = (max_score + buttons_per_page - 1) // buttons_per_page
        if total_pages > 1:
            nav_buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"vu^{touser_id}^1"))
            keyboard.append(nav_buttons)
        
        # اضافه کردن دکمه بازگشت
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="tovote^")])
        
        # ایجاد متن پیام
        page_info = f" (صفحه 1 از {total_pages})" if total_pages > 1 else ""
        
        # نمایش صفحه انتخاب امتیاز
        message_text = (
            f"شما در حال امتیاز دادن به {touser_name} هستید!{page_info}\n\n"
            f"درحال حاضر شما {profile[3]} امتیاز دارید که میتوانید استفاده کنید.\n\n"
            f"لطفا مقدار امتیازی که میخواهید بدهید را انتخاب کنید:"
        )
        
        # اگر این پیام از جستجوی اینلاین می‌آید، می‌توانیم پیام اصلی را ویرایش کنیم
        if hasattr(update, 'message') and update.message:
            # ذخیره اطلاعات پیام برای استفاده بعدی
            context.user_data['voting_message'] = {
                'chat_id': update.message.chat_id,
                'message_id': update.message.message_id
            }
            
            try:
                # ویرایش پیام فعلی به جای ارسال پیام جدید
                await update.message.edit_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            except Exception as e:
                logger.error(f"خطا در ویرایش پیام: {e}")
                # در صورت خطا، ادامه به ارسال پیام جدید
        
        # اگر امکان ویرایش نبود یا خطایی رخ داد، پیام جدید ارسال می‌کنیم
        new_message = await update.effective_chat.send_message(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # ذخیره اطلاعات پیام جدید برای استفاده بعدی
        context.user_data['voting_message'] = {
            'chat_id': new_message.chat_id,
            'message_id': new_message.message_id
        }

async def handle_ai_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش پیام‌های چت با هوش مصنوعی"""
    if not AI_MODULE_AVAILABLE:
        await update.message.reply_text("ماژول هوش مصنوعی در دسترس نیست.")
        return

    model_type = context.user_data.get('ai_model', 'gemini')
    
    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_ai_prompt', None)
    model_name = "Google Gemini" if model_type == "gemini" else "OpenAI GPT"
      # ارسال پیام "در حال پردازش"
    processing_message = await update.message.reply_text(
        f"🤖 <b>در حال دریافت پاسخ از {model_name}...</b>\n\nلطفاً کمی صبر کنید.",
        parse_mode="HTML"
    )
    
    try:
        # AI functionality temporarily disabled
        if not AI_MODULE_AVAILABLE:
            await update.message.reply_text(
                "⚠️ سرویس هوش مصنوعی موقتاً غیرفعال است.",
                reply_markup=main_menu_keyboard()
            )
            return
        
        # دریافت پاسخ از هوش مصنوعی
        # ai_model = get_ai_model(model_type)
        # system_message = f"شما یک دستیار هوش مصنوعی مفید و دوستانه هستید که به زبان فارسی پاسخ می‌دهید. نام شما {config.BOT_NAME} است."
        # response = ai_model.get_completion(message_text, system_message)
        
        # ارسال پاسخ به کاربر (temporarily disabled)
        # keyboard = InlineKeyboardMarkup([
        #     [InlineKeyboardButton("🔄 سوال جدید", callback_data=f"ai_model^{model_type}")],
        #     [InlineKeyboardButton("🔙 تغییر مدل", callback_data="ai_chat^")],
        #     [InlineKeyboardButton("» بازگشت به منو", callback_data="userpanel^")]        # ])
        
        # await processing_message.edit_text(
        #     f"🤖 <b>پاسخ {model_name}:</b>\n\n{response}",
        #     reply_markup=keyboard,
        #     parse_mode="HTML"
        # )
    except Exception as e:
        logger.error(f"خطا در دریافت پاسخ از هوش مصنوعی: {e}")
        await processing_message.edit_text(
            f"❌ متأسفانه در دریافت پاسخ از {model_name} خطایی رخ داد.\n\nلطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"ai_model^{model_type}")],
                [InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]
            ]),
            parse_mode="HTML"
        )

async def handle_admin_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش تایید کاربر توسط ادمین"""
    # دریافت اطلاعات کاربر از context
    pending_approval = context.user_data.get('pending_approval', {})
    if not pending_approval:
        await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
        return
        
    user_id = pending_approval.get('user_id')
    username = pending_approval.get('username')
    telegram_name = pending_approval.get('telegram_name')
    
    if not user_id:
        await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
        return
        
    # ثبت کاربر با نام وارد شده توسط ادمین
    real_name = message_text.strip()
    if not real_name:
        await update.message.reply_text("نام وارد شده نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.")
        return

    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_name', None)
    context.user_data.pop('pending_approval', None)
    
    conn = None
    try:
        # افزودن کاربر به دیتابیس
        conn = get_db_connection()
        c = conn.cursor()
        
        # بررسی وجود فصل فعال و دریافت امتیاز پیش‌فرض
        c.execute("SELECT id, balance FROM season WHERE is_active=1")
        active_season = c.fetchone()
        if not active_season:
            await update.message.reply_text("خطا: هیچ فصل فعالی یافت نشد!")
            return
            
        season_id = active_season[0]
        season_balance = active_season[1]  # امتیاز پیش‌فرض فصل (مثلاً 100 امتیاز)
        
        # ثبت کاربر در دیتابیس با امتیاز پیش‌فرض فصل
        # کاربر جدید همان امتیازی را دریافت می‌کند که برای فصل فعال تعریف شده
        c.execute("""
            INSERT INTO users (user_id, username, telegram_name, name, join_date, is_approved, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username or '', telegram_name, real_name, int(time.time()), 1, season_balance))
        
        # افزودن کاربر به فصل فعلی با همان امتیاز پیش‌فرض
        c.execute("""
            INSERT INTO user_season (user_id, season_id, join_date, balance)
            VALUES (?, ?, ?, ?)
        """, (user_id, season_id, int(time.time()), season_balance))
        
        conn.commit()
        
        # ارسال پیام موفقیت به ادمین با اطلاعات کامل
        await update.message.reply_text(
            f"✅ کاربر {real_name} با موفقیت به سیستم اضافه شد.\n"
            f"💰 امتیاز دریافتی: {season_balance} امتیاز (امتیاز پیش‌فرض فصل)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]])
        )
        
        # ارسال پیام خوش‌آمدگویی به کاربر
        welcome_text = f"کاربر گرامی {real_name}، به {config.BOT_NAME} خوش آمدید! ✅"
        welcome_text += f"\nدرخواست دسترسی شما تایید شد."
        welcome_text += f"\n💰 امتیاز اولیه شما: {season_balance} امتیاز"
        welcome_text += "\nمی‌توانید از طریق منوی زیر به امکانات ربات دسترسی داشته باشید."

        await context.bot.send_message(
            chat_id=user_id,
            text=welcome_text,
            reply_markup=main_menu_keyboard(user_id)
        )

    except Exception as e:
        logger.error(f"خطا در افزودن کاربر به دیتابیس: {e}")
        await update.message.reply_text(
            f"❌ خطا در ثبت کاربر: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="admin_panel^")]])
        )
    finally:
        if conn:
            conn.close()

async def handle_voting_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش دلیل امتیازدهی"""
    user = update.effective_user
    touser_id = context.user_data.get('voting_target_user_id')
    amount = context.user_data.get('voting_amount')
    
    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_reason', None)
    context.user_data.pop('voting_target_user_id', None)
    context.user_data.pop('voting_amount', None)
    
    if not touser_id or not amount:
        await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
        return
    
    # دریافت نام کاربر مقصد
    from ..database.models import db_manager
    target_user = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (touser_id,), 
        fetchone=True
    )
    touser_name = target_user[0] if target_user else "کاربر"
    
    # بررسی موجودی کاربر
    from ..database.user_functions import get_user_profile
    profile = get_user_profile(user.id)
    if not profile or profile[3] < amount:
        await update.message.reply_text(
            "اعتبار کافی ندارید!",
            reply_markup=main_menu_keyboard(user.id)
        )
        return
    
    # دریافت فصل فعال
    from ..database.season_functions import get_active_season
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
    else:
        season_id = active_season[0]
    
    # دریافت نام کاربر فرستنده
    sender_info = db_manager.execute_query(
        "SELECT name FROM users WHERE user_id=?", 
        (user.id,), 
        fetchone=True
    )
    sender_name = sender_info[0] if sender_info else "کاربر"
    
    # تنظیم دکمه تأیید و لغو
    keyboard = [
        [InlineKeyboardButton("✅ تأیید", callback_data=f"Confirm^{touser_id}^{amount}^{message_text}")],
        [InlineKeyboardButton("❌ لغو", callback_data="tovote^")]
    ]
    
    await update.message.reply_text(
        f"در حال ارسال {amount} امتیاز به {touser_name}\n\n"
        f"📝 دلیل: {message_text}\n\n"
        f"آیا تأیید می‌کنید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_gift_card_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش پیام تشکر‌نامه"""
    user = update.effective_user
    receiver_id = context.user_data.get('gift_card_receiver_id')
    receiver_name = context.user_data.get('gift_card_receiver_name', 'کاربر')
    sender_id = user.id
    
    # دریافت نام فرستنده از دیتابیس
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE user_id=?", (sender_id,))
        sender_result = c.fetchone()
        sender_name = sender_result[0] if sender_result else "یک دوست"
    finally:
        conn.close()

    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_gift_card_message', None)
    context.user_data.pop('gift_card_receiver_id', None)
    context.user_data.pop('gift_card_receiver_name', None)
    context.user_data.pop('gift_card_mode', None)

    if not receiver_id:
        await update.message.reply_text("خطا در پردازش تشکر‌نامه. لطفاً دوباره تلاش کنید.")
        return

    gift_message = message_text.strip()
    if not gift_message:
        await update.message.reply_text("متن تشکر‌نامه نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.")
        return

    # نمایش پیام "در حال پردازش"
    status_message = await update.message.reply_text(
        "🎨 در حال طراحی تشکر‌نامه...\nلطفاً کمی صبر کنید.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="letter_start^")]])
    )

    try:
        # مسیر ذخیره‌سازی فایل موقت
        from datetime import datetime
        import os
        
        # اطمینان از وجود پوشه tmp
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tmp')
        os.makedirs(temp_dir, exist_ok=True)
        
        image_filename = f"giftcard_{user.id}_{int(datetime.now().timestamp())}.png"
        image_path = os.path.join(temp_dir, image_filename)
        
        # ایجاد تشکر‌نامه
        create_gift_card_image(
            sender_name=sender_name,
            receiver_name=receiver_name,
            message=gift_message,
            output_path=image_path
        )

        if not os.path.exists(image_path):
            raise Exception("فایل تشکر‌نامه ایجاد نشد")

        # آپدیت پیام وضعیت
        await status_message.edit_text("📤 در حال ارسال تشکر‌نامه...")

        # ارسال تشکر‌نامه به گیرنده
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=receiver_id,
                photo=photo,
                caption=f"💌 تشکر‌نامه‌ای از طرف {sender_name} برای شما ارسال شده است!"
            )

        # ارسال کپی به فرستنده
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=sender_id,
                photo=photo,
                caption=f"✅ تشکر‌نامه شما با موفقیت به {receiver_name} ارسال شد!"
            )

        # ارسال کپی به ادمین اگر مشخص شده باشد
        if hasattr(config, 'GOD_ADMIN_ID') and config.GOD_ADMIN_ID:
            try:
                with open(image_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=config.GOD_ADMIN_ID,
                        photo=photo,
                        caption=f"📬 تشکر‌نامه ارسالی\n\n"
                                f"📤 از: {sender_name}\n"
                                f"📥 به: {receiver_name}\n"
                                f"💌 پیام: {gift_message}"
                    )
            except Exception as e:
                logger.error(f"خطا در ارسال کپی تشکر‌نامه به ادمین: {e}")
        
        # حذف فایل موقت
        try:
            os.remove(image_path)
            logger.debug(f"فایل موقت {image_path} حذف شد")
        except Exception as e:
            logger.warning(f"خطا در حذف فایل موقت {image_path}: {e}")
        
        # آپدیت پیام وضعیت
        await status_message.edit_text(
            "✅ تشکر‌نامه با موفقیت ارسال شد!",
            reply_markup=main_menu_keyboard(user.id)
        )
    except Exception as e:
        logger.error(f"خطا در پردازش تشکر‌نامه: {e}")
        await status_message.edit_text(
            f"⚠️ متأسفانه در ارسال تشکر‌نامه خطایی رخ داد: {str(e)}\n\nلطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 تلاش مجدد", callback_data="letter_start^")]])
        )

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش پیام همگانی ادمین"""
    # پاک کردن وضعیت انتظار
    context.user_data.pop('admin_action', None)
    
    # نمایش پیام تأیید
    keyboard = [
        [InlineKeyboardButton("✅ تأیید و ارسال", callback_data=f"confirm_broadcast^{message_text}")],
        [InlineKeyboardButton("❌ لغو", callback_data="broadcast_menu^")]
    ]
    
    await update.message.reply_text(
        f"📝 <b>پیش‌نمایش پیام همگانی:</b>\n\n{message_text}\n\n"
        f"آیا مطمئن هستید که این پیام به تمام کاربران ارسال شود؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_custom_points(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """پردازش امتیاز دلخواه وارد شده توسط کاربر"""
    user = update.effective_user
    custom_points_data = context.user_data.get('custom_points', {})
    
    # پاک کردن وضعیت انتظار
    context.user_data.pop('waiting_for_custom_points', None)
    
    if not custom_points_data:
        await update.message.reply_text("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
        return
    
    touser_id = custom_points_data.get('touser_id')
    touser_name = custom_points_data.get('touser_name', 'کاربر')
    max_score = custom_points_data.get('max_score', 0)
    
    # بررسی ورودی کاربر
    try:
        amount = int(message_text.strip())
        
        if amount <= 0:
            await update.message.reply_text(
                "مقدار وارد شده باید عددی مثبت باشد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]])
            )
            return
            
        if amount > max_score:
            await update.message.reply_text(
                f"مقدار وارد شده بیشتر از موجودی شما ({max_score} امتیاز) است. لطفاً مقدار کمتری را وارد کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]])
            )
            return
    except ValueError:
        await update.message.reply_text(
            "لطفاً یک عدد صحیح وارد کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="tovote^")]])
        )
        return
    
    # ادامه به مرحله وارد کردن دلیل
    context.user_data['voting_target_user_id'] = touser_id
    context.user_data['voting_amount'] = amount
    context.user_data['waiting_for_reason'] = True
    
    await update.message.reply_text(
        f"شما در حال ارسال {amount} امتیاز به {touser_name} هستید.\n\n"  
        f"دلیل:\n-----------------\n\n"  
        f"لطفاً دلیل امتیازدهی را بنویسید و ارسال کنید.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» لغو", callback_data="tovote^")]])
    )
