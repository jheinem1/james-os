# Fetch and validate a pinned native package without installing build dependencies.
FROM ghcr.io/ublue-os/bazzite:stable AS updater-package
COPY system/bazzite-updater-kde /tmp/kde-updater
RUN python3 /tmp/kde-updater/acquire.py --lock /tmp/kde-updater/package.json --destination /out

FROM ghcr.io/ublue-os/bazzite:stable

COPY --from=updater-package /out/usr/lib/bazzite-updater-kde /usr/lib/bazzite-updater-kde
COPY system/bazzite-updater-kde/launch /tmp/kde-updater-launch
COPY system/bazzite-updater-kde/verify /tmp/kde-updater-verify
COPY build.sh /tmp/build.sh
COPY vencord-overlay /tmp/vencord-overlay
ENV GNUPGHOME=/var/tmp/gnupg

# Copy in baked config files
COPY --chmod=0755 system/usr_bin__james-os-brew /usr/bin/james-os-brew
COPY --chmod=0755 system/usr_libexec__james-os-steam /usr/libexec/james-os-steam
COPY --chmod=0755 system/usr_bin__james-os-update-chatgpt /usr/bin/james-os-update-chatgpt
COPY --chmod=0755 system/usr_bin__james-os-check-staged-update /usr/bin/james-os-check-staged-update
COPY --chmod=0644 system/usr_lib_systemd_system_uupd.service.d__30-desktop-update.conf /usr/lib/systemd/system/uupd.service.d/30-desktop-update.conf
COPY --chmod=0644 system/usr_lib_systemd_system_uupd-manual.service.d__30-desktop-update.conf /usr/lib/systemd/system/uupd-manual.service.d/30-desktop-update.conf
COPY --chmod=0644 system/usr_lib_systemd_system_uupd.service.d__20-homebrew-path.conf /usr/lib/systemd/system/uupd.service.d/20-homebrew-path.conf
COPY --chmod=0644 system/usr_lib_systemd_system_uupd-manual.service.d__20-homebrew-path.conf /usr/lib/systemd/system/uupd-manual.service.d/20-homebrew-path.conf
COPY --chmod=0755 system/usr_bin__james-os-install-kwin-mcp /usr/bin/james-os-install-kwin-mcp
COPY --chmod=0755 system/usr_bin__james-os-install-piper /usr/bin/james-os-install-piper
COPY --chmod=0755 system/usr_bin__james-os-install-piper-gtk /usr/bin/james-os-install-piper-gtk
COPY system/piper-g600 /usr/share/james-os/piper-g600
COPY system/piper-kirigami /usr/share/james-os/piper-kirigami
COPY --chmod=0644 system/etc__hostname /etc/hostname
COPY --chmod=0644 system/etc__kvm-display-recover.env /etc/kvm-display-recover.env
COPY --chmod=0644 system/etc_ublue-os__topgrade.toml /etc/ublue-os/topgrade.toml
COPY --chmod=0644 system/etc__vencord-kde-idle-sync.env /etc/vencord-kde-idle-sync.env
COPY --chmod=0755 system/usr_bin__discord_encoder.py /usr/bin/discord_encoder.py
COPY --chmod=0755 system/usr_bin__dolphin_discord_encode.py /usr/bin/dolphin_discord_encode.py
COPY --chmod=0755 system/usr_bin__kvm-display-recover /usr/bin/kvm-display-recover
COPY --chmod=0755 system/usr_bin__kde-discord-idle-sync.py /usr/bin/kde-discord-idle-sync.py
COPY --chmod=0755 system/usr_bin__patch-discord-vencord-asar.mjs /usr/bin/patch-discord-vencord-asar.mjs
COPY --chmod=0644 system/usr_lib_systemd_user__kvm-display-recover.service /usr/lib/systemd/user/kvm-display-recover.service
COPY --chmod=0644 system/usr_lib_systemd_user_kvm-focus-daemon.service.d__50-james-os-replacement.conf /usr/lib/systemd/user/kvm-focus-daemon.service.d/50-james-os-replacement.conf
COPY --chmod=0644 system/usr_lib_systemd_user__kde-discord-idle-sync.service /usr/lib/systemd/user/kde-discord-idle-sync.service
COPY --chmod=0644 system/usr_share_applications__discord-h264-encode.desktop /usr/share/applications/discord-h264-encode.desktop
COPY --chmod=0644 system/usr_share_applications__system-update.desktop /usr/share/applications/system-update.desktop

RUN chmod +x /tmp/build.sh && \
    mkdir -p "$GNUPGHOME" /var/lib/alternatives && chmod 700 "$GNUPGHOME" && \
    /tmp/build.sh && \
    echo "image finalize: install updater launcher" && \
    install -Dm0755 /usr/bin/bazzite-updater /usr/libexec/bazzite-updater-upstream && \
    install -m0755 /tmp/kde-updater-launch /usr/bin/bazzite-updater && \
    timeout --kill-after=5s 45s bash /tmp/kde-updater-verify && \
    test -x /usr/bin/bazzite-updater && \
    echo "image finalize: remove temporary files" && \
    timeout --kill-after=5s 60s rm -rf /var/cache/dnf /tmp/* && \
    echo "image finalize: bootc lint" && \
    timeout --kill-after=5s 60s bootc container lint

LABEL org.opencontainers.image.source="https://github.com/jheinem1/james-os"
