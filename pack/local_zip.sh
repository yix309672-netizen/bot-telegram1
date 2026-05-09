#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"  # 即 local-deploy 的父级目录
PACK_NAME="telebot_local_deploy.zip"

if command -v zip >/dev/null 2>&1; then
  echo "正在打包本地部署包为 $PACK_NAME..."
  zip -r "$PACK_NAME" ./ 
  echo "打包完成：$PACK_NAME"
else
  echo "系统中未安装 zip，尝试使用 apt 安装后再打包";
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y zip
    zip -r "$PACK_NAME" ./
    echo "打包完成：$PACK_NAME"
  else
    echo "无法打包：系统缺少 zip，并且无法通过 apt-get 安装，请手动打包或在支持的平台执行该脚本。"
  fi
fi
