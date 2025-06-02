# -*- coding: utf-8 -*-
# اسکریپت برای تصحیح خطای f-string در bot.py

def fix_bot_file():
    try:
        # خواندن محتوای فایل اصلی
        with open('bot.py', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # جایگزینی رشته‌های خطادار
        fixed_content = content.replace(
            'welcome_text = f"کاربر گرامی {real_name}، به {config.BOT_NAME} خوش آمدید! ✅\n\n"',
            'welcome_text = f"کاربر گرامی {real_name}، به {config.BOT_NAME} خوش آمدید! ✅"\nwelcome_text += "\\nدرخواست دسترسی شما تایید شد."\nwelcome_text += "\\nمی‌توانید از طریق منوی زیر به امکانات ربات دسترسی داشته باشید."'
        )
        
        # ذخیره محتوای اصلاح شده
        with open('bot.py', 'w', encoding='utf-8') as file:
            file.write(fixed_content)
        
        print("فایل bot.py با موفقیت اصلاح شد.")
        return True
    except Exception as e:
        print(f"خطا در اصلاح فایل: {e}")
        return False

if __name__ == "__main__":
    fix_bot_file() 