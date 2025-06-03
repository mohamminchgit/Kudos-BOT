"""
هندلر برای پردازش پرس‌وجوهای اینلاین (inline queries)
این ماژول برای پشتیبانی از جستجوی کاربران به صورت اینلاین در ربات استفاده می‌شود
"""

import logging
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import uuid

# وارد کردن توابع مورد نیاز
from ..database.user_functions import search_users, get_user_by_id
from ..database.season_functions import get_active_season

logger = logging.getLogger(__name__)

async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پرس‌وجوهای اینلاین برای جستجوی کاربران"""
    query = update.inline_query.query
    user_id = update.effective_user.id
    
    # اضافه کردن گزارش برای اشکال‌زدایی
    logger.debug(f"درخواست جستجوی اینلاین از کاربر {user_id} با متن: '{query}'")
    
    # بررسی آیا کاربر ادمین است
    from ..handlers.admin_handlers import is_admin
    from ..database.user_functions import is_user_approved
    
    # بررسی دسترسی کاربر
    if not is_admin(user_id) and not is_user_approved(user_id):
        logger.warning(f"کاربر {user_id} دسترسی لازم برای استفاده از جستجو را ندارد")
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="شما دسترسی لازم ندارید",
                input_message_content=InputTextMessageContent(
                    message_text="برای استفاده از این قابلیت باید در سیستم تایید شده باشید."
                ),
                description="لطفاً با پشتیبانی تماس بگیرید."
            )
        ], cache_time=5)
        return
    
    # بررسی آیا کاربر در سیستم تعریف شده است
    user_profile = get_user_by_id(user_id)
    logger.debug(f"نتیجه get_user_by_id برای کاربر {user_id}: {user_profile}")
    
    if not user_profile:
        logger.warning(f"کاربر {user_id} در سیستم تعریف نشده است")
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="شما در سیستم تعریف نشده‌اید",
                input_message_content=InputTextMessageContent(
                    message_text="برای استفاده از این قابلیت باید در سیستم تعریف شده باشید."
                ),
                description="لطفاً با پشتیبانی تماس بگیرید."
            )
        ], cache_time=5)
        return
    
    # بررسی حالت کاربر - آیا در حالت ارسال تشکرنامه است یا امتیازدهی
    is_gift_card_mode = context.user_data.get('gift_card_mode', False)
    is_top_vote_mode = context.user_data.get('top_vote_mode', False)
    
    # اگر در حالت معمولی (امتیازدهی) است، موجودی را بررسی می‌کنیم
    if not is_gift_card_mode and not is_top_vote_mode:
        try:
            from ..database.models import db_manager
            balance_result = db_manager.execute_query(
                "SELECT balance FROM users WHERE user_id = ?", 
                (user_id,), 
                fetchone=True
            )
            
            # ثبت نتیجه برای اشکال‌زدایی
            logger.debug(f"نتیجه بررسی موجودی کاربر {user_id}: {balance_result}")
            
            # بررسی نتیجه و تبدیل به عدد
            if balance_result is None:
                user_balance = 0
                logger.warning(f"موجودی برای کاربر {user_id} یافت نشد")
            else:
                user_balance = balance_result[0] if balance_result[0] is not None else 0
                
            # تبدیل به عدد صحیح
            try:
                user_balance = int(user_balance)
            except (TypeError, ValueError):
                logger.error(f"خطا در تبدیل موجودی به عدد: {user_balance}")
                user_balance = 0
                
            logger.debug(f"موجودی نهایی کاربر {user_id}: {user_balance}")
            
            if user_balance <= 0:
                logger.warning(f"کاربر {user_id} موجودی کافی ندارد. موجودی: {user_balance}")
                await update.inline_query.answer([
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="شما امتیاز کافی ندارید",
                        input_message_content=InputTextMessageContent(
                            message_text="برای امتیازدهی باید حداقل 1 امتیاز داشته باشید."
                        ),
                        description="موجودی شما صفر است."
                    )
                ], cache_time=5)
                return
        except Exception as e:
            logger.error(f"خطا در بررسی موجودی کاربر {user_id}: {e}")
            await update.inline_query.answer([
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="خطا در بررسی موجودی",
                    input_message_content=InputTextMessageContent(
                        message_text="متأسفانه در بررسی موجودی شما خطایی رخ داد. لطفاً دوباره تلاش کنید."
                    ),
                    description="خطای سیستمی"
                )
            ], cache_time=5)
            return
    
    if not query or len(query) < 2:
        # اگر پرس‌وجو خالی است یا کمتر از 2 کاراکتر است، هیچ نتیجه‌ای نمایش نمی‌دهیم
        await update.inline_query.answer([])
        return
    
    # جستجوی کاربران بر اساس نام
    logger.debug(f"جستجوی کاربران با عبارت '{query}' (به جز کاربر {user_id})")
    users = search_users(query, limit=10, exclude_id=user_id)
    logger.debug(f"نتیجه جستجو: {len(users) if users else 0} کاربر یافت شد")
    
    # اگر هیچ کاربری یافت نشد
    if not users:
        logger.warning(f"هیچ کاربری با عبارت '{query}' یافت نشد")
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="هیچ کاربری یافت نشد",
                input_message_content=InputTextMessageContent(
                    message_text="هیچ کاربری با این نام یافت نشد."
                ),
                description="لطفاً جستجوی دیگری را امتحان کنید."
            )
        ], cache_time=30)
        return
    
    # ساخت نتایج اینلاین
    results = []
    
    for user in users:
        user_id = user[0]  # شناسه کاربر
        name = user[1]     # نام کاربر
        username = None    # نام کاربری (به طور پیش‌فرض خالی)
        
        # سعی می‌کنیم نام کاربری را از دیتابیس بگیریم
        try:
            from ..database.models import db_manager
            user_data = db_manager.execute_query(
                "SELECT username FROM users WHERE user_id=?", 
                (user_id,), 
                fetchone=True
            )
            if user_data and user_data[0]:
                username = user_data[0]
        except Exception as e:
            logger.error(f"خطا در دریافت نام کاربری: {e}")
        
        # تنظیم آدرس تصویر پروفایل
        # برای کاربرانی که نام کاربری دارند، لینک به پروفایل تلگرام
        if username:
            thumbnail_url = f"https://t.me/{username.lstrip('@')}"
        else:
            # اگر نام کاربری نداشت، از آیکون پیش‌فرض استفاده می‌کنیم
            thumbnail_url = "https://img.icons8.com/fluency/48/000000/user-male-circle.png"
        
        # ساخت نتیجه برای هر کاربر با توجه به حالت کاربر
        if is_gift_card_mode:
            # در حالت ارسال تشکرنامه - استفاده از دکمه‌های کیبورد به جای پیام مستقیم
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"ارسال تشکرنامه به {name}", callback_data=f"giftcard_selectuser^{user_id}")]
            ])
            message_text = f"کاربر انتخاب شده: {name}"
            description = f"ارسال تشکرنامه به {name}"
        elif is_top_vote_mode:
            # در حالت رأی‌گیری ترین‌ها - استفاده از دکمه‌های کیبورد
            question_id = context.user_data.get('current_question_id')
            if question_id:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"انتخاب {name}", callback_data=f"top_select^{question_id}^{user_id}")]
                ])
                message_text = f"کاربر انتخاب شده: {name}"
                description = f"انتخاب {name} برای رأی‌گیری"
            else:
                message_text = "خطا در پردازش رأی‌گیری"
                description = "لطفاً دوباره تلاش کنید"
        else:
            # در حالت امتیازدهی معمولی - استفاده از دکمه‌های کیبورد
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"امتیازدهی به {name}", callback_data=f"voteuser^{user_id}")]
            ])
            message_text = f"کاربر انتخاب شده: {name}"
            description = f"انتخاب {name} برای امتیازدهی"
            
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"{name}",
                input_message_content=InputTextMessageContent(
                    message_text=message_text
                ),
                description=description,
                thumbnail_url=thumbnail_url,  # آیکون کاربر
                reply_markup=keyboard  # افزودن کیبورد اینلاین
            )
        )
    
    # پاسخ به پرس‌وجوی اینلاین
    await update.inline_query.answer(results, cache_time=60) 