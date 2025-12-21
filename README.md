# James OS

A [Fedora Atomic](https://fedoraproject.org/atomic-desktops) image built with [Universal Blue](https://universal-blue.org/)’s toolkit.

## Changes from Bazzite
- Replaces Bazaar with KDE Discover as the default software center.
- Replaces GNOME Disk Utility with KDE Partition Manager.
- Removes Lutris.
- Preinstalls 1Password and the 1Password CLI.
- Adds back Konsole as a terminal option and Yakuake to complement it (ptyxis remains the default for compatibility with some Bazzite features).
- Preinstalls Piper for configuring mice.
- Preinstalls CoreCtrl for power management.
- Includes preinstalled VS Code, Docker, and [other developer tools](https://docs.bazzite.gg/Dev/?h=bazzite+dx#new-additions) via the Bazzite-DX base image.

## How to use

> There isn't a prebuilt ISO yet, so you'll have to rebase from an existing Fedora Atomic image.

1. From a Fedora Atomic image, run the following command to install James OS:

    ```bash
    sudo rpm-ostree rebase --experimental ostree-unverified-registry:ghcr.io/jheinem1/james-os:v0.0.5
    ```
2. Reboot your system.

## Contributing
I'm not actively seeking contributions, but if you want to help out, feel free to open an issue or pull request.

## Important files
- 'Containerfile': The file used to build the container image.
- 'build.sh': The main script ran to configure the image from the Containerfile.
- 'Justfile': This file contains the "ujust" commands available in the image (there are currently none other than the ones inherited by Bazzite and a template).
