#!/bin/sh
echo "Starting KaiOPS Frontend..."
nginx -t
if [ $? -ne 0 ]; then
    echo "nginx configuration validation failed!"
    exit 1
fi
echo "nginx configuration is valid"
exec nginx -g "daemon off;"
