# KDE updater integration

The image builds `jheinem1/bazzite-updater-kde` at the exact `UPDATER_REF` in
`Containerfile`. Its upstream Controllable submodule is pinned separately.
Build-only dependencies stay in a disposable stage. The final image keeps
its distribution Qt/KDE runtime; undefined symbols or QML startup errors
fail the build before image publication.

The fork's application and Controllable module live privately under
`/usr/lib/bazzite-updater-kde`. The existing `/usr/bin/bazzite-updater` command
and desktop IDs launch the fork, preserving command arguments and trusted
`/etc/bazzite-updater` configuration. Config files are never replaced by this
integration. `BAZZITE_UPDATER_UI_PROBE` is explicitly OFF.

The distribution executable is retained at
`/usr/libexec/bazzite-updater-upstream` for diagnosis or temporary recovery.
An OSTree deployment rollback also restores the previous whole image.
Neither recovery operation nor an actual update/rebase/reboot is run by
build verification. The smoke test starts an offscreen window for eight
seconds without pressing any action buttons.
