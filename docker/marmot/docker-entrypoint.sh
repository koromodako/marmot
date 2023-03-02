#!/bin/sh
set -e

MARMOT_CONFIG=/data/marmot.json

# initialize configuration file if not present
if [ ! -f ${MARMOT_CONFIG} ]; then
    marmot-config -c ${MARMOT_CONFIG} init-server --use-defaults
    sed -i -e 's/127.0.0.1/0.0.0.0/g' ${MARMOT_CONFIG}
    sed -i -e 's/localhost/marmot-redis/g' ${MARMOT_CONFIG}
    marmot-config -c ${MARMOT_CONFIG} show-server
fi
# first arg is `-f` or `--some-option`
# append marmot-server before
if [ "${1#-}" != "$1" ]; then
    set -- marmot-server "$@"
fi

# allow the container to be started with `--user`
if [ "$1" = 'marmot-server' -a "$(id -u)" = '0' ]; then
    find . \! -user marmot -exec chown marmot '{}' +
    exec su-exec marmot "$0" "$@"
fi

exec "$@"
