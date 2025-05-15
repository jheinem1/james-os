FROM ghcr.io/ublue-os/bazzite:stable

COPY build.sh /tmp/build.sh
RUN chmod +x /tmp/build.sh && \
    mkdir -p /usr/etc/alternatives && \
    /tmp/build.sh && \
    rm -rf /var/cache/dnf /tmp/* && \
    ostree container commit

LABEL org.opencontainers.image.source="https://github.com/jheinem1/james-os"
