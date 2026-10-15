"""Offline mock for Critical Ops 1.32 API. Fully local, zero outbound connections.

Routes (canonical paths after stripping the same junk-prefix segments the
URL-patched APK sends, e.g. /aaa.../api/... -> /api/...):
  /status/ping/            -> 200 (boot-time connectivity check; client
                                success handler is a no-op, any 200 passes)
  */country                -> 200 stub (matches real upstream success shape)
  */telemetrics/record     -> 200 stub (fire-and-forget telemetry sink)
  everything else          -> 404 + full request dump to logs/offline_mock.log
"""
import http.server
import socketserver
import re
import time
import os

PORT = 8080
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "logs", "offline_mock.log")
os.makedirs(os.path.dirname(LOG), exist_ok=True)

# Same junk-prefix scheme as patch_config_asset.py / api_proxy.py:
# /a{18,19,23,29}/api... -> main API, /b{7,12}/api... -> main API,
# /c{6,11}/v148... and /c{12}/api... -> analytics API.
CANON = [
    (re.compile(r"^/[ab]+/api(/.*)?$"), "/api"),
    (re.compile(r"^/[ab]+/status(/.*)?$"), "/status"),
    (re.compile(r"^/c+/v148(/.*)?$"), "/v148"),
    (re.compile(r"^/c+/api(/.*)?$"), "/v148"),
]


def canonical(path):
    raw = path.split("?", 1)[0]
    for rx, base in CANON:
        m = rx.match(raw)
        if m:
            return base + (m.group(1) or "")
    return raw


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


OK_BODY = b'{"status":"success"}'


def _variants(base):
    out = [base]
    if base[:1].isupper():
        out.append(base[:1].lower() + base[1:])
    else:
        out.append(base[:1].upper() + base[1:])
    out.append(base.lower())
    seen, res = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            res.append(v)
    return res


def app_start_body(req_body):
    # Wire names recovered from the JsonName string pool in libil2cpp.so
    # (.rodata run at 0x1E85372; typedef-ordered, verified against dump.cs
    # StartRequest.Return TypeDefIndex 8687). Flat object, no envelope
    # (ProcessSuccessfulResponse calls JsonHelper.Deserialize<Return>(Text)).
    try:
        import json as _j
        req = _j.loads(req_body.decode("utf-8") or "{}")
    except Exception:
        req = {}
    dev = req.get("deviceid") or "offline-device"
    obj = {
        "envID": "prod",
        "udid": dev,
        "deviceSessionID": 1,
        "deviceSessionToken": "offline-token",
        "assetBundleServerURLs": ["http://192.168.0.249:8080/bundles"],
        "hubAddress": "http://192.168.0.249:8080/hub",
        "loginType": 1,
        "platform": 1,  # candidate wire name for Return.loginType (cf. LoginParameters.platform)
        "type": 1,  # candidate wire name for Return.loginType
        "tutorialCompleted": True,
        "telemetricsApiURL": "http://192.168.0.249:8080/cccccc/v148",
        "config": {
            "eventName": "",
            "eventAssetId": 0,
            "eventTags": [],
            "timeLeft": 0,
        },
        "sessionKey": "offline-session-key",
        "enabledFeatures": {
            "iap": True,
            "enable_xp_as_reward": True,
            "prompt_critical_pass": True,
            "adverty": False,
            "inbox": True,
            "ping_markers": True,
        },
    }
    import json as _j
    return _j.dumps(obj).encode()


# Real CharacterSkinDef asset IDs from assets/assetpack/characterskindefs
# (UnityPy: Coalition=9581/5 prototypes, Breach=9582/5, Jesse=9861/1).
# GameSystem.CreateCharacter reads FactionProperties+0x2C
# (CharacterSkinDefAssetId) and GetVariant throws if the def has 0
# prototypes - id 0 (our old stub) always crashed bot spawn.
_FACTION_SKINS = {1: 9581, 2: 9582}


def _faction(fid, primary=4278190335, secondary=4294901760):
    # FactionProperties (TypeDef 9662): Id@0x10 + snake_case pool names.
    # Id wire key unknown (absent from binary pool) -> union-serve every
    # plausible variant; unknown keys are ignored by the deserializer.
    skin = _FACTION_SKINS.get(fid, 9581)
    globe = skin  # CharacterGlobeSkinAssetId unknown; same def until proven otherwise
    sk = {"character_skin_def_asset_id": skin, "characterSkinDefAssetId": skin,
          "CharacterSkinDefAssetId": skin,
          "character_globe_skin_asset_id": globe,
          "characterGlobeSkinAssetId": globe,
          "CharacterGlobeSkinAssetId": globe}
    ret = {
        "id": fid, "Id": fid, "ID": fid,
        "faction_id": fid, "factionId": fid, "factionID": fid,
        "FactionID": fid, "FactionId": fid,
        "first_live_version": "", "firstLiveVersion": "",
        "FirstLiveVersion": "",
        "localization_key": "", "localizationKey": "",
        "LocalizationKey": "",
        "victory_screen_index": 0, "victoryScreenIndex": 0,
        "VictoryScreenIndex": 0,
        "icon_asset_id": "", "iconAssetId": "", "IconAssetId": "",
        "audio_pack_asset_id": "", "audioPackAssetId": "",
        "AudioPackAssetId": "",
        "weapon_blueprint_ids": [], "weaponBlueprintIds": [],
        "WeaponBluePrints": [], "WeaponBlueprints": [],
        "hex_color_primary": primary, "hexColorPrimary": primary,
        "HexColorPrimary": primary,
        "hex_color_secondary": secondary, "hexColorSecondary": secondary,
        "HexColorSecondary": secondary,
        "loadout_configurable": True, "loadoutConfigurable": True,
        "LoadoutConfigurable": True,
    }
    ret.update(sk)
    return ret


def game_mode_state_body():
    # GameModeData (TypeDef 9794): ConfigID@0x10, GameModeManagements@0x18,
    # GameModes@0x20, ColorGradings@0x28, Factions@0x30, SurrenderVotes@0x38.
    # Pool gives config_id/game_mode_managements/game_modes/color_gradings/
    # surrender_votes; the Factions list key is absent from the binary, so
    # union-serve every candidate. Two entries (ids 1+2) for both teams.
    f1 = _faction(1)
    f2 = _faction(2)
    gms = {
        "config_id": 1, "ConfigID": 1, "configID": 1, "configId": 1,
        "game_mode_managements": [], "GameModeManagements": [],
        "game_modes": [], "GameModes": [],
        "color_gradings": [], "ColorGradings": [],
        "surrender_votes": [], "SurrenderVotes": [],
    }
    for k in ("factions", "Factions", "faction_properties",
              "factionProperties", "FactionProperties", "factionList",
              "faction_lists", "FactionList"):
        gms[k] = [dict(f1), dict(f2)]
    return gms


def login_body():
    # LoginData wire names from the JsonName pool in libil2cpp.so
    # (typedef-ordered run at 0x1E85372). profile = UserProfile god-mode.
    import json as _j
    owned = {str(i): 1 for i in range(1, 2001)}
    profile = {
        "basicInfo": {
            "userID": 1, "userid": 1, "username": "GOD", "name": "GOD",
            "userType": 1, "iconID": 1, "icon": 1,
            "playerLevel": {"level": 999, "Level": 999, "xp": 99999999,
                            "XP": 99999999, "experience": 99999999,
                            "current_xp": 99999999, "next_level_xp": 1,
                            "currentExperience": 99999999,
                            "nextLevelExperience": 1,
                            "CurrentExperience": 99999999,
                            "NextLevelExperience": 1},
            "level": 999, "xp": 99999999,
        },
        "milestones": [], "milestoneProgresses": [],
        "challengeProgress": [], "ban": {"Type": 0, "Reason": 0, "SecondsLeft": 0},
        "milestoneRewards": [], "milestoneRewardData": [],
        "clan": {"id": 0, "ID": 0,
                 "basicInfo": {"name": "", "Name": "", "tag": "",
                               "Tag": "", "clanName": ""},
                 "BasicInfo": {"name": "", "Name": "", "tag": "",
                               "Tag": "", "clanName": ""},
                 "memberLimit": 99, "MemberLimit": 99,
                 "memberExpansionPrice": 0, "MemberExpansionPrice": 0,
                 "invites": [], "Invites": [],
                 "memberRank": 0, "MemberRank": 0},
        "Clan": {"id": 0, "ID": 0,
                 "basicInfo": {"name": "", "Name": "", "tag": "",
                               "Tag": "", "clanName": ""},
                 "memberLimit": 99, "invites": [], "memberRank": 0},
        "stats": {"ranked": {"highest_rank": 9, "HighestRank": 9, "rank": 9,
                             "Rank": 9, "rating": 9999, "Rating": 9999,
                             "global_position": 1, "GlobalPosition": 1,
                             "placement_matches_left": 0,
                             "PlacementMatchesLeft": 0},
                  "Ranked": {"highest_rank": 9, "HighestRank": 9, "rank": 9,
                             "Rank": 9, "rating": 9999, "Rating": 9999,
                             "global_position": 1, "GlobalPosition": 1,
                             "placement_matches_left": 0,
                             "PlacementMatchesLeft": 0},
                  "seasonal_stats": [], "SeasonalStats": [],
                  "rankedStats": {}, "customStats": {}, "casualStats": {}},
        "Stats": {"Ranked": {"HighestRank": 9, "Rank": 9, "Rating": 9999,
                             "GlobalPosition": 1, "PlacementMatchesLeft": 0},
                  "SeasonalStats": []},
        "inventory": {"unseen_product_ids": [], "unseenIds": [], "boosters": [],
                      "owned_items": owned, "OwnedItems": owned},
        "rankedKillLimit": 999, "rankedPenaltyLeft": 0,
        "userSettings": {"blockFriendRequests": False,
                         "block_clan_requests": False,
                         "BlockFriendRequests": False,
                         "BlockClanRequests": False},
        "loadout": [], "equippedItems": [], "EquippedItems": [],
        "counterSkin": 999, "terroristSkin": 999,
        "friendLimit": 999, "FriendLimit": 999,
        "contacts": [], "skillRatings": [], "elitePassSlots": [],
        "playerLevelConfig": {"exp_per_level": 1, "max_level": 999,
                              "top_level": 999},
        "advertising": {"videoad_limit_enabled": False,
                        "videoad_max_allowed": 0, "videoad_watched": 0,
                        "videoad_started_timestamp": 0,
                        "videoad_cooldown_seconds": 0, "ad_token": ""},
    }
    obj = {
        "accountFound": True, "accountfound": True,
        "userSessionToken": "offline-user-token",
        "userSessionID": 1,
        "accountLinks": {"facebook": False, "google": False,
                         "gamecenter": False, "apple": False},
        "nameChange": True, "nameChangePrice": 0,
        "skinpackOffers": [], "SkinpackOfferQuantities": [],
        "clanCreationPrice": 0, "clanRenamePrice": 0,
        "clanMaxMemberLimit": 99, "clanInitialMemberLimit": 99,
        "products": {}, "StoreConfiguration": {},
        "weaponSkinPackMeta": [], "WeaponCaseMetaData": [],
        "productPriceConfigs": [], "ProductPriceConfigs": [],
        "refunds": 0, "RefundCount": 0,
        "profile": profile,
        "onboardingStage": 70, "stage": 70, "tutorialStage": 70,
        "TutorialStage": 70,
        "news": {"videos": [], "Videos": [], "articles": [], "Articles": []},
        # NOTE: LoginData.GameModeData field binds key "game_mode_state"
        # (typedef-ordered pool run at 0x1E84E1D). "GameModeData" key served
        # too in case the deserializer falls back to the field name.
        # NEVER add a second "game_mode_state" key later in this dict: it
        # silently overwrote this payload with {} and nulled the factions.
        "game_mode_state": game_mode_state_body(),
        "GameModeData": game_mode_state_body(),
        "map_pools": {},
        "network_indicator_threshold": 0, "missionAdMultiplier": 1.0,
        "ranked_season": {"season": 1, "Season": 1, "season_id": 1,
                          "placement_matches": 10, "PlacementMatches": 10,
                          "rank_thresholds": [0, 100, 300, 600, 1000, 1500,
                                              2100, 2800, 3600, 4500],
                          "RankThresholds": [0, 100, 300, 600, 1000, 1500,
                                             2100, 2800, 3600, 4500],
                          "rank_divisions_count": 5, "DivisionCount": 5,
                          "ranked_rewards": [], "RankedRewards": [],
                          "endingSoon": False, "EndingSoon": False,
                          "pools": [], "Pools": []}, "lucky_spin_data": {}, "analytics_data": {},
        "ab_testing": {}, "offer_data": {},
        # KillMedalDefinitions (TypeDef 9997): Medals@0x10, Conditions@0x18,
        # Priorities@0x20. Handler ctor NREs on null lists (0xAAF154/0xAAF268),
        # so serve empty arrays (loops skip, no medals awarded offline).
        # Pool confirms medals/priorities; Conditions/Definitions keys absent
        # from binary -> union-serve.
        "killMedals": {"medals": [], "Medals": [],
                       "conditions": [], "Conditions": [],
                       "priorities": [], "Priorities": [],
                       "definitions": {"medals": [], "Medals": [],
                                       "conditions": [], "Conditions": [],
                                       "priorities": [], "Priorities": []},
                       "Definitions": {"Medals": [], "Conditions": [],
                                       "Priorities": []}},
        "survey_state": 0, "recruit_a_friend_data": {},
        "new_account": False,
        "inbox": [], "surveyState": 0, "is_paying_user": False,
        "account_age": 999,
    }
    return _j.dumps(obj).encode()


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OfflineMock/1.0"

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self):
        raw_path = self.path
        canon = canonical(raw_path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            body_txt = body.decode("utf-8", "replace") if body else ""
        except Exception:
            body_txt = "<undecodable %db>" % len(body)

        if canon.endswith("/status/ping/") or canon.endswith("/status/ping"):
            log("PING %s %s -> 200" % (self.command, raw_path))
            self._send(200, OK_BODY)
        elif canon.endswith("/app/start/") or canon.endswith("/app/start"):
            resp = app_start_body(body)
            log("APPSTART %s %s (%db) -> 200 session (%db)" % (self.command, raw_path, len(body), len(resp)))
            self._send(200, resp)
        elif canon.endswith("/server/list/") or canon.endswith("/server/list"):
            # GetServersRequest.ReturnValue = ServerData[] (no JsonName attrs ->
            # field names). One entry pointing back at the mock.
            resp = b'[{"id":1,"addr":"192.168.0.249:8080","name":"offline"}]'
            log("SERVERS %s %s -> 200 (1 offline entry)" % (self.command, raw_path))
            self._send(200, resp)
        elif canon.endswith("/user/login/") or canon.endswith("/user/login"):
            resp = login_body()
            log("LOGIN %s %s (%db) -> 200 god-mode (%db)" % (self.command, raw_path, len(body), len(resp)))
            self._send(200, resp)
        elif canon.endswith("/user/namecheck/") or canon.endswith("/user/namecheck"):
            # CheckUsernameRequest.Return {username, available} - every name is free offline
            import json as _j
            try:
                _req = _j.loads(body.decode("utf-8") or "{}")
            except Exception:
                _req = {}
            _name = _req.get("username") or "GOD"
            resp = _j.dumps({"username": _name, "available": True,
                             "Username": _name, "Available": True}).encode()
            log("NAMECHECK %s %s name=%r -> 200 available" % (self.command, raw_path, _name))
            self._send(200, resp)
        elif canon.endswith("/user/namechange/") or canon.endswith("/user/namechange"):
            # ChangeUsernameRequest.Return {username} - accept any name
            import json as _j
            try:
                _req = _j.loads(body.decode("utf-8") or "{}")
            except Exception:
                _req = {}
            _name = _req.get("username") or "GOD"
            resp = _j.dumps({"username": _name, "Username": _name}).encode()
            log("NAMECHANGE %s %s name=%r -> 200" % (self.command, raw_path, _name))
            self._send(200, resp)
        elif canon.endswith("/battlepass/status/") or canon.endswith("/battlepass/status"):
            import json as _j
            resp = _j.dumps({
                "startDate": "2026-01-01T00:00:00Z", "StartDate": "2026-01-01T00:00:00Z",
                "endDate": "2027-01-01T00:00:00Z", "EndDate": "2027-01-01T00:00:00Z",
                "timeLeft": 99999999, "TimeLeft": 99999999,
                "promptImages": {}, "PromptImages": {},
                "seasonID": 1, "SeasonID": 1, "seasonNumber": 1, "SeasonNumber": 1,
                "price": 0, "Price": 0, "tiers": [], "Tiers": [],
                "purchased": True, "Purchased": True,
                "freeTier": 70, "FreeTier": 70, "eliteTier": 70, "EliteTier": 70,
                "exp": 999999, "XP": 999999,
            }).encode()
            log("BATTLEPASS %s %s -> 200 (elite owned)" % (self.command, raw_path))
            self._send(200, resp)
        elif "/client/config" in canon:
            import json as _j
            resp = _j.dumps({
                "matchmaking": {"suggest_global_queue_after_seconds": 60,
                                "SuggestGlobalQueueTimeout": 60},
                "Matchmaking": {"SuggestGlobalQueueTimeout": 60},
                "local_notifications": {"short_retention_duration": 86400,
                                         "long_retention_duration": 604800,
                                         "double_offer_notice_lead_time": 3600},
                "LocalNotifications": {"ShortRetentionDuration": 86400,
                                       "LongRetentionDuration": 604800,
                                       "DoubleOfferNoticeLeadTime": 3600},
                "game_prompts": {"critical_pass_prompt": {
                    "ending_hours": 48, "EndingHours": 48,
                    "first_session": False, "FirstSession": False,
                    "sessions": 99, "Sessions": 99, "wins": 99, "Wins": 99}},
                "GamePrompts": {"CriticalPassPrompt": {
                    "EndingHours": 48, "FirstSession": False,
                    "Sessions": 99, "Wins": 99}},
            }).encode()
            log("CONFIG %s %s -> 200" % (self.command, raw_path))
            self._send(200, resp)
        elif canon.endswith("/gamemode/gamemodestate"):
            # GameModeDataRequest endpoint (from stringliteral.json). Not yet
            # observed on the wire - served pre-emptively with the same shape
            # as login's game_mode_state in case gameplay init refetches it.
            import json as _j
            resp = _j.dumps(game_mode_state_body()).encode()
            log("GAMEMODESTATE %s %s (%db) -> 200 (%db)" % (self.command, raw_path, len(body), len(resp)))
            self._send(200, resp)
        elif canon.endswith("/country"):
            log("COUNTRY %s %s -> 200 stub" % (self.command, raw_path))
            self._send(200, OK_BODY)
        elif canon.endswith("/telemetrics/record"):
            log("TELEMETRY %s %s (%db) -> 200 stub" % (self.command, raw_path, len(body)))
            if body_txt:
                log("  BODY: " + body_txt[:2000])
            self._send(200, OK_BODY)
        else:
            log("==== UNMOCKED %s %s (canonical %s) -> 404 ====" % (self.command, raw_path, canon))
            log("  HEADERS: " + " | ".join("%s: %s" % (k, v) for k, v in self.headers.items()))
            if body_txt:
                log("  BODY(%db): %s" % (len(body), body_txt[:4000]))
            else:
                log("  BODY: <empty>")
            self._send(404, b'{"error":"unmocked"}')

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def log_message(self, fmt, *args):
        pass


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def get_request(self):
        conn, addr = super().get_request()
        try:
            import socket as _s
            conn.settimeout(1.5)
            peek = conn.recv(256, _s.MSG_PEEK)
            conn.settimeout(None)
            log("CONN %s:%s first-bytes=%r" % (addr[0], addr[1], peek[:150]))
        except Exception as e:
            log("CONN %s:%s (peek: %s)" % (addr[0], addr[1], e))
        return conn, addr


if __name__ == "__main__":
    log("Offline mock starting on 0.0.0.0:%d (no upstream, all local)" % PORT)
    TS(("0.0.0.0", PORT), H).serve_forever()
