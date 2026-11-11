# Piper Kirigami signed update channel

JamesOS supplies `james-os-install-piper`, which subscribes the desktop user to
Piper's signed Flatpak repository. It installs the latest published release, not
a fixed application commit. Subsequent releases arrive with normal Flatpak
updates (including Discover and `flatpak update --user`). Updating JamesOS itself
is not required for a new Piper release.

## Provisioning status

This integration is prepared but is **not ready to ship**. The publisher must
configure GitHub Pages and the signing secret, publish and test its repository,
then add the verified public key as `piper-repository.gpg` and its uppercase
primary fingerprint to `repository.json`. Until then, both installer and final
image verification fail closed. Never disable signature verification to bypass
this gate, and never put the private signing key in this repository.

The planned remote is `piper-kirigami` at
`https://jheinem1.github.io/piper-kirigami/repo/`. The app keeps the exact identity
`io.github.jheinem1.PiperKirigami/x86_64/development`; `development` names its
existing update channel, not a fixed version. Only tested published releases
should advance that channel. KDE Platform 6.11 remains a runtime dependency.

## Install and migrate an existing bundle

Run `james-os-install-piper` as your desktop user, without sudo. The installer
checks the bundled public key, refuses existing remotes with another URL or key
or disabled signature verification, and asks Flatpak to verify the signed remote.
It backs up existing Piper bundles, launchers and the GTK saved-profile library,
then reinstalls the same app identity from the named remote. It never uses
`--delete-data`; the existing app's private directory and mouse state remain.
The installed origin must match the update remote before launcher activation.

After installation, the installer checks matching Qt/PySide/Shiboken versions and
renders the actual installed mock UI. Failure leaves launchers and private
backups unchanged, although the new application may remain installed. GTK Piper
remains available for rollback. No ratbagd restart, device write, shared-runtime
downgrade or desktop-theme change is performed.

Backups live in private `~/.local/state/james-os/piper/before-qt-*` directories.
They contain the previous bundles and launchers, copied profile library,
repository metadata, remote information, installed commit and runtime evidence.
Piper's app ID and Flatpak branch stay unchanged to preserve data and updates.

## Rollback

Close Piper and launch the preserved GTK application with
`flatpak run org.freedesktop.Piper/x86_64/master`. Restore the saved GTK user
launcher if present; otherwise remove only the generated launcher override
identified by `X-JamesOS-Piper-redirect=true`. For migrated taskbar favorites,
repin GTK Piper; prior pin targets are recorded in `plasma-launchers.json`.

A saved application bundle can be restored with
`flatpak install --user --reinstall /path/to/backup/Piper-bundle.flatpak`.
This may return the app to a bundle origin; rerun the installer when ready to
resume the signed update channel. Do not import device profiles merely to roll
back the frontend. Existing private profile data is not deleted by installation.

## Verification boundary

The final image verifies its installer, trust configuration, required commands
and libratbag 0.18+ package, without starting ratbagd. Target-side runtime checks
run during initial installation/migration. Ordinary later Flatpak updates do not
invoke this installer or its backup/runtime hooks; release CI must test each
published build against its matching Platform runtime. Independently updated
Qt runtimes can still require a matched Piper release rebuild. Physical hardware
writes, firmware persistence and live-desktop update migration need separate
verification in a disposable test account before rollout.
