# PATCHES.md — every native patch applied

Target file: `extract/lib/arm64-v8a/libil2cpp.so`.
**RVA == file offset** for this binary (verified at 4 sites). All patches are
same-length (APK layout unchanged). Always verify original bytes first, keep the
`.bak`, and re-verify after writing.

Rebuild cycle after any `.so` change (do not skip steps):

```powershell
# 0. STAGE to spaceless paths first! 7za 16.04 + Start-Process split spaced
#    args ("D:\Critical" + "ops-Community" + ...) and 7za CREATES stray archives
#    instead of updating (seen: D:\Critical.7z, extract\*.apk 7 MB decoys).
#    ALWAYS verify the output ("Updating archive", size ~763 MB), never
#    "Creating archive" (~7 MB).
Copy-Item <repo>\critical-ops-1.32-f1831-offline.apk $T\offline.apk
Copy-Item <repo>\tools\uber-apk-signer-1.3.0.jar $T\signer.jar
# 1. inject (workdir = extract/, so zip paths stay lib/...):
7za u $T\offline.apk 'lib\arm64-v8a\libil2cpp.so'
# 2. sign (uber-apk-signer mints a FRESH temp debug key every run!):
java -jar tools\uber-apk-signer-1.3.0.jar -a critical-ops-1.32-f1831-offline.apk -o signed --allowResign
#    NOTE: -o and --overwrite are mutually exclusive (errors out if combined).
# 3. reinstall (adb streamed-install FAILS on 728 MB APKs — push + pm install):
& 'D:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 uninstall com.criticalforceentertainment.criticalops
& 'D:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 push 'D:\Critical ops-Community edition\signed\critical-ops-1.32-f1831-offline-aligned-debugSigned.apk' /data/local/tmp/x.apk
& 'D:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 shell pm install /data/local/tmp/x.apk
# 4. launch:
& 'D:\LDPlayer\LDPlayer9\adb.exe' -s emulator-5554 shell monkey -p com.criticalforceentertainment.criticalops -c android.intent.category.LAUNCHER 1
```

Uninstall-first is mandatory because the signer key changes every run
(`INSTALL_FAILED_UPDATE_INCOMPATIBLE` otherwise — adb swallows the reason).

## Patch table

| # | Offset | Orig bytes | New bytes | Meaning |
|---|---|---|---|---|
| P1 | `0xE29F00` | `68 02 00 34` | `85 00 00 14` | Boot gate: `cbz w8,#0xE29F4C` → `b #0xE2A114` (jump to success tail: `*out=1` + static flag set, telemetry `Create` skipped) |
| P2 | `0xD42F8C` | `FD 7B BF A9` | `C0 03 5F D6` | `AdManager.OnApplicationStarted` → `ret` (pure flag store, NRE'd on null `featureSettings`) |
| P3 | `0xAEE7C4` | `FD 7B BF A9` | `C0 03 5F D6` | `PlayerDataManager.OnApplicationStarted` → `ret` (same shape) |
| P4 | `0xDEADEC` (8 B) | `F7 0F 1C F8 F6 57 01 A9` | `00 10 40 F9 C0 03 5F D6` | `BackendManager.GetSessionToken` → `ldr x0,[x0,#0x20]; ret` (return `m_deviceSessionToken` = `"offline-token"`; the real builder needs protection-SDK + login tokens) |
| P5 | `0xE087E8` | `88 16 40 B9` | `28 00 80 52` | `LoginManager.ProcessLogin`: `ldr w8,[x20,#0x14]` → `mov w8,#1` (force Guest; `m_usedLoginType` never gets set — see WIRENAMES §5) |
| P6 | `0x9F4264` | `F4 4F BE A9` | `C0 03 5F D6` | Verdict poller `ef34bnq8q2jd` → `ret` (pure check, no side effects) |
| P7 | `0xCD7D38` (8 B) | `F5 0F 1D F8 F4 4F 01 A9` | `00 00 80 52 C0 03 5F D6` | `CheckErrors.MoveNext` → `mov w0,#0; ret` (coroutine instantly finished) |
| P8 | 19 addrs `0x9F4BE4`–`0x9F5EE4` (skip `0x9F57E4`) | `F4 4F BE A9` each | `C0 03 5F D6` each | 19 short verdict checks → `ret` (all verified write-free, capstone scan) |
| P9 | `0x9F57E4` | `F4 4F BE A9` | `C0 03 5F D6` | `rowaqw0cz8dj` (verdict check called from `AppManager.ChangeStateAsync`) → `ret` |
| P10 | `0x1206EF0` | `FF 83 03 D1` | `C0 03 5F D6` | `NetworkPeer.Connect(address,name)` → `ret` (kills ALL CFNet/ENet dial attempts; peer never connected in offline setup anyway, practice runs local — removes retry storm + UnableToConnect boot-from-match popup) |

Full list for P8: `0x9F4BE4,0x9F4CE4,0x9F4DE4,0x9F4EE4,0x9F4FE4,0x9F50E4,0x9F51E4,
0x9F52E4,0x9F53E4,0x9F54E4,0x9F55E4,0x9F56E4,0x9F58E4(n0b5384pb2ap),0x9F59E4,
0x9F5AE4,0x9F5BE4,0x9F5CE4,0x9F5DE4,0x9F5EE4`.

## DO NOT ret-patch (boot hang!)

8 long verdict methods `0x9F4364,0x9F4474,0x9F4584,0x9F4694,0x9F47A4,0x9F48B4,
0x9F49C4,0x9F4AD4` WRITE a caller verdict flag (`strb [x19],0/1`). Ret-patching
them hangs boot at 0% pre-ping (verified by bisect: 28-patch → hang; revert 27 →
boot works). If one fires post-login, patch only its throw branch, never the entry.

Rule of thumb: disassemble first (capstone `disasm.py` in Temp); `ret`-patch only
methods with no stores except prologue spills + class-init flags.

## How patches were found (repeatable)

1. Unity crash dialog gives `Class.Method` + call chain (no offsets).
2. `dump.cs` gives the method RVA (= file offset).
3. Capstone disassembly (`Temp\disasm.py <rva> <len>`); `script.json`
   (`ScriptMethod` list) resolves every `bl` target address to a name.
4. Classify: pure-check (reads + conditional throw) → `ret`; data-dependent →
   fix the mock; init/order logic → leave alone or force a constant (P5).
5. The `bl 0x97B4D0`-family = `raise_null_reference_exception` (every null-guard
   throw site calls it); `bl 0x97B3F8` = class initializer; `bl 0x97B394` =
   write barrier; `0x97B49C/0x97B4C8/0x97B4EC` = other throw helpers.
