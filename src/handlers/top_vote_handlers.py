"""
Handler های مربوط به سیستم رأی‌گیری ترین‌ها
این ماژول برای پردازش رأی‌های ترین‌ها و نمایش نتایج استفاده می‌شود
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.models import db_manager
from ..database.user_functions import get_all_users
from ..database.season_functions import get_active_season
from ..utils.ui_helpers_new import main_menu_keyboard

logger = logging.getLogger(__name__)

async def handle_top_vote_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش callback های مربوط به سیستم رأی‌گیری ترین‌ها"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data == "top_vote^":
        await _handle_top_voting_start(query, user.id, context)
    elif data.startswith("top_select^"):
        await _handle_top_vote_selection(query, user.id, data, context)
    elif data == "top_results^":
        await _handle_top_results(query, user.id)

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


async def _process_next_top_question(query, user_id, context):
    """پردازش سوال بعدی در رأی‌گیری ترین‌ها"""
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
        season_name = config.SEASON_NAME
    else:
        season_id = active_season[0]
        season_name = active_season[1]
    
    # دریافت سوال بعدی
    next_question = _get_next_unanswered_question(user_id)
    
    if not next_question:
        # اگر همه سوالات پاسخ داده شده‌اند، نمایش خلاصه رأی‌های کاربر
        user_votes = _get_user_top_votes(user_id)
        summary = f"🎉 <b>تبریک!</b>\n\nشما به تمام سوالات ترین‌های فصل {season_name} پاسخ دادید.\n\n<b>رأی‌های شما:</b>\n\n"
        
        for q_text, voted_name, _ in user_votes:
            summary += f"🔹 {q_text}\n"
            summary += f"✓ رأی شما: {voted_name}\n\n"
        
        keyboard = [[InlineKeyboardButton("» مشاهده نتایج", callback_data="top_results^")]]
        
        # پاک کردن داده‌های موقت
        context.user_data.pop('top_vote_mode', None)
        context.user_data.pop('current_question_id', None)
        
        # بررسی نوع آبجکت query برای فراخوانی متد مناسب
        try:
            # سعی در استفاده از edit_message_text
            await query.edit_message_text(
                summary,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        except AttributeError:
            # اگر query یک Message است و نه CallbackQuery
            try:
                await query.edit_text(
                    summary,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except (AttributeError, Exception) as e:
                # اگر هیچ یک از موارد بالا کار نکرد، از context.bot استفاده می‌کنیم
                logger.error(f"خطا در به‌روزرسانی پیام: {e}")
                try:
                    chat_id = getattr(query, 'chat_id', None) or getattr(query.chat, 'id', None)
                    message_id = getattr(query, 'message_id', None)
                    
                    if chat_id and message_id:
                        await context.bot.edit_message_text(
                            text=summary,
                            chat_id=chat_id,
                            message_id=message_id,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="HTML"
                        )
                    else:
                        # اگر نتوانستیم پیام را ویرایش کنیم، باید اطلاعات کاربر را از context استفاده کنیم
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=summary,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="HTML"
                        )
                except Exception as e2:
                    logger.error(f"خطا در ارسال پیام به کاربر: {e2}")
        return
    
    question_id, question_text = next_question
    
    # ذخیره شناسه سوال فعلی در داده‌های کاربر
    context.user_data['current_question_id'] = question_id
    
    # دریافت تنظیم نمایش همه کاربران
    show_all_users_result = db_manager.execute_query(
        "SELECT value FROM settings WHERE key='show_all_users'", 
        fetchone=True
    )
    show_all_users = show_all_users_result[0] if show_all_users_result else "0"
    
    # دریافت لیست کاربران برای رأی‌دهی (به جز خود کاربر)
    users = get_all_users(exclude_id=user_id)
    keyboard = []
    
    # اضافه کردن دکمه جستجو با حالت اینلاین
    keyboard.append([
        InlineKeyboardButton("🔍 جستجوی کاربر", switch_inline_query_current_chat="")
    ])
    
    # اضافه کردن دکمه‌های کاربران اگر تنظیمات نمایش همه کاربران فعال باشد
    if show_all_users == "1":
        row = []
        for i, u in enumerate(users):
            row.append(InlineKeyboardButton(f"{i+1}- {u[1]}", callback_data=f"top_select^{question_id}^{u[0]}"))
            if len(row) == 2 or i == len(users) - 1:  # دو دکمه در هر ردیف
                keyboard.append(row)
                row = []
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="userpanel^")])
    
    message_text = (
        f"🏆 <b>ترین‌های فصل {season_name}</b>\n\n"
        f"<b>سوال {len(_get_user_top_votes(user_id))+1}:</b> {question_text}\n\n"
    )
    
    if show_all_users == "1":
        message_text += "لطفاً یکی از همکاران خود را انتخاب کنید:\n\n"
    
    message_text += "برای جستجوی سریع‌تر می‌توانید از دکمه 🔍 جستجو استفاده کنید."
    
    # بررسی نوع آبجکت query برای فراخوانی متد مناسب
    try:
        # سعی در استفاده از edit_message_text
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except AttributeError:
        # اگر query یک Message است و نه CallbackQuery
        try:
            await query.edit_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        except (AttributeError, Exception) as e:
            # اگر هیچ یک از موارد بالا کار نکرد، از context.bot استفاده می‌کنیم
            logger.error(f"خطا در به‌روزرسانی پیام: {e}")
            try:
                chat_id = getattr(query, 'chat_id', None) or getattr(query.chat, 'id', None)
                message_id = getattr(query, 'message_id', None)
                
                if chat_id and message_id:
                    await context.bot.edit_message_text(
                        text=message_text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
                else:
                    # اگر نتوانستیم پیام را ویرایش کنیم، باید اطلاعات کاربر را از context استفاده کنیم
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="HTML"
                    )
            except Exception as e2:
                logger.error(f"خطا در ارسال پیام به کاربر: {e2}")

async def _save_top_vote(user_id, question_id, voted_for):
    """ذخیره رأی کاربر برای سوال ترین‌ها"""
    try:
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            season_id = config.SEASON_ID
        else:
            season_id = active_season[0]
        
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # بررسی آیا کاربر قبلاً به این سوال رأی داده است
        c.execute("""
            SELECT vote_id FROM top_votes 
            WHERE user_id = ? AND question_id = ? AND season_id = ?
        """, (user_id, question_id, season_id))
        
        existing_vote = c.fetchone()
        
        if existing_vote:
            # اگر قبلاً رأی داده، آن را به‌روز کنیم
            c.execute("""
                UPDATE top_votes 
                SET voted_for_user_id = ?, vote_time = CURRENT_TIMESTAMP
                WHERE user_id = ? AND question_id = ? AND season_id = ?
            """, (voted_for, user_id, question_id, season_id))
        else:
            # رأی جدید ثبت کنیم
            c.execute("""
                INSERT INTO top_votes (user_id, question_id, voted_for_user_id, season_id, vote_time)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, question_id, voted_for, season_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"خطا در ذخیره رأی ترین‌ها: {e}")
        return False


def _get_next_unanswered_question(user_id):
    """دریافت سوال بعدی ترین‌ها که کاربر هنوز به آن پاسخ نداده است"""
    try:
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            season_id = config.SEASON_ID
        else:
            season_id = active_season[0]
        
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # یافتن سوالات فعال برای فصل که کاربر هنوز پاسخ نداده است
        c.execute("""
            SELECT question_id, text
            FROM top_questions
            WHERE is_active = 1
            AND NOT EXISTS (
                SELECT 1 FROM top_votes v
                WHERE v.question_id = top_questions.question_id
                AND v.user_id = ?
                AND v.season_id = ?
            )
            ORDER BY question_id
            LIMIT 1
        """, (user_id, season_id))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            return (result['question_id'], result['text'])
        return None
    except Exception as e:
        logger.error(f"خطا در دریافت سوال بعدی ترین‌ها: {e}")
        return None


def _get_active_top_questions():
    """دریافت لیست سوالات فعال ترین‌ها"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT question_id, text
            FROM top_questions
            WHERE is_active = 1
            ORDER BY question_id
        """)
        
        results = c.fetchall()
        conn.close()
        
        if results:
            return [(row['question_id'], row['text']) for row in results]
        return []
    except Exception as e:
        logger.error(f"خطا در دریافت سوالات فعال ترین‌ها: {e}")
        return []


def _get_user_top_votes(user_id):
    """دریافت لیست رأی‌های ترین‌های کاربر"""
    try:
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            season_id = config.SEASON_ID
        else:
            season_id = active_season[0]
        
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT tq.text AS question_text, u.name AS voted_name, v.voted_for_user_id
            FROM top_votes v
            JOIN top_questions tq ON v.question_id = tq.question_id
            JOIN users u ON v.voted_for_user_id = u.user_id
            WHERE v.user_id = ? AND v.season_id = ?
            ORDER BY v.vote_id
        """, (user_id, season_id))
        
        results = c.fetchall()
        conn.close()
        
        if results:
            return [(row['question_text'], row['voted_name'], row['voted_for_user_id']) for row in results]
        return []
    except Exception as e:
        logger.error(f"خطا در دریافت رأی‌های کاربر: {e}")
        return []


def _get_top_results_for_question(question_id):
    """دریافت نتایج رأی‌گیری برای یک سوال ترین‌ها"""
    try:
        # دریافت فصل فعال
        active_season = get_active_season()
        if not active_season:
            season_id = config.SEASON_ID
        else:
            season_id = active_season[0]
        
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # شمارش رأی‌ها برای هر کاربر
        c.execute("""
            SELECT v.voted_for, COUNT(v.id) AS vote_count, u.name
            FROM top_votes v
            JOIN users u ON v.voted_for = u.user_id
            WHERE v.question_id = ? AND v.season_id = ?
            GROUP BY v.voted_for
            ORDER BY vote_count DESC
        """, (question_id, season_id))
        
        results = c.fetchall()
        conn.close()
        
        if results:
            return [(row['voted_for'], row['vote_count'], row['name']) for row in results]
        return []
    except Exception as e:
        logger.error(f"خطا در دریافت نتایج رأی‌گیری: {e}")
        return []