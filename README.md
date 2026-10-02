# Stem Separator

Clean Windows desktop stem-separation application.

This repository was created from scratch. No source code, build scripts, packaging files, or workflows from the previous Stem Separator projects are reused.

## Engineering rules

- Python 3.11 runtime is pinned.
- Separation runs through a Python API inside the packaged process; never through `sys.executable -m demucs` from a frozen executable.
- Audio decoding/encoding and FFmpeg availability are validated explicitly.
- Model acquisition and cache behavior must be deliberate and visible to the user.
- CI must test source imports, packaged imports, real separation, installation, installed-app launch, shortcuts, uninstaller registration, and uninstall.
- A Windows installer is not published until every release gate passes.
- Installer creates Desktop and Start Menu shortcuts and a registered uninstaller.
- Uninstall must not remove user exports.

## Initial milestone

Prove the audio engine end-to-end before building the full GUI or installer.


## CI status note

The clean repository has been tested with Windows and Linux GitHub-hosted runner probes. If a probe reports zero executed steps and runner_id 0, no application code has run; application development remains isolated from that external runner-allocation condition.
