"""
Handler های مربوط به callback های کاربری (پروفایل، تاریخچه، امتیازات)
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sys
import os

# اضافه کردن مسیر پوشه اصلی برای دسترسی به config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

from ..database.user_functions import get_user_transactions, count_user_transactions, get_scoreboard
from ..database.season_functions import get_active_season, get_all_seasons
from ..database.db_utils import get_db_connection, get_user_profile
from ..utils.ui_helpers_new import main_menu_keyboard
from ..utils.season_utils import get_season_scoreboard, get_user_season_stats

logger = logging.getLogger(__name__)

async def handle_user_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش callback های مربوط به کاربران"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data == "userprofile^":
        await _handle_user_profile(query, user.id)
    elif data == "historypoints^":
        await _handle_history_points(query, user.id)
    elif data.startswith("receivedpoints^"):
        await _handle_received_points(query, user.id, data)
    elif data.startswith("givenpoints^"):
        await _handle_given_points(query, user.id, data)
    elif data == "season_archive":
        await _handle_season_archive(query, user.id)
    elif data.startswith("season_details^"):
        await _handle_season_details(query, user.id, data)
    elif data.startswith("Scoreboard^"):
        await _handle_scoreboard(query, data)

async def _handle_user_profile(query, user_id):
    """نمایش پروفایل کاربر"""
    await query.answer()
    profile = get_user_profile(user_id)
    if profile:
        # profile = [name, user_id, season_id, balance, total_received]
        name = profile[0]
        balance = profile[3]
        total_received = profile[4] or 0
        
        # دریافت یوزرنیم از جدول users
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            username_result = cursor.fetchone()
            username = username_result[0] if username_result and username_result[0] else "ندارد"
            conn.close()
        except Exception as e:
            logger.error(f"خطا در دریافت یوزرنیم: {e}")
            username = "ندارد"
        
        await query.edit_message_text(
            f"👤 پروفایل شما\n\nنام: {name}\nیوزرنیم: @{username}\nاعتبار فعلی: {balance}\nمجموع امتیازات دریافتی: {total_received}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧠 پروفایل هوشمند", callback_data="ai_profile^")],
                [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
            ])
        )
    else:
        await query.edit_message_text(
            "خطا در دریافت اطلاعات پروفایل!",
            reply_markup=main_menu_keyboard(user_id)
        )

async def _handle_history_points(query, user_id):
    """نمایش منوی تاریخچه امتیازات"""
    await query.answer()
    
    # دریافت فصل فعال
    active_season = get_active_season()
    if not active_season:
        season_id = config.SEASON_ID
        season_name = config.SEASON_NAME
    else:
        season_id = active_season[0]
        season_name = active_season[1]
    
    keyboard = [
        [InlineKeyboardButton("🏆 تابلوی امتیازات", callback_data=f"Scoreboard^{season_id}")],
        [InlineKeyboardButton("امتیازهای شما 🎯", callback_data=f"receivedpoints^0^{season_id}"), 
         InlineKeyboardButton("امتیازهایی که دادید 💬", callback_data=f"givenpoints^0^{season_id}")],
        [InlineKeyboardButton("🗂 آرشیو فصل‌ها", callback_data="season_archive")],
        [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
    ]
    await query.edit_message_text(
        f"🗂 تاریخچه امتیازات شما - فصل فعال: {season_name}\n\n"
        "در این بخش می‌توانید تاریخچه کامل امتیازات خود و دیگران را مشاهده کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def _handle_received_points(query, user_id, data):
    """نمایش امتیازات دریافتی"""
    await query.answer()
    parts = data.split("^")
    
    # پردازش صفحه‌بندی
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    season_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    
    # دریافت تراکنش‌ها
    transactions = get_user_transactions(user_id, given=False, offset=page*3, limit=3, season_id=season_id)
    total_count = count_user_transactions(user_id, given=False, season_id=season_id)
    
    if not transactions:
        season_text = f"در فصل انتخابی" if season_id else "در کل"
        await query.edit_message_text(
            f"📊 شما {season_text} هیچ امتیازی دریافت نکرده‌اید!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
        )
        return
    
    # ساخت متن نمایش
    text = "🎯 <b>امتیازات دریافتی شما:</b>\n\n"
    for i, transaction in enumerate(transactions):
        amount, sender_id, sender_name, reason, created_at, message_id, transaction_id, trans_season_id = transaction
        text += f"💎 <b>{amount}</b> امتیاز از 👤 {sender_name}\n"
        text += f"📝 دلیل: {reason}\n"
        text += f"🕒 تاریخ: {created_at}\n"
        
        # اگر این آخرین آیتم نیست، خط جداکننده اضافه کن
        if i < len(transactions) - 1:
            text += "\n" + "┄" * 20 + "\n\n"
    
    # دکمه‌های ناوبری
    keyboard = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« قبلی", callback_data=f"receivedpoints^{page-1}^{season_id or ''}"))
    
    if (page + 1) * 3 < total_count:
        nav_buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"receivedpoints^{page+1}^{season_id or ''}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def _handle_given_points(query, user_id, data):
    """نمایش امتیازات داده شده"""
    await query.answer()
    parts = data.split("^")
    
    # پردازش صفحه‌بندی
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    season_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    
    # دریافت تراکنش‌ها
    transactions = get_user_transactions(user_id, given=True, offset=page*3, limit=3, season_id=season_id)
    total_count = count_user_transactions(user_id, given=True, season_id=season_id)
    
    if not transactions:
        season_text = f"در فصل انتخابی" if season_id else "در کل"
        await query.edit_message_text(
            f"📊 شما {season_text} هیچ امتیازی نداده‌اید!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
        )
        return
    
    # ساخت متن نمایش
    text = "💬 <b>امتیازات داده شده توسط شما:</b>\n\n"
    for i, transaction in enumerate(transactions):
        amount, receiver_id, receiver_name, reason, created_at, message_id, transaction_id, trans_season_id = transaction
        text += f"💎 <b>{amount}</b> امتیاز به 👤 {receiver_name}\n"
        text += f"📝 دلیل: {reason}\n"
        text += f"🕒 تاریخ: {created_at}\n"
        
        # اگر این آخرین آیتم نیست، خط جداکننده اضافه کن
        if i < len(transactions) - 1:
            text += "\n" + "┄" * 20 + "\n\n"
    
    # دکمه‌های ناوبری
    keyboard = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« قبلی", callback_data=f"givenpoints^{page-1}^{season_id or ''}"))
    
    if (page + 1) * 3 < total_count:
        nav_buttons.append(InlineKeyboardButton("بعدی »", callback_data=f"givenpoints^{page+1}^{season_id or ''}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def _handle_season_archive(query, user_id):
    """نمایش آرشیو فصل‌ها"""
    await query.answer()
    
    seasons = get_all_seasons()
    if not seasons:
        await query.edit_message_text(
            "هیچ فصلی در سیستم تعریف نشده است!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
        )
        return
    
    keyboard = []
    for season in seasons:
        season_id, name, balance, is_active = season
        status = "🟢 فعال" if is_active else "⚪️"
        keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"season_details^{season_id}")])
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data="historypoints^")])
    
    await query.edit_message_text(
        "🗂 <b>آرشیو فصل‌ها</b>\n\n"
        "فصل مورد نظر را برای مشاهده جزئیات انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def _handle_season_details(query, user_id, data):
    """نمایش جزئیات فصل"""
    await query.answer()
    
    parts = data.split("^")
    season_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    
    if not season_id:
        await query.edit_message_text(
            "فصل مورد نظر یافت نشد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="season_archive")]])
        )
        return
    
    # دریافت اطلاعات فصل
    seasons = get_all_seasons()
    selected_season = None
    
    for season in seasons:
        if season[0] == season_id:
            selected_season = season
            break
    
    if not selected_season:
        await query.edit_message_text(
            "فصل مورد نظر یافت نشد!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="season_archive")]])
        )
        return
    
    season_id, season_name, balance, is_active = selected_season
    
    # دریافت تابلوی امتیازات فصل
    scoreboard = get_season_scoreboard(season_id)
    
    # دریافت آمار کاربر در این فصل
    stats = get_user_season_stats(user_id, season_id)
    
    status = "🟢 فعال" if is_active else "⚪️ غیرفعال"
    
    # ساخت متن نمایش
    text = f"🏆 <b>آرشیو فصل {season_name}</b> {status}\n\n"
    
    # نمایش 10 نفر برتر
    text += "<b>🥇 نفرات برتر:</b>\n\n"
    
    if scoreboard:
        for i, (user_id_in_list, total_points, name) in enumerate(scoreboard):
            medal = ""
            if i == 0:
                medal = "🥇 "
            elif i == 1:
                medal = "🥈 "
            elif i == 2:
                medal = "🥉 "
                
            # برجسته کردن کاربر جاری
            if user_id_in_list == user_id:
                name = f"<tg-spoiler>{name}</tg-spoiler>"
                
            text += f"{i+1}- {medal}{name}: <b>{total_points}</b> امتیاز\n"
    else:
        text += "هیچ امتیازی در این فصل ثبت نشده است.\n"
        
    text += "\n" + "┄" * 20 + "\n\n"
    
    # نمایش آمار کاربر
    text += f"<b>📊 آمار من در فصل {season_name}:</b>\n\n"
    
    if stats['rank'] > 0:
        text += f"• رتبه شما: <b>{stats['rank']}</b> از {stats['total_users']} کاربر\n"
    text += f"• تعداد امتیازهای دریافتی: {stats['received_count']} (مجموع: {stats['received_amount']})\n"
    text += f"• تعداد امتیازهای داده شده: {stats['given_count']} (مجموع: {stats['given_amount']})\n\n"
    
    # نمایش ترین‌های کاربر
    if stats['top_votes']:
        text += "<b>🏆 ترین‌های من از نظر دیگران:</b>\n\n"
        
        for q_text, vote_count, voters in stats['top_votes']:
            text += f"• {q_text} ({vote_count} رأی)\n"
            text += f"  از نظر: {voters}\n\n"
    
    # اضافه کردن دکمه‌های مشاهده امتیازهای دریافتی و داده شده در این فصل
    keyboard = [
        [InlineKeyboardButton("👁 امتیازهای دریافتی", callback_data=f"receivedpoints^0^{season_id}")],
        [InlineKeyboardButton("👁 امتیازهای داده شده", callback_data=f"givenpoints^0^{season_id}")],
        [InlineKeyboardButton("» بازگشت به آرشیو", callback_data="season_archive")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def _handle_scoreboard(query, data):
    """نمایش تابلوی امتیازات"""
    await query.answer()
    
    parts = data.split("^")
    season_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    
    # دریافت اطلاعات فصل
    if season_id:
        # اگر فصل مشخص شده باشد از آن استفاده می‌کنیم
        seasons = get_all_seasons()
        selected_season = None
        
        for season in seasons:
            if season[0] == season_id:
                selected_season = season
                break
        
        if not selected_season:
            season_name = "نامشخص"
        else:
            season_name = selected_season[1]
    else:
        # در غیر این صورت از فصل فعال استفاده می‌کنیم
        active_season = get_active_season()
        if active_season:
            season_id = active_season[0]
            season_name = active_season[1]
        else:
            await query.edit_message_text(
                "هیچ فصل فعالی یافت نشد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]])
            )
            return
    
    # دریافت تابلوی امتیازات
    scoreboard = get_scoreboard(season_id)
    
    if not scoreboard:
        await query.edit_message_text(
            f"🏆 <b>تابلوی امتیازات {season_name}</b>\n\n"
            "هیچ امتیازی در این فصل ثبت نشده است!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]]),
            parse_mode="HTML"
        )
        return
    
    # ساخت متن تابلوی امتیازات
    text = f"🏆 <b>تابلوی امتیازات {season_name}</b>\n\n"
    
    for i, (user_id, total_points, name) in enumerate(scoreboard, 1):
        if i <= 3:
            medals = ["🥇", "🥈", "🥉"]
            text += f"{medals[i-1]} {name}: <b>{total_points}</b> امتیاز\n"
        else:
            text += f"{i}. {name}: <b>{total_points}</b> امتیاز\n"
    
    keyboard = [[InlineKeyboardButton("» بازگشت", callback_data="historypoints^")]]
    
    # اگر از آرشیو فصل‌ها آمده باشیم، دکمه بازگشت به جزئیات فصل را اضافه می‌کنیم
    if parts[2] if len(parts) > 2 else None == "archive":
        keyboard[0] = [InlineKeyboardButton("» بازگشت به جزئیات فصل", callback_data=f"season_details^{season_id}")]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def handle_scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تابلوی امتیازات"""
    query = update.callback_query
    user = update.effective_user
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # دریافت اطلاعات فصل فعال
        c.execute("SELECT id, name FROM season WHERE is_active = 1")
        season = c.fetchone()
        if not season:
            await query.edit_message_text(
                "❌ هیچ فصل فعالی یافت نشد!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
            )
            return
            
        season_id, season_name = season
        
        # دریافت لیست برتر‌ها
        c.execute("""
            SELECT u.name, us.balance 
            FROM user_season us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.season_id = ?
            ORDER BY us.balance DESC
            LIMIT 10
        """, (season_id,))
        
        top_users = c.fetchall()
        
        if not top_users:
            await query.edit_message_text(
                f"🏆 <b>تابلوی امتیازات {season_name}</b>\n\n"
                "هنوز هیچ کاربری در این فصل امتیازی دریافت نکرده است.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]]),
                parse_mode="HTML"
            )
            return
            
        # ساخت متن تابلوی امتیازات
        text = f"🏆 <b>تابلوی امتیازات {season_name}</b>\n\n"
        
        for i, (name, points) in enumerate(top_users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {name}: {points} امتیاز\n"
            
        keyboard = [
            [InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"خطا در نمایش تابلوی امتیازات: {e}")
        await query.edit_message_text(
            "❌ خطا در دریافت اطلاعات تابلوی امتیازات. لطفاً دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data="userpanel^")]])
        )
    finally:
        conn.close()
