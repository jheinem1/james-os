#!/usr/bin/env bash
set -euo pipefail

VENCORD_REF="cba0eb9897419432e68277b0b60c301a6f8323cf"
VENCORD_TAG="v1.14.6"
DISCORD_RPM_URL="https://discord.com/api/download?platform=linux&format=rpm"

###############################################################################
# Directories that must exist during the RPM unpack phase
###############################################################################
mkdir -p /etc/yum.repos.d
mkdir -p /var/opt               # /opt → /var/opt symlink target on Silverblue/Bazzite

###############################################################################
# 1Password repo + GPG key
###############################################################################
cat > /etc/yum.repos.d/1password.repo <<'EOF'
[1password]
name = 1Password Stable Channel
baseurl = https://downloads.1password.com/linux/rpm/stable/$basearch
enabled = 1
gpgcheck = 1
repo_gpgcheck = 1
gpgkey = https://downloads.1password.com/linux/keys/1password.asc
EOF

rpm --import https://downloads.1password.com/linux/keys/1password.asc

###############################################################################
# Install all desired packages in one shot
###############################################################################
dnf5 makecache -y

dnf5 install -y \
  1password \
  1password-cli \
  cargo \
  konsole \
  nodejs \
  npm \
  patch \
  piper \
  yakuake \
  corectrl \
  kde-partitionmanager \
  plasma-oxygen \
  plasma-oxygen-qt6 \
  oxygen-icon-theme

###############################################################################
# Install Discord at image level (official RPM)
###############################################################################
curl -fL "${DISCORD_RPM_URL}" -o /tmp/discord.rpm
dnf5 install -y /tmp/discord.rpm
rm -f /tmp/discord.rpm
if [[ -x /usr/bin/discord ]]; then
  :
else
  echo "Discord executable not found after installing official RPM" >&2
  exit 1
fi
cat > /usr/bin/discord <<'EOF'
#!/bin/sh

CHANNEL=stable
DOWNLOAD=https://updates.discord.com/
DIR=discord
EXE=Discord
BOOTSTRAP_SUFFIX=discord/updater_bootstrap

config_home=$XDG_CONFIG_HOME
if [ -z "$config_home" ]; then
    config_home=$HOME/.config
fi

discord_host=$config_home/$DIR/$EXE

apply_discord_vaapi_fixes() {
    for voice_dir in "$config_home"/$DIR/[0-9]*.[0-9]*.[0-9]*/modules/discord_voice; do
        [ -d "$voice_dir" ] || continue
        chmod u+x "$voice_dir/gpu_encoder_helper" "$voice_dir/discord_voice.node" 2>/dev/null || true
    done
}

discord_flags="--enable-features=VaapiVideoDecoder,VaapiVideoEncoder,AcceleratedVideoEncoder --ignore-gpu-blocklist"

if [ ! -x "$discord_host" ]; then
    mkdir -p "$config_home/$DIR"
    if [ ! -d "$config_home/$DIR" ]; then
        echo "Fatal error, failed to create $DIR in $config_home" >&2
        exit 1
    fi
    if [ -t 1 ]; then
        zenity=--no-zenity
    else
        zenity=--zenity
    fi
    bootstrap=/usr/share/$BOOTSTRAP_SUFFIX
    if [ ! -x "$bootstrap" ]; then
        bootstrap=/opt/$BOOTSTRAP_SUFFIX
        if [ ! -x "$bootstrap" ]; then
            bootstrap=`dirname -- "$0"`/updater_bootstrap
        fi
    fi
    app_dir=`"$bootstrap" $zenity "$config_home/$DIR" $CHANNEL "$DOWNLOAD"`

    if [ $? -eq 0 ] ; then
        echo "Bootstrap complete"
        apply_discord_vaapi_fixes
        exec "$config_home/$DIR/$app_dir/$EXE" $discord_flags "$@"
    else
        echo "Bootstrap failed or was canceled"
        exit 2
    fi
fi

apply_discord_vaapi_fixes
exec "$discord_host" $discord_flags "$@"
EOF
chmod 0755 /usr/bin/discord
if [[ -e /usr/share/discord/chrome-sandbox ]]; then
  chmod 4755 /usr/share/discord/chrome-sandbox
fi

# Discord's RPM desktop file uses Icon=discord but does not install that icon
# into the theme search path. Provide a stable hicolor entry when Discord exists.
mkdir -p /usr/share/icons/hicolor/256x256/apps
ln -sfn /usr/share/discord/discord.png /usr/share/icons/hicolor/256x256/apps/discord.png

if [[ -f /usr/share/discord/resources/app.asar ]]; then
  ###############################################################################
  # Install Vencord into the image-level Discord tree with the KDE idle plugin
  ###############################################################################
  git clone --depth=1 --branch "${VENCORD_TAG}" https://github.com/Vendicated/Vencord.git /tmp/Vencord
  git -C /tmp/Vencord checkout "${VENCORD_REF}"
  mkdir -p /tmp/Vencord/src/plugins/kdeIdleSync.discordDesktop
  cp /tmp/vencord-overlay/src/plugins/kdeIdleSync.discordDesktop/index.ts /tmp/Vencord/src/plugins/kdeIdleSync.discordDesktop/index.ts
  cp /tmp/vencord-overlay/src/plugins/kdeIdleSync.discordDesktop/native.ts /tmp/Vencord/src/plugins/kdeIdleSync.discordDesktop/native.ts
  export HOME=/tmp
  export XDG_CONFIG_HOME=/tmp/.config
  export XDG_DATA_HOME=/tmp/.local/share
  export npm_config_cache=/tmp/npm-cache
  export npm_config_prefix=/tmp/npm-global
  npm install -g pnpm@10.4.1
  export PATH="/tmp/npm-global/bin:${PATH}"
  (
    cd /tmp/Vencord
    pnpm install --frozen-lockfile
    pnpm build
    install -Dm0644 dist/patcher.js /usr/share/vencord/patcher.js
    install -Dm0644 dist/preload.js /usr/share/vencord/preload.js
    install -Dm0644 dist/renderer.js /usr/share/vencord/renderer.js
    install -Dm0644 dist/renderer.css /usr/share/vencord/renderer.css
  )

  node /usr/local/bin/patch-discord-vencord-asar.mjs
  test -f /usr/share/discord/resources/_app.asar
  test -f /usr/share/discord/resources/app.asar
  grep -aqF '/usr/share/vencord/patcher.js' /usr/share/discord/resources/app.asar
  test -f /usr/share/vencord/patcher.js
  test -f /usr/share/vencord/preload.js
  test -f /usr/share/vencord/renderer.js
  test -f /usr/share/vencord/renderer.css
else
  echo "Discord package does not include resources/app.asar; skipping image-level Vencord patch"
fi

# Enable the KDE idle sync watcher for all users by default.
mkdir -p /usr/lib/systemd/user/graphical-session.target.wants
ln -sfn /usr/lib/systemd/user/kde-discord-idle-sync.service \
  /usr/lib/systemd/user/graphical-session.target.wants/kde-discord-idle-sync.service
ln -sfn /usr/lib/systemd/user/kvm-display-recover.service \
  /usr/lib/systemd/user/graphical-session.target.wants/kvm-display-recover.service


###############################################################################
# Remove unwanted packages
###############################################################################
dnf5 remove -y gnome-disk-utility
dnf5 remove -y lutris
dnf5 remove -y nodejs nodejs22 npm nodejs22-npm

###############################################################################
# Relocate 1Password into /usr (so it's captured in the OSTree commit)
###############################################################################
mv /var/opt/1Password /usr/lib/1Password

###############################################################################
# Permissions, groups, hardening
###############################################################################
# Choose high numeric GIDs that won't collide with regular user groups
GID_ONEPASSWORD=1500
GID_ONEPASSWORDCLI=1600

# Create the groups in the image itself. Relying only on sysusers.d is not
# sufficient on deployed ostree systems when systemd-sysusers is skipped because
# /etc does not need an update.
getent group onepassword >/dev/null || groupadd --system --gid "${GID_ONEPASSWORD}" onepassword
getent group onepassword-cli >/dev/null || groupadd --system --gid "${GID_ONEPASSWORDCLI}" onepassword-cli

# Chromium sandbox binaries must be root-owned before setuid is enabled.
for sandbox_bin in \
  /usr/lib/1Password/chrome-sandbox \
  /usr/lib64/discord/chrome-sandbox \
  /usr/lib/discord/chrome-sandbox
do
  if [[ -f "${sandbox_bin}" ]]; then
    chown root:root "${sandbox_bin}"
    chmod 4755 "${sandbox_bin}"
  fi
done

# Helper & CLI binaries need dedicated groups + setgid
chgrp ${GID_ONEPASSWORD} /usr/lib/1Password/1Password-BrowserSupport
chmod g+s               /usr/lib/1Password/1Password-BrowserSupport

chgrp ${GID_ONEPASSWORDCLI} /usr/bin/op
chmod g+s                 /usr/bin/op

# sysusers file – creates groups (once) at boot
cat > /usr/lib/sysusers.d/onepassword.conf <<EOF
g onepassword     ${GID_ONEPASSWORD}     "1Password application group"
g onepassword-cli ${GID_ONEPASSWORDCLI}  "1Password CLI group"
EOF

# tmpfiles rule – recreates /opt/1Password symlink on every boot
cat > /usr/lib/tmpfiles.d/onepassword.conf <<'EOF'
L /var/opt/1Password - - - - /usr/lib/1Password
EOF

###############################################################################
# Cleanup – drop repo files & dnf caches to keep image lean
###############################################################################
rm -f /etc/yum.repos.d/1password.repo
dnf5 clean all
rm -rf /var/cache/dnf
