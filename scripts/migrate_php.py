#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PHP后台 MySQL（ea_*）→ Python统一后端一次性迁移（幂等，可重跑）"""
import os
import secrets
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pymysql  # noqa: E402
from backend.core.database import (  # noqa: E402
    SessionLocal, PhoneNumber, SmsRecord, SystemConfig, AdminUser, MallCate, MallGoods,
)

MYSQL = dict(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
             user=os.getenv("MYSQL_USER", "root"), password=os.getenv("MYSQL_PASS", ""),
             database=os.getenv("MYSQL_DB", "telebotadmin"), charset="utf8mb4")
ENV_ADMIN = os.getenv("ADMIN_USERNAME", "admin")


def rows(cur, sql):
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    conn = pymysql.connect(**MYSQL)
    cur = conn.cursor()
    db = SessionLocal()
    stat = {}

    # 号码：is_imported=1 视为有效，其余为待验证（原表status语义不明，不硬转）
    phones = rows(cur, "SELECT * FROM ea_phone WHERE delete_time IS NULL")
    n = 0
    for p in phones:
        if db.query(PhoneNumber).filter(PhoneNumber.number == p["number"]).first():
            continue
        valid = bool(p.get("is_imported"))
        db.add(PhoneNumber(number=p["number"], country=p.get("country") or "HK",
                           status="valid" if valid else "generated", is_valid=valid))
        n += 1
    db.commit()
    stat["phones"] = (n, len(phones))

    # 短信：原status=1 记入队
    sms = rows(cur, "SELECT * FROM ea_sms WHERE delete_time IS NULL")
    n = 0
    for s in sms:
        db.add(SmsRecord(phone=s["phone"], content=s.get("content") or "",
                         sender=s.get("sender") or "TelegramBot", status="queued",
                         note="从PHP后台迁移"))
        n += 1
    db.commit()
    stat["sms"] = (n, len(sms))

    # 机器人配置直转键值
    cfgs = rows(cur, "SELECT * FROM ea_bot_config WHERE delete_time IS NULL")
    n = 0
    for c in cfgs:
        if db.query(SystemConfig).filter(SystemConfig.key == c["config_key"]).first():
            continue
        db.add(SystemConfig(key=c["config_key"], value=c.get("config_value") or "",
                            remark=c.get("remark") or "从PHP bot_config迁移"))
        n += 1
    db.commit()
    stat["bot_config"] = (n, len(cfgs))

    # 系统配置：group.name 拼键防碰撞
    syscfgs = rows(cur, "SELECT * FROM ea_system_config")
    n = 0
    for c in syscfgs:
        key = f"{c.get('group')}.{c.get('name')}"
        if db.query(SystemConfig).filter(SystemConfig.key == key).first():
            continue
        db.add(SystemConfig(key=key, value=c.get("value") or "",
                            remark=c.get("remark") or "从PHP system_config迁移"))
        n += 1
    db.commit()
    stat["sys_config"] = (n, len(syscfgs))

    # 商城分类/商品
    cates = rows(cur, "SELECT * FROM ea_mall_cate WHERE delete_time IS NULL")
    n = 0
    for t in cates:
        if db.query(MallCate).filter(MallCate.title == t["title"]).first():
            continue
        db.add(MallCate(title=t["title"], sort=t.get("sort") or 0, status=t.get("status") or 1))
        n += 1
    db.commit()
    stat["cate"] = (n, len(cates))

    goods = rows(cur, "SELECT * FROM ea_mall_goods WHERE delete_time IS NULL")
    n = 0
    for gd in goods:
        if db.query(MallGoods).filter(MallGoods.title == gd["title"],
                                      MallGoods.cate_id == (gd.get("cate_id") or 0)).first():
            continue
        price = float(gd.get("discount_price") or gd.get("market_price") or 0)
        db.add(MallGoods(cate_id=gd.get("cate_id") or 0, title=gd["title"], price=price,
                         stock=gd.get("stock") or 0, status=gd.get("status") or 1))
        n += 1
    db.commit()
    stat["goods"] = (n, len(goods))

    # 账号：跳过与环境超级管理员同名；PHP哈希不可复用，置随机不可用密码并保持原状态，需重置
    admins = rows(cur, "SELECT * FROM ea_system_admin WHERE delete_time IS NULL")
    n = skip = 0
    reset = []
    for a in admins:
        if a["username"] == ENV_ADMIN:
            skip += 1
            continue
        if db.query(AdminUser).filter(AdminUser.username == a["username"]).first():
            continue
        db.add(AdminUser(username=a["username"], password_hash="migrated:" + secrets.token_hex(16),
                         role="operator", status=a.get("status") if a.get("status") in (0, 1) else 1))
        reset.append(a["username"])
        n += 1
    db.commit()
    stat["admins"] = (n, len(admins), f"跳过同名{skip}个")

    for k, v in stat.items():
        print(f"{k}: 新增{v[0]}/来源{v[1]}" + (f"（{v[2]}）" if len(v) > 2 else ""))
    if reset:
        print("需重置密码的账号:", ", ".join(reset), "（PHP哈希不可复用，用PUT /api/users/{id}重置）")
    cur.close()
    conn.close()
    db.close()
    print("迁移完成（幂等，可重跑）")


if __name__ == "__main__":
    main()
