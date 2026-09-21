from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from moving_cube import Pickup


def test_contact_requires_opposing_fingers():
    p = Pickup.__new__(Pickup)
    p.cgeom = 0
    p.finger_geoms = [1, 2, 3]
    p.m = SimpleNamespace(geom_bodyid=[10, 20, 20, 21])

    def c(other):
        return SimpleNamespace(dist=0, geom1=0, geom2=other)

    p.d = SimpleNamespace(contact=[c(1), c(2)])
    assert not p.contacts()  # Two geoms on the same finger must not pass.
    p.d.contact.append(c(3))
    assert p.contacts()
