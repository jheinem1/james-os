#!/usr/bin/env bash
set -euo pipefail

VENCORD_REF="cba0eb9897419432e68277b0b60c301a6f8323cf"
VENCORD_TAG="v1.14.6"

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
  git \
  konsole \
  nodejs \
  npm \
  piper \
  yakuake \
  corectrl \
  kde-partitionmanager \
  plasma-oxygen \
  plasma-oxygen-qt6 \
  oxygen-icon-theme

###############################################################################
# Install Discord at image level (official tarball)
###############################################################################
curl -L 'https://discord.com/api/download?platform=linux&format=tar.gz' \
  -o /tmp/discord.tar.gz
mkdir -p /usr/share/discord
tar -xzf /tmp/discord.tar.gz --strip-components=1 -C /usr/share/discord
ln -sf /usr/share/discord/Discord /usr/bin/discord
install -Dm0644 /usr/share/discord/discord.desktop /usr/share/applications/discord.desktop
chmod 4755 /usr/share/discord/chrome-sandbox

# Discord's RPM desktop file uses Icon=discord but does not install that icon
# into the theme search path. Provide a stable hicolor entry when Discord exists.
mkdir -p /usr/share/icons/hicolor/256x256/apps
ln -sfn /usr/share/discord/discord.png /usr/share/icons/hicolor/256x256/apps/discord.png

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
  node scripts/runInstaller.mjs -- --install -location /usr/share/discord
)

# Enable the KDE idle sync watcher for all users by default.
mkdir -p /usr/lib/systemd/user/default.target.wants
ln -sfn /usr/lib/systemd/user/kde-discord-idle-sync.service \
  /usr/lib/systemd/user/default.target.wants/kde-discord-idle-sync.service


###############################################################################
# Remove unwanted packages
###############################################################################
dnf5 remove -y gnome-disk-utility
dnf5 remove -y lutris
dnf5 remove -y git nodejs npm

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
