from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display
import os
import random
from datetime import datetime
import math
import jdatetime
import textwrap
import logging

# تنظیم لاگر
logger = logging.getLogger(__name__)

# تنظیمات ابعاد تصویر
WIDTH = 1920
HEIGHT = 1080

# تم‌های رنگی مدرن با طراحی تمیزتر
THEMES = [
    {
        'name': 'blue_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (53, 152, 219),  # آبی روشن
        'dark_accent_color': (41, 128, 185),  # آبی تیره
        'text_color': (50, 50, 50),
        'secondary_color': (235, 245, 255)  # پس‌زمینه آبی بسیار روشن
    },
    {
        'name': 'teal_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (26, 188, 156),  # فیروزه‌ای روشن
        'dark_accent_color': (22, 160, 133),  # فیروزه‌ای تیره
        'text_color': (50, 50, 50),
        'secondary_color': (235, 255, 250)
    },
    {
        'name': 'purple_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (155, 89, 182),  # بنفش روشن
        'dark_accent_color': (142, 68, 173),  # بنفش تیره
        'text_color': (50, 50, 50),
        'secondary_color': (245, 240, 255)
    },
    {
        'name': 'coral_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (231, 76, 60),  # مرجانی روشن
        'dark_accent_color': (192, 57, 43),  # مرجانی تیره
        'text_color': (50, 50, 50),
        'secondary_color': (255, 240, 240)
    },
    {
        'name': 'green_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (46, 204, 113),  # سبز روشن
        'dark_accent_color': (39, 174, 96),  # سبز تیره
        'text_color': (50, 50, 50),
        'secondary_color': (240, 255, 245)
    }
]

def add_rounded_rectangle(draw, position, size, radius, fill_color, outline_color=None, width=0):
    """رسم مستطیل با گوشه‌های گرد"""
    x0, y0 = position
    x1, y1 = x0 + size[0], y0 + size[1]
    
    # رسم مستطیل اصلی
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill_color, outline=outline_color)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill_color, outline=outline_color)
    
    # رسم چهار گوشه
    draw.pieslice([x0, y0, x0 + radius * 2, y0 + radius * 2], 180, 270, fill=fill_color, outline=outline_color)
    draw.pieslice([x1 - radius * 2, y0, x1, y0 + radius * 2], 270, 0, fill=fill_color, outline=outline_color)
    draw.pieslice([x0, y1 - radius * 2, x0 + radius * 2, y1], 90, 180, fill=fill_color, outline=outline_color)
    draw.pieslice([x1 - radius * 2, y1 - radius * 2, x1, y1], 0, 90, fill=fill_color, outline=outline_color)
    
    # اگر خط دور (outline) مشخص شده باشد، آن را جداگانه رسم می‌کنیم
    if outline_color and width > 0:
        draw.arc([x0, y0, x0 + radius * 2, y0 + radius * 2], 180, 270, fill=outline_color, width=width)
        draw.arc([x1 - radius * 2, y0, x1, y0 + radius * 2], 270, 0, fill=outline_color, width=width)
        draw.arc([x0, y1 - radius * 2, x0 + radius * 2, y1], 90, 180, fill=outline_color, width=width)
        draw.arc([x1 - radius * 2, y1 - radius * 2, x1, y1], 0, 90, fill=outline_color, width=width)
        
        draw.line([x0 + radius, y0, x1 - radius, y0], fill=outline_color, width=width)
        draw.line([x0, y0 + radius, x0, y1 - radius], fill=outline_color, width=width)
        draw.line([x1, y0 + radius, x1, y1 - radius], fill=outline_color, width=width)
        draw.line([x0 + radius, y1, x1 - radius, y1], fill=outline_color, width=width)

def create_gift_card_image(sender_name: str, receiver_name: str, message: str, output_path: str = None) -> str | None:
    """ایجاد تصویر تشکر‌نامه با طراحی مینیمال و ساده"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        from bidi.algorithm import get_display
        import arabic_reshaper
        import jdatetime
        import os
        
        # تعیین مسیر خروجی و ایجاد پوشه
        if not output_path:
            # ایجاد پوشه برای ذخیره تصاویر موقت
            os.makedirs("static/img", exist_ok=True)
            output_path = "static/img/temp_gift_card.png"
        else:
            # اطمینان از وجود پوشه مقصد
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        
        # تنظیمات و ابعاد کارت
        card_width = 800
        card_height = 500
        
        # رنگ‌های مینیمال
        bg_color = (245, 245, 245)  # پس‌زمینه روشن
        accent_color = (64, 131, 170)  # آبی ملایم
        text_color = (68, 68, 68)  # خاکستری تیره
        
        # ایجاد تصویر پایه
        image = Image.new('RGB', (card_width, card_height), color=bg_color)
        draw = ImageDraw.Draw(image)
        
        # لود فونت‌های مورد نیاز - مسیر فونت را متناسب با سیستم خود تنظیم کنید
        try:
            title_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 32)
            header_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 24)
            message_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 22)
            footer_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 16)
        except OSError:
            # استفاده از فونت پیش‌فرض در صورت عدم وجود فونت دلخواه
            title_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 32)
            header_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 24)  
            message_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 22)
            footer_font = ImageFont.truetype("static/fonts/Dana-Regular.ttf", 16)
        
        # افزودن حاشیه ساده دور کارت
        border = 10
        draw.rectangle([border, border, card_width-border, card_height-border], 
                      outline=accent_color, width=2, fill=None)
        
        # رسم خط افقی زیر عنوان
        title_line_y = 90
        draw.line([(50, title_line_y), (card_width-50, title_line_y)], 
                 fill=accent_color, width=2)
        
        # رسم خط افقی بالای تاریخ
        footer_line_y = card_height - 70
        draw.line([(50, footer_line_y), (card_width-50, footer_line_y)], 
                 fill=accent_color, width=2)
        
        # رسم عنوان کارت
        card_title = "تشکر‌نامه"
        reshaped_title = arabic_reshaper.reshape(card_title)
        bidi_title = get_display(reshaped_title)
        
        # محاسبه موقعیت برای قرار دادن عنوان در وسط
        title_bbox = draw.textbbox((0, 0), bidi_title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (card_width - title_width) // 2
        title_y = 40
        
        draw.text((title_x, title_y), bidi_title, font=title_font, fill=accent_color)
        
        # تهیه متن فرستنده و گیرنده
        sender_text = f"از: {sender_name}"
        receiver_text = f"به: {receiver_name}"
        
        reshaped_sender = arabic_reshaper.reshape(sender_text)
        bidi_sender = get_display(reshaped_sender)
        
        reshaped_receiver = arabic_reshaper.reshape(receiver_text)
        bidi_receiver = get_display(reshaped_receiver)
        
        # محاسبه موقعیت متن فرستنده و گیرنده - جابجا کردن موقعیت‌ها
        sender_bbox = draw.textbbox((0, 0), bidi_sender, font=header_font)
        sender_width = sender_bbox[2] - sender_bbox[0]
        sender_x = card_width - sender_width - 50
        sender_y = 120
        
        receiver_bbox = draw.textbbox((0, 0), bidi_receiver, font=header_font)
        receiver_width = receiver_bbox[2] - receiver_bbox[0]
        receiver_x = 50  # تغییر موقعیت به سمت چپ
        receiver_y = 120
        
        # رسم نام فرستنده و گیرنده
        draw.text((sender_x, sender_y), bidi_sender, font=header_font, fill=text_color)
        draw.text((receiver_x, receiver_y), bidi_receiver, font=header_font, fill=text_color)
        
        # پردازش متن پیام و تقسیم به خطوط
        max_line_width = card_width - 100
        message_lines = []
        current_line = ""
        
        for word in message.split():
            test_line = current_line + " " + word if current_line else word
            reshaped_test = arabic_reshaper.reshape(test_line)
            bidi_test = get_display(reshaped_test)
            
            test_width = draw.textlength(bidi_test, font=message_font)
            
            if test_width <= max_line_width:
                current_line = test_line
            else:
                if current_line:
                    message_lines.append(current_line)
                current_line = word
        
        if current_line:
            message_lines.append(current_line)
        
        # رسم متن پیام در وسط کارت
        message_y = 180
        padding = 20
        
        for line in message_lines:
            reshaped_line = arabic_reshaper.reshape(line)
            bidi_line = get_display(reshaped_line)
            
            line_width = draw.textlength(bidi_line, font=message_font)
            line_x = (card_width - line_width) // 2
            
            draw.text((line_x, message_y), bidi_line, font=message_font, fill=text_color)
            message_y += message_font.size + padding
        
        # اضافه کردن تاریخ در پایین کارت
        j_date = jdatetime.datetime.now().strftime("%Y/%m/%d")
        date_text = f"تاریخ: {j_date}"
        
        reshaped_date = arabic_reshaper.reshape(date_text)
        bidi_date = get_display(reshaped_date)
        
        date_width = draw.textlength(bidi_date, font=footer_font)
        date_x = (card_width - date_width) // 2
        date_y = card_height - 50
        
        draw.text((date_x, date_y), bidi_date, font=footer_font, fill=text_color)
        
        # ذخیره و بازگشت مسیر تصویر
        image.save(output_path)
        return output_path
        
    except Exception as e:
        print(f"خطای ناشناخته در ایجاد تشکر‌نامه: {e}")
        import traceback
        print(traceback.format_exc())
        return None

if __name__ == '__main__':
    # برای تست مستقیم این ماژول
    sender = "امین ۲"
    receiver = "ادمین اصلی"
    message = "از صمیم قلب سپاسگزارم بابت توجه، صبر و حوصله‌ای که همیشه در پاسخ به سوالاتم داشتید—حتی اون‌هایی که بارها تکرار شده بودن. این حس حمایت شما واقعا ارزشمند و دلگرم‌کننده است.\n\nحضور همیشگی‌تون در کنار ما و راهنمایی‌های دقیق‌تون نه‌تنها به پیشبرد بهتر کارها کمک کرده، بلکه فضایی مثبت و سازنده در محیط کاری ایجاد کرده. قدردان این همراهی هستم و از شما بابت این تعامل حرفه‌ای و صمیمی سپاسگزارم."
    
    image_file = create_gift_card_image(sender, receiver, message)
    if image_file:
        print(f"تشکر‌نامه با موفقیت در {image_file} ایجاد شد.")
        try:
            Image.open(image_file).show() # نمایش تصویر برای بررسی
        except Exception as e_show:
            print(f"امکان نمایش خودکار تصویر وجود ندارد: {e_show}")
    else:
        print("ایجاد تشکر‌نامه ناموفق بود.") 