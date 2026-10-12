# Piper for James OS

Piper 0.8, pinned to upstream commit
[`5d3c8845b55643595ccb8029dfa5c7a2fb079e77`](https://github.com/libratbag/piper/commit/5d3c8845b55643595ccb8029dfa5c7a2fb079e77),
with two small patches:

- Preserve the installed Logitech G600 Normal/G-Shift selector. Normal buttons
  retain indices 0–19; shifted buttons retain indices 21–40. The reserved index
  20 is not shown. No device configuration is imported or written by installation.
- Follow `org.freedesktop.appearance`'s `color-scheme` portal setting, including
  changes while Piper is open. Dark mode works in the GTK 3 Flatpak on KDE.
  An explicit `GTK_THEME` override remains authoritative, and desktops without
  the portal retain their GTK preference.

The July 2026 local Flatpak already included upstream through `452f46ce8619`.
The newer upstream commit fixes a device-disconnection assertion while the
device selection page is visible. Upstream still calls this version 0.8.
The G600 patch was recovered from the installed app after its original local
build directory was removed. The dependencies match that app's build recipe.

## Install or update

Run `james-os-install-piper` as your desktop user. From a source checkout, run
`bash system/usr_bin__james-os-install-piper` instead. This requires a user
Flathub remote and downloads the Flatpak Builder and GNOME 49 SDK if needed.
It builds in the user's cache, keeps the local Flatpak repository under
`~/.local/state/james-os/piper/repo`, saves the existing custom `master` build
as a rollback bundle, and replaces the user installation of
`org.freedesktop.Piper//master`. Close and reopen Piper after installation.

The installer does not restart ratbagd, change the desktop theme, or modify
mouse bindings. The image continues to provide the libratbag/ratbagd backend.
This source and installer are included in the image; building the user Flatpak
is an explicit user action.

## Rollback

Close Piper and run `flatpak install --user --reinstall /path/to/piper-before-….flatpak`
with the backup path printed by the installer, then reopen it.

## Maintenance

Update the upstream commit in `org.freedesktop.Piper.json`, rebase the patches,
and rebuild before deploying. Run upstream's SVG checks and Python checks,
the added `tests/appearance-test.py`, and inspect both G600 layers with a real
device. Read all ratbagd properties before and after UI verification to confirm
that bindings, profiles, resolutions, and LEDs are unchanged. Keep device
snapshots and screenshots outside this repository.
