# Piper Kirigami for JamesOS

JamesOS installs the tested development Flatpak from
[jheinem1/piper-kirigami](https://github.com/jheinem1/piper-kirigami).
`release.json` pins its public release tag, source commit, bundle SHA-256 and
installed Flatpak commit. This is an actively developed Qt 6/Kirigami frontend,
not an official upstream Piper release.

## Install or update

Run `james-os-install-piper` as your desktop user, or
`bash system/usr_bin__james-os-install-piper` from this checkout.
The x86_64 bundle uses KDE Platform 6.11; Flatpak downloads that runtime from
Flathub when needed. Use the existing user Flathub remote on JamesOS. No Builder, SDK, native RPM layering or reboot is required.

The installer verifies the downloaded checksum before making changes, backs up
existing user Piper bundles and launchers, then installs the pinned Qt commit.
It leaves GTK Piper installed. The new Qt launcher is visible in the app menu;
a user override makes existing GTK Piper favorites open Qt and hides the duplicate
GTK menu entry. Close and reopen Piper after updating.
On a running KDE Plasma desktop, exact Piper taskbar pins are also redirected
through Plasma's live API, including pins that reference the old exported file
directly. Other pinned apps and their order are preserved. Previous pin values
are saved in `plasma-launchers.json` in the private backup directory.

Backups are private directories under `~/.local/state/james-os/piper/before-qt-*`.
They include the original launchers and GTK saved-profile library if present.
No device bindings are imported or written, ratbagd is not restarted, and the
desktop theme is not changed. The OS image continues to supply ratbagd 0.18 or
later; installing the user Flatpak is an explicit action.

Normal/G-Shift bindings use the existing G600 state. Qt Profiles currently means
on-device slots; the GTK saved-profile library is retained, but Qt does not yet
provide its saved-profile import/export UI. Physical writes and firmware
persistence remain outside the read-only deployment verification.

## Rollback

Close Piper. Launch the preserved GTK build directly:

```sh
flatpak run org.freedesktop.Piper/x86_64/master
```

To restore its menu/favorite behavior, remove only the generated
`~/.local/share/applications/org.freedesktop.Piper.desktop` override, identified
by `X-JamesOS-Piper-redirect=true`. If the backup contains
`applications/org.freedesktop.Piper.desktop`, restore that previous user override
instead. The original saved-profile directory remains untouched.
If the taskbar pin was migrated, unpin Piper Kirigami and pin the preserved GTK
launcher again. The backup's `plasma-launchers.json` records its previous target.

If an application bundle needs restoring, use the appropriate `.flatpak` file
from the printed backup directory:

```sh
flatpak install --user --reinstall /path/to/backup/Piper-bundle.flatpak
```

The previous GTK source recipe is also available through
`james-os-install-piper-gtk`; see [the GTK recipe](../piper-g600/README.md).
Do not import saved device profiles merely to roll back the application.

## Maintenance

Build and test the selected Piper source commit, including the installed-runtime
smoke checks. Publish the exact CI artifact and checksums, then update all pins
in `release.json` together. Test this installer with isolated command fixtures
and verify real G600 properties before/after UI inspection without pressing Apply.
Keep private device snapshots, backups and screenshots outside this repository.
