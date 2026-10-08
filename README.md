# James OS

A [Fedora Atomic](https://fedoraproject.org/atomic-desktops) image built with [Universal Blue](https://universal-blue.org/)’s toolkit.

## Changes from Bazzite
- Replaces GNOME Disk Utility with KDE Partition Manager.
- Removes Lutris.
- Preinstalls 1Password and the 1Password CLI.
- Adds back Konsole as a terminal option and Yakuake to complement it (ptyxis remains the default for compatibility with some Bazzite features).
- Launches the System Update shortcut in Konsole and preinstalls OpenAI's official ChatGPT desktop app, including ChatGPT Work and Codex.
- Keeps Homebrew formula upgrades working in both automatic and manual System Update runs by preserving Homebrew's prefix entrypoint through uupd's user switch.
- Preinstalls the libratbag/ratbagd backend for configuring supported devices; graphical frontends such as Piper can be installed separately.
- Preinstalls CoreCtrl for power management.
- Adds an Open With action in Dolphin to encode videos for Discord using CPU H.264 with a target-size popup and progress bar.
- Installs Discord from the official RPM at image build time, patches it with a pinned Vencord build when app resources are available, and includes a KDE idle/lock watcher that can drive Discord presence over a local socket.
- Includes a KDE user service that automatically reapplies the right HDR display configuration after a KVM reconnect on the default dual-monitor setup.

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

## ChatGPT browser permissions on Atomic desktops

Automatic and manual System Update runs also update the installed ChatGPT/Codex
desktop RPM in the current boot. Image downloads alone stage a deployment for
the next reboot; they do not update the currently running desktop package.
The live updater verifies OpenAI's package signature, refuses downgrades, and
uses a temporary OSTree `/usr` overlay without creating a persistent RPM override.
It preserves the canonical `CODEX_HOME` launcher and leaves running app sessions
open. Quit and reopen the app to use its new version.

Run `sudo james-os-update-chatgpt` for an app-only update. The overlay is discarded
at reboot, so also complete System Update for the next boot's image. The updater
checks that OSTree's shutdown finalization services are active when an image is
staged and explicitly reports the reboot requirement. A forced shutdown or a
full disk can still prevent the staged image from becoming bootable; the live
app update makes desktop upgrades independent of that activation step.

The image launcher resolves `CODEX_HOME` to its canonical path before starting
ChatGPT and Codex. This avoids Browser Use's configuration reader rejecting
Bazzite's `/home` symlink when it loads saved website permissions. The default
remains the existing `~/.codex` directory; configuration and history stay in place.

If an existing MCP configuration explicitly sets
`mcp_servers.node_repl.env.CODEX_HOME`, use the canonical path there too (for
example `/var/home/<user>/.codex` on Bazzite). An explicit MCP environment override
takes precedence over the launcher environment. Reconnect the helper after
changing that override. This fix preserves browser permission enforcement.

## KWin MCP user installation

Run `james-os-install-kwin-mcp` as your desktop user (without sudo) to install
[the customized KWin MCP server](https://github.com/jheinem1/kwin-mcp-mcp2).
The installer downloads release `v0.7.1-mcp2`, verifies its pinned SHA-256,
backs up any existing uv tool environment, and replaces the user-level tool.
The image includes the installer and native build dependencies; it does not
start desktop automation or install a tool into anyone's home during image build.

The release adds relative mouse movement for locked game cursors and button
presses without cursor repositioning. Input still affects the focused session.
Reconnect the MCP client after installing to discover the new tools. No reboot
or desktop restart is needed. The existing `~/.local/bin/kwin-mcp` command remains
the normal MCP entrypoint (unless you configured a different uv tool bin directory).

To apply this on an older JamesOS image that already has uv and the native
Python build dependencies, run the same installer from a checkout:

```bash
bash system/usr_bin__james-os-install-kwin-mcp
```

Backups are stored under `${XDG_STATE_HOME:-~/.local/state}/james-os/kwin-mcp`.
For rollback, disconnect the MCP client, move the current `kwin-mcp` directory
out of `uv tool dir`, and extract the chosen backup into that directory. The uv
entrypoint symlinks continue to point at the restored environment.
