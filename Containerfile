FROM ghcr.io/ublue-os/bazzite:stable-41.20250331

COPY build.sh /tmp/build.sh
ENV GNUPGHOME=/var/tmp/gnupg

RUN chmod +x /tmp/build.sh && \
    mkdir -p "$GNUPGHOME" /var/lib/alternatives && chmod 700 "$GNUPGHOME" && \
    /tmp/build.sh && \
    rm -rf /var/cache/dnf /tmp/* && \
    ostree container commit

LABEL org.opencontainers.image.source="https://github.com/jheinem1/james-os"
