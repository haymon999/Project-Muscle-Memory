# NETWORK.md — URL redirect + offline mock

## 1. URL redirect (APK assets → LAN mock)

The game's base URLs live as length-sensitive strings in 4 files under
`assets/bin/Data/`:

- `1207045bb64717947b58e1d734d6208c`
- `23c4b1085680b46728537f05afd19c12`
- `349fd4f296f3ca7458c24584fd725710`
- `7e59afa27917d60489f9a01815978ad6`

`tools/patch/patch_config_asset.py` replaces 7 production URLs with
`http://192.168.0.249:8080/` + junk filler (`a`/`b`/`c` chars) + real suffix,
keeping EXACT byte length (asserted per pair):

| Original | Replacement shape |
|---|---|
| `https://1-32-0.prod.copsapi.criticalforce.fi/api` | `http://192.168.0.249:8080/aaa…/api` (18/19/23/29 a's by length) |
| `https://api-cops.criticalforce.fi/api` | `http://192.168.0.249:8080/bbb…/api` |
| `https://api-prod.prod.an.cf.fi/v1_4_8` | `http://192.168.0.249:8080/ccc…/v148` |
| `https://api-analytics…`, staging/dev variants | same scheme |

Patched files are committed in `patch_out/` (+`swap.json`); inject with 7za from a
staging dir so zip paths stay `assets/bin/Data/<name>` (see PATCHES.md cycle).
Verify after inject: prefix count > 0, `criticalforce.fi` count == 0 per file.

The mock strips the junk prefix back to a canonical path (`CANON` table in
`offline_mock.py`): `/a…/api/…→/api/…`, `/b…/api/…→/api/…`, `/c…/v148…→/v148…`,
`/c…/api…→/v148…`. The emulator reaches the host at its LAN IP (confirmed via
`CONN` lines showing `Host: 192.168.0.249:8080`).

## 2. The mock (`tools/proxy/offline_mock.py`)

Threading stdlib HTTP server on `0.0.0.0:8080`, **zero outbound**. Restart after
every edit (kill PID on :8080 first — two servers can't bind). Smoke-test with
`Invoke-WebRequest` (note: it throws on 404 — that IS the expected 404 path).

Known quirk: `get_request` peeks with `MSG_PEEK`; our own probes race it and dump
a socketserver traceback to the console. Harmless — override `handle_error` to
silence if it annoys you.

Routes (canonical paths):

| Route | Behavior |
|---|---|
| `*/status/ping/` | `200 {"status":"success"}` (boot connectivity; client handler is a no-op) |
| `*/country` | `200 {"status":"success"}` |
| `*/telemetrics/record` | `200`, logs body (telemetry is the operation journal — read it) |
| `/api/app/start/` | session JSON (`app_start_body()` — see WIRENAMES.md) |
| `/api/server/list/` | `[{"id":1,"addr":"192.168.0.249:8080","name":"offline"}]` (`ServerData[]`, no JsonName → field names) |
| `/api/user/login/` | god-mode `LoginData` (`login_body()` — see WIRENAMES.md §6) |
| `/api/user/namecheck/` | echoes `{"username":<req>,"available":true}` (any name free) |
| `/api/user/namechange/` | echoes `{"username":<req>}` |
| `/api/battlepass/status/` | elite-owned stub (see §3) |
| `/api/client/config/*` | matchmaking/notification/prompt stubs (see §3) |
| everything else | `404 {"error":"unmocked"}` + full dump (method/path/headers/body) to `logs/offline_mock.log` |

`Authorization: Bearer offline-token` arrives on authed calls (P4 makes the token
constant). `X-ApiVersion: 1.32.0.f1831` identifies the client.

## 3. Response notes (gotchas already paid for)

- `LoginData.StoreConfiguration` binds key `"products"` and must be an OBJECT
  (`{}`), not an array — array throws `JsonTypeCoercionException`.
- `telemetricsApiURL` — case matters (`URL` uppercase).
- `LaunchConfig` inner: `eventName, eventAssetId, eventTags, timeLeft`
  (NOT `EndTime`).
- `FeatureSettings` inner: `iap, enable_xp_as_reward, prompt_critical_pass,
  adverty, inbox, ping_markers`. Keep `adverty:false` (ad SDK stays dead).
- `LoginData.TutorialStage` (int) ← `"onboardingStage": 70` (max stage =
  `ProfileOpened`; skips tutorial).
- `StartRequest.Return.tutorialStage` (enum) ← `"tutorialCompleted": true`
  (bool coerces; telemetry flips `OnboardingPhase` to `GameplayStarted` — proof).
- `CheckUsernameRequest.Return` = `{username, available}`; echo the request name.
- `ChangeUsernameRequest.Return` = `{username}`; echo it.
- `CriticalPassStatusData`: `seasonID:1, seasonNumber:1, tiers:[], purchased:true,
  freeTier/eliteTier:70, XP:999999, price:0, timeLeft:99999999`,
  ISO dates for Start/EndDate, `promptImages:{}`.
- `ConfigData`: `matchmaking/local_notifications/game_prompts` (+ snake_case
  inners from the pool) — values are inert timeouts.
- `ServerData[]`: plain `id/addr/name` objects (no attributes on the class).
- Telemetry `Login` event echoes your profile back — use it as the oracle:
  `CurrentPlayerLevel:999`, `LoginType:Guest`, `Rank:12`, `IsInClan:1` = success.
