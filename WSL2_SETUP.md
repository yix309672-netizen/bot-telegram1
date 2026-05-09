# WSL2 完整配置指南

**适用于 Windows 11 + WSL2 Ubuntu 的完整配置，覆盖 Docker 部署所有问题。**

---

## 1. WSL2 基础配置

### 查看当前状态
```bash
wsl -l -v
```

### 更新 WSL2 内核
```powershell
wsl --update
```

### 设置默认版本为 WSL2
```powershell
wsl --set-default-version 2
```

### 重启所有 WSL 实例
```powershell
wsl --shutdown
```

---

## 2. 网络配置（解决 Docker TLS/503 问题）

### 关闭 IPv6（必须！解决 Docker Hub 连接问题）
```bash
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
```

### 永久保存 IPv6 关闭配置
```bash
echo 'net.ipv6.conf.all.disable_ipv6=1' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv6.conf.default.disable_ipv6=1' | sudo tee -a /etc/sysctl.conf
```

### 告诉 Docker daemon 使用 IPv4（解决 Docker TLS 超时）
```bash
echo '{"ipv6": false, "dns": ["8.8.8.8", "8.8.4.4"]}' | sudo tee /etc/docker/daemon.json
```

---

## 3. Docker 安装和启动

### 安装 Docker Engine（如果没有）
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
```

### 启动 Docker daemon
```bash
sudo service docker start
```

### 重启 Docker daemon（修改配置后必须重启）
```bash
sudo service docker stop
sudo service docker start
```

### 检查 Docker 状态
```bash
sudo service docker status
docker ps
```

---

## 4. Docker 权限配置（解决 permission denied）

### 确认当前用户在 docker 组
```bash
groups
id
```

### 应该看到 `docker` 组
输出示例：`uid=1000(thikbookxiaoyi) gid=1000(thikbookxiaoyi) groups=...,108(docker)`

### 如果不在 docker 组，手动添加
```bash
sudo usermod -aG docker $USER
```

### 修复 docker.sock 权限（如果报 permission denied）
```bash
sudo chmod 666 /var/run/docker.sock
```

---

## 5. TeleBot 部署步骤

### 进入部署目录
```bash
cd "/mnt/c/Users/Thikbook/Desktop/telegram-client-login-bot (1)/local-deploy"
```

### 给脚本加执行权限
```bash
chmod +x deploy.sh duckdns_setup.sh tls_setup.sh auto_deploy.sh
```

### 配置环境变量（填入 Bot Token）
```bash
cp .env.template .env
nano .env
```
修改 `TELEGRAM_BOT_TOKEN=你的真实Token`

### 一键部署
```bash
sudo docker-compose up -d --build
```

### 查看服务状态
```bash
sudo docker-compose ps
```

### 测试后端健康接口
```bash
curl http://localhost:8000/health
```

---

## 6. 常见问题解决

### 问题：TLS handshake timeout
解决：关闭 IPv6，重启 Docker
```bash
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
sudo service docker restart
```

### 问题：503 Docker Hub 不可用
解决：等待 5-30 分钟后重试，或挂后台下载
```bash
nohup bash -c 'docker pull mysql:8.0 && docker pull redis:7 && docker pull nginx:alpine' &
```

### 问题：Docker API permission denied
解决：修复 socket 权限
```bash
sudo chmod 666 /var/run/docker.sock
sudo service docker restart
```

### 问题：容器启动后后端不响应
解决：检查日志
```bash
sudo docker-compose logs backend
sudo docker-compose logs telegram_bot
```

---

## 7. 常用命令速查

```bash
# 重启 WSL
wsl --shutdown
wsl -d Ubuntu

# 重启 Docker
sudo service docker stop
sudo service docker start

# 查看所有容器
sudo docker-compose ps

# 查看日志
sudo docker-compose logs -f

# 停止所有服务
sudo docker-compose down

# 重新构建和启动
sudo docker-compose up -d --build

# 测试后端接口
curl http://localhost:8000/health
curl http://localhost:8000/

# 运行测试
cd tests
pytest -v
```

---

## 8. 自动部署脚本

一键运行自动部署脚本（自动处理所有步骤）：
```bash
cd "/mnt/c/Users/Thikbook/Desktop/telegram-client-login-bot (1)/local-deploy"
bash auto_deploy.sh
```

查看部署结果：
```bash
cat /tmp/deploy_log.txt
```

---

## 9. Windows 端命令（PowerShell 管理员）

```powershell
# 更新 WSL
wsl --update

# 重启 WSL
wsl --shutdown

# 查看 WSL 状态
wsl -l -v

# 在 WSL 里执行命令
wsl -d Ubuntu -e bash -c "命令"
```