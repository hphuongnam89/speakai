#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/media
  chown -R app:app /app/media
  mkdir -p /app/.cache
  chown -R app:app /app/.cache
  exec su -s /bin/sh app -c "$*"
fi

exec "$@"
