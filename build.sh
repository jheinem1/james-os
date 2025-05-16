#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# 0. Directories that must exist during the RPM unpack phase
###############################################################################
mkdir -p /etc/yum.repos.d
mkdir -p /var/opt               # /opt → /var/opt symlink target on Silverblue/Bazzite

###############################################################################
# 1. 1Password repo + GPG key
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
# 2. Visual Studio Code repo + key
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
# 3. Install all desired packages in one shot
###############################################################################
dnf5 makecache -y
dnf5 install -y \
  1password \
  1password-cli \
  code \
  konsole \
  piper \
  yakuake

###############################################################################
# 4. Relocate 1Password into /usr (so it's captured in the OSTree commit)
###############################################################################
mv /var/opt/1Password /usr/lib/1Password

###############################################################################
# 5. Permissions, groups, hardening
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
# 6. Optional cleanup – drop repo files & dnf caches to keep image lean
###############################################################################
rm -f /etc/yum.repos.d/1password.repo /etc/yum.repos.d/vscode.repo
dnf5 clean all
rm -rf /var/cache/dnf

###############################################################################
# Pin Mesa to 25.0.2 (last Gamescope-friendly build)
###############################################################################
MESA_VER=25.0.2
MESA_REL=3          # Koji release number to fetch (see notes)
ARCHES="x86_64 i686"  # keep multilib wine / Steam working

# Where Fedora keeps the archived RPMs — change fc42 if you ever rebase
KOJI=https://kojipkgs.fedoraproject.org/packages/mesa/${MESA_VER}/${MESA_REL}.fc42

mkdir -p /tmp/mesa-${MESA_VER}
cd       /tmp/mesa-${MESA_VER}

# Sub-package list the loader insists be from the *same* build
PKGS=(
  mesa-filesystem
  mesa-libglapi
  mesa-libEGL
  mesa-libGL
  mesa-libgbm
  mesa-dri-drivers
  mesa-vulkan-drivers
  mesa-va-drivers
  mesa-vdpau-drivers
)

echo ">> downloading Mesa ${MESA_VER}-${MESA_REL}.fc42 …"
for pkg in "${PKGS[@]}"; do
  for arch in ${ARCHES}; do
    curl -L -O  "${KOJI}/${arch}/${pkg}-${MESA_VER}-${MESA_REL}.fc42.${arch}.rpm"
  done
done

echo ">> replacing base Mesa with ${MESA_VER}"
rpm-ostree override replace ./*.rpm

# clean up temp files so they don't bloat the layer
cd /
rm -rf /tmp/mesa-${MESA_VER}