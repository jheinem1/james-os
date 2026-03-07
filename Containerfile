FROM ghcr.io/ublue-os/bazzite:stable

COPY build.sh /tmp/build.sh
ENV GNUPGHOME=/var/tmp/gnupg

# Copy in baked config files
COPY --chmod=0644 system/etc__hostname /etc/hostname
COPY --chmod=0755 system/usr_local_bin__discord_encoder.py /usr/local/bin/discord_encoder.py
COPY --chmod=0755 system/usr_local_bin__dolphin_discord_encode.py /usr/local/bin/dolphin_discord_encode.py
COPY --chmod=0644 system/usr_share_applications__discord-h264-encode.desktop /usr/share/applications/discord-h264-encode.desktop

RUN chmod +x /tmp/build.sh && \
    mkdir -p "$GNUPGHOME" /var/lib/alternatives && chmod 700 "$GNUPGHOME" && \
    /tmp/build.sh && \
    rm -rf /var/cache/dnf /tmp/* && \
    ostree container commit

LABEL org.opencontainers.image.source="https://github.com/jheinem1/james-os"
