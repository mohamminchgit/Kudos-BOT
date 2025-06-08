# -*- coding: utf-8 -*-

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.database.db_utils import get_active_season, execute_db_query
import config

def main_menu_keyboard(user_id=None):
    """ایجاد کیبورد منوی اصلی"""
    keyboard = [
        [InlineKeyboardButton("✉️ ارسال نامه", callback_data="letter_start^"),
        InlineKeyboardButton("🎯 امتیازدهی به دیگران", callback_data="tovote^")]
    ]
    
    # دریافت فصل فعال
    active_season = get_active_season()
    
    # اضافه کردن دکمه ترین‌ها فقط اگر فصل فعالی وجود داشته باشد
    if active_season:
        season_id = active_season[0]
        season_name = active_season[1]
        
        # بررسی آیا کاربر در فصل جاری به سوالات ترین‌ها پاسخ داده است
        has_voted_all = False
        if user_id:
            total_questions_result = execute_db_query("""
                SELECT COUNT(*) FROM top_questions WHERE is_active=1 AND season_id=?
            """, (season_id,), fetchone=True)
            total_questions = total_questions_result[0] if total_questions_result else 0
            
            user_votes_result = execute_db_query("""
                SELECT COUNT(*) FROM top_votes 
                WHERE user_id=? AND season_id=?
            """, (user_id, season_id), fetchone=True)
            user_votes = user_votes_result[0] if user_votes_result else 0
            
            has_voted_all = user_votes >= total_questions
          # اضافه کردن دکمه ترین‌ها با متن مناسب
        if has_voted_all:
            keyboard.append([InlineKeyboardButton(f"🏆 نتایج ترین‌های {season_name}", callback_data="top_results^")])
        else:
            keyboard.append([InlineKeyboardButton(f"🏆 ترین‌های {season_name}!", callback_data="top_vote^")])
    
    # بررسی وضعیت فعال/غیرفعال بودن قابلیت‌های هوش مصنوعی
    ai_features_enabled = execute_db_query("SELECT value FROM settings WHERE key='ai_features_enabled'", fetchone=True)
    ai_features_enabled = ai_features_enabled[0] if ai_features_enabled else "1"  # پیش‌فرض: فعال
    
    # فقط اگر قابلیت‌های هوش مصنوعی فعال باشند یا کاربر ادمین باشد، دکمه را نمایش بده
    if ai_features_enabled == "1" or (user_id and execute_db_query("SELECT role FROM admins WHERE user_id=?", (user_id,), fetchone=True)):
        keyboard.append([InlineKeyboardButton("🤖 دستیار هوشمند", callback_data="ai_chat^")])
    
    keyboard += [
        [InlineKeyboardButton("» پروفایل شما", callback_data="userprofile^"), InlineKeyboardButton("ردپای امتیازات", callback_data="historypoints^")],
        [InlineKeyboardButton("» راهنما", callback_data="help^"), InlineKeyboardButton("» پشتیبانی", url=config.SUPPORT_USERNAME)]
    ]
    
    # اضافه کردن دکمه پنل ادمین برای کاربران ادمین
    if user_id:
        admin_result = execute_db_query("SELECT role, permissions FROM admins WHERE user_id=?", (user_id,), fetchone=True)
        if admin_result:
            role, permissions = admin_result
            if role == 'god' or permissions:
                keyboard.append([InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel^")])
    
    return InlineKeyboardMarkup(keyboard)

def create_back_button(callback_data="userpanel^"):
    """ایجاد دکمه بازگشت"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("» بازگشت", callback_data=callback_data)]])

def create_user_list_keyboard(users, callback_prefix, back_button="userpanel^"):
    """ایجاد کیبورد لیست کاربران"""
    keyboard = []
    row = []
    
    for i, user in enumerate(users):
        user_id = user[0] if isinstance(user, (list, tuple)) else user.user_id
        user_name = user[1] if isinstance(user, (list, tuple)) else user.name
        
        row.append(InlineKeyboardButton(f"{i+1}- {user_name}", callback_data=f"{callback_prefix}^{user_id}"))
        
        if len(row) == 2 or i == len(users) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("» بازگشت", callback_data=back_button)])
    return InlineKeyboardMarkup(keyboard)

def create_admin_panel_keyboard(user_id):
    """ایجاد کیبورد پنل ادمین"""
    # لیست دسترسی‌های ادمین
    ADMIN_PERMISSIONS = [
        ("admin_users", "مدیریت کاربران"),
        ("admin_transactions", "مدیریت تراکنش"),
        ("admin_stats", "آمار و گزارشات"),
        ("manage_admins", "مدیریت ادمین‌ها"),
        ("manage_questions", "مدیریت سوالات ترین‌ها"),
    ]
    
    admin_result = execute_db_query("SELECT role, permissions FROM admins WHERE user_id=?", (user_id,), fetchone=True)
    if not admin_result:
        return None
    
    role, permissions = admin_result
    allowed = []
    if role == 'god':
        allowed = [p[0] for p in ADMIN_PERMISSIONS]
    elif permissions:
        allowed = [p.strip() for p in permissions.split(",") if p.strip()]
    
    keyboard = []
    if "admin_users" in allowed:
        keyboard.append([InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users^")])
    if "admin_transactions" in allowed:
        keyboard.append([InlineKeyboardButton("💰 مدیریت تراکنش‌ها", callback_data="admin_transactions^")])
    if "admin_stats" in allowed:
        keyboard.append([InlineKeyboardButton("📊 آمار و گزارشات", callback_data="admin_stats^")])
    if "manage_admins" in allowed:
        keyboard.append([InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="manage_admins^")])
    if "admin_users" in allowed:  # استفاده از همان دسترسی مدیریت کاربران
        keyboard.append([InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast_menu^")])
    if "manage_questions" in allowed:
        keyboard.append([InlineKeyboardButton("🏆 مدیریت سوالات ترین‌ها", callback_data="manage_top_questions^")])
        keyboard.append([InlineKeyboardButton("🔄 مدیریت فصل‌ها", callback_data="manage_seasons^")])
    if "admin_stats" in allowed:
        keyboard.append([InlineKeyboardButton("🧠 تحلیل با هوش مصنوعی", callback_data="ai_analysis^")])
    
    # اضافه کردن گزینه تنظیمات نمایش کاربران
    if "admin_users" in allowed:
        # بررسی وضعیت فعلی نمایش لیست کاربران
        show_all_users = execute_db_query("SELECT value FROM settings WHERE key='show_all_users'", fetchone=True)
        show_all_users = show_all_users[0] if show_all_users else "0"
        button_text = "🔄 غیرفعال کردن نمایش کاربران" if show_all_users == "1" else "🔄 فعال کردن نمایش کاربران"
        keyboard.append([InlineKeyboardButton(button_text, callback_data="toggle_show_users^")])
    
    # اضافه کردن گزینه فعال/غیرفعال کردن قابلیت‌های هوش مصنوعی
    if "admin_stats" in allowed:
        # بررسی وضعیت فعلی قابلیت‌های هوش مصنوعی
        ai_features_enabled = execute_db_query("SELECT value FROM settings WHERE key='ai_features_enabled'", fetchone=True)
        ai_features_enabled = ai_features_enabled[0] if ai_features_enabled else "1"  # پیش‌فرض: فعال
        button_text = "🤖 غیرفعال کردن هوش مصنوعی" if ai_features_enabled == "1" else "🤖 فعال کردن هوش مصنوعی"
        keyboard.append([InlineKeyboardButton(button_text, callback_data="toggle_ai_features^")])
    
    keyboard.append([InlineKeyboardButton("» بازگشت به منوی اصلی", callback_data="userpanel^")])
    
    return InlineKeyboardMarkup(keyboard)

def format_transaction_text(transaction, is_given=True):
    """فرمت کردن متن تراکنش"""
    amount = transaction[0]
    user_name = transaction[2] if len(transaction) > 2 else "نامشخص"
    reason = transaction[3] if len(transaction) > 3 else "بدون دلیل"
    created_at = transaction[4] if len(transaction) > 4 else ""
    
    if is_given:
        return f"💰 {amount} امتیاز به {user_name}\n📝 {reason}\n📅 {created_at}"
    else:
        return f"💰 {amount} امتیاز از {user_name}\n📝 {reason}\n📅 {created_at}"
