"""
AI Callbacks Handler
Handles all AI-related callback functions including:
- AI chat functionality
- User perspective analysis
- AI profile generation
- Top voting processes
- Admin AI analysis
"""

import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
import datetime
import random

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

# Database and utility imports
from ..database.models import DatabaseManager
from ..database.user_functions import get_user_by_id, get_all_users
from ..database.db_utils import get_user_profile
from ..database.season_functions import get_active_season
from ..services.ai import get_user_perspective, generate_user_profile, analyze_admin_data, AI_MODULE_AVAILABLE
from ..utils.ui_helpers_new import main_menu_keyboard
from .top_vote_handlers import handle_top_vote_callbacks, _process_next_top_question, _save_top_vote, _get_active_top_questions, _get_top_results_for_question

# Initialize database manager
db_manager = DatabaseManager()
logger = logging.getLogger(__name__)


async def handle_ai_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """مدیریت کالبک‌های مربوط به هوش مصنوعی"""
    query = update.callback_query
    user = update.effective_user
    
    # بررسی وضعیت فعال/غیرفعال بودن قابلیت‌های هوش مصنوعی
    ai_features_enabled = db_manager.execute_query(
        "SELECT value FROM settings WHERE key='ai_features_enabled'", 
        fetchone=True
    )
    ai_features_enabled = ai_features_enabled[0] if ai_features_enabled else "1"  # پیش‌فرض: فعال
    
    # اگر قابلیت‌های هوش مصنوعی غیرفعال شده باشند و کاربر ادمین نباشد، پیام مناسب نمایش دهیم
    # فقط برای کالبک‌های مرتبط با هوش مصنوعی اعمال شود نه ترین‌ها
    if ai_features_enabled == "0" and not callback_data.startswith(("top_vote^", "top_select^", "top_results^")):
        from ..handlers.admin_handlers import is_admin
        if not is_admin(user.id):
            await query.answer("⚠️ این بخش موقتاً غیرفعال است.", show_alert=True)
            await query.edit_message_text(
                "🤖 <b>دستیار هوشمند</b>\n\n"
                "⚠️ این بخش به صورت موقت غیرفعال شده است. لطفاً بعداً مراجعه کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
                parse_mode="HTML"
            )
            return
    
    if callback_data == "ai_chat^":
        # چون فقط از Gemini استفاده می‌کنیم، مستقیماً به تنظیم مدل می‌رویم
        context.user_data['ai_model'] = "gemini"
        context.user_data['waiting_for_ai_prompt'] = True
        
        await query.edit_message_text(
            "🤖 <b>گفتگو با Google Gemini</b>\n\n"
            "سوال یا درخواست خود را بنویسید و ارسال کنید.\n"
            "می‌توانید هر زمان که خواستید با کلیک روی دکمه‌های زیر، گفتگو را پایان دهید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("» لغو و بازگشت", callback_data="userpanel^")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # پردازش انتخاب مدل هوش مصنوعی (برای سازگاری با کد قبلی)
    if callback_data.startswith("ai_model^"):
        model_type = "gemini"  # همیشه از Gemini استفاده می‌کنیم
        context.user_data['ai_model'] = model_type
        context.user_data['waiting_for_ai_prompt'] = True
        
        await query.edit_message_text(
            "🤖 <b>گفتگو با Google Gemini</b>\n\n"
            "سوال یا درخواست خود را بنویسید و ارسال کنید.\n"
            "می‌توانید هر زمان که خواستید با کلیک روی دکمه‌های زیر، گفتگو را پایان دهید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("» لغو و بازگشت", callback_data="userpanel^")]
            ]),
            parse_mode="HTML"
        )
        return
    
    if callback_data == "ai_chat^":
        await handle_ai_chat_menu(query, user.id)
    elif callback_data.startswith("ai_perspective^"):
        await _handle_ai_perspective(query, user.id, callback_data)
    elif callback_data == "ai_profile^":
        await _handle_ai_profile(query, user.id)
    elif callback_data == "ai_seasons_view^":
        await _handle_ai_seasons_view(query, user.id)
    elif callback_data.startswith("ai_model^"):
        await _handle_ai_model_selection(query, user.id, callback_data, context)
    elif callback_data.startswith("ai_analysis^"):
        await _handle_ai_analysis(query, user.id, callback_data)
    elif callback_data == "top_vote^":
        await _handle_top_voting_start(query, user.id, context)
    elif callback_data.startswith("top_select^"):
        await _handle_top_vote_selection(query, user.id, callback_data, context)
    elif callback_data == "top_results^":
        await _handle_top_results(query, user.id)


async def handle_ai_chat_menu(query, user_id):
    """نمایش منوی اصلی دستیار هوشمند"""
    await query.answer()
    
    # بررسی دسترسی به ماژول هوش مصنوعی
    if not AI_MODULE_AVAILABLE:
        await query.edit_message_text(
            "🤖 <b>دستیار هوشمند</b>\n\n"
            "متأسفانه ماژول هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً با پشتیبان تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
            parse_mode="HTML"
        )
        return
    
    # اطلاع رسانی به کاربر درباره قابلیت دستیار هوشمند
    await query.edit_message_text(
        "🤖 <b>دستیار هوشمند</b>\n\n"
        "از دستیار هوشمند برای دریافت تحلیل‌های جالب درباره خودتان و عملکردتان استفاده کنید:\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 پروفایل هوشمند من", callback_data="ai_profile^")],
            [InlineKeyboardButton("🔍 زاویه دید", callback_data="ai_seasons_view^")],
            [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
        ]),
        parse_mode="HTML"
    )


async def _handle_ai_perspective(query, user_id, data):
    """پردازش درخواست تحلیل زاویه دید دیگران"""
    await query.answer()
    
    # بررسی دسترسی به ماژول هوش مصنوعی
    if not AI_MODULE_AVAILABLE:
        await query.edit_message_text(
            "🤖 <b>دستیار هوشمند</b>\n\n"
            "متأسفانه ماژول هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً با پشتیبان تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
            parse_mode="HTML"
        )
        return
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        await query.edit_message_text(
            "در حال حاضر هیچ فصل فعالی وجود ندارد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]])
        )
        return
    
    season_id = active_season[0]
    season_name = active_season[1]
    
    # اگر شناسه فصل در دیتا وجود دارد، از آن استفاده کن
    if len(data.split("^")) > 1 and data.split("^")[1]:
        season_id = int(data.split("^")[1])
        # دریافت نام فصل
        season_data = db_manager.execute_query(
            "SELECT name FROM season WHERE id=?", 
            (season_id,), 
            fetchone=True
        )
        if season_data:
            season_name = season_data[0]
    
    # بررسی آیا کاربر اخیراً زاویه دید را برای این فصل دریافت کرده است
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT perspective, created_at FROM user_perspectives 
            WHERE user_id = ? AND season_id = ?
        """, (user_id, season_id))
        
        existing = c.fetchone()
        
        # اگر زاویه دید قبلی وجود دارد، زمان آخرین به‌روزرسانی را بررسی کنیم
        if existing:
            current_time = datetime.datetime.now()
            created_time = datetime.datetime.strptime(existing['created_at'], "%Y-%m-%d %H:%M:%S")
            time_diff = (current_time - created_time).total_seconds() / 3600  # تفاوت به ساعت
            
            # اگر کمتر از 24 ساعت گذشته باشد و کاربر درخواست به‌روزرسانی داده باشد
            if time_diff < 24:
                remaining_hours = 24 - int(time_diff)
                remaining_minutes = 60 - int((time_diff - int(time_diff)) * 60)
                
                # فرمت تاریخ و زمان فارسی
                jalali_time = created_time.strftime("%Y/%m/%d %H:%M:%S")
                
                # نمایش پیغام به کاربر با پاپ‌آپ
                await query.answer(
                    f"شما باید {remaining_hours} ساعت و {remaining_minutes} دقیقه دیگر صبر کنید تا بتوانید زاویه دید را برای این فصل به‌روزرسانی کنید.",
                    show_alert=True
                )
                
                # نمایش زاویه دید موجود با افزودن زمان آخرین به‌روزرسانی
                # افزودن ایموجی‌ها به پاراگراف‌های متن
                perspective_text = existing['perspective']
                enhanced_perspective = _add_emojis_to_profile(perspective_text)  # از همان تابع استفاده می‌کنیم
                
                # ایجاد دکمه‌های فصل
                season_buttons = []
                seasons = db_manager.execute_query(
                    "SELECT id, name, is_active FROM season ORDER BY is_active DESC, id DESC"
                )
                
                for s in seasons:
                    s_id, s_name, is_active = s
                    status = "🟢" if is_active == 1 else "🔴"
                    if s_id != season_id:  # فصل فعلی را نشان نده
                        season_buttons.append(
                            InlineKeyboardButton(f"فصل {s_name} {status}", callback_data=f"ai_perspective^{s_id}")
                        )
                
                # ایجاد دکمه‌های کیبورد
                keyboard = []
                # دکمه‌های فصل را به صورت 1 در هر ردیف نمایش بده
                for button in season_buttons:
                    keyboard.append([button])
                
                keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")])
                
                # تنظیم عنوان پیام
                message_title = f"🔍 <b>زاویه دید در فصل {season_name}</b>"
                
                await query.edit_message_text(
                    f"{message_title}\n\n{enhanced_perspective}\n\n"
                    f"🕒 <i>آخرین به‌روزرسانی: {jalali_time}</i>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
                return
    except Exception as e:
        logger.error(f"خطا در بررسی وضعیت زاویه دید: {e}")
    finally:
        if conn:
            conn.close()
    
    # نمایش پیام در حال دریافت
    await query.edit_message_text(
        f"🔍 <b>در حال تحلیل زاویه دید دیگران...</b>\n\n"
        f"لطفاً کمی صبر کنید. در حال دریافت و تحلیل نظرات دیگران درباره شما در فصل {season_name}...",
        parse_mode="HTML"
    )
    
    try:
        # دریافت زاویه دید دیگران
        perspective = get_user_perspective(user_id, season_id)
        
        # افزودن ایموجی‌ها به پاراگراف‌های متن
        enhanced_perspective = _add_emojis_to_profile(perspective)
        
        # ایجاد دکمه‌های فصل
        season_buttons = []
        seasons = db_manager.execute_query(
            "SELECT id, name, is_active FROM season ORDER BY is_active DESC, id DESC"
        )
        
        for s in seasons:
            s_id, s_name, is_active = s
            status = "🟢" if is_active == 1 else "🔴"
            if s_id != season_id:  # فصل فعلی را نشان نده
                season_buttons.append(
                    InlineKeyboardButton(f"فصل {s_name} {status}", callback_data=f"ai_perspective^{s_id}")
                )
        
        # ایجاد دکمه‌های کیبورد
        keyboard = []
        # دکمه‌های فصل را به صورت 1 در هر ردیف نمایش بده
        for button in season_buttons:
            keyboard.append([button])
        
        keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")])
        
        # تنظیم عنوان پیام
        message_title = f"🔍 <b>زاویه دید در فصل {season_name}</b>"
        
        # زمان فعلی برای نمایش زمان به‌روزرسانی
        current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        
        await query.edit_message_text(
            f"{message_title}\n\n{enhanced_perspective}\n\n"
            f"🕒 <i>آخرین به‌روزرسانی: {current_time}</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"خطا در دریافت زاویه دید: {e}")
        await query.edit_message_text(
            "❌ متأسفانه در دریافت زاویه دید خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]])
        )


async def _handle_ai_profile(query, user_id):
    """پردازش درخواست ایجاد پروفایل هوشمند"""
    await query.answer()
    
    # بررسی دسترسی به ماژول هوش مصنوعی
    if not AI_MODULE_AVAILABLE:
        await query.edit_message_text(
            "🤖 <b>دستیار هوشمند</b>\n\n"
            "متأسفانه ماژول هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً با پشتیبان تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
            parse_mode="HTML"
        )
        return
    
    # بررسی آیا کاربر اخیراً پروفایل هوشمند دریافت کرده است
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT profile_text, created_at FROM user_profiles WHERE user_id = ?", (user_id,))
        existing = c.fetchone()
        
        # اگر پروفایل قبلی وجود دارد، زمان آخرین به‌روزرسانی را بررسی کنیم
        if existing:
            current_time = datetime.datetime.now()
            created_time = datetime.datetime.strptime(existing['created_at'], "%Y-%m-%d %H:%M:%S")
            time_diff = (current_time - created_time).total_seconds() / 3600  # تفاوت به ساعت
            
            # اگر کمتر از 24 ساعت گذشته باشد و کاربر درخواست به‌روزرسانی داده باشد
            if time_diff < 24:
                remaining_hours = 24 - int(time_diff)
                remaining_minutes = 60 - int((time_diff - int(time_diff)) * 60)
                
                # فرمت تاریخ و زمان فارسی
                jalali_time = created_time.strftime("%Y/%m/%d %H:%M:%S")
                
                # نمایش پیغام به کاربر با پاپ‌آپ
                await query.answer(
                    f"شما باید {remaining_hours} ساعت و {remaining_minutes} دقیقه دیگر صبر کنید تا بتوانید پروفایل خود را به‌روزرسانی کنید.",
                    show_alert=True
                )
                
                # نمایش پروفایل موجود با افزودن زمان آخرین به‌روزرسانی
                # افزودن ایموجی‌های مناسب به متن برای خوانایی بهتر
                profile_text = existing['profile_text']
                
                # افزودن ایموجی‌ها به پاراگراف‌های متن
                enhanced_profile = _add_emojis_to_profile(profile_text)
                
                # دریافت اطلاعات کاربر
                c.execute("SELECT name FROM users WHERE user_id=?", (user_id,))
                user_data = c.fetchone()
                user_name = user_data['name'] if user_data else "کاربر"
                
                await query.edit_message_text(
                    f"👤 <b>پروفایل هوشمند {user_name}</b>\n\n"
                    f"{enhanced_profile}\n\n"
                    f"🕒 <i>آخرین به‌روزرسانی: {jalali_time}</i>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 به‌روزرسانی پروفایل", callback_data="ai_profile^")],
                        [InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]
                    ]),
                    parse_mode="HTML"
                )
                return
    except Exception as e:
        logger.error(f"خطا در بررسی وضعیت پروفایل: {e}")
    finally:
        if conn:
            conn.close()
    
    # نمایش پیام در حال دریافت
    await query.edit_message_text(
        "👤 <b>در حال ایجاد پروفایل هوشمند...</b>\n\n"
        "لطفاً کمی صبر کنید. در حال تحلیل داده‌ها و ایجاد پروفایل هوشمند شما...",
        parse_mode="HTML"
    )
    
    try:
        # ایجاد پروفایل کاربر
        profile = generate_user_profile(user_id)
        
        # افزودن ایموجی‌های مناسب به متن برای خوانایی بهتر
        enhanced_profile = _add_emojis_to_profile(profile)
        
        # دریافت اطلاعات کاربر
        user_data = db_manager.execute_query(
            "SELECT name FROM users WHERE user_id=?", 
            (user_id,), 
            fetchone=True
        )
        user_name = user_data[0] if user_data else "کاربر"
        
        # زمان فعلی برای نمایش زمان به‌روزرسانی
        current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        
        await query.edit_message_text(
            f"👤 <b>پروفایل هوشمند {user_name}</b>\n\n"
            f"{enhanced_profile}\n\n"
            f"🕒 <i>آخرین به‌روزرسانی: {current_time}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 به‌روزرسانی پروفایل", callback_data="ai_profile^")],
                [InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"خطا در ایجاد پروفایل هوشمند: {e}")
        await query.edit_message_text(
            "❌ متأسفانه در ایجاد پروفایل هوشمند خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]])
        )


def _add_emojis_to_profile(text):
    """افزودن ایموجی‌های مناسب به پاراگراف‌های متن پروفایل"""
    # لیست ایموجی‌های مناسب برای پروفایل
    emojis = ["✨", "🌟", "🔍", "🚀", "🧠", "👥", "💡", "🎯", "🌈", "📊"]
    
    # تقسیم متن به پاراگراف‌ها
    paragraphs = text.split('\n\n')
    
    # افزودن ایموجی به ابتدای هر پاراگراف
    enhanced_paragraphs = []
    for i, para in enumerate(paragraphs):
        if para.strip():
            emoji = emojis[i % len(emojis)]
            enhanced_paragraphs.append(f"{emoji} {para}")
    
    # اتصال مجدد پاراگراف‌ها با ایموجی
    return '\n\n'.join(enhanced_paragraphs)


async def _handle_ai_model_selection(query, user_id, data, context):
    """پردازش انتخاب مدل هوش مصنوعی برای چت"""
    await query.answer()
    
    # همیشه از Gemini استفاده می‌کنیم
    model_type = "gemini"
    context.user_data['ai_model'] = model_type
    context.user_data['waiting_for_ai_prompt'] = True
    
    await query.edit_message_text(
        "🤖 <b>گفتگو با Google Gemini</b>\n\n"
        "سوال یا درخواست خود را بنویسید و ارسال کنید.\n"
        "می‌توانید هر زمان که خواستید با کلیک روی دکمه‌های زیر، گفتگو را پایان دهید.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("» لغو و بازگشت", callback_data="userpanel^")]
        ]),
        parse_mode="HTML"
    )


async def _handle_ai_analysis(query, user_id, data):
    """پردازش تحلیل ادمین با هوش مصنوعی"""
    # بررسی مجوز ادمین
    admin_data = db_manager.execute_query(
        "SELECT role, permissions FROM admins WHERE user_id=?", 
        (user_id,), 
        fetchone=True
    )
    
    if not admin_data or (admin_data[0] != 'god' and "admin_stats" not in admin_data[1].split(",")):
        await query.answer("شما به این بخش دسترسی ندارید!", show_alert=True)
        return
    
    # بررسی دسترسی به ماژول هوش مصنوعی
    if not AI_MODULE_AVAILABLE:
        await query.edit_message_text(
            "🧠 <b>تحلیل با هوش مصنوعی</b>\n\n"
            "متأسفانه ماژول هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً با توسعه‌دهنده تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]]),
            parse_mode="HTML"
        )
        return
    
    # اگر فصل انتخاب شده، آن را استفاده کن
    season_id = None
    season_name = "همه فصل‌ها"
    
    if len(data.split("^")) > 1 and data.split("^")[1]:
        if data.split("^")[1] == "all":
            season_id = None
            season_name = "همه فصل‌ها"
        elif data.split("^")[1] == "back":
            # نمایش منوی انتخاب فصل
            await _show_ai_analysis_season_menu(query)
            return
        else:
            season_id = int(data.split("^")[1])
            season_data = db_manager.execute_query(
                "SELECT name FROM season WHERE id=?", 
                (season_id,), 
                fetchone=True
            )
            if season_data:
                season_name = season_data[0]
    else:
        # دریافت فصل فعال
        active_season = get_active_season()
        if active_season:
            season_id = active_season[0]
            season_name = active_season[1]
    
    # اگر انتخاب نوع تحلیل
    if len(data.split("^")) > 2:
        # نمایش پیام در حال دریافت
        await query.edit_message_text(
            f"🧠 <b>در حال تحلیل داده‌ها...</b>\n\n"
            f"لطفاً کمی صبر کنید. در حال تحلیل اطلاعات {season_name}...",
            parse_mode="HTML"
        )
        
        try:
            # دریافت تحلیل از هوش مصنوعی
            analysis = analyze_admin_data(season_id)
            
            # ایجاد دکمه‌های بازگشت
            keyboard = [
                [InlineKeyboardButton("🔄 به‌روزرسانی تحلیل", callback_data=f"ai_analysis^{season_id if season_id else 'all'}^general")],
                [InlineKeyboardButton("↩️ انتخاب فصل دیگر", callback_data="ai_analysis^back")],
                [InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")]
            ]
            
            await query.edit_message_text(
                f"🧠 <b>تحلیل هوش مصنوعی - {season_name}</b>\n\n{analysis}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"خطا در دریافت تحلیل هوش مصنوعی: {e}")
            await query.edit_message_text(
                "❌ متأسفانه در دریافت تحلیل خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="ai_analysis^back")]])
            )
        return
    
    # نمایش منوی انتخاب فصل
    await _show_ai_analysis_season_menu(query)


async def _show_ai_analysis_season_menu(query):
    """نمایش منوی انتخاب فصل برای تحلیل ادمین"""
    keyboard = []
    seasons = db_manager.execute_query(
        "SELECT id, name, is_active FROM season ORDER BY id DESC"
    )
    
    for s in seasons:
        status = "🟢" if s[2] == 1 else "🔴"
        keyboard.append([InlineKeyboardButton(f"{s[1]} {status}", callback_data=f"ai_analysis^{s[0]}^general")])
    
    keyboard.append([InlineKeyboardButton("📊 همه فصل‌ها", callback_data=f"ai_analysis^all^general")])
    keyboard.append([InlineKeyboardButton("» بازگشت به پنل ادمین", callback_data="admin_panel^")])
    
    await query.edit_message_text(
        "🧠 <b>تحلیل با هوش مصنوعی</b>\n\n"
        "با استفاده از هوش مصنوعی می‌توانید تحلیل‌های جامعی از داده‌های سیستم امتیازدهی دریافت کنید. "
        "این تحلیل‌ها شامل الگوهای امتیازدهی، شناسایی احتمالی تقلب، و روندهای کلی سیستم می‌شود.\n\n"
        "لطفاً فصل مورد نظر برای تحلیل را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def _handle_top_voting_start(query, user_id, context):
    """شروع فرآیند رأی‌گیری ترین‌ها"""
    # تنظیم حالت رأی‌گیری ترین‌ها در داده‌های کاربر
    context.user_data['top_vote_mode'] = True
    await _process_next_top_question(query, user_id, context)


async def _handle_top_vote_selection(query, user_id, data, context):
    """پردازش انتخاب رأی در ترین‌ها"""
    await query.answer()
    try:
        parts = data.split("^")
        if len(parts) < 3:
            logger.error(f"ساختار داده کالبک نامعتبر است: {data}")
            await query.edit_message_text(
                "❌ خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
            return
            
        question_id = int(parts[1])
        voted_for = int(parts[2])
        
        # ذخیره رأی کاربر
        if await _save_top_vote(user_id, question_id, voted_for):
            # ادامه به سوال بعدی
            await _process_next_top_question(query, user_id, context)
        else:
            await query.edit_message_text(
                "❌ خطا در ثبت رأی شما. ممکن است قبلاً به این سوال رأی داده باشید یا مشکلی در سیستم وجود داشته باشد. لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
    except Exception as e:
        logger.error(f"خطا در پردازش رأی‌گیری ترین‌ها: {e}")
        await query.edit_message_text(
            "❌ خطای سیستمی در ثبت رأی. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
        )


async def _handle_top_results(query, user_id):
    """نمایش نتایج ترین‌ها"""
    await query.answer()
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
        season_name = config.SEASON_NAME
    else:
        season_id = active_season[0]
        season_name = active_season[1]
    
    # دریافت سوالات فعال
    questions = _get_active_top_questions()
    
    if not questions:
        await query.edit_message_text(
            f"هیچ سوالی برای فصل {season_name} تعریف نشده است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
        )
        return
    
    # ساخت متن نتایج
    result_text = f"🏆 <b>نتایج ترین‌های فصل {season_name}</b>\n\n"
    
    for q_id, q_text in questions:
        result_text += f"<b>{q_text}</b>\n"
        
        # دریافت نتایج برای این سوال
        top_results = _get_top_results_for_question(q_id)
        
        if top_results:
            for i, (voted_for, count, name) in enumerate(top_results[:3]):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                result_text += f"{medal} {name}: {count} رأی\n"
        else:
            result_text += "هنوز رأیی ثبت نشده است.\n"
        
        result_text += "\n" + "-" * 30 + "\n\n"
    
    await query.edit_message_text(
        result_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
        parse_mode="HTML"
    )

async def _handle_ai_seasons_view(query, user_id):
    """نمایش منوی انتخاب فصل برای زاویه دید"""
    await query.answer()
    
    # بررسی دسترسی به ماژول هوش مصنوعی
    if not AI_MODULE_AVAILABLE:
        await query.edit_message_text(
            "🤖 <b>دستیار هوشمند</b>\n\n"
            "متأسفانه ماژول هوش مصنوعی در حال حاضر در دسترس نیست. لطفاً با پشتیبان تماس بگیرید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
            parse_mode="HTML"
        )
        return
    
    # ایجاد دکمه‌های فصل
    keyboard = []
    seasons = db_manager.execute_query(
        "SELECT id, name, is_active FROM season ORDER BY is_active DESC, id DESC"
    )
    
    if not seasons:
        await query.edit_message_text(
            "در حال حاضر هیچ فصلی تعریف نشده است!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")]])
        )
        return
    
    for season in seasons:
        s_id, s_name, is_active = season
        status = "🟢" if is_active == 1 else "🔴"
        keyboard.append([InlineKeyboardButton(f"فصل {s_name} {status}", callback_data=f"ai_perspective^{s_id}")])
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="ai_chat^")])
    
    await query.edit_message_text(
        "🔍 <b>زاویه دید</b>\n\n"
        "با استفاده از هوش مصنوعی می‌توانید دریابید که دیگران چگونه به شما و عملکردتان نگاه می‌کنند. "
        "این تحلیل بر اساس امتیازاتی که به شما داده شده و دلایل آن‌ها انجام می‌شود.\n\n"
        "لطفاً فصلی که می‌خواهید زاویه دید آن را مشاهده کنید انتخاب نمایید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

