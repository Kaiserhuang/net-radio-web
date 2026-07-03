#!/bin/bash
# ============================================================
# 白泽网络电台 - Ubuntu 26.04 一键部署脚本
# 用法: sudo bash deploy/setup.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[→]${NC} $1"; }

[[ $EUID -ne 0 ]] && err "请使用 sudo 运行此脚本"

# ---- 配置 ----
REPO_URL="https://github.com/Kaiserhuang/net-radio-web.git"
INSTALL_DIR="/opt/net-radio"
read -rp "请输入域名 (如 radio.example.com): " DOMAIN
[[ -z "$DOMAIN" ]] && err "域名不能为空"
read -rp "是否配置 SSL 证书? (y/n, 默认 y): " SETUP_SSL
SETUP_SSL="${SETUP_SSL:-y}"

# ============================================================
# 1. 系统更新 & 安装依赖
# ============================================================
info "更新系统软件包..."
apt update -y && apt upgrade -y

info "安装必要软件包..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl

# ============================================================
# 2. 克隆仓库
# ============================================================
info "克隆项目代码..."
[[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"
git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# ============================================================
# 3. 创建用户 & 目录权限
# ============================================================
info "创建专用用户..."
id -u netradio &>/dev/null || useradd -M -r -s /usr/sbin/nologin netradio
chown -R netradio:netradio "$INSTALL_DIR"

# ============================================================
# 4. Python 虚拟环境 & 依赖
# ============================================================
info "创建 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate

info "安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# ============================================================
# 5. 配置 systemd 服务
# ============================================================
info "配置 systemd 服务..."
sed "s/DOMAIN_NAME/$DOMAIN/g" deploy/net-radio.service > /etc/systemd/system/net-radio.service
systemctl daemon-reload
systemctl enable net-radio

# ============================================================
# 6. 配置 Nginx
# ============================================================
info "配置 Nginx..."
sed "s/DOMAIN_NAME/$DOMAIN/g" deploy/net-radio.conf > /etc/nginx/sites-available/net-radio
[[ -f /etc/nginx/sites-enabled/default ]] && rm /etc/nginx/sites-enabled/default
[[ -f /etc/nginx/sites-enabled/net-radio ]] && rm /etc/nginx/sites-enabled/net-radio
ln -s /etc/nginx/sites-available/net-radio /etc/nginx/sites-enabled/

# ============================================================
# 7. 启动后端服务
# ============================================================
info "启动后端服务..."
systemctl start net-radio
sleep 2
systemctl is-active --quiet net-radio || err "后端服务启动失败"
log "后端服务运行中"

# ============================================================
# 8. SSL 证书
# ============================================================
if [[ "$SETUP_SSL" == "y" ]]; then
    info "申请 SSL 证书..."
    systemctl stop nginx
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || \
        warn "SSL 证书申请失败，稍后手动运行: certbot --nginx -d $DOMAIN"
    systemctl start nginx
else
    # 无 SSL，临时修改 nginx config 只监听 80 端口
    warn "跳过 SSL 配置，将使用 HTTP"
    cat > /etc/nginx/sites-available/net-radio <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 10m;

    location /static/ {
        alias $INSTALL_DIR/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        root $INSTALL_DIR/static/;
        try_files \$uri /static/index.html;
    }
}
EOF
fi

# ============================================================
# 9. 启动 Nginx
# ============================================================
info "启动 Nginx..."
nginx -t || err "Nginx 配置错误"
systemctl start nginx || true
systemctl reload nginx || true
systemctl is-active --quiet nginx || err "Nginx 启动失败"
log "Nginx 运行中"

# ============================================================
# 10. 完成
# ============================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成!${NC}"
echo -e "${GREEN}  访问地址: ${CYAN}https://$DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "常用命令:"
echo "  查看日志:  journalctl -u net-radio -f"
echo "  重启服务:  systemctl restart net-radio"
echo "  更新代码:  cd $INSTALL_DIR && git pull && systemctl restart net-radio"
echo ""
