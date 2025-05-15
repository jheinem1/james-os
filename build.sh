#!/bin/bash

set -ouex pipefail
basearch=${basearch:-$(uname -m)}

### Install packages

# Add 1Password repo
curl -o /etc/yum.repos.d/1password.repo https://downloads.1password.com/linux/rpm/stable/$basearch/1password.repo

# Install packages with dnf5
dnf5 install -y 1password
dnf5 install -y 1password-cli
dnf5 install -y konsole
dnf5 install -y piper
dnf5 install -y yakuake

# Run Zed install script
curl -f https://zed.dev/install.sh | sh
