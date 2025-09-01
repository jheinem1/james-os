#!/usr/bin/env bash
set -euo pipefail

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
# Visual Studio Code repo + key
###############################################################################
cat > /etc/yum.repos.d/vscode.repo <<'EOF'
[code]
name = Visual Studio Code
baseurl = https://packages.microsoft.com/yumrepos/vscode
enabled = 1
gpgcheck = 1
gpgkey = https://packages.microsoft.com/keys/microsoft.asc
EOF

rpm --import https://packages.microsoft.com/keys/microsoft.asc

###############################################################################
# RPM Fusion (free + nonfree) – provides Discord
###############################################################################
dnf5 install -y \
  https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

###############################################################################
# Gamescope Git repo from COPR
###############################################################################
# Install the copr plugin then enable the gamescope-git repo
dnf5 install -y 'dnf-command(copr)'
dnf5 copr enable -y vulongm/gamescope-git

###############################################################################
# Install all desired packages in one shot
###############################################################################
dnf5 makecache -y
dnf5 install -y \
  1password \
  1password-cli \
  code \
  discord \
  konsole \
  piper \
  yakuake \
  corectrl \
  plasma-discover \
  plasma-discover-kns \
  plasma-discover-flatpak \
  plasma-discover-notifier \
  kde-partitionmanager \
  discord

# Update plasma desktop and KDE components
dnf5 update -y \
  plasma-desktop \
  plasma-workspace

###############################################################################
# Remove unwanted packages
###############################################################################
dnf5 remove -y gnome-disk-utility
dnf5 remove -y bazaar krunner-bazaar
dnf5 remove -y lutris

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

# Chromium sandbox needs set-uid root
chmod 4755 /usr/lib/1Password/chrome-sandbox

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
rm -f /etc/yum.repos.d/1password.repo /etc/yum.repos.d/vscode.repo
rm -f /etc/yum.repos.d/negativo17-fedora-multimedia.repo
dnf5 clean all
rm -rf /var/cache/dnf
