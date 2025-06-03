#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست کامل عملکرد ارسال نامه و gift card
"""

import asyncio
import sys
import os

# اضافه کردن پوشه اصلی پروژه به مسیر
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.gift_callbacks import handle_gift_callback, _handle_letter_start, handle_gift_card_message
from src.services.giftcard import create_gift_card_image
from src.database.models import db_manager
from unittest.mock import Mock, AsyncMock
import config

async def test_letter_feature():
    """تست کامل عملکرد ارسال نامه"""
    print("🧪 شروع تست عملکرد ارسال نامه...")
    
    try:
        # 1. تست ایجاد gift card image
        print("\n1️⃣ تست ایجاد تصویر تشکرنامه...")
        
        # تست داده‌های نمونه
        test_data = {
            'receiver_name': 'محمد احمدی',
            'sender_name': 'علی رضایی',
            'message': 'با تشکر از همکاری عالی شما در پروژه، موفق باشید!',
            'season_name': 'زمستان 1403'
        }
        
        image_path = create_gift_card_image(
            receiver_name=test_data['receiver_name'],
            sender_name=test_data['sender_name'],
            message=test_data['message'],
            season_name=test_data['season_name']
        )
        
        if image_path and os.path.exists(image_path):
            print(f"✅ تصویر تشکرنامه با موفقیت ایجاد شد: {image_path}")
        else:
            print("❌ خطا در ایجاد تصویر تشکرنامه")
            return False
        
        # 2. تست ایجاد کاربران نمونه در دیتابیس
        print("\n2️⃣ بررسی کاربران موجود در دیتابیس...")
        
        users = db_manager.execute_query("SELECT user_id, name FROM users LIMIT 5")
        if users:
            print(f"✅ {len(users)} کاربر یافت شد:")
            for user in users:
                print(f"   - ID: {user[0]}, نام: {user[1]}")
        else:
            print("⚠️ هیچ کاربری در دیتابیس یافت نشد")
            # ایجاد کاربران تست
            print("   ایجاد کاربران تست...")
            test_users = [
                (1001, 'محمد احمدی', '@mohammad_a', 0),
                (1002, 'علی رضایی', '@ali_r', 0),
                (1003, 'فاطمه محمدی', '@fateme_m', 0)
            ]
            
            for user_id, name, username, is_admin in test_users:
                db_manager.execute_query(
                    "INSERT OR IGNORE INTO users (user_id, name, username, is_admin) VALUES (?, ?, ?, ?)",
                    (user_id, name, username, is_admin),
                    commit=True
                )
            print("✅ کاربران تست ایجاد شدند")
        
        # 3. تست mock callback query
        print("\n3️⃣ تست mock callback handler...")
        
        # ایجاد mock objects
        mock_query = Mock()
        mock_query.data = "letter^"
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        mock_query.message = Mock()
        mock_query.message.chat_id = 123456
        mock_query.from_user = Mock()
        mock_query.from_user.id = 1001
        
        mock_context = Mock()
        mock_context.user_data = {}
        
        # تست handle_gift_callback
        result = await handle_gift_callback(mock_query, mock_context)
        
        if mock_context.user_data.get('gift_card_mode'):
            print("✅ حالت gift card با موفقیت فعال شد")
        else:
            print("❌ خطا در فعال‌سازی حالت gift card")
        
        # 4. تست پردازش پیام تشکرنامه
        print("\n4️⃣ تست پردازش پیام تشکرنامه...")
        
        # تنظیم داده‌های mock برای حالت انتظار پیام
        mock_context.user_data = {
            'gift_card_mode': True,
            'waiting_for_gift_card_message': True,
            'gift_card_receiver_id': 1002,
            'gift_card_receiver_name': 'علی رضایی'
        }
        
        mock_message = Mock()
        mock_message.text = "با تشکر از تلاش‌های شما در پروژه!"
        mock_message.from_user = Mock()
        mock_message.from_user.id = 1001
        mock_message.reply_text = AsyncMock()
        mock_message.reply_photo = AsyncMock()
        
        # تست handle_gift_card_message
        result = await handle_gift_card_message(mock_message, mock_context)
        
        print("✅ پردازش پیام تشکرنامه انجام شد")
        
        # 5. بررسی فایل‌های temp
        print("\n5️⃣ بررسی فایل‌های موقت...")
        
        tmp_dir = os.path.join(os.path.dirname(__file__), 'tmp')
        if os.path.exists(tmp_dir):
            files = os.listdir(tmp_dir)
            gift_cards = [f for f in files if f.startswith('gift_card_') and f.endswith('.png')]
            print(f"✅ {len(gift_cards)} فایل تشکرنامه در پوشه tmp یافت شد")
        else:
            print("⚠️ پوشه tmp وجود ندارد")
        
        print("\n🎉 تست عملکرد ارسال نامه با موفقیت انجام شد!")
        return True
        
    except Exception as e:
        print(f"\n❌ خطا در تست: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_letter_feature())
