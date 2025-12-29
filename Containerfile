FROM ghcr.io/ublue-os/bazzite:stable

COPY build.sh /tmp/build.sh
ENV GNUPGHOME=/var/tmp/gnupg

# Copy in baked config files
COPY --chmod=0644 system/etc__hostname /etc/hostname

RUN chmod +x /tmp/build.sh && \
    mkdir -p "$GNUPGHOME" /var/lib/alternatives && chmod 700 "$GNUPGHOME" && \
    /tmp/build.sh && \
    rm -rf /var/cache/dnf /tmp/* && \
    ostree container commit

LABEL org.opencontainers.image.source="https://github.com/jheinem1/james-os"
