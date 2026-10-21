#!/usr/bin/env bash
# Запускать на ВАШЕМ компьютере (где стоит Ollama), пока идёт демо:
#   bash deploy/tunnel.sh root@142.93.163.218
# Сервер получает доступ к вашей Ollama по своему адресу 127.0.0.1:11434.
# Наружу порт не открывается, доступ только изнутри сервера.
set -euo pipefail
TARGET="${1:?Укажите пользователя и адрес сервера, например root@142.93.163.218}"
exec ssh -N \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
  -R 127.0.0.1:11434:127.0.0.1:11434 "$TARGET"
