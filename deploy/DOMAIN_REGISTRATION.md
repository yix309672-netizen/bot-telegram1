# 域名注册与 TLS 配置

域名获取与指向
- 使用你的域名（请替换为实际域名）: your-domain.com
- 将域名的 A 记录指向部署服务器的公网 IP
- 如果你尚未有域名，以下是常见免费/低成本选项（仅用于测试/评估，生产请购买正式域名）：
  - Freenom: 免费域名（TK、ML、GA、CF 等）
  - 动态 DNS 服务商提供的免费子域名（如 Cloudflare、DuckDNS 等）

- 证书申请（Let’s Encrypt）
- 证书邮箱：yix309672@gmail.com
- 使用 Let’s Encrypt 的 certbot 自动化申请证书
- 证书生命周期：证书有效期 90 天，建议自动续期
- 部署后 TLS 证书路径：/etc/letsencrypt/live/your-domain.com/

生产环境注意
- 域名需可访问外网，80 与 443 端口对外开放
- 首次证书申请需要域名解析生效，DNS propagation 可能需要几分钟到几十分钟
- 使用 nginx 做 TLS 终止，后端服务通过 80/443 的反向代理暴露

- 示例命令（用于示范，实际替换域名后执行）
- certbot --nginx -d your-domain.com -m yix309672@gmail.com --agree-tos --no-eff-email
- 证书自动续期已启用后，Certbot 会在 90 天内续期证书
