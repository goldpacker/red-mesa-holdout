# CC0 source credits

Raw inputs from [Poly Haven](https://polyhaven.com) (all **CC0 1.0**,
public domain; no attribution is required, we credit them anyway). Per
GAME_SPEC §14.2 they are only raw material: every one is substantially
modified and baked into the game's own textures. Downloads live in
`assets/source/cc0/<id>/` (git-ignored); re-fetch with the owning
workstream's fetch script. Add a row for every source you use.

## Environment (ENV) — `python3 tools/env/cc0.py fetch`

Terrain MaterialVariants built by `tools/env/terrain_textures.py`
(outputs `assets/textures/terrain/<Name>/`). All are downsampled to 1024²,
re-tinted to the art-bible palette (the source keeps only its luminance
detail and a fraction of its own colour variation), relit-flattened
(large-scale photo lighting removed) and combined with procedural layers.

| Poly Haven id | Name / authors | URL | Licence | Used for | What we did to it |
|---|---|---|---|---|---|
| `aerial_beach_01` | Aerial Beach 01 — Rob Tuytel | https://polyhaven.com/a/aerial_beach_01 | CC0 | `Sand` (and drift sand in `Wash`) | Colour re-tinted to ochre `#C9824F`; fine ripple normals kept under new procedural asymmetric wind ripples; procedural pebble scatter added; ripple-sorted grain tint |
| `gravelly_sand` | Gravelly Sand — Dario Barresi | https://polyhaven.com/a/gravelly_sand | CC0 | `SandCoarse` (Mud patches), `Road` grain | Re-tinted (coarse sand `#B8703F`, road dirt `#9A6B48`); procedural pebbles, faint ripples; for the road, procedural tyre ruts, tread, berms and crown pebbles on top |
| `mud_cracked_dry_03` | Mud Cracked Dry 03 — Dario Barresi, Dimitrios Savva | https://polyhaven.com/a/mud_cracked_dry_03 | CC0 | `Wash` (Salt) | Re-tinted to bleached `#D9B98C`, cracks darkened from the height map, procedural wind-drift sand patches that flatten the normals |
| `rock_face_03` | Rock Face 03 — Dario Barresi, Rico Cilliers | https://polyhaven.com/a/rock_face_03 | CC0 | `Rock` | Re-tinted to shadow-strata rust `#7A3D2B`, cavity darkening, large relief flattened to hide tiling |
| `cliff_side` | Cliff Side — James Ray Cock, Jenelle van Heerden, Dario Barresi | https://polyhaven.com/a/cliff_side | CC0 | `Sandstone` | Re-tinted to cliff rust-red `#9E4A2E`, procedural horizontal strata banding, cavity darkening |
| `marble_cliff_04` | Marble Cliff 04 — Amal Kumar | https://polyhaven.com/a/marble_cliff_04 | CC0 | `Limestone` | Rotated 90° (strata horizontal, normals re-oriented), re-tinted to light strata `#BA6A44`, strata banding |
| `dark_rock_02` | Dark Rock 02 — Amal Kumar | https://polyhaven.com/a/dark_rock_02 | CC0 | `Slate` | Re-tinted to cap rock `#5A3226`, strata banding |

The skyboxes (`tools/env/sky.py`) use no external sources: Blender's
physical Sky Texture plus our own OSL shader (clouds, haze, stars).

Landscape meshes (ENV-2, `tools/env/landscape/`) reuse three of the sources
above as raw input only, never as a visible tile: their **luminance**,
high-passed (divided by a wide blur so only grain and fractures remain),
is projected triplanar in world space at several scales and offset per
strata bed, and multiplied into our own strata colour ramp before the
unique per-chunk bake; their **height maps** drive a world-space bump that
Cycles bakes into each chunk's normal map.

| Poly Haven id | Used for (landscape) | What we did to it |
|---|---|---|
| `cliff_side` | Layered-sandstone grain on wall faces (26- and 7.5-stud tiles) | Luminance high-passed, offset per bed; height map as bump; colour discarded |
| `rock_face_03` | Fracture detail, slickrock tops, talus rubble | Luminance high-passed; height map as bump; colour discarded |
| `gravelly_sand` | Wind-blown sand on ledges and at the foot | Luminance only, under our ochre/pale sand colours |

Ground strips and dressing (ENV-3, `tools/env/ground/`) fetch nothing new.
The road core mesh shows the terrain `RedMesaRoad` maps (from
`gravelly_sand`, above) with its ruts turned to follow the road; the strip
atlas (`strip_textures.py`) resamples our terrain `Road`, `Sand` and `Wash`
textures (from `gravelly_sand`, `aerial_beach_01`, `mud_cracked_dry_03`)
under procedural gravel berms, pebble beds, rills and lip crust; the
dressing atlas (`dressing_textures.py`) crops our terrain `Rock` texture
(from `rock_face_03`) for pebbles and rock clusters. Plants, bark, tyre
tracks, craters and contact shadows are painted procedurally.

## Hard-surface (HS) — `python3 tools/assets/cc0.py fetch`

Used through `photo=` layers in `tools/assets/rmh/materials.py`: the photo
is box-projected in object space and only its *variation* (ratio to its own
mean colour, partly desaturated) is multiplied into our art-bible colour;
its roughness and height maps add their deviation from the mean. The result
is combined with procedural wear (chips, dust, fading, stains) and baked
into the asset's own 1024² atlases (`assets/exported/<Name>/`).

| Poly Haven id | Name / authors | URL | Licence | Used for | What we did to it |
|---|---|---|---|---|---|
| `hessian_230` | Hessian 230 — colormass (photography), Rico Cilliers (processing) | https://polyhaven.com/a/hessian_230 | CC0 | Emplacement sandbags (burlap weave) | Weave scaled 2.5× coarser, re-tinted to four burlap tints (`#9A8560`…), weave height into the normal map; sun-bleach, damp bottoms, seam dust and cloth-sim wrinkles layered on top; baked per sandbag template |
| `green_metal_rust` | Green Metal Rust — Rob Tuytel | https://polyhaven.com/a/green_metal_rust | CC0 | Emplacement turret, gun, pedestal, crates, cans (painted steel); HS-3: Tank hull/turret/skirts and Buggy body paint | Only its variation (rust flecks, scratches, roughness breakup) kept, re-tinted to olive drab `#55563A`/`#45472F`; procedural blotch chips to bare steel, fading, touch-up patches and ochre dust on top; for the vehicles re-tinted to enemy gunmetal `#3E4247` / charcoal `#2A2C30` (35–50 % of its variation, nearly desaturated) under procedural convex-edge chips, caked dust, soot and roughness breakup, baked from high polys |
| `concrete_floor_worn_001` | Concrete Floor Worn 001 — Dimitrios Savva (photography), Rico Cilliers (processing) | https://polyhaven.com/a/concrete_floor_worn_001 | CC0 | Emplacement bunker floor and walls | Scratch/stain variation re-tinted to concrete `#837D70`; procedural slab joints, cracks, water stains, soot/oil/sand marks and ochre dust added |
