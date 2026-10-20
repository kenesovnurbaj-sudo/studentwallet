# Развёртывание StudentWallet на сервере

Схема: браузер → Nginx (порт 80) → FastAPI (127.0.0.1:8000, SQLite).
ИИ-ассистент работает в Ollama на вашем компьютере; сервер достаёт до него через SSH-туннель.

```
Браузер ──► Nginx :80 ──► FastAPI :8000 ──► Ollama (127.0.0.1:11434 на сервере)
                                                    ▲
                                       SSH-туннель с вашего Mac (tunnel.sh)
```

Сервер слабый (1 ГБ RAM), поэтому Docker не используется, а frontend собирается на вашем компьютере.

## 1. Установка на сервере (один раз)

```bash
ssh root@142.93.163.218
curl -fsSLO https://raw.githubusercontent.com/kenesovnurbaj-sudo/studentwallet/<ветка>/deploy/setup-server.sh
bash setup-server.sh <ветка>
```

Пока изменения не влиты в `main`, вместо `<ветка>` подставьте `feature/ai-assistant-and-deploy`.
Скрипт ставит Nginx и Python-окружение, создаёт сервис `studentwallet` и файл настроек `/etc/studentwallet.env` (со случайным `SECRET_KEY`).

## 2. Сборка frontend на вашем компьютере

Нужен Node.js 18+.

```bash
cd frontend
npm ci
npm run build          # появится папка dist/
```

## 3. Загрузка frontend на сервер

```bash
rsync -av --delete frontend/dist/ root@142.93.163.218:/var/www/studentwallet/
```

Сайт открывается по адресу `http://142.93.163.218`.

## 4. ИИ-ассистент

На вашем компьютере (Ollama должна быть запущена, модель скачана):

```bash
ollama pull qwen2.5:3b
bash deploy/tunnel.sh root@142.93.163.218     # оставьте окно открытым
```

Пока туннель работает, чат отвечает. Если туннеля нет, чат пишет «ИИ-ассистент сейчас недоступен», остальное приложение работает.
Другая модель: поменяйте `OLLAMA_MODEL` в `/etc/studentwallet.env` и выполните `systemctl restart studentwallet`.

## 5. Администратор (по желанию)

В `/etc/studentwallet.env` добавьте строки `ADMIN_EMAIL=...` и `ADMIN_PASSWORD=...`, затем `systemctl restart studentwallet`.

## Обновление после изменений в коде

```bash
ssh root@142.93.163.218 'bash /opt/studentwallet/deploy/setup-server.sh <ветка>'
# и, если менялся frontend, повторить шаги 2 и 3
```

## Полезные команды на сервере

```bash
systemctl status studentwallet        # состояние
journalctl -u studentwallet -n 50     # логи
curl http://127.0.0.1:11434/api/tags  # виден ли туннель с Ollama
```

## HTTPS без своего домена (по желанию)

Домена нет, но бесплатное имя можно получить из IP: `142-93-163-218.sslip.io` указывает на ваш сервер.

```bash
apt-get install -y certbot python3-certbot-nginx
sed -i 's/server_name _;/server_name 142-93-163-218.sslip.io;/' /etc/nginx/sites-available/studentwallet
certbot --nginx -d 142-93-163-218.sslip.io
```

## Безопасность

- Вход на сервер лучше по SSH-ключу, а не паролю root.
- Не коммитьте `/etc/studentwallet.env` и ключи.
- SQLite-файл лежит в `/var/lib/studentwallet/`; для бэкапа достаточно скопировать его.
