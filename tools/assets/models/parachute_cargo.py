"""ParachuteCargo: a large round cargo canopy (original design, heavy-drop
class), the same three states as the personnel `Parachute` and the same
builder (`models/parachute.py`). AD-2 hangs 2 over a buggy and 3-4 over a
tank from the drop platform's `SlingApex`.

Asset origin (model pivot) = the **riser confluence**: the bottom of the
riser, at the connector link that clips onto the platform's sling apex.
Model forward -Z, up +Y.

- `Open`: `CanopyOpen` (48-stud inflated canopy, 20 wide gores, scalloped
  skirt, apex vent) + `LinesOpen` (20 suspension lines into the
  confluence ring 7 studs up, one heavy riser down to the connector).
- `Deploying`: `CanopyDeploying` + `LinesDeploying` (partly open, with the
  deployment bag at the apex and the bag's pilot line). Transparency 1.
- `Collapsed`: `CanopyCollapsed` + `LinesCollapsed` (deflated on the
  ground, lying toward +Z; pivot on the ground). Transparency 1.
- `Root` marker (PrimaryPart) with `LoadAttach` (the connector) and
  `NightLight` (on the riser, 2 studs up) + `NightLamp` (Neon,
  Transparency 1). `CanopyOpen` carries `Apex`.

Fabric on the shared `TrimAirdrop` sheet (`canopy` strip, 2 periods).
"""
from rmh import trim
from rmh.asset import Asset

from models.parachute import Spec, build_chute, views

CARGO = Spec(gores=20, radius=24.0, depth=17.0, line_len=50.0, riser_len=7.0, periods=2, harness=False,
             rings=8, thickness=0.08, line_r=0.06, riser_w=0.35, collapse_offset=14.0, seed=11)


def build(**kw):
    a = Asset("ParachuteCargo", pivot=(0, 0, 0), tex_size=512)
    a.preview_hide_transparent = True
    T = trim.use(a, "airdrop", "TrimAirdrop")
    a.material("lamp", kind="flat", color="#ff5c3d")
    build_chute(a, T, CARGO, night_at=(0.0, 0.4, 2.0))
    return a.finish(views=views(CARGO, "ParachuteCargo"), **kw)
