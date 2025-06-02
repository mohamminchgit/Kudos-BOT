"""
Handler های مربوط به تشکرنامه و نامه‌نگاری - راهنمای ارجاع
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from .gift_callbacks import handle_gift_callbacks

logger = logging.getLogger(__name__)

async def handle_letter_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تابع هدایت کننده برای کالبک‌های مربوط به نامه
    این تابع یک wrapper برای handle_gift_callbacks است
    """
    # ارجاع مستقیم به تابع اصلی پردازش نامه‌ها در gift_callbacks
    await handle_gift_callbacks(update, context) 