"""
ماژول هوش مصنوعی برای ربات کادوس
این ماژول شامل کلاس‌ها و توابع مورد نیاز برای ارتباط با سرویس‌های هوش مصنوعی مختلف است
از جمله OpenAI و Google Gemini
"""

import logging
import config
import sqlite3
from openai import OpenAI
from abc import ABC, abstractmethod

# متغیر مشخص کننده در دسترس بودن ماژول هوش مصنوعی
AI_MODULE_AVAILABLE = True
import traceback
import datetime
import time
# وارد کردن توابع مدیریت دیتابیس
from ..database import db_utils

# تنظیم لاگر
logger = logging.getLogger(__name__)

class AIModel(ABC):
    """کلاس پایه برای مدل‌های هوش مصنوعی"""
    
    @abstractmethod
    def get_completion(self, prompt, system_message=None):
        """دریافت پاسخ از مدل هوش مصنوعی"""
        pass

class OpenAIModel(AIModel):
    """کلاس مدیریت ارتباط با سرویس OpenAI"""
    
    def __init__(self, api_key=None, model="gpt-3.5-turbo"):
        """راه‌اندازی کلاینت OpenAI"""
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
    
    def get_completion(self, prompt, system_message="You are a helpful assistant."):
        """
        دریافت پاسخ از مدل OpenAI
        
        Args:
            prompt (str): پیام ورودی کاربر
            system_message (str): پیام سیستم برای تنظیم رفتار مدل
            
        Returns:
            str: پاسخ دریافتی از مدل
        """
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"خطا در دریافت پاسخ از OpenAI: {e}")
            return f"متأسفانه در دریافت پاسخ از هوش مصنوعی خطایی رخ داد: {e}"

class GeminiModel(AIModel):
    """کلاس مدیریت ارتباط با سرویس Google Gemini از طریق رابط OpenAI"""
    
    def __init__(self, api_key=None, model="gemini-2.0-flash"):
        """راه‌اندازی کلاینت Gemini با استفاده از OpenAI Client"""
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=config.GEMINI_BASE_URL
        )
    
    def get_completion(self, prompt, system_message="You are a helpful assistant."):
        """
        دریافت پاسخ از مدل Gemini
        
        Args:
            prompt (str): پیام ورودی کاربر
            system_message (str): پیام سیستم برای تنظیم رفتار مدل
            
        Returns:
            str: پاسخ دریافتی از مدل
        """
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            # تلاش اول
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    logger.warning(f"خطا در دریافت پاسخ از Gemini (تلاش {retry_count+1}/{max_retries}): {error_msg}")
                    
                    # اگر خطای بار اضافی سرور بود، زمان انتظار را افزایش دهیم
                    if "overloaded" in error_msg.lower() or "503" in error_msg or "unavailable" in error_msg.lower():
                        wait_time = (retry_count + 1) * 2  # 2، 4، 6 ثانیه
                        logger.info(f"سرور Gemini دچار بار اضافی است. انتظار باید {wait_time} ثانیه...")
                        time.sleep(wait_time)
                    else:
                        # برای سایر خطاها، انتظار کوتاه‌تر
                        time.sleep(1)
                    
                    retry_count += 1
            
            # اگر تمام تلاش‌ها ناموفق بود، خطای آخر را لاگ کنیم
            logger.error(f"تلاش‌های متعدد برای دریافت پاسخ از Gemini ناموفق بود: {last_error}")
            
            # بررسی نوع خطا برای ارائه پیام مناسب به کاربر
            error_msg = str(last_error).lower()
            
            # پیام خطای مناسب بر اساس نوع خطا
            if "overloaded" in error_msg or "503" in error_msg or "unavailable" in error_msg:
                user_message = "متأسفانه در حال حاضر سرویس هوش مصنوعی Google Gemini با ترافیک بالا مواجه است. لطفاً چند دقیقه دیگر دوباره امتحان کنید."
            elif "quota" in error_msg or "rate limit" in error_msg:
                user_message = "متأسفانه سهمیه استفاده از Google Gemini به اتمام رسیده است. لطفاً با ادمین تماس بگیرید."
            elif "invalid" in error_msg and "key" in error_msg:
                user_message = "خطا در کلید API هوش مصنوعی. لطفاً به ادمین سیستم اطلاع دهید."
            else:
                user_message = "متأسفانه در دریافت پاسخ از Google Gemini خطایی رخ داد. لطفاً دوباره تلاش کنید."
            
            # سعی می‌کنیم از OpenAI استفاده کنیم به عنوان پشتیبان
            if hasattr(config, 'OPENAI_API_KEY') and config.OPENAI_API_KEY and config.OPENAI_API_KEY != "YOUR_OPENAI_API_KEY":
                logger.info("در حال تغییر به مدل OpenAI به عنوان پشتیبان...")
                try:
                    openai_model = OpenAIModel()
                    return openai_model.get_completion(prompt, system_message)
                except Exception as openai_error:
                    logger.error(f"خطا در استفاده از OpenAI به عنوان پشتیبان: {openai_error}")
                    return f"{user_message}\n\nهمچنین تلاش برای استفاده از مدل پشتیبان نیز ناموفق بود."
            
            return user_message
        except Exception as e:
            logger.error(f"خطا در دریافت پاسخ از Gemini: {e}")
            traceback.print_exc()
            return f"متأسفانه در دریافت پاسخ از هوش مصنوعی خطایی رخ داد: {e}"

# فانکشن کمکی برای دریافت نمونه مدل هوش مصنوعی
def get_ai_model(model_type="gemini"):
    """
    دریافت مدل هوش مصنوعی بر اساس نوع مشخص شده
    
    Args:
        model_type (str): نوع مدل هوش مصنوعی ("openai" یا "gemini")
        
    Returns:
        AIModel: نمونه‌ای از کلاس مدل هوش مصنوعی
    """
    if model_type.lower() == "openai":
        return OpenAIModel()
    elif model_type.lower() == "gemini":
        return GeminiModel()
    else:
        logger.warning(f"نوع مدل نامعتبر: {model_type}. استفاده از Gemini به صورت پیش‌فرض.")
        return GeminiModel()

# توابع تحلیل داده و پروفایل کاربر
def get_user_data(user_id):
    """دریافت اطلاعات کاربر از دیتابیس"""
    conn = None
    try:
        # ایجاد اتصال جدید به دیتابیس
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # دریافت اطلاعات اصلی کاربر
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = c.fetchone()
        
        if not user_data:
            return None
        
        # دریافت تراکنش‌ها (امتیازات داده شده)
        c.execute("""
            SELECT t.*, u.name AS to_name 
            FROM transactions t 
            JOIN users u ON t.touser = u.user_id 
            WHERE t.user_id = ? 
            ORDER BY t.created_at DESC LIMIT 20
        """, (user_id,))
        given_points = c.fetchall()
        
        # دریافت تراکنش‌ها (امتیازات دریافت شده)
        c.execute("""
            SELECT t.*, u.name AS from_name 
            FROM transactions t 
            JOIN users u ON t.user_id = u.user_id 
            WHERE t.touser = ? 
            ORDER BY t.created_at DESC LIMIT 20
        """, (user_id,))
        received_points = c.fetchall()
        
        # دریافت رای‌های ترین‌ها
        c.execute("""
            SELECT tv.*, tq.text AS question_text, u.name AS voted_name
            FROM top_votes tv
            JOIN top_questions tq ON tv.question_id = tq.question_id
            JOIN users u ON tv.voted_for_user_id = u.user_id
            WHERE tv.user_id = ?
            ORDER BY tv.vote_time DESC
        """, (user_id,))
        top_votes = c.fetchall()
        
        # چه کسانی به این کاربر رای داده‌اند؟
        c.execute("""
            SELECT tv.*, tq.text AS question_text, u.name AS voter_name
            FROM top_votes tv
            JOIN top_questions tq ON tv.question_id = tq.question_id
            JOIN users u ON tv.user_id = u.user_id
            WHERE tv.voted_for_user_id = ?
            ORDER BY tv.vote_time DESC
        """, (user_id,))
        received_votes = c.fetchall()
        
        # تجمیع داده‌های امتیازدهی
        received_from = {}
        given_to = {}
        
        for p in received_points:
            from_name = p['from_name'] if 'from_name' in p else 'ناشناس'
            amount = p['amount'] if 'amount' in p else 0
            if from_name in received_from:
                received_from[from_name] += amount
            else:
                received_from[from_name] = amount
                
        for p in given_points:
            to_name = p['to_name'] if 'to_name' in p else 'ناشناس'
            amount = p['amount'] if 'amount' in p else 0
            if to_name in given_to:
                given_to[to_name] += amount
            else:
                given_to[to_name] = amount
        
        # تبدیل user_data به دیکشنری قابل استفاده
        user_dict = dict(user_data)
        # اضافه کردن فیلدهای مورد نیاز
        total_received = sum([p['amount'] for p in received_points]) if received_points else 0
        total_given = sum([p['amount'] for p in given_points]) if given_points else 0
        
        result = {
            'user_id': user_dict.get('user_id', user_id),
            'name': user_dict.get('name', 'کاربر'),
            'username': user_dict.get('username', ''),
            'balance': user_dict.get('balance', 0),
            'total_received': total_received,
            'total_given': total_given,
            'transactions': given_points,
            'received_from': received_from,
            'given_to': given_to,
            'top_votes': top_votes,
            'received_votes': received_votes
        }
        
        return result
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات کاربر: {e}")
        traceback.print_exc()  # چاپ جزئیات خطا در لاگ
        return None
    finally:
        # حتما اتصال دیتابیس را ببندیم، حتی اگر خطایی رخ داده باشد
        if conn:
            conn.close()

def get_user_perspective(user_id, season_id=None, force_update=False, is_admin=False):
    """
    تحلیل زاویه دید دیگران نسبت به کاربر
    
    Args:
        user_id (int): شناسه کاربر
        season_id (int, optional): شناسه فصل مورد نظر
        force_update (bool, optional): آیا دیدگاه قبلی نادیده گرفته شود
        is_admin (bool, optional): آیا درخواست از طرف ادمین است
        
    Returns:
        str: متن تحلیلی دیدگاه دیگران
    """
    conn = None
    try:
        # بررسی آیا کاربر وجود دارد
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return "کاربر مورد نظر یافت نشد."
        
        # اگر فصل مشخص نشده، از فصل فعال استفاده کن
        if not season_id:
            c.execute("SELECT id, name FROM season WHERE is_active = 1")
            season = c.fetchone()
            if season:
                season_id = season['id']
                season_name = season['name']
            else:
                return "در حال حاضر هیچ فصل فعالی وجود ندارد."
        else:
            # دریافت نام فصل
            c.execute("SELECT name FROM season WHERE id = ?", (season_id,))
            season_data = c.fetchone()
            if season_data:
                season_name = season_data['name']
            else:
                season_name = "نامشخص"
        
        # بررسی آیا قبلاً دیدگاهی ایجاد شده
        c.execute("""
            SELECT perspective, created_at FROM user_perspectives 
            WHERE user_id = ? AND season_id = ?
        """, (user_id, season_id))
        
        existing = c.fetchone()
        current_time = datetime.datetime.now()
        
        # اگر دیدگاه قبلی وجود دارد و نیاز به به‌روزرسانی نیست
        if existing and not force_update:
            # بررسی تاریخ ایجاد (هر 24 ساعت به‌روزرسانی)
            created_time = datetime.datetime.strptime(existing['created_at'], "%Y-%m-%d %H:%M:%S")
            # برای ادمین‌ها زمان را 1 ساعت در نظر بگیر
            cache_hours = 1 if is_admin else 24
            
            if (current_time - created_time).total_seconds() < cache_hours * 3600:
                return existing['perspective']
        
        # دریافت اطلاعات کاربر
        user_name = user['name']
        
        # دریافت تمام امتیازات دریافتی کاربر در فصل مشخص شده
        c.execute("""
            SELECT t.amount, t.reason, u.name AS from_name, t.created_at
                FROM transactions t
                JOIN users u ON t.user_id = u.user_id
            WHERE t.touser = ? AND t.season_id = ?
                ORDER BY t.created_at DESC
        """, (user_id, season_id))
        
        received_points = c.fetchall()
        
        # دریافت امتیازات داده شده توسط کاربر
        c.execute("""
            SELECT t.amount, t.reason, u.name AS to_name, t.created_at
            FROM transactions t
            JOIN users u ON t.touser = u.user_id
            WHERE t.user_id = ? AND t.season_id = ?
            ORDER BY t.created_at DESC
        """, (user_id, season_id))
        
        given_points = c.fetchall()
        
        # دریافت رأی‌های ترین‌ها برای کاربر
        c.execute("""
            SELECT q.text, COUNT(*) as vote_count
            FROM top_votes v
            JOIN top_questions q ON v.question_id = q.question_id
            WHERE v.voted_for_user_id = ? AND v.season_id = ?
            GROUP BY q.question_id
            ORDER BY vote_count DESC
        """, (user_id, season_id))
        
        top_votes = c.fetchall()
        
        # جمع‌آوری اطلاعات برای ارسال به هوش مصنوعی
        prompt = f"""
        لطفاً یک تحلیل شخصیتی و زاویه دید دیگران را برای فردی به نام '{user_name}' ارائه دهید.
        
        اطلاعات دریافتی:
        
        1. امتیازات دریافتی:
        """
        
        # افزودن امتیازات دریافتی
        if received_points:
            for point in received_points:
                prompt += f"- {point['amount']} امتیاز از {point['from_name']} به دلیل: {point['reason']}\n"
        else:
            prompt += "- هیچ امتیازی دریافت نکرده است.\n"
        
        prompt += "\n2. امتیازات داده شده:\n"
        
        # افزودن امتیازات داده شده
        if given_points:
            for point in given_points:
                prompt += f"- {point['amount']} امتیاز به {point['to_name']} به دلیل: {point['reason']}\n"
        else:
            prompt += "- هیچ امتیازی نداده است.\n"
        
        prompt += "\n3. رأی‌های ترین‌ها:\n"
        
        # افزودن رأی‌های ترین‌ها
        if top_votes:
            for vote in top_votes:
                prompt += f"- {vote['vote_count']} نفر به او در دسته '{vote['text']}' رأی داده‌اند.\n"
        else:
            prompt += "- هیچ رأیی در بخش ترین‌ها دریافت نکرده است.\n"
        
        prompt += f"""
        با توجه به این اطلاعات، لطفاً یک تحلیل جامع و دقیق از زاویه دید دیگران نسبت به '{user_name}' ارائه دهید.
        این تحلیل باید شامل:
        
        1. خلاصه‌ای از تصویر کلی فرد از نگاه دیگران
        2. نقاط قوت و ویژگی‌های مثبت فرد
        3. زمینه‌هایی که می‌تواند در آن بهبود یابد
        4. مشارکت و تأثیر فرد در جامعه
        
        پاسخ باید به زبان فارسی، صمیمی و غیررسمی باشد. از اطلاعات دقیق ارائه شده استفاده کنید و از بیان کلیشه‌ای اجتناب کنید.
        پاسخ نهایی را حداکثر در 4 پاراگراف ارائه دهید.
        """
        
        # استفاده از هوش مصنوعی برای تحلیل (فقط از Gemini استفاده کن)
        model = get_ai_model("gemini")
        system_message = """
        تو یک سیستم تحلیل شخصیت هوشمند هستی. وظیفه تو ارائه تحلیل‌های دقیق، سازنده و مفید از دیدگاه دیگران به یک فرد است.
        تحلیل‌های تو باید صادقانه و در عین حال مثبت و سازنده باشد و به شخص کمک کند تا دیدگاه دیگران را نسبت به خود بهتر درک کند.
        پاسخ‌های تو باید به زبان فارسی روان، صمیمی و غیررسمی باشد.
        """
        
        # دریافت پاسخ از مدل
        perspective = model.get_completion(prompt, system_message)
        
        # ذخیره نتیجه در دیتابیس
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # اگر قبلاً وجود داشته، به‌روزرسانی کن
        if existing:
            c.execute("""
                UPDATE user_perspectives
                SET perspective = ?, created_at = ?
                WHERE user_id = ? AND season_id = ?
            """, (perspective, current_time_str, user_id, season_id))
        else:
            # در غیر این صورت، رکورد جدید ایجاد کن
            c.execute("""
                INSERT INTO user_perspectives (user_id, season_id, perspective, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, season_id, perspective, current_time_str))
        
        conn.commit()
        return perspective
        
    except Exception as e:
        logger.error(f"خطا در دریافت زاویه دید کاربر: {e}")
        traceback.print_exc()
        return "متأسفانه در دریافت زاویه دید کاربر خطایی رخ داد. لطفاً دوباره تلاش کنید."
    finally:
        if conn:
            conn.close()

def save_user_perspective(user_id, season_id, perspective_text):
    """ذخیره زاویه دید کاربر در دیتابیس برای استفاده مجدد"""
    conn = None
    try:
        # ایجاد اتصال جدید به دیتابیس
        conn = db_utils.get_db_connection()
        c = conn.cursor()
        
        # بررسی وجود جدول ai_user_perspectives
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_user_perspectives'")
        if not c.fetchone():
            # ایجاد جدول اگر وجود ندارد
            c.execute("""
                CREATE TABLE ai_user_perspectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    season_id INTEGER,
                    perspective_text TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        
        # ذخیره نتیجه تحلیل
        c.execute("""
            INSERT INTO ai_user_perspectives (user_id, season_id, perspective_text)
            VALUES (?, ?, ?)
        """, (user_id, season_id or 0, perspective_text))
        
        conn.commit()
    except Exception as e:
        logger.error(f"خطا در ذخیره زاویه دید کاربر: {e}")
        traceback.print_exc()
    finally:
        # حتما اتصال دیتابیس را ببندیم، حتی اگر خطایی رخ داده باشد
        if conn:
            conn.close()

def generate_user_profile(user_id, force_update=False, is_admin=False):
    """
    ایجاد پروفایل هوشمند برای کاربر با استفاده از هوش مصنوعی
    
    Args:
        user_id (int): شناسه کاربر
        force_update (bool, optional): آیا پروفایل قبلی نادیده گرفته شود
        is_admin (bool, optional): آیا درخواست از طرف ادمین است
        
    Returns:
        str: متن پروفایل هوشمند
    """
    conn = None
    try:
        # بررسی آیا کاربر وجود دارد
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return "کاربر مورد نظر یافت نشد."
        
        # بررسی آیا قبلاً پروفایلی ایجاد شده
        c.execute("""
            SELECT profile_text, created_at FROM user_profiles 
            WHERE user_id = ?
        """, (user_id,))
        
        existing = c.fetchone()
        current_time = datetime.datetime.now()
        
        # اگر پروفایل قبلی وجود دارد و نیاز به به‌روزرسانی نیست
        if existing and not force_update:
            # بررسی تاریخ ایجاد (هر 24 ساعت به‌روزرسانی)
            created_time = datetime.datetime.strptime(existing['created_at'], "%Y-%m-%d %H:%M:%S")
            # برای ادمین‌ها زمان را 1 ساعت در نظر بگیر
            cache_hours = 1 if is_admin else 24
            
            if (current_time - created_time).total_seconds() < cache_hours * 3600:
                return existing['profile_text']
        
        # دریافت داده‌های کاربر
        user_data = get_user_data(user_id)
        if not user_data:
            # اگر اطلاعات کاربر دریافت نشد، از اطلاعات پایه استفاده کنیم
            user_name = dict(user).get('name', 'کاربر')
            return f"اطلاعات کافی برای ایجاد پروفایل هوشمند {user_name} وجود ندارد. لطفاً بعد از انجام چند تراکنش دوباره تلاش کنید."
        
        # ایجاد پرامپت برای مدل هوش مصنوعی
        prompt = f"""
        لطفاً یک پروفایل هوشمند برای کاربری با نام '{user_data['name']}' بر اساس اطلاعات زیر ایجاد کنید:
        
        اطلاعات کاربر:
        - نام: {user_data['name']}
        - یوزرنیم: {user_data['username'] or 'ندارد'}
        - امتیاز فعلی: {user_data['balance']}
        - مجموع امتیازات دریافتی: {user_data['total_received']}
        - مجموع امتیازات داده شده: {user_data['total_given']}
        - تعداد تراکنش‌های انجام شده: {len(user_data['transactions']) if 'transactions' in user_data else 0}
        
        نمونه‌هایی از دلایل امتیاز دادن:
        """
        
        # افزودن نمونه‌هایی از دلایل امتیاز دادن
        if user_data.get('transactions', []):
            for i, tx in enumerate(user_data['transactions'][:5]):
                reason = tx['reason'] if 'reason' in tx else 'بدون دلیل'
                prompt += f"- {reason}\n"
        else:
            prompt += "- هیچ تراکنشی وجود ندارد\n"
        
        prompt += "\nآمار دریافت امتیاز:\n"
        
        # افزودن آمار دریافت امتیاز از هر کاربر
        if user_data.get('received_from', {}):
            for person, amount in user_data['received_from'].items():
                prompt += f"- از {person}: {amount} امتیاز\n"
        else:
            prompt += "- هیچ امتیازی دریافت نشده است\n"
        
        prompt += "\nآمار دادن امتیاز:\n"
        
        # افزودن آمار دادن امتیاز به هر کاربر
        if user_data.get('given_to', {}):
            for person, amount in user_data['given_to'].items():
                prompt += f"- به {person}: {amount} امتیاز\n"
        else:
            prompt += "- هیچ امتیازی داده نشده است\n"
        
        # اضافه کردن اطلاعات رأی‌های ترین‌ها
        prompt += "\nآمار رأی‌های ترین‌ها:\n"
        
        # دریافت رأی‌های ترین‌ها برای کاربر
        c.execute("""
            SELECT q.text as question_text, COUNT(*) as vote_count
            FROM top_votes v
            JOIN top_questions q ON v.question_id = q.question_id
            WHERE v.voted_for_user_id = ?
            GROUP BY q.question_id
            ORDER BY vote_count DESC
        """, (user_id,))
        
        top_votes = c.fetchall()
        
        if top_votes:
            for vote in top_votes:
                prompt += f"- {vote['vote_count']} رأی در '{vote['question_text']}'\n"
        else:
            prompt += "- هیچ رأیی در بخش ترین‌ها ندارد\n"
        
        prompt += f"""
        با توجه به این اطلاعات، لطفاً یک پروفایل هوشمند جامع برای '{user_data['name']}' ایجاد کنید.
        این پروفایل باید شامل:
        
        1. تحلیلی از سبک تعامل و مشارکت کاربر
        2. نقاط قوت و ویژگی‌های برجسته
        3. علایق و زمینه‌های فعالیت (بر اساس دلایل امتیازدهی)
        4. تأثیر کاربر در جامعه و ارتباط با دیگران
        
        پاسخ باید به زبان فارسی، صمیمی و غیررسمی باشد. سعی کنید پروفایل را طوری بنویسید که منعکس‌کننده شخصیت واقعی کاربر باشد.
        پاسخ نهایی را حداکثر در 4 پاراگراف ارائه دهید.
        """
        
        # استفاده از هوش مصنوعی برای ایجاد پروفایل (فقط از Gemini استفاده کن)
        model = get_ai_model("gemini")
        system_message = """
        تو یک سیستم تحلیل شخصیت هوشمند هستی. وظیفه تو ایجاد پروفایل‌های دقیق، جذاب و شخصی‌سازی شده برای کاربران است.
        پروفایل‌های تو باید صادقانه، مثبت و الهام‌بخش باشد و به کاربر نگاهی جدید به خودش بدهد.
        پاسخ‌های تو باید به زبان فارسی روان، صمیمی و غیررسمی باشد.
        """
        
        # دریافت پاسخ از مدل
        profile_text = model.get_completion(prompt, system_message)
        
        # ذخیره نتیجه در دیتابیس
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # اگر قبلاً وجود داشته، به‌روزرسانی کن
        if existing:
            c.execute("""
                UPDATE user_profiles
                SET profile_text = ?, created_at = ?
                    WHERE user_id = ?
            """, (profile_text, current_time_str, user_id))
        else:
            c.execute("""
                INSERT INTO user_profiles (user_id, profile_text, created_at)
                VALUES (?, ?, ?)
            """, (user_id, profile_text, current_time_str))
            
            conn.commit()
        return profile_text
        
    except Exception as e:
        logger.error(f"خطا در ایجاد پروفایل هوشمند: {e}")
        traceback.print_exc()
        return "متأسفانه در ایجاد پروفایل هوشمند خطایی رخ داد. لطفاً دوباره تلاش کنید."
    finally:
        if conn:
            conn.close()

def is_admin(user_id):
    """بررسی اینکه آیا کاربر ادمین است یا خیر"""
    try:
        admin = db_utils.execute_db_query(
            "SELECT role FROM admins WHERE user_id = ?", 
            (user_id,), 
            fetchone=True
        )
        
        return admin is not None
    except Exception as e:
        logger.error(f"خطا در بررسی وضعیت ادمین: {e}")
        return False

def analyze_admin_data(season_id=None, force_update=True):
    """تحلیل داده‌ها برای ادمین
    
    Args:
        season_id (int, optional): شناسه فصل
        force_update (bool, optional): همیشه آنالیز جدید انجام شود (برای ادمین پیش‌فرض true است)
        
    Returns:
        str: متن تحلیل برای ادمین
    """
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # تعیین شرط فصل
        season_condition = ""
        if season_id:
            season_condition = f"AND season_id = {season_id}"
            
            # دریافت اطلاعات فصل
            c.execute("SELECT name FROM season WHERE id = ?", (season_id,))
            season = c.fetchone()
            season_name = season['name'] if season else "نامشخص"
        else:
            # دریافت فصل فعال
            c.execute("SELECT id, name FROM season WHERE is_active = 1")
            season = c.fetchone()
            if season:
                season_id = season['id']
                season_name = season['name']
                season_condition = f"AND season_id = {season_id}"
            else:
                season_name = "همه فصل‌ها"
        
        # تعداد کل تراکنش‌ها
        c.execute(f"SELECT COUNT(*) as count FROM transactions WHERE 1=1 {season_condition}")
        total_transactions = c.fetchone()['count']
        
        # میانگین امتیازات
        c.execute(f"SELECT AVG(amount) as avg_amount FROM transactions WHERE 1=1 {season_condition}")
        avg_amount = c.fetchone()['avg_amount']
        
        # کاربرانی که بیشترین امتیاز را داده‌اند
        c.execute(f"""
            SELECT u.name, COUNT(*) as count, SUM(t.amount) as total
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE 1=1 {season_condition}
            GROUP BY t.user_id
            ORDER BY total DESC
            LIMIT 5
        """)
        top_givers = c.fetchall()
        
        # کاربرانی که بیشترین امتیاز را دریافت کرده‌اند
        c.execute(f"""
            SELECT u.name, COUNT(*) as count, SUM(t.amount) as total
            FROM transactions t
            JOIN users u ON t.touser = u.user_id
            WHERE 1=1 {season_condition}
            GROUP BY t.touser
            ORDER BY total DESC
            LIMIT 5
        """)
        top_receivers = c.fetchall()
        
        # بررسی الگوهای متقابل (کاربرانی که به هم امتیاز می‌دهند)
        c.execute(f"""
            SELECT 
                u1.name as from_name, 
                u2.name as to_name, 
                COUNT(*) as transaction_count,
                SUM(t1.amount) as total_amount
            FROM 
                transactions t1
            JOIN 
                users u1 ON t1.user_id = u1.user_id
            JOIN 
                users u2 ON t1.touser = u2.user_id
            WHERE 
                EXISTS (
                    SELECT 1 FROM transactions t2
                    WHERE t2.user_id = t1.touser
                    AND t2.touser = t1.user_id
                    {season_condition}
                )
                {season_condition}
            GROUP BY 
                t1.user_id, t1.touser
            HAVING 
                transaction_count >= 2
            ORDER BY 
                total_amount DESC
            LIMIT 10
        """)
        mutual_transactions = c.fetchall()
        
        # کلمات پرتکرار در دلایل
        c.execute(f"""
            SELECT reason FROM transactions 
            WHERE reason IS NOT NULL AND reason != '' {season_condition}
        """)
        reasons = c.fetchall()
        
        # تهیه پرامپت برای هوش مصنوعی
        prompt = f"""
        بر اساس اطلاعات زیر، یک تحلیل جامع از وضعیت سیستم امتیازدهی در فصل {season_name} ارائه بده.
        
        اطلاعات کلی:
        - تعداد کل تراکنش‌ها: {total_transactions}
        - میانگین امتیازات داده شده: {avg_amount}
        
        کاربرانی که بیشترین امتیاز را داده‌اند:
        """
        
        for giver in top_givers:
            prompt += f"- {giver['name']}: {giver['total']} امتیاز در {giver['count']} تراکنش\n"
        
        prompt += "\nکاربرانی که بیشترین امتیاز را دریافت کرده‌اند:\n"
        for receiver in top_receivers:
            prompt += f"- {receiver['name']}: {receiver['total']} امتیاز در {receiver['count']} تراکنش\n"
        
        prompt += "\nالگوهای امتیازدهی متقابل (ممکن است نشان‌دهنده تقلب باشد):\n"
        for mutual in mutual_transactions:
            prompt += f"- {mutual['from_name']} و {mutual['to_name']}: {mutual['transaction_count']} تراکنش متقابل با مجموع {mutual['total_amount']} امتیاز\n"
        
        prompt += "\nدلایل امتیازدهی:\n"
        all_reasons = " ".join([r['reason'] for r in reasons])
        prompt += all_reasons[:1000] + "...\n\n"  # محدود کردن متن برای جلوگیری از طولانی شدن پرامپت
        
        prompt += """
        لطفاً یک تحلیل جامع ارائه بده که شامل این بخش‌ها باشد:
        1. وضعیت کلی سیستم امتیازدهی (با ایموجی 📊)
        2. الگوهای مثبت (کاربرانی که به درستی از سیستم استفاده می‌کنند) (با ایموجی ✅)
        3. الگوهای منفی یا مشکوک (احتمال تقلب یا سوءاستفاده) (با ایموجی ⚠️)
        4. روندهای کلی و چشم‌انداز (با ایموجی 🔍)
        5. پیشنهادات برای بهبود سیستم (با ایموجی 💡)
        
        هر بخش را با ایموجی مناسب شروع کن و از علامت‌های ستاره (**) یا فرمت‌های markdown استفاده نکن.
        خروجی باید به زبان فارسی محاوره‌ای، صمیمی و مودبانه باشد. 
        از کلمات و جملات رسمی و کتابی استفاده نکن.
        اگر نشانه‌های تقلب وجود دارد، آن را به صورت محترمانه بیان کن.
        """
          # دریافت پاسخ از هوش مصنوعی
        ai_model = get_ai_model("gemini")
        system_message = """تو یک تحلیلگر داده با لحن دوستانه و صمیمی هستی. وظیفه‌ات ارائه تحلیل‌های کاربردی و قابل فهم از داده‌هاست. 
از زبان فارسی محاوره‌ای و صمیمی استفاده کن. خیلی رسمی و کتابی صحبت نکن.
از ایموجی‌های مناسب برای جدا کردن بخش‌ها استفاده کن و از علامت‌های ** یا markdown استفاده نکن."""
        response = ai_model.get_completion(prompt, system_message)
        
        return response
    except Exception as e:
        logger.error(f"خطا در تحلیل داده‌ها برای ادمین: {e}")
        return f"متأسفانه در تحلیل داده‌ها خطایی رخ داد: {e}"
    finally:
        # اطمینان از بسته شدن اتصال
        if conn:
            conn.close()

# مثال استفاده
if __name__ == "__main__":
    # تست مدل OpenAI
    openai_model = get_ai_model("openai")
    openai_response = openai_model.get_completion("سلام، حال شما چطور است؟")
    print(f"پاسخ OpenAI: {openai_response}")
    
    # تست مدل Gemini
    gemini_model = get_ai_model("gemini")
    gemini_response = gemini_model.get_completion("سلام، حال شما چطور است؟")
    print(f"پاسخ Gemini: {gemini_response}")
