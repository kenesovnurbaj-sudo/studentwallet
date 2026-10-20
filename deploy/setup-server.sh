#!/usr/bin/env bash
# Первичная установка на Ubuntu 24.04 (запускать на сервере от root):
#   bash setup-server.sh [ветка]
# Скрипт можно запускать повторно: он обновит код и перезапустит сервис.
# Ничего, кроме StudentWallet, он не трогает (порты 80 и 8000, пользователь studentwallet).
set -euo pipefail

BRANCH="${1:-main}"
REPO="https://github.com/kenesovnurbaj-sudo/studentwallet"
APP=/opt/studentwallet

apt-get update -y
apt-get install -y nginx python3-venv git

id studentwallet &>/dev/null || useradd --system --home "$APP" --shell /usr/sbin/nologin studentwallet

if [ -d "$APP/.git" ]; then
  git -C "$APP" fetch origin
  git -C "$APP" checkout "$BRANCH"
  git -C "$APP" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO" "$APP"
fi

python3 -m venv "$APP/backend/.venv"
"$APP/backend/.venv/bin/pip" install --no-cache-dir -r "$APP/backend/requirements.txt"

mkdir -p /var/lib/studentwallet /var/www/studentwallet
chown studentwallet: /var/lib/studentwallet
chown -R studentwallet: "$APP"

# Файл настроек создаём один раз, ключ генерируем случайный
if [ ! -f /etc/studentwallet.env ]; then
  cat > /etc/studentwallet.env <<ENV
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:////var/lib/studentwallet/studentwallet.db
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=150
ENV
  chmod 600 /etc/studentwallet.env
fi

cp "$APP/deploy/studentwallet.service" /etc/systemd/system/studentwallet.service
cp "$APP/deploy/nginx.conf" /etc/nginx/sites-available/studentwallet
ln -sf /etc/nginx/sites-available/studentwallet /etc/nginx/sites-enabled/studentwallet
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable --now studentwallet
systemctl restart studentwallet
nginx -t && systemctl reload nginx

sleep 2
curl -fsS http://127.0.0.1/api/health && echo
echo "Готово. Теперь загрузите frontend: см. deploy/DEPLOY.md, шаг 3."
