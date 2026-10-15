# Reproduce — Critical Ops v1.32.0.f1831 Offline + God-Mode

Devlog for replicating this work (same game other versions, or similar Unity IL2CPP targets).
Read in order: `PATCHES.md` → `NETWORK.md` → `WIRENAMES.md` → `VERDICT.md`,
then `OBFUSCATION.md` (reference) and `DEVLOG.md` (session chronology).

## What was achieved

Full offline boot of Critical Ops 1.32.0.f1831 on an emulator:
production boot-gate bypassed → API redirected to a LAN mock → session/login
mocked → god-mode profile (level 999, 2000 owned items, elite battlepass) →
main menu with working UI → bot-game creation reaches gameplay init.

## Current frontier (where the next session starts)

`GameModeData.FindFactionProperties() Failed - Can't find faction properties id:1`
when starting a bot game. The `Factions` list never populates — its wire key is
not discoverable by the pool method (see `WIRENAMES.md` §5 and `DEVLOG.md` day-end).

## Environment

| Item | Value |
|---|---|
| Target | `com.criticalforceentertainment.criticalops`, v1.32.0.f1831 |
| Engine | Unity 2020.3.33f1, IL2CPP, `arm64-v8a` |
| Emulator | LDPlayer 9, x86_64 (ARM translated), adb device `emulator-5554` |
| ADB | `D:\LDPlayer\LDPlayer9\adb.exe` (has `7za.exe`, `dnconsole.exe` next to it) |
| Host LAN IP | `192.168.0.249`, mock port `8080` |
| Workspace root | `D:\Critical ops-Community edition` |
| Original APK | `critical-ops-1-32-0-f1831.apk` (763,605,819 B) |
| Work APK | `critical-ops-1.32-f1831-offline.apk` → signed output in `signed/` |

## Key directories

- `extract/` — APK contents; `extract/lib/arm64-v8a/libil2cpp.so` is the patch target.
  `extract/...so.bak` = pristine backup (pre-patch).
- `dump/` — Il2CppDumper output: `dump.cs` (515,243 lines), `script.json`
  (address→name map), `stringliteral.json`, `DummyDll/` (no custom-attribute blobs — dead end).
- `patch_out/` — 4 URL-patched config assets + `swap.json`.
- `tools/proxy/offline_mock.py` — the offline server (sole network dependency).
- `tools/proxy/api_proxy.py` — OLD online forwarder (STOP before using the mock; port conflict).
- `tools/patch/patch_config_asset.py` — URL redirect generator (has stale hardcoded
  `Desktop` ROOT path — patch_out/ files are already generated, reuse them).
- `logs/offline_mock.log` — every game request lands here; this file IS the API spec.
- `C:\Users\HAYMON\AppData\Local\Temp\opencode\` — scratch scripts (`disasm.py`,
  `blobhunt.py`, `metastrings*.py`, `classdump.py`, `wirenames*.txt`).

## The 10-second method (for a new version)

1. Dump IL2CPP (`dump.cs` + `script.json` are mandatory; `DummyDll` is optional).
2. Apply `PATCHES.md` §1 (boot gate) + §2 (URL redirect) → sign → install.
3. Run `tools/proxy/offline_mock.py`, launch, read `logs/offline_mock.log`.
4. For each 404: decode request/response classes from `dump.cs`, get wire names
   via `WIRENAMES.md` §1 (pool method), add a mock route. Iterate.
5. For each managed crash: read the trace → disassemble the faulting method
   (capstone; `script.json` resolves callees) → data fix (mock) or 4-byte `ret`
   patch (native). Never ret-patch methods that write caller flags (`VERDICT.md` §4).
6. Protection verdicts (`Error_0xA38B`-family): kill only write-free check methods.
