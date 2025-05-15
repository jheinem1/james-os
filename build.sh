#!/bin/bash

set -ouex pipefail
basearch=${basearch:-$(uname -m)}

### Install packages

# Add 1Password repo
wget https://downloads.1password.com/linux/rpm/stable/x86_64/1password-latest.rpm

# Install packages with dnf5
dnf5 install -y ./1password-latest.rpm
dnf5 install -y 1password-cli
dnf5 install -y konsole
dnf5 install -y piper
dnf5 install -y yakuake

# Run Zed install script
curl -f https://zed.dev/install.sh | sh
