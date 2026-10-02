# Working installer forensic verification

The user-confirmed working installer was inspected before reconstructing the application.

## Container-level verification

- ZIP contains exactly one payload: `Stem_Separator_Setup_1.0.0.exe`
- Payload size: 340,136,700 bytes
- Windows PE type: GUI executable, PE32 installer bootstrap
- Embedded product strings include `Stem Separator Setup` and `Stem Separator`
- Baseline SHA-256 is recorded in `docs/working-installer-baseline.md`

## Reconstruction policy

The installer is treated as a behavioral oracle, not as a source-code substitute. New implementation work must preserve the behavior the user confirmed works and prove parity through Windows end-to-end tests before newer UI/features are layered on.

The first parity target is: install -> launch -> choose media -> separate -> verify all expected stem files -> uninstall while preserving user output.
