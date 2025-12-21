# GitHub Copilot Instructions for James OS

## Project Overview

James OS is a custom Fedora Atomic Desktop image built using Universal Blue's toolkit, based on Bazzite. It provides a customized immutable Linux desktop experience with specific software pre-installed for productivity and gaming.

**Key Features:**
- Replaces Bazaar with KDE Discover for software management
- Replaces GNOME Disk Utility with KDE Partition Manager
- Pre-installs 1Password and its CLI for password management
- Pre-installs Visual Studio Code for development
- Adds Konsole and Yakuake terminal emulators alongside ptyxis
- Includes Piper for mouse configuration and CoreCtrl for power management
- Pre-installs Discord RPM

## Tech Stack

- **Base Image:** Fedora Atomic (via Bazzite from Universal Blue)
- **Build System:** Podman/Buildah with Containerfile
- **Package Management:** DNF5 (during build), rpm-ostree (runtime)
- **Task Runner:** Just (Justfile)
- **Image Builder:** Bootc Image Builder (BIB) for ISO/QCOW2/RAW
- **CI/CD:** GitHub Actions
- **Container Registry:** GitHub Container Registry (ghcr.io)

## Repository Structure

```
├── .github/
│   └── workflows/        # GitHub Actions CI/CD pipelines
├── system/               # System configuration files
├── Containerfile         # Main container build definition
├── build.sh              # Package installation and configuration script
├── Justfile              # Development commands (build, test, VM)
├── image.toml            # BIB configuration for VM images
└── iso.toml              # BIB configuration for ISO images
```

## Build Process

### Container Image Build
The image is built from the Containerfile which:
1. Starts from `ghcr.io/ublue-os/bazzite:stable`
2. Copies `build.sh` and system configuration files
3. Executes `build.sh` to install packages and configure the system
4. Commits the ostree container

### Build Script (`build.sh`)
The build.sh script:
- Adds third-party repositories (1Password, VS Code, Discord)
- Installs desired packages via DNF5
- Removes unwanted packages (gnome-disk-utility, bazaar, lutris)
- Relocates 1Password from `/var/opt` to `/usr/lib` for ostree compatibility
- Sets up proper permissions and groups for 1Password security
- Creates sysusers and tmpfiles configuration for 1Password

## Development Commands

Use the `just` command to run common tasks:

### Building
- `just build [target_image] [tag]` - Build the container image locally
- `just build-qcow2` - Build a QCOW2 VM image
- `just build-iso` - Build an ISO installer
- `just build-raw` - Build a RAW disk image

### Testing VMs
- `just run-vm-qcow2` - Run QCOW2 image in VM
- `just run-vm-iso` - Run ISO in VM
- `just spawn-vm` - Run VM with systemd-vmspawn

### Maintenance
- `just lint` - Run shellcheck on all bash scripts
- `just format` - Format bash scripts with shfmt
- `just clean` - Clean build artifacts
- `just check` - Check Justfile syntax

## Coding Standards

### Shell Scripts
- Use `#!/usr/bin/env bash` shebang
- Enable strict error handling: `set -euo pipefail`
- Use `dnf5` (not `dnf`) for package management
- Clean up caches and temporary files to keep image size small
- Document complex operations with comments

### Security Practices
- Import GPG keys for third-party repositories
- Use specific GID values (1500+) to avoid conflicts with user groups
- Set appropriate permissions (4755 for suid, g+s for sgid)
- Remove repository files after package installation

### Container Best Practices
- Minimize layers by chaining commands with `&&`
- Clean up caches and temporary files: `rm -rf /var/cache/dnf /tmp/*`
- Commit ostree container at the end: `ostree container commit`
- Use `COPY --chmod` for file permissions when possible

## Common Workflows

### Adding a New Package
1. Edit `build.sh`
2. Add repository configuration if needed (third-party packages)
3. Import GPG key if needed
4. Add package name to `dnf5 install` command
5. Clean up repository files if added
6. Test locally with `just build`

### Removing a Package
1. Edit `build.sh`
2. Add package name to `dnf5 remove` command
3. Test locally with `just build`

### Modifying System Configuration
1. Add configuration file to `system/` directory with appropriate naming (e.g., `etc__hostname`)
2. Add `COPY` command in Containerfile to place file in correct location
3. Test locally with `just build`

### Testing Changes Locally
1. Build image: `just build localhost/james-os test`
2. Build VM image: `just build-qcow2 localhost/james-os test`
3. Run VM: `just run-vm-qcow2 localhost/james-os test`
4. Test functionality in the VM

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/build.yml`):
- Triggers on: push to main, pull requests, schedule (daily), manual dispatch
- Builds the container image using buildah
- Tags with: latest, latest.YYYYMMDD, YYYYMMDD, PR sha
- Pushes to GitHub Container Registry (ghcr.io)
- Signs images with Cosign
- Runs on: ubuntu-24.04

## Important Notes

### OSTree/Immutable System Considerations
- System is read-only at runtime; changes must be in container image
- `/usr` is immutable, `/var` and `/etc` are mutable
- Applications in `/opt` or `/var/opt` need special handling (see 1Password example)
- Use tmpfiles.d for symlinks created at boot
- Use sysusers.d for group/user creation at boot

### Package Management
- Use `dnf5` during image build (not at runtime)
- Users install software via Flatpak, Toolbox, or rpm-ostree layering
- Focus on essential system packages in the image

### File Paths
- Always use absolute paths when referencing files
- Build scripts run in `/tmp` during container build
- System files are in standard FHS locations after COPY

## Testing

### Manual Testing
1. Build the image locally
2. Create a VM image (QCOW2 or ISO)
3. Boot the VM and verify:
   - All expected packages are installed
   - Software centers work (KDE Discover)
   - Pre-installed applications launch correctly
   - System boots and operates normally

### Automated Testing
- Shellcheck runs on all `.sh` files via `just lint`
- GitHub Actions builds images on every PR
- Daily scheduled builds ensure continued compatibility with upstream Bazzite

## Resources

- [Universal Blue Documentation](https://universal-blue.org/)
- [Bazzite Documentation](https://docs.bazzite.gg/)
- [Fedora Atomic Desktops](https://fedoraproject.org/atomic-desktops/)
- [Bootc Image Builder](https://github.com/osbuild/bootc-image-builder)
- [OSTree Documentation](https://ostreedev.github.io/ostree/)
- [Just Command Runner](https://github.com/casey/just)

## Tips for AI Assistants

- This is an immutable OS built as a container image; traditional package management doesn't apply
- Changes must be made to the Containerfile or build.sh, not applied at runtime
- OSTree and Fedora Atomic concepts are critical to understanding the architecture
- The build.sh script is the primary place for customization
- Testing requires building container images and VM images, which takes time
- Follow the existing patterns for adding/removing packages
- Security is important: proper GPG key handling, file permissions, and group management
