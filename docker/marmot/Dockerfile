FROM alpine:3.17

# add our user and group first to make sure their IDs get assigned consistently,
# regardless of whatever dependencies get added
RUN addgroup -S -g 1000 marmot && adduser -S -G marmot -u 999 marmot
# alpine already has a gid 999, so we'll use the next id

RUN mkdir -p /data && chown marmot:marmot /data

RUN apk add --no-cache \
# grab su-exec for easy step-down from root
        'su-exec>=0.2' \
# install python3 as marmot will need it
        python3 \
        sed

COPY packages/*.whl /data/

RUN set -eux; \
    \
    apk add --no-cache --virtual .build-deps \
        coreutils \
        dpkg-dev dpkg \
        gcc \
        linux-headers \
        make \
        musl-dev \
        openssl-dev \
        python3-dev \
        py3-pip \
    ; \
    python3 -m pip install /data/*.whl; \
    apk del --no-network .build-deps; \
    \
    marmot-config -h

VOLUME /data
WORKDIR /data

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["marmot-server"]
