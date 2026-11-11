# KDE updater integration

The image downloads the exact native release asset recorded in `package.json`.
The repository-pinned SHA256 is verified before any archive metadata is parsed
or files are extracted. Source and Controllable commits, fork/package versions,
architecture, operating-system target, binary digest and production build mode
must match the package contract. Only the private updater tree is accepted;
escaping links, special files, duplicate paths and pre-existing runtime
verification markers are rejected. The staging directory is published only
after all checks pass.

No compiler or development packages are installed during the image build.
The package uses distribution Qt/KDE/SDL libraries, so it is not portable.
The Fedora target is explicitly pinned as `os_version` in `package.json` and
must match the builder's `VERSION_ID` before download. The current Bazzite
stable image targets Fedora 45, despite the running desktop and older native
release using Fedora 44. The asset filename includes the pinned target; do
not infer compatibility from the running desktop or the fork version alone.
The final image still checks dynamic linking and safe offscreen startup on
every build. A Bazzite runtime change can require a new package build revision;
never bypass the runtime check or silently replace an existing release asset.

To update the package, publish and test a new updater image release first,
then update all matching pins in `package.json` through a reviewed image PR.
Do not use a moving latest URL or trust a checksum fetched alongside the asset.
For a downloaded asset, the same validation can be run without network access:

```sh
python3 system/bazzite-updater-kde/acquire.py \
  --lock system/bazzite-updater-kde/package.json \
  --archive /path/to/release.tar.xz --destination /path/to/new-staging-directory
```

The target staging directory must not exist. This only stages private package
files; it does not modify the running desktop or perform an update.

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

After successful runtime verification, the image records its source commit
in `runtime-verified` and its fork release in `fork-version`. Temporary user
launchers prefer `/usr/bin/bazzite-updater` after booting a verified image
with identical source or a newer well-formed fork version. Older, unverified,
or malformed image metadata keeps the local fallback. No reboot is needed
or performed to test this routing decision.
