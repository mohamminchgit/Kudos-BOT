# -*- coding: utf-8 -*-
# اسکریپت برای تصحیح خطای f-string در bot.py

def fix_bot_file():
    try:
        # خواندن محتوای فایل اصلی
        with open('bot.py', 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # یافتن خطوط مورد نظر و اصلاح آنها
        for i in range(len(lines)):
            if i >= 5738 and i <= 5744:
                if '# ارسال پیام خوش‌آمدگویی به کاربر' in lines[i]:
                    # خط 5739 (ارسال پیام خوش‌آمدگویی)
                    lines[i+1] = '            welcome_text = f"کاربر گرامی {real_name}، به {config.BOT_NAME} خوش آمدید! ✅"\n'
                    # خط 5740 (درخواست دسترسی)
                    lines[i+2] = '            welcome_text += "\\nدرخواست دسترسی شما تایید شد."\n'
                    # خط 5741 (منوی زیر)
                    lines[i+3] = '            welcome_text += "\\nمی‌توانید از طریق منوی زیر به امکانات ربات دسترسی داشته باشید."\n'
                    break
        
        # ذخیره محتوای اصلاح شده
        with open('bot.py', 'w', encoding='utf-8') as file:
            file.writelines(lines)
        
        print("فایل bot.py با موفقیت اصلاح شد.")
        return True
    except Exception as e:
        print(f"خطا در اصلاح فایل: {e}")
        return False

if __name__ == "__main__":
    fix_bot_file() 