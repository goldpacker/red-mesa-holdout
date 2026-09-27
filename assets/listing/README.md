# Roblox listing art (LOOK-7)

Thumbnails (1920×1080, 16:9, PNG) and the icon (512×512, PNG) for the Red
Mesa Holdout experience page. Everything shows the game's own assets in
situations the game produces. The only text is the game's logo: the full
"RED MESA / HOLDOUT" on two thumbnails and its "RM" stencil on the icon.
There is no Roblox branding and there are no third-party marks.
Nothing here is uploaded; the lead sets the listing art when publishing.

| File | What it shows | Source |
|---|---|---|
| `thumb_1_hero.png` | The key art: the emplacement at sunset over the strata basin, tracking an airdrop (a transport with its ramp open, a stick of eight troopers, a tank under four cargo chutes). Logo lower left. | Blender, `listing_scene.py --shot hero`: the LOOK-4 key-art camera and drop, re-rendered at 2880×1620 and area-averaged to 1920×1080. |
| `thumb_2_airdrop.png` | A two-ship formation mid-drop over the basin: the lead's stick trailing behind it, the wing's first troopers leaving the ramp, a tank on its platform under the four-chute cluster; the lit right flank and far wall below. Small logo lower right. | Blender, `listing_scene.py --shot airdrop` (2880×1620 → 1920×1080). |
| `thumb_3_combat.png` | The real game in Studio at Sunset, over the gun: a rocket bursting on the tank on the road, a machine-gun burst kicking up at the advancing infantry, the buggy and a helicopter. No HUD. | Studio capture (below). |
| `thumb_4_boss.png` | The real game in Studio at Sunset: the Siege Crawler coming up the road with its escorts, a rocket bursting on its turret and a machine-gun burst in front, the gun's shield at the bottom. No HUD. | Studio capture (below). |
| `icon.png` | The tank under its four canopies with the lead transport, the stick and the flank wall, and the logo's "RM" stencil over the sky. | Blender, `listing_scene.py --shot icon` (1536² → 1024² master → 512), `listing_letters.py` for the stencil. |
| `icon_plain.png` | The same icon without the stencil (alternative). | as above |
| `contact.jpg` | Every image at full size (thumbnails at half) and at list size: thumbnails 400 wide, icons at 150 and 64. | `listing_compose.py` |

`src/` holds the inputs `listing_compose.py` builds the finals from: the
Blender renders (`*_render.png`), the Studio grabs (`*_studio.png`, 1920×1080)
and the stencil (`icon_rm.png`). `src/combat_alt_studio.png` is an unused
alternative (the rocket's streak leaving the pod, MG muzzle flash, no
explosion). `src/drafts/` and `src/frames/` are git-ignored scratch.

There is no storm thumbnail; the optional fourth slot is the boss.

## What is real

- **Blender images** are built from the game's shipped assets by the
  LOOK-4 key-art pipeline (`tools/ui/keyart_*.py`): the HS-4 emplacement,
  ENV's landscape chunks with their baked maps, the terrain surface and all
  1,965 placed parts captured from Studio (`assets/ui/art/src/`), ENV's
  Sunset sky (the same OSL sky and sun as the game's preset), and the
  airdrop assets (HS-6 transport with its ramp and cargo door open, CHAR's
  skinned soldier in the Hang pose, the Parachute, ParachuteCargo and
  DropPlatform, the enemy Tank).
- **The drops follow the game's rules** (`src/shared/AirdropConfig.luau`):
  transports at 250–350 studs, 90 studs/s, sticks 0.4 s apart with 1.1 s of
  free fall, 17 studs/s under canopy; formations trail 2.5 s, 70 studs to
  the side and 18 up; a tank hangs under four chutes tilted 29°. The flight
  lines keep the 280-stud clearance from the outpost.
- **Differences from a live frame**, all small: the renders are path traced
  (softer shadows and bounce light than Roblox's), and in the airdrop
  thumbnail and the icon the drop casts no shadows: at the low sunset sun
  Cycles laid the canopies' shadows as dark blotches on the far canyon
  wall, which read as dirt at thumbnail size. The hero keeps the key art
  as shipped.

## Studio captures (thumbnails 3 and 4)

- The build under test was `90a9b45`: AD-4's boss retune, balance only,
  and LOOK-6's film layer are both in. The shots use the beauty
  rig's own staging (`RedMesaDebug "beauty"`, shots 2 and 6 at Sunset: the
  frozen combat and boss stages from `src/shared/BeautyShots.luau`) at
  QualityLevel 15.
- The camera was a fixed free camera just above and behind the turret, a
  little tighter than the player's turret camera: FOV 34, and FOV 27 for
  the boss.
- The weapons were fired through the Studio debug hooks
  (`DebugYaw`/`DebugPitch`/`DebugWeapon`/`DebugFire`). That is the real
  client and server weapon path: rockets, MG rounds, impacts and
  explosions are the game's own effects.
- The frames were picked from bursts of screen grabs taken during the
  action.
- The HUD ScreenGuis, Roblox's CoreGui and the top bar were hidden. The
  game's film layer (grain and vignette) was kept: it is part of the
  game's look.
- The viewport was widened to 1899×1068, which is 16:9, and grabbed at the
  display's native 3798×2136 by `tools/ui/listing_capture.py`. The grabs
  were then area-downsampled to 1920×1080, so nothing was upscaled.
- Studio was put back to the baseline afterwards: viewport 1177×1068, which
  captures at 1190×1080.

## Rebuild

```bash
tools/blender-lock.sh acquire look7
B=/Applications/Blender.app/Contents/MacOS/Blender
for s in hero airdrop icon; do
  $B -b --factory-startup -P tools/ui/listing_scene.py -- --shot $s --sky   # sky plate (~10 s)
  $B -b --factory-startup -P tools/ui/listing_scene.py -- --shot $s         # render (~1-4 min)
done
tools/blender-lock.sh release look7
tools/ui/py.sh tools/ui/listing_letters.py     # src/icon_rm.png
tools/qa/py tools/ui/listing_compose.py        # finals + contact.jpg
```
Studio grabs: see the docstring of `tools/ui/listing_capture.py` (find the
viewport with a magenta marker, `burst`, then `pick <burst> <frame>`).
