#!/bin/bash
# DuckDNS 动态域名更新脚本
# 用于自动更新 DuckDNS 的 IP 地址

set -e

# 从环境变量读取配置，或使用默认值
DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-36c79923-2d16-42b8-a5bf-218654a4395b}"
DOMAIN="${DOMAIN:-telegramweb.duckdns.org}"
IP="${IP:-}"  # 留空则使用当前公网 IP

echo "正在更新 DuckDNS 域名: $DOMAIN"

# 构建请求 URL
if [ -z "$IP" ]; then
    # 不指定 IP，让 DuckDNS 使用请求来源 IP
    URL="https://www.duckdns.org/update?domains=${DOMAIN}&token=${DUCKDNS_TOKEN}&ip="
else
    URL="https://www.duckdns.org/update?domains=${DOMAIN}&token=${DUCKDNS_TOKEN}&ip=${IP}"
fi

# 发送更新请求
RESPONSE=$(curl -s "$URL")

if [ "$RESPONSE" = "OK" ]; then
    echo "✅ DuckDNS 更新成功！"
    echo "域名: $DOMAIN"
    echo "时间: $(date)"
else
    echo "❌ DuckDNS 更新失败: $RESPONSE"
    exit 1
fi

# 可选：添加到 crontab 实现自动更新（每 5 分钟）
if [ "${SETUP_CRON:-false}" = "true" ]; then
    echo "正在设置定时任务（每 5 分钟更新一次）..."
    (crontab -l 2>/dev/null; echo "*/5 * * * * $PWD/duckdns_setup.sh") | crontab -
    echo "定时任务已设置"
fi
