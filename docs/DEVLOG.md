# DEVLOG.md — session chronology (error → fix chain)

Each entry: symptom → diagnosis → fix. Times are 2026-10-15 AST (single session).

1. **Boot telemetry `1-83-Error_0xA38B:`** (handover). Disasm showed the real
   gate (`b1df…`, `cbz` @ 0xB58AEC/0xB58B14 skipping `ApplicationStart`).
   → P1 (4-byte branch @ 0xE29F00). APK rebuilt via 7za-inject + uber-apk-signer;
   `adb install` silently fails on 728 MB → push + `pm install`.
2. **`HTTP 500` from production `app/start`.** Gate passed; server rejects.
   Decision: go fully offline instead of fighting attestation.
3. **URL redirect.** 4 config assets × 7 URL pairs → `192.168.0.249:8080`
   (length-preserving junk fillers); proxy CANON rules map them back.
4. **`offline_mock.py` born.** Ping `200` → game advances to `app/start`
   (the ping path is `/api/status/ping/`, found in logcat, not `/status/ping/`).
5. **Session decode.** `StartRequest.Return` (12 fields) from `dump.cs`;
   wire names from the `.rodata` pool (WIRENAMES.md §1). Key break: the pool
   run mirrors typedef order. `tutorialCompleted:true` flips telemetry
   `OnboardingPhase` to `GameplayStarted` (proof of parse).
6. **NRE chain #1 (event handlers).** `AdManager` → `PlayerDataManager` →
   `CriticalPassPrompt` `OnApplicationStarted` NRE'd. Root cause found by
   disassembly: each reads `evt.featureSettings?.X` and the null path is an
   explicit `raise_null_reference_exception` — my `featureSettings` key was
   wrong (`"features"` ≠ `"enabledFeatures"`). Fixed data instead of code;
   ret-patched only AdManager + PlayerDataManager (P2/P3, kept — harmless).
7. **`GetSessionToken: Failed to build header`** on server-list request.
   `SetSessionToHeaders` slow-path needs login/attestation tokens. → P4
   (return `m_deviceSessionToken`). Server list then reaches the mock.
8. **Server list + login screen.** Mocked `ServerData[]`; UI renders
   Guest/Facebook/Google buttons. Guest login forced via P5 (the session
   `loginType` key never binds — absent from binary; `m_usedLoginType` stays 0).
9. **God-mode login.** `LoginData` (35 fields) + `UserProfile` decoded;
   level 999 + 2000 owned items + elite battlepass served. Telemetry confirms
   (`CurrentPlayerLevel:999`, `Rank:12`, `Guest`). Crash trail then led through:
   `StoreConfiguration(products must be {})` → `NewsData(videos/articles:[])` →
   `ranked_season.rank_thresholds` (rank calc NRE) → verdict enforcers.
10. **Verdict enforcers.** `Error_0xA38B` rethrown per-frame (`ef34bnq8q2jd`,
    P6), then via `CheckErrors` coroutine (P7, must return false not bare ret),
    then 28 same-shape siblings — batch-patched 28 → **boot hung at 0%**.
    Bisect: the 8 long ones write caller verdict flags; reverted 27, kept the
    write-free `rowaqw0cz8dj` → boot works. Then patched the 19 short ones
    (P8/P9). Lesson: classify before batch-patching (PATCHES.md rule).
11. **Menu + name flow.** `SetLocalPlayer` NRE → clan+stats must be non-null
    (stub clan served). `namecheck` → always available; `namechange` → echo.
    Battlepass (`purchased:true`) + client config stubs unblock loading.
12. **Bot-game gameplay init.** `FindFactionProperties id:1` throws — the
    `Factions` list never populates (key absent from binary; `factions`/
    `Factions` don't bind) and `FactionProperties.Id` has no discoverable key.
    → OPEN FRONTIER (next session).

13. **Duplicate-key wipe (2026-10-16).** `login_body()` had TWO
    `"game_mode_state"` keys — detailed factions payload + trailing `{}`.
    Python kept the `{}` → `GameModeData` always null → `FindFactionProperties`
    could never succeed. Fix: single `game_mode_state_body()` helper, payload
    served under both `game_mode_state` (true wire key, pool-confirmed) and
    `GameModeData` (field-name fallback); faction entries union-serve all id
    variants + full snake_case pool fields; pre-emptive
    `/gamemode/gamemodestate` route added. Lesson: `json.dumps` never warns on
    duplicate keys — grep the mock for them after every edit.

14. **Factions fix verified (2026-10-16).** Duplicate-key wipe removed;
    bot-game creation now passes `FindFactionProperties` and reaches
    `PracticeModeOfflineServer..ctor` → new NRE in
    `KillMedalsHandler..ctor(definitions)` (0xAAEFF4): ctor null-guards
    `Conditions+0x18` (0xAAF154) and `Medals+0x10` (0xAAF268). Pool confirms
    `medals`/`priorities` keys; `conditions`/`definitions` absent → union-serve
    all with `[]` (loops skip, empty medal set, no awards offline).

15. **Bot-spawn skin crash (2026-10-16).** `GetVariant` threw
    `Could not locate prototype. idx:0` — disasm (0xFDDE20) shows the resolved
    def had 0 prototypes. Source traced: `GameSystem.CreateCharacter`
    (0xA80E5C) reads `FactionProperties+0x2C` (`CharacterSkinDefAssetId`,
    `ldr w25,[x0,#0x2C]`) into `Character.Init`. Our stub served 0. Fix:
    extracted `assets/assetpack/characterskindefs` from the APK, parsed with
    UnityPy → Coalition=9581 (5 prototypes), Breach=9582 (5), Jesse=9861 (1);
    factions now serve real IDs (method: 7za-extract bundle + UnityPy
    typetree `m_ID`/`m_prototypes` — reusable for any IDAsset stub).

16. **Random mid-match disconnects (2026-10-16).** `UnableToConnect` popup +
    QUIT boots the player; overlay log (`0143: Connecting` → `0173: Connection
    timeout` → `0183: Exaused retries` — numbers are seconds-since-boot)
    shows the CFNet/ENet `NetworkPeer` retry loop against our mocked server
    addr. UDP capture on :8080 confirmed ENet CONNECT spam (`4fff peerID`,
    ~30/s retransmits, nothing answering). Practice runs fully local and the
    peer NEVER connected in our setup, so killing attempts changes nothing
    functionally → P10 NOPs `NetworkPeer.Connect` (0x1206EF0). Rebuild
    lesson: stage APK+signer to spaceless Temp paths or 7za mangles spaced
    args and writes decoy archives. ENet stub server (VERIFY_CONNECT + auth)
    remains the long-term path to real multiplayer — CONNECT bytes captured
    in this session's tool output.

17. **MuMu "Cannot connect to destination host" (2026-10-16).** MuMu's NAT
    can't route to the host LAN IP (LDPlayer could). Fix: re-patched all 7
    URLs to `http://10.0.2.2:8080/` — the Android emulator loopback-to-host
    alias, reachable from LDPlayer + MuMu without LAN/firewall/VPN/DHCP
    dependence. Length-preserving (`build()` pads the 5 freed bytes with
    extra junk; CANON regexes unchanged). Mock response URLs
    (hub/telemetrics/server-list) switched too. One build now serves all
    emulators. Tooling: WinPS 5.1 `Start-Process` joins `-ArgumentList`
    WITHOUT quoting — spaced args MUST carry explicit inner quotes, else
    7za/java receive split paths and 7za writes decoy archives.

18. **MuMu bridge-mode networking (2026-10-16).** MuMu with Network bridge
    mode ON is a separate LAN device: `10.0.2.2` is meaningless, the LAN IP
    works. Browser test from inside MuMu
    (`http://192.168.0.249:8080/status/ping/` → `{"status":"success"}`) is the
    1-minute decisive routing check — use it before rebuilding for any new
    emulator. Rebuilt with `.249` URLs (script takes the prefix as argv[1]).
    Note: `New-NetFirewallRule` needs admin (failed, non-elevated shell) —
    but inbound already flows, no rule needed. Rule of thumb: NAT emulator →
    `10.0.2.2` build; bridged emulator → LAN-IP build.

19. **MuMu "Cannot connect" false alarm (2026-10-16).** Emulator was in
    AIRPLANE MODE with WiFi off. Note the trap: an earlier in-guest browser
    test SUCCEEDED (stale radio state / different timing), which sent the
    investigation down routing/firewall/proxy holes. Rule: before ANY
    network diagnosis on a new emulator, verify radios first (WiFi on,
    airplane off, guest IP present) — 10 seconds, saves hours.

Standing rules learned: extra JSON keys are always ignored (union-serve freely);
telemetry `Login`/`ApplicationStarted` events are the parse oracle; crash
dialogs give exact `Class.Method` → `dump.cs` RVA → capstone → `script.json`
callees; mock-only cycles (~1 min with user tapping) beat rebuild cycles
(~6 min: 7za+sign+uninstall+push+install); never ret-patch flag-writers.
