#!/bin/bash
# Запуск веб-приложения «Афиша мероприятий»
cd "$(dirname "$0")"
[ -f data/afisha.db ] || python3 seed.py
# Порт по умолчанию 5000; на macOS он может быть занят приёмником AirPlay,
# в этом случае запустите: AFISHA_PORT=5050 ./run.sh
PORT="${AFISHA_PORT:-5000}"
echo "Приложение доступно по адресу http://127.0.0.1:$PORT"
AFISHA_PORT="$PORT" python3 app.py
