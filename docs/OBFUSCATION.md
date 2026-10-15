# OBFUSCATION.md — names, RVAs, and file inventory

## 1. What is obfuscated

IL2CPP C# identifiers for the protection SDK and parts of game flow:
`b1df84um1p6bw5d` (boot gate), `uq4syc8r10xtscy6.n0yumwktt1tb28k` (gate flag @
0xE29ED0/ED4), `qi4t0ty88k.kiwp3jfkca7wlcq3` (cctor flag @ 0xE29EFC),
`i78bqku0yh8.r818ck0epp` + `tgl40htn`/`irxbayllqp1275pp` (verdict statics),
`efor15x.tav3uy2i1u3mrbeb5` + ~35 methods (`ef34bnq8q2jd`, `rowaqw0cz8dj`,
`n0b5384pb2ap`, `CheckErrors`, …), helpers `tm5e2vhk.gl2io0dough4aqp.*`,
`kreoisui5oqb804j.*`. Game logic (`BackendManager`, `LoginManager`,
`PlayerDataManager`, `GameModeData`, …) is NOT obfuscated — anchor on it.

Prior Q&A artifacts (from the handover brief, verified in disasm):
- Slots: `0x288EC88=com.criticalforceentertainment.criticalops`,
  `0x28C7750=fi.criticalforce.copsdev`, `0x28A9478=fi.criticalforce.copsstaging`,
  `0x28DF590="2-"`, `0x28B68D8="com."`, `0x2889EC8="org."`, `0x28F0C20="5-"`,
  `0x28E5EC0="-"`, `0x28DBAC0="1-{0}-{1}"`, `"0-init-fail"` @ 0x28C2C68.
- The three `eyvr3my` sub-checkers (incl. `scf0uy4vu` path/package checks and
  `ojbz5lf` `/proc*` existence checks → `"6-1"`–`"6-4"`) never run: the two
  `cbz` gates (0xB58AEC on `b1df`, 0xB58B14 on the static flag) return first.
- `BackendManager.ApplicationStart` @ 0xB58CBC; `StartRequest.ctor` @ 0xE29024
  (9 args); `ProcessSuccessfulResponse` parses via shared generic
  `JsonHelper.Deserialize<T>` @ 0x1028BB0 → JsonFx `JsonReader.ReadObject` @
  0x1DC10CC (exact key match, unknown keys ignored).
- `EventManager.Send<T>` (shared) @ 0xF16C64; `GetSessionToken` @ 0xDEADEC;
  `SetSessionToHeaders` @ 0xDEACC4; `ProcessLogin` @ 0xE08720 with login-type
  jump table @ 0x1EEF0F0 (Guest/None→`m_guest`, others→their handlers,
  Custom/out-of-range→throw); `GuestLoginHandler..ctor` @ 0xBD8318;
  `FindFactionProperties` @ 0xED0F58; `GameModeSystem.Init` @ 0xED9650;
  `PlayerInfo.SetLocalPlayer` @ 0xAF2918; `CheckErrors.MoveNext` @ 0xCD7D38.

## 2. TypeDefIndex anchors (stable across dumps, use for re-location)

`StartRequest.Return` 8687 / `StartRequest` 8688 / `LoginData` 7099 /
`UserProfile` 7997 / `BackendManager` 6760 / `LoginManager` 6791 /
`GameModeData` 9794 / `FactionProperties` 9662 / `ServerData` 9474 /
`LoginType` 9475 / `TutorialStage` 9464 / `LoginParameters` 9476 /
`GetServersRequest` 8634 / `LoginRequest` 8643 / `CheckUsernameRequest.Return`
8592 / `ChangeUsernameRequest.Return` 8589 / `CriticalPassStatusData` 8601 /
`ConfigData` 11466 / `LaunchConfig` 7096 / `FeatureSettings` 7089.

## 3. Internal files & data (workspace)

- `critical-ops-1-32-0-f1831.apk` — original; `critical-ops-1.32-f1831-{gatepatch,
  offline}.apk` — intermediates; `signed/*-aligned-debugSigned.apk` — installs.
- `extract/` — APK tree; `lib/arm64-v8a/libil2cpp.so` (44,741,824 B) + `.bak`.
- `dump/` — `dump.cs`, `script.json` (114,494 methods; `Addresses` list),
  `stringliteral.json` (15,370), `il2cpp.h`, `DummyDll/` (no attr blobs).
- `extract/assets/bin/Data/Managed/Metadata/global-metadata.dat` (v27,
  8,062,536 B) — string table useful for negative checks only.
- `patch_out/` — URL-patched assets + `swap.json` (paths reference stale
  `Desktop` root — files themselves are fine).
- `tools/proxy/offline_mock.py` (the server), `tools/proxy/api_proxy.py`
  (legacy online forwarder), `tools/patch/patch_config_asset.py`,
  `tools/analyze/memscan.py`, `tools/hook/` (frida-server 17.23.3 x86_64
  present but never needed), `tools/Il2CppDumper*`, `tools/jadx*`.
- `logs/` — `offline_mock.log` (API journal), `api_proxy.log` (legacy traffic:
  `country`, `telemetrics/record` shapes), `run1_online.log`,
  `patched_run.log`, `*.png` (screenshots).
- `shots/`, `smali_out/`, `smali_check/`, `jadx_out*/`, `classes2_patched.dex`,
  `AGENT_BRIEF_bootgate.md` — prior-phase artifacts, mostly superseded.
- Temp scripts (not in repo): `%LOCALAPPDATA%\Temp\opencode\*.py`
  (`disasm.py` capstone helper — the single most-used tool, `disbatch.py`,
  `classify.py`, `classdump.py`, `blobhunt.py`, `blobwalk.py`,
  `metastrings*.py`, `wirename.py`, `wirenames*.txt` pool dumps).

## 4. Porting to another version

Re-dump, then re-locate in this order: (1) boot-gate shape (`cbz` after the
telemetry-`Create` call site — search `"1-{0}-{1}"` usage); (2) URL strings in
`assets/bin/Data/*` (search `criticalforce.fi`); (3) wire pool (`\0`-separated
run near other JsonName values — search for `"deviceid"`); (4) verdict class
(search `"Error_0xA38B"`/`"1-{0}-{1}"` xrefs); (5) re-verify every PATCHES.md
offset — RVAs WILL shift, the shapes won't.
