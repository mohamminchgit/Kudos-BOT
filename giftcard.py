from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display
import os
import random
from datetime import datetime
import math
import jdatetime
import textwrap

# تنظیمات ابعاد تصویر
WIDTH = 1920
HEIGHT = 1080

# تم‌های رنگی مدرن با طراحی تمیزتر
THEMES = [
    {
        'name': 'teal_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (0, 150, 136),  # فیروزه‌ای
        'text_color': (50, 50, 50),
        'secondary_color': (240, 255, 250)
    },
    {
        'name': 'blue_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (41, 98, 255),  # آبی
        'text_color': (50, 50, 50),
        'secondary_color': (240, 245, 255)
    },
    {
        'name': 'purple_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (123, 31, 162),  # بنفش
        'text_color': (50, 50, 50),
        'secondary_color': (248, 240, 255)
    },
    {
        'name': 'coral_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (255, 87, 51),  # مرجانی
        'text_color': (50, 50, 50),
        'secondary_color': (255, 245, 240)
    },
    {
        'name': 'green_minimal',
        'bg_color': (255, 255, 255),
        'accent_color': (0, 150, 80),  # سبز
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

def create_gift_card_image(sender_name: str, receiver_name: str, message: str) -> str | None:
    """
    یک تصویر کارت هدیه با طراحی مینیمال و تمیز ایجاد می‌کند.

    Args:
        sender_name: نام فرستنده.
        receiver_name: نام گیرنده.
        message: پیام کارت هدیه.

    Returns:
        مسیر فایل تصویر ایجاد شده در صورت موفقیت، در غیر این صورت None.
    """
    try:
        # انتخاب تم تصادفی - ترجیحاً تم سبز را انتخاب می‌کنیم
        theme = next((t for t in THEMES if t['name'] == 'green_minimal'), random.choice(THEMES))
        
        # ایجاد تصویر پس‌زمینه
        image = Image.new('RGB', (WIDTH, HEIGHT), theme['bg_color'])
        draw = ImageDraw.Draw(image)
        
        # محاسبه ابعاد کارت (80% اندازه تصویر)
        card_width = int(WIDTH * 0.8)
        card_height = int(HEIGHT * 0.75)  # کمی کوتاه‌تر برای ظاهر بهتر
        card_x = (WIDTH - card_width) // 2
        card_y = (HEIGHT - card_height) // 2
        
        # رسم سایه برای کارت
        shadow_offset = 15
        shadow_color = (0, 0, 0, 25)  # مشکی با شفافیت 25%
        shadow_img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        add_rounded_rectangle(
            shadow_draw, 
            (card_x + shadow_offset, card_y + shadow_offset), 
            (card_width, card_height), 
            15,
            shadow_color
        )
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=15))
        image.paste(Image.alpha_composite(Image.new('RGBA', image.size, (0, 0, 0, 0)), shadow_img).convert('RGB'), (0, 0), mask=shadow_img)
        
        # رسم کارت اصلی (مستطیل با پس‌زمینه سفید و گوشه‌های گرد)
        add_rounded_rectangle(
            draw, 
            (card_x, card_y), 
            (card_width, card_height), 
            15,
            (255, 255, 255),
            outline_color=None
        )
        
        # بارگیری فونت‌ها (ابر برای تایتل و وزیر برای متن پیام)
        try:
            # استفاده از فونت ابر برای تایتل
            title_font = ImageFont.truetype("AbarLow-SemiBold.ttf", 60)
            # اگر فونت وزیر موجود است، از آن استفاده می‌کنیم، در غیر این صورت از همان ابر استفاده می‌کنیم
            try:
                message_font = ImageFont.truetype("Vazir.ttf", 48)
            except IOError:
                message_font = ImageFont.truetype("AbarLow-SemiBold.ttf", 48)
                
            date_font = ImageFont.truetype("AbarLow-SemiBold.ttf", 36)
        except IOError:
            print("خطا: فایل فونت AbarLow-SemiBold.ttf یافت نشد. از فونت پیش‌فرض استفاده می‌شود.")
            title_font = ImageFont.load_default()
            message_font = ImageFont.load_default()
            date_font = ImageFont.load_default()
        
        # آماده‌سازی متن‌ها
        reshaped_message = arabic_reshaper.reshape(message)
        bidi_message = get_display(reshaped_message)
        
        # ایجاد متن یکپارچه برای سربرگ - اطمینان از نمایش صحیح راست به چپ
        greeting_text = f"{receiver_name} عزیز، شما یک نامه از طرف {sender_name} داری!"
        reshaped_greeting = arabic_reshaper.reshape(greeting_text)
        bidi_greeting = get_display(reshaped_greeting)
        
        # ایجاد تاریخ به فرمت شمسی
        j_date = jdatetime.datetime.now().strftime("%Y/%m/%d")
        reshaped_date = arabic_reshaper.reshape(f"تاریخ: {j_date}")
        bidi_date = get_display(reshaped_date)
        
        # رسم نوار رنگی بالای کارت
        accent_color = theme['accent_color']
        header_height = 10
        draw.rectangle(
            [card_x, card_y, card_x + card_width, card_y + header_height],
            fill=accent_color
        )
        
        # رسم نوار رنگی عمودی در سمت راست سربرگ
        title_bar_width = 15
        title_bar_height = 70
        title_bar_y = card_y + 50
        title_bar_x = card_x + card_width - 50 - title_bar_width  # انتقال به سمت راست کارت
        
        draw.rectangle(
            [title_bar_x, title_bar_y, title_bar_x + title_bar_width, title_bar_y + title_bar_height],
            fill=accent_color
        )
        
        # رسم عنوان (متن یکپارچه) - راست‌چین
        text_color = theme['text_color']
        
        # محاسبه موقعیت X برای راست‌چین کردن
        greeting_width = draw.textlength(bidi_greeting, font=title_font)
        right_aligned_x = title_bar_x - greeting_width - 20  # فاصله مناسب از نوار عمودی
        
        # رسم متن سربرگ
        draw.text(
            (right_aligned_x, title_bar_y),
            bidi_greeting,
            fill=text_color,
            font=title_font
        )
        
        # محاسبه ارتفاع خط
        bbox = draw.textbbox((0, 0), bidi_greeting, font=title_font)
        line_height = bbox[3] - bbox[1]
        next_element_y = title_bar_y + line_height + 15
        
        # باکس پیام با طراحی مینیمال
        message_box_x = card_x + 50
        message_box_y = next_element_y + 30  # فاصله مناسب از سربرگ
        message_box_width = card_width - 100
        message_box_height = card_height - (message_box_y - card_y) - 80  # فضای کافی برای تاریخ در پایین
        
        # رسم کادر پیام با پس‌زمینه کمرنگ
        add_rounded_rectangle(
            draw,
            (message_box_x, message_box_y),
            (message_box_width, message_box_height),
            10,
            (230, 255, 240)  # رنگ سبز بسیار کمرنگ برای مطابقت با نمونه
        )
        
        # رسم پیام اصلی - روش بهتر برای شکستن خطوط فارسی
        padding = 30  # فاصله از لبه‌های کادر پیام
        max_line_width = message_box_width - (padding * 2)
        
        # روش جدید برای پردازش متن فارسی و شکستن خطوط
        # ابتدا پاراگراف‌ها را جدا می‌کنیم
        paragraphs = message.split('\n')
        
        # موقعیت شروع برای متن
        message_text_y = message_box_y + padding
        
        for paragraph in paragraphs:
            if not paragraph.strip():  # پاراگراف خالی - فقط فاصله ایجاد می‌کنیم
                message_text_y += 30
                continue
            
            # پردازش هر پاراگراف به صورت مستقل
            # شکستن پاراگراف به خطوط با عرض محدود
            remaining_width = max_line_width
            current_line = ""
            line_parts = []
            
            # شکستن پاراگراف به کلمات
            words = paragraph.split()
            
            for word in words:
                # محاسبه عرض کلمه پس از reshape و bidi
                reshaped_word = arabic_reshaper.reshape(word)
                bidi_word = get_display(reshaped_word)
                word_width = draw.textlength(bidi_word, font=message_font)
                
                # اضافه کردن فاصله بین کلمات
                space_width = draw.textlength(" ", font=message_font)
                
                # اگر کلمه در خط جاری جا می‌شود
                if current_line and (word_width + space_width) <= remaining_width:
                    current_line += " " + word
                    remaining_width -= (word_width + space_width)
                else:
                    # اگر خط جاری پر شده یا اولین کلمه خط جدید است
                    if current_line:
                        # خط قبلی را ذخیره می‌کنیم
                        line_parts.append(current_line)
                    
                    # خط جدید شروع می‌شود
                    current_line = word
                    remaining_width = max_line_width - word_width
            
            # آخرین خط را اضافه می‌کنیم
            if current_line:
                line_parts.append(current_line)
            
            # حالا هر خط را رسم می‌کنیم
            for line in line_parts:
                # متن فارسی را آماده می‌کنیم
                reshaped_line = arabic_reshaper.reshape(line)
                bidi_line = get_display(reshaped_line)
                
                # عرض متن را محاسبه می‌کنیم
                line_width = draw.textlength(bidi_line, font=message_font)
                
                # موقعیت راست‌چین را محاسبه می‌کنیم
                text_x = message_box_x + message_box_width - line_width - padding
                
                # متن را رسم می‌کنیم
                draw.text(
                    (text_x, message_text_y),
                    bidi_line,
                    fill=text_color,
                    font=message_font
                )
                
                # ارتفاع خط را محاسبه می‌کنیم
                bbox = draw.textbbox((0, 0), bidi_line, font=message_font)
                line_height = bbox[3] - bbox[1]
                
                # به خط بعدی می‌رویم
                message_text_y += line_height + 10
            
            # فاصله بین پاراگراف‌ها
            message_text_y += 15
        
        # رسم تاریخ در پایین کارت
        date_width = draw.textlength(bidi_date, font=date_font)
        date_x = card_x + card_width - date_width - 1200  # راست‌چین
        date_y = card_y + card_height - 70  # فاصله مناسب از پایین کارت
        
        draw.text(
            (date_x, date_y),
            bidi_date,
            fill=text_color,
            font=date_font
        )
        
        # ذخیره تصویر
        output_path = "temp_gift_card.png"
        image.save(output_path)
        
        return output_path
        
    except Exception as e:
        print(f"خطای ناشناخته در ایجاد کارت هدیه: {e}")
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
        print(f"کارت هدیه با موفقیت در {image_file} ایجاد شد.")
        try:
            Image.open(image_file).show() # نمایش تصویر برای بررسی
        except Exception as e_show:
            print(f"امکان نمایش خودکار تصویر وجود ندارد: {e_show}")
    else:
        print("ایجاد کارت هدیه ناموفق بود.") 