#!/bin/bash

set -ouex pipefail
basearch=${basearch:-$(uname -m)}

### Install packages

# Install packages with dnf5
dnf5 install -y konsole
dnf5 install -y piper
dnf5 install -y yakuake
