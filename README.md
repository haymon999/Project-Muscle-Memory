# Muscle Memory Patcher

Play Critical Ops 1.32 on your own machine, no internet needed. The game
talks to a small server that runs on your PC. Your profile is stored
locally and comes maxed out. Bot matches work start to finish.

Made for this exact version only:

- Package: `com.criticalforceentertainment.criticalops`
- Version: `1.32.0.f1831`, file `critical-ops-1-32-0-f1831.apk`
  (763,605,819 bytes)

Nothing in this repo is a game file. You need your own copy of that APK.
Do not upload APKs, OBBs, or `.so` files anywhere.

## What you get

Offline boot, guest login, full menu, name change, and bot matches.
Matchmaking, ranked, and anything with real players does not work.
That stuff needs the real servers, which are gone for this setup.

## You need

- The APK listed above
- An Android emulator with adb access
- Python 3, Java, and 7-Zip on your PC

## Setup

1. Pick your PC's IP address (the emulator must be able to reach it).
   Quick check: open `http://<that-IP>:8080/status/ping/` in the
   emulator's browser later — it should print `{"status":"success"}`.
   Under NAT `10.0.2.2` usually works; under bridge mode use your LAN IP.

2. Put that IP into `tools/proxy/offline_mock.py` and
   `tools/patch/patch_config_asset.py` (search for the current IP and
   replace it), then start the server:

   `start-offline-server.bat`

   Leave that window open while you play.

3. Unzip the APK somewhere and back up `lib/arm64-v8a/libil2cpp.so`.

4. Patch it:

   `python tools/patch/apply_patches.py extract/lib/arm64-v8a/libil2cpp.so`

   The script checks everything before writing. If it stops with a
   mismatch error, your APK is a different build — don't force it.

5. Rewrite the server addresses inside the APK assets:

   `python tools/patch/patch_config_asset.py "http://<that-IP>:8080/"`

6. Put the patched files back into the APK (the `.so` plus the files
   from `patch_out/`, keeping their folders as-is), sign it, uninstall
   any old copy from the emulator, then install the new one.
   Big APKs fail with plain `adb install` — copy it over first, then
   install from inside:

   `adb push mybuild.apk /data/local/tmp/x.apk`
   `adb shell pm install /data/local/tmp/x.apk`

7. Open the game, log in as guest, pick a name, start a bot match.

## If it doesn't work

- First: WiFi on, airplane mode off. Really. Check it before anything else.
- Then: can the emulator browser open the ping address from step 1?
  No page = the emulator can't reach your PC. Fix the network, not the game.
- Then: look at `logs/offline_mock.log`. Every request the game makes
  shows up there. No lines at all = connection problem. Error lines =
  read on from there.
- Reinstalls need an uninstall first (the signing key changes each build).

## Playing on a real phone, with no PC nearby

The server doesn't have to run on a computer. It can run on the phone
itself, and the game connects to it through the phone's own loopback
address. You only need a PC once, to build the APK. After that the phone
is self-sufficient.

1. Build the APK exactly like above, but use `http://127.0.0.1:8080/`
   as the address in step 5:

   `python tools/patch/patch_config_asset.py "http://127.0.0.1:8080/"`

   (Also replace the IP inside `tools/proxy/offline_mock.py` with
   `127.0.0.1` before you copy it over.)

2. Install the finished APK on the phone.

3. On the phone, install Termux (get it from F-Droid or its GitHub
   page — the Play Store version is outdated and broken).

4. Copy `tools/proxy/offline_mock.py` onto the phone (USB, Bluetooth,
   a file-sharing app, whatever works) and put it somewhere easy, like
   the Termux home folder.

5. In Termux, run:

   `pkg install python -y`
   `python offline_mock.py`

   Leave Termux running in the background while you play. If Android
   keeps killing it, run `termux-wake-lock` once, and turn off battery
   optimization for Termux in the system settings.

6. Open the game and play. The game talks to `127.0.0.1:8080`, which is
   the Termux server on the same phone. No WiFi needed, no PC needed.

Notes: ports above 1024 need no root, so 8080 is fine. If the game can't
connect, check that Termux is still running and that you built the APK
with the `127.0.0.1` address — the emulator builds from the section
above point at a different IP and won't work here.

### Starting the server with one tap (phone)

No, the `.bat` file doesn't run on Android — that's Windows-only. The
equivalent is a home-screen button:

1. Install the **Termux:Widget** app (same place you got Termux).

2. Copy `start-offline-server.sh` from this repo into the Termux
   shortcuts folder. In Termux:

   `mkdir -p ~/.shortcuts`
   `cp <repo>/start-offline-server.sh ~/.shortcuts/`
   `chmod +x ~/.shortcuts/start-offline-server.sh`

3. Open `start-offline-server.sh` once in any text editor and set
   `GAME_DIR` at the top to the folder where this repo lives on your
   phone (for example `/sdcard/muscle-memory` or wherever you put it).

4. Long-press your home screen → Widgets → Termux:Widget (or
   "Termux Shortcut") → pick the script. You get a button that opens
   Termux with the server running. Tap it before opening the game,
   every time.

(The same `.sh` also works on a Linux PC: `sh start-offline-server.sh`.)

## Building the APK on the phone itself (no PC at all)

Same idea as above, one step further: do the patching on the phone too.
You need about 2 GB free space and the original APK file on the phone
(download it on the phone directly, or copy it over once from anywhere).

1. Install Termux (F-Droid or GitHub, not the Play Store version).

2. In Termux, install everything the build needs:

   `pkg install python openjdk-17 p7zip -y`

3. Copy this whole repo folder onto the phone, and put the original APK
   next to it as `critical-ops-1-32-0-f1831.apk`.

4. Run the same three steps as on PC (in the repo folder, in Termux):

   `python tools/patch/apply_patches.py <unzipped-lib-path>`
   (unzip the APK first, patch `lib/arm64-v8a/libil2cpp.so` inside)

   `python tools/patch/patch_config_asset.py "http://127.0.0.1:8080/"`

   then put the patched files back into the APK and sign it with
   `uber-apk-signer` (needs the `.jar`, copy it over too):

   `java -jar uber-apk-signer-1.3.0.jar -a mybuild.apk -o signed --allowResign`

5. Install the finished APK by tapping it in the file manager.
   Uninstall any older copy of the game first.

6. Run the server from the earlier section (`python offline_mock.py`
   in Termux, keep it running) and play.

Honest note: the PC route is tested and known good; this phone-only
route follows the same steps but hasn't been verified on a real phone
here. If `openjdk-17` or `p7zip` is missing in Termux, that step has no
quick replacement — that would be the next thing to solve.

## Files

- `tools/proxy/offline_mock.py` — the local server. This is the whole trick.
- `tools/patch/apply_patches.py` — puts the patches into the game library.
- `tools/patch/patch_config_asset.py` — points the game at your PC.
- `start-offline-server.bat` — double-click to run the server.
- `docs/` — technical notes, one topic per file. Start with
  `docs/README.md` if you want to know how anything works.
