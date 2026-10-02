# Working installer recovery baseline

This branch is based on the user-confirmed working Stem Separator installer and is intentionally isolated from experimental rebuilds.

## Verified installer

- Archive: `Stem_Separator_Setup_1.0.0.zip`
- Installer: `Stem_Separator_Setup_1.0.0.exe`
- Installer size: 340,136,700 bytes
- SHA-256: `9c029c23628f555acccc4635c85a1a4471e96b115c6ba71935d8472994831470`
- Installer framework signature: Inno Setup 6.7.0
- Product version represented by installer filename: 1.0.0

## Recovery rule

The uploaded installer is the behavioral reference for the new build. Preserve the known-working separation behavior first, then add the newer UI/features incrementally. Do not replace the separation core until an equivalent end-to-end Windows test proves the replacement.

## Release gate

A replacement installer is not considered ready until it installs cleanly, launches, performs a real separation, creates the expected outputs, exposes Desktop and Start Menu shortcuts, registers an uninstaller, and uninstalls without deleting user exports.
