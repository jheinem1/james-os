#!/bin/bash

set -ouex pipefail
basearch=${basearch:-$(uname -m)}

### Install packages

# Add 1Password repo
sudo rpm --import https://downloads.1password.com/linux/keys/1password.asc
sudo sh -c 'echo -e "[1password]\nname=1Password Stable Channel\nbaseurl=https://downloads.1password.com/linux/rpm/stable/\$basearch\nenabled=1\ngpgcheck=1\nrepo_gpgcheck=1\ngpgkey=\"https://downloads.1password.com/linux/keys/1password.asc\"" > /etc/yum.repos.d/1password.repo'

# Install packages with dnf5
dnf5 install -y 1password
dnf5 install -y 1password-cli
dnf5 install -y konsole
dnf5 install -y piper
dnf5 install -y yakuake

# Run Zed install script
curl -f https://zed.dev/install.sh | sh
