# 免费域名与动态 DNS（DuckDNS）方案

背景
- 生产环境需要一个域名用于 TLS 证书申请与公网访问。完全免费的域名通常稳定性较低，推荐在测试阶段使用免费域名。
- DuckDNS 提供一个稳定的免费二级域名服务，配合自建或路由器的定时更新，可以实现免费域名指向你的服务器。

步骤
1. 注册 DuckDNS 账户
- 访问 https://www.duckdns.org 并用任意邮箱注册一个账号。
- 登陆后，在左侧创建一个子域名，例如 telegramweb，选择域名后缀 duckdns.org。

1. 记录 DNS 指向
- 在 DuckDNS 的面板中，点击你创建的子域名，记录类型通常是 A（IPv4）记录。
- 把你的服务器公网 IPv4 地址填入 A 记录，保存。

1. 证书获取与部署（TLS）
- 由于域名是 DuckDNS 动态域名，你的域名也可以用于 Let’s Encrypt 的证书获取。方法是使用 Nginx + Certbot，HTTP-01 验证。
- 你需要保证服务器对外暴露 80/443 端口，Certbot 能够完成域名验证。
- 证书有效期 90 天，请确保开启证书续期（Certbot 自动续期）。

1. 动态域名更新（可选，但推荐）
- 使用定时任务（cron）或 DDNS 客户端定期调用 DuckDNS 更新接口以保持域名指向正确的服务器 IP。
- 示例（Linux）:
  "5 * * * * curl -k "https://duckdns.org/update?domains=telegramweb&token=YOUR_TOKEN" >/dev/null 2>&1"

1. 集成到部署流程
- 将 DuckDNS 域名与你的部署域名合并，确保 Nginx 配置中使用的域名就是 DuckDNS 提供的域名。
- 配置自动证书续期，确保证书在 DuckDNS 域名变更时仍然有效。

注意
- 免费域名和 DDNS 方案通常用于测试与 accelerate；正式生产请尽量使用正式域名以获得长期稳定性。
- 如果你愿意我也可以替你生成一个部署脚本，自动化完成域名创建、DNS 指向、证书申请等步骤（前提是你愿意使用 DuckDNS 做域名）
