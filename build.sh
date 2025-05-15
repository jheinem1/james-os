#!/bin/bash

set -ouex pipefail
basearch=${basearch:-$(uname -m)}

### Setup 1Password repo
install -d -m 0755 /etc/yum.repos.d        # make sure the dir exists

cat > /etc/yum.repos.d/1password.repo <<'EOF'
[1password]
name = 1Password Stable Channel
baseurl = https://downloads.1password.com/linux/rpm/stable/$basearch
enabled = 1
gpgcheck = 1
repo_gpgcheck = 1
gpgkey = https://downloads.1password.com/linux/keys/1password.asc
EOF

# import the GPG key so dnf5 trusts the packages
rpm --import https://downloads.1password.com/linux/keys/1password.asc

### Setup VSCode repo
rpm --import https://packages.microsoft.com/keys/microsoft.asc

cat > /etc/yum.repos.d/vscode.repo <<'EOF'
[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF

### Install packages

# Install packages with dnf5
dnf5 install -y 1password 1password-cli
dnf5 install -y code
dnf5 install -y konsole
dnf5 install -y piper
dnf5 install -y yakuake
