# James OS Vencord bundle

`build.sh` pins upstream Vencord to a tag and exact commit, then applies this
source-only overlay before building `/usr/share/vencord`. The installed
`james-os-version.txt` records that upstream version and commit.

Included plugins:

- KDEIdleSync: KDE session idle integration.
- CodexWindowBridge: opt-in local Unix-socket window controls. Disabled by default;
  the socket is mode 0600 and mutating requests require `allowMutation`.
- UserTimeZones: locally configured time-zone labels. Personal entries remain in
  the user's Vencord settings, not in this repository.

Discord's system launcher patches its updater-managed app to load
`/usr/share/vencord/patcher.js`. A user launcher or previously injected development
checkout can override this path and must be migrated separately, preserving
settings and backups. Updating the OS image cannot update a development checkout.

The image workflow builds pull requests without publishing. Main branch builds
publish and sign `ghcr.io/jheinem1/james-os:latest` and dated tags. A successful PR
build is not a released image. Activating a new OS deployment normally requires a
reboot; replacing an existing writable runtime overlay is only a temporary hotfix.
