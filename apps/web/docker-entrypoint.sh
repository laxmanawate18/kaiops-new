#!/bin/sh
set -eu

# Render the nginx config from the environment at container start.
# PORT is supplied by Cloud Run; default to 8080 for local runs.
: "${PORT:=8080}"
: "${BACKEND_URL:=http://localhost:8000}"

export PORT BACKEND_URL

envsubst '${PORT} ${BACKEND_URL}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

# Fail fast and loudly on a bad config rather than crash-looping silently.
nginx -t

exec nginx -g 'daemon off;'
