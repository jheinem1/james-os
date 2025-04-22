#!/bin/bash

set -ouex pipefail

### Install packages

# Install 1Password and 1Password CLI
dnf config-manager --add-repo=https://downloads.1password.com/linux/rpm/stable/$basearch/
dnf install -y 1password
dnf install -y 1password-cli

dnf install -y zed
dnf install -y konsole
dnf install -y piper
dnf install -y yakuake

#### Example for enabling a System Unit File

# systemctl enable podman.socket
