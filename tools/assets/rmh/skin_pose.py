"""Poses for skinned assets (rmh/skin.py): Roblox `CFrame.Angles`
conventions, the Blender pose-bone conversion and a world-space pose
builder with FK and analytic two-bone IK. Every bone's rest rotation is
the same (pointing up, roll 0), so a bone's rotation relative to its
parent in model axes is exactly its Roblox `Bone.Transform`."""
import math

from mathutils import Matrix, Vector


def euler_roblox(rx, ry, rz):
    """Rotation matrix (Blender world axes) for Roblox CFrame.Angles(rx, ry, rz) in degrees.
    Roblox (x, y, z) = Blender (x, z, -y)."""
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    # Roblox X = Blender X, Roblox Y = Blender Z, Roblox Z = Blender -Y.
    return (Matrix.Rotation(rx, 3, "X") @ Matrix.Rotation(ry, 3, "Z") @ Matrix.Rotation(-rz, 3, "Y"))


# Rest orientation of every bone (armature space): Y along +Z, X = +X.
_BONE_BASIS = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # columns: X=(1,0,0), Y=(0,0,1), Z=(0,-1,0)


def pose_quaternion(rx, ry, rz):
    """Pose-bone rotation (bone local space) equal to Roblox Bone.Transform = CFrame.Angles(rx, ry, rz)."""
    r_world = euler_roblox(rx, ry, rz)
    return (_BONE_BASIS.transposed() @ r_world @ _BONE_BASIS).to_quaternion()


# --- poses: FK + analytic two-bone IK, exported as Roblox Transform angles --

# Roblox (x, y, z) -> Blender (x, -z, y) as a matrix acting on Roblox coords.
_R2B = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def _frame(a, n):
    a = a.normalized()
    n = (n - a * n.dot(a)).normalized()
    return Matrix((a, n, a.cross(n))).transposed()


def rot(rx=0.0, ry=0.0, rz=0.0):
    """Blender-world rotation for Roblox CFrame.Angles(rx, ry, rz) (degrees)."""
    return euler_roblox(rx, ry, rz)


class Pose:
    """World-space pose builder. `local[b]` is the bone's rotation relative
    to its parent in rest (model) axes, i.e. exactly Roblox Bone.Transform
    once converted by `angles()`. Hips may also translate (`offset`)."""

    def __init__(self, asset):
        self.a = asset
        self.bones = {b.name: b for b in asset.bones}
        self.local = {}
        self.offset = Vector((0, 0, 0))

    def set(self, bone, R):
        self.local[bone] = Matrix(R).to_3x3()
        return self

    def world_rot(self, bone):
        b = self.bones[bone]
        L = self.local.get(bone, Matrix.Identity(3))
        return L if b.parent is None else self.world_rot(b.parent) @ L

    def world_head(self, bone):
        b = self.bones[bone]
        if b.parent is None:
            return b.head + self.offset
        p = self.bones[b.parent]
        return self.world_head(b.parent) + self.world_rot(b.parent) @ (b.head - p.head)

    def world_point(self, bone, rest_point):
        """Where a rest-pose point rigidly attached to `bone` ends up."""
        return self.world_head(bone) + self.world_rot(bone) @ (Vector(rest_point) - self.bones[bone].head)

    def ik(self, upper, lower, hand, wrist, hand_rot, pole):
        """Two-bone IK: place `hand`'s head at `wrist` with world rotation
        delta `hand_rot`, elbow/knee bending towards `pole` (a direction)."""
        bu, bl, bh = self.bones[upper], self.bones[lower], self.bones[hand]
        Dp = self.world_rot(bu.parent) if bu.parent else Matrix.Identity(3)
        S = self.world_head(upper)
        u_rest = Dp @ (bl.head - bu.head)
        f_rest = Dp @ (bh.head - bl.head)
        L1, L2 = u_rest.length, f_rest.length
        W = Vector(wrist)
        to = W - S
        d = max(abs(L1 - L2) + 1e-3, min(L1 + L2 - 1e-3, to.length))
        axis = to.normalized()
        W = S + axis * d
        a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        p = Vector(pole)
        p = (p - axis * p.dot(axis)).normalized()
        E = S + axis * a + p * h
        n_rest = u_rest.cross(f_rest).normalized()
        u_new, f_new = E - S, W - E
        n_new = u_new.cross(f_new)
        if n_new.length < 1e-4:
            n_new = u_new.cross(p)
        n_new.normalize()
        Du = _frame(u_new, n_new) @ _frame(u_rest, n_rest).transposed()
        Dl = _frame(f_new, n_new) @ _frame(f_rest, n_rest).transposed()
        # Du/Dl turn the parent-rotated rest segments (u_rest, f_rest) onto
        # the solution, so the bones' world rotations are Du @ Dp, Dl @ Dp.
        # (Before CHAR-2 this used Du, Dl alone, which is only right when the
        # parent is unrotated; the manifest's Patrol/Aim came from that.)
        Wu, Wl = Du @ Dp, Dl @ Dp
        self.local[upper] = Dp.transposed() @ Wu
        self.local[lower] = Wu.transposed() @ Wl
        self.local[hand] = Wl.transposed() @ Matrix(hand_rot).to_3x3()
        return E

    def angles(self):
        """{bone: [rx, ry, rz(, [x, y, z])]} in degrees / studs for Roblox
        `Bone.Transform = CFrame.new(x, y, z) * CFrame.Angles(rx, ry, rz)`."""
        out = {}
        for name, L in self.local.items():
            Rr = _R2B.transposed() @ L @ _R2B
            e = Rr.to_euler("ZYX")  # matrix = Rx @ Ry @ Rz, like CFrame.Angles
            vals = [round(math.degrees(e.x), 2), round(math.degrees(e.y), 2), round(math.degrees(e.z), 2)]
            if abs(sum(abs(v) for v in vals)) > 0.01:
                out[name] = vals
        if self.offset.length > 1e-4:
            hips = next(b.name for b in self.a.bones if b.parent is None)
            o = self.offset
            out.setdefault(hips, [0.0, 0.0, 0.0])
            out[hips] = out[hips][:3] + [[round(o.x, 3), round(o.z, 3), round(-o.y, 3)]]
        return out
