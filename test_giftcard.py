#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

# اضافه کردن مسیر src به sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.giftcard import create_gift_card_image

def test_gift_card():
    print("شروع تست تشکرنامه...")
    
    sender_name = "محمدامین"
    receiver_name = "کاربر تست"
    message = "این یک پیام تست برای تشکرنامه است. متشکرم از تمام کمک‌هایتان."
    
    try:
        result = create_gift_card_image(sender_name, receiver_name, message)
        if result:
            print(f"✅ تشکرنامه با موفقیت ایجاد شد: {result}")
            return True
        else:
            print("❌ خطا در ایجاد تشکرنامه")
            return False
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_gift_card()
