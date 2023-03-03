#!/bin/sh
set -e

echo "(entrypoint): invoked as uid=$(id -u)"

if [ -z "${MARMOT_CONFIG}" ]; then
    MARMOT_CONFIG="/data/marmot.json"
fi
if [ -z "${MARMOT_REDIS_URL}" ]; then
    MARMOT_REDIS_URL="redis://marmot-redis"
fi

# initialize configuration file if not present
if [ ! -f ${MARMOT_CONFIG} ]; then
    echo "(entrypoint): initializing configuration file for the first time"
    marmot-config -c ${MARMOT_CONFIG} init-server --use-defaults
    sed -i -e "s|127.0.0.1|0.0.0.0|g" ${MARMOT_CONFIG}
    sed -i -e "s|redis://localhost|${MARMOT_REDIS_URL}|g" ${MARMOT_CONFIG}
fi

# first arg is `-f` or `--some-option`
# append marmot-server before
if [ "${1#-}" != "$1" ]; then
    set -- marmot-server "$@"
fi

# allow the container to be started with `--user`
if [ "$1" = 'marmot-server' -a "$(id -u)" = '0' ]; then
    find . \! -user marmot -exec chown marmot '{}' +
    echo "(entrypoint): step down from root"
    exec su-exec marmot "$0" "$@"
fi

echo "(entrypoint): marmot server current configuration"
marmot-config -c ${MARMOT_CONFIG} show-server
echo "(entrypoint): exec marmot-server"
exec "$@"
