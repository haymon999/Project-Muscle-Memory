# WIRENAMES.md — how to recover the JSON wire names

The game uses a JsonFx fork: every serialized field has `[JsonName("…")]` and the
deserializer matches keys **exactly** (no fallback, unknown keys ignored, missing
keys → defaults/null). `dump.cs` shows the attribute but NOT its string. The
strings live in a packed pool in `libil2cpp.so` `.rodata`.

## 1. The pool method (primary technique)

```python
d = open('extract/lib/arm64-v8a/libil2cpp.so','rb').read()
# main run found at ~0x1E85372-0x1E872C1; a second LoginData block sits ~0x1E84E1D
reg = d[0x1E84000:0x1E8C000]
strs = [s.decode() for s in reg.split(b'\0') if valid printable 1..64 chars]
```

The run is a single `\0`-separated blob, ordered by TypeDef (params, then
return, then next request…). For `StartRequest` the run reads:
`…udid, deviceid, model, vram, platform, appversion, bundleidentifier,
envID, deviceSessionID, deviceSessionToken, assetBundleServerURLs, hubAddress,
tutorialCompleted, telemetricsApiURL, sessionKey, enabledFeatures, stage,
userid, reporttype, apphash…`
which maps 1:1 onto `StartRequestParameters` + `StartRequest.Return` fields.
Read the names off positionally, confirm against `dump.cs`, serve them.

Scripts: `Temp\wirename.py`, `blobscan.py`, `metastrings*.py`, pool dumps
`wirenames.txt` (1297 strings) / `wirenames2.txt` (382 strings).

Dead ends (don't repeat): `DummyDll/*.dll` have NO attribute blobs;
`global-metadata.dat` (v27) has no blob section pre-v29; metadata string-table
existence checks are ambiguous (identifiers collide with wire names).

## 2. Precedents (naming style)

`deviceModel→"model"`, `deviceOS→"os"`, `devicePlatform→"platform"`,
`deviceId→"deviceid"`, `appVersion→"appversion"`, `featureSettings→
"enabledFeatures"`, `telemetricsApiUrl→"telemetricsApiURL"`,
`EndTime→"timeLeft"`, `tutorialStage→"tutorialCompleted"`,
`FactionProperties.*` → snake_case (`hex_color_primary`,
`loadout_configurable`, …).

## 3. StartRequest.Return (TypeDef 8687) — served, working

`envID, udid, deviceSessionID, deviceSessionToken, assetBundleServerURLs,
hubAddress, loginType?, tutorialCompleted(true), telemetricsApiURL,
config{eventName,eventAssetId,eventTags,timeLeft}, sessionKey,
enabledFeatures{iap,enable_xp_as_reward,prompt_critical_pass,adverty:false,
inbox,ping_markers}` (+ harmless `platform:1/type:1` extras).

## 4. LoginData (TypeDef 7099) — served, working

`accountFound, userSessionToken:"offline-user-token", userSessionID:1,
accountLinks{all false}, nameChange:true, nameChangePrice:0, skinpackOffers:[],
clanCreationPrice/RenamePrice:0, clanMax/InitialMemberLimit:99,
products:{}, weaponSkinPackMeta:[], productPriceConfigs:[], refunds:0,
profile:{…}, onboardingStage:70, news:{videos:[],articles:[]},
game_mode_state:{config_id:1,…}, map_pools:{}, network_indicator_threshold:0,
missionAdMultiplier:1.0, ranked_season:{season,placement_matches,
rank_thresholds[10 ascending],rank_divisions_count:5,ranked_rewards:[],
endingSoon:false,pools:[]}, lucky_spin_data/analytics_data/ab_testing/
offer_data/killMedals:{}, survey_state:0, recruit_a_friend_data:{},
new_account:false, inbox:[]`.

## 5. KNOWN UNKNOWNS (fields absent from every pool — cause real bugs)

- `Return.loginType`, `Return.config`(?), `GameModeData.Factions`,
  `FactionProperties.Id` — none of `loginType/logintype/Factions/factions/
  config(?)` exist anywhere in the binary. Hypothesis: null-valued attributes
  are SKIPPED by the deserializer (no field-name fallback — proven: serving the
  field names does nothing). Consequences handled natively:
  - loginType → P5 forces Guest in `ProcessLogin`.
  - Factions → **OPEN FRONTIER** (`FindFactionProperties id:1` throws; §6).
- `FactionProperties.Id` candidates all ruled out (`id/Id/ID/faction_id` —
  `faction_id` belongs to `RoomProperties`). The faction entry parses with Id=0.
- 2026-10-16 CORRECTION: the earlier "field names don't bind" conclusion was
  INVALID — the mock had a duplicate `"game_mode_state"` key (detailed payload
  + trailing `{}`), and Python kept only the `{}`. So factions never populated
  regardless of key. Retest with union-served keys before concluding anything
  about null-`JsonName` fallback. Also confirmed `game_mode_state` IS the true
  wire key for `LoginData.GameModeData` (pool run at 0x1E84E1D), and the
  `Factions` list key is genuinely absent from the binary pool
  (`config_id/game_mode_managements/game_modes/color_gradings/surrender_votes`
  run at 0x1E866F0 has no factions entry).

## 6. God-mode profile (`UserProfile`, TypeDef 7997)

- `basicInfo{userID:1, username/name:"GOD", userType:1, iconID:1,
  playerLevel:{level:999,…}}` + `playerLevelConfig{max_level:999,…}` → level 999.
- `inventory.owned_items` = `{"1":1,…,"2000":1}` (~45 KB response, fine) → own
  everything with numeric IDs. `boosters:[], unseen_product_ids:[]`.
- `stats.ranked{highest_rank/rank:9, rating:9999, global_position:1,
  placement_matches_left:0}` → Rank 12 in telemetry (rank calc needs
  `ranked_season.rank_thresholds` non-null or `ConvertRatingToRank` NREs).
- `userSettings{block*:false}`, `skillRatings:[]`, `elitePassSlots:[]`,
  `clan:{…}` (MUST be non-null — see below), `friendLimit:999`,
  `rankedKillLimit:999`, `advertising{videoad_*:0,""}`.
- `PlayerDataManager.SetLocalPlayer` (0xAF2918) REQUIRES `profile.Clan`,
  `profile.Stats` (+`Stats.Ranked`), `profile.BasicInfo`, `Clan.BasicInfo`
  non-null — null clan/stats = instant NRE on state enter. Served clan is
  stub `{id:0,…}` (shows as in-clan in telemetry; harmless).
- `UserSettings`, `ContactData`, `ClanData`, `UserEquippedItem{Item uint,
  Slot ulong}`, `SkillRating{gameMode/gameType byte, rating float}`,
  `PlayerLevel{CurrentExperience, Level, NextLevelExperience}` — layouts in
  `dump.cs` 386594–387600; wire keys mostly pooled, union-serve when unsure
  (extra keys are always ignored — safe).
- Currencies live elsewhere (`current_credits` pool key; wallet endpoint
  unmapped) — not needed for menu/inventory.
