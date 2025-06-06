# 🏆 ربات امتیازدهی کودوز (Kudos-BOT)

ربات تلگرامی پیشرفته برای مدیریت سیستم امتیازدهی و ارزیابی عملکرد در سازمان‌ها و تیم‌ها

## ✨ ویژگی‌های اصلی

- 🎯 **سیستم امتیازدهی هوشمند**: امتیازدهی به همکاران با ثبت دلیل
- 🏆 **رای‌گیری ترین‌ها**: سیستم رای‌گیری برای انتخاب برترین‌ها در دسته‌های مختلف
- 🎁 **ارسال کارت هدیه**: ایجاد و ارسال کارت‌های هدیه زیبا
- 🤖 **هوش مصنوعی**: تحلیل شخصیت و زاویه دید دیگران با AI
- 📊 **گزارش‌گیری پیشرفته**: آمار و گزارش‌های جامع برای ادمین‌ها
- 🔄 **مدیریت فصول**: امکان مدیریت چندین دوره امتیازدهی
- 👥 **مدیریت کاربران**: سیستم تایید کاربران و مدیریت دسترسی‌ها

## 🚀 راه‌اندازی سریع

### پیش‌نیازها
- Python 3.8+
- کلید API ربات تلگرام
- کلید API Google Gemini (اختیاری برای AI)

### مراحل نصب

1. **کلون کردن پروژه**:
```bash
git clone [repository-url]
cd Kudos-BOT
```

2. **نصب پکیج‌های مورد نیاز**:
```bash
pip install -r requirements.txt
```

3. **تنظیم config.py**:
```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"  # اختیاری
ADMIN_USER_ID = 123456789  # Telegram User ID شما
```

4. **ایجاد دیتابیس**:
```bash
python create_db.py
```

5. **اجرای ربات**:
```bash
python bot.py
```

### اجرای دائمی با Runner
برای اطمینان از کارکرد مداوم ربات:
```bash
python bot_runner.py
```

## 📁 ساختار پروژه

```
Kudos-BOT/
├── src/
│   ├── handlers/          # پردازش‌گرهای مختلف ربات
│   ├── database/          # عملیات دیتابیس
│   ├── services/          # سرویس‌های کاربردی (AI، کارت هدیه)
│   └── utils/             # ابزارهای کمکی
├── static/                # فایل‌های استاتیک (فونت‌ها، تصاویر)
├── docs/                  # مستندات
├── scripts/               # اسکریپت‌های کمکی
└── tests/                 # تست‌ها
```

## 🎮 نحوه استفاده

### برای کاربران عادی:
- `/start` - شروع کار با ربات
- استفاده از منوی اصلی برای دسترسی به قابلیت‌ها
- امتیازدهی از طریق جستجو یا لیست کاربران
- شرکت در رای‌گیری ترین‌ها
- ارسال کارت هدیه به همکاران

### برای ادمین‌ها:
- مدیریت کاربران و تایید عضویت‌ها
- ایجاد و مدیریت فصول جدید
- مشاهده گزارش‌های تحلیلی
- مدیریت سوالات ترین‌ها
- دسترسی به آمار کامل سیستم

## 🔧 پیکربندی پیشرفته

### تنظیمات دیتابیس:
فایل `config.py` شامل تنظیمات مختلف:
- مسیر دیتابیس
- تنظیمات فصل پیش‌فرض
- محدودیت‌های امتیازدهی

### ماژول هوش مصنوعی:
برای فعال‌سازی قابلیت‌های AI:
1. کلید Gemini API را در config قرار دهید
2. ماژول به صورت خودکار فعال می‌شود

## 🛠 توسعه و سفارشی‌سازی

### اضافه کردن handler جدید:
```python
# در src/handlers/
async def my_handler(update, context):
    # کد handler
    pass

# در callback_handler.py اضافه کنید
```

### ایجاد سرویس جدید:
```python
# در src/services/
class MyService:
    def __init__(self):
        pass
    
    def my_method(self):
        pass
```

## 🔍 مشکل‌یابی

### مشکلات رایج:
1. **خطای دیتابیس**: `python create_db.py` را اجرا کنید
2. **خطای توکن**: config.py را بررسی کنید
3. **مشکل فونت**: فایل‌های فونت در static/fonts/ باشند

### لاگ‌ها:
- لاگ‌های ربات در `bot.log` ذخیره می‌شوند
- برای debug بیشتر: `python bot.py --debug`

## 📊 قابلیت‌های نسخه فعلی

- ✅ سیستم امتیازدهی کامل
- ✅ رای‌گیری ترین‌ها
- ✅ کارت‌های هدیه
- ✅ تحلیل هوش مصنوعی
- ✅ مدیریت فصول
- ✅ گزارش‌گیری پیشرفته
- ✅ سیستم تایید کاربران
- ✅ رانر خودکار برای پایداری

## 🤝 مشارکت

برای مشارکت در پروژه:
1. Fork کنید
2. Branch جدید بسازید
3. تغییرات را commit کنید
4. Pull Request ارسال کنید

## 📝 لیسنس

این پروژه تحت لیسنس MIT منتشر شده است.

## 🆘 پشتیبانی

برای گزارش مشکل یا درخواست ویژگی جدید، Issue جدید ایجاد کنید.