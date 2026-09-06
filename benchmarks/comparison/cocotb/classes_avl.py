# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) comparison benchmark - the workload, in AVL.
#
# Sixteen classes, each declaring the same representative set of variables -
# four unsigned logic vectors and two signed integers - under the same eleven
# constraints, and differing in the constants those constraints are written
# with. The SystemVerilog classes are in ../rtl/classes.svh and the pyvsc ones
# in classes_pyuvm.py; all three are the same workload.
#
# The constraints are written once, in item_base, against the constants each
# class declares - the way a testbench parameterizes one item type rather than
# writing the same constraint out sixteen times.
#
# | constraint    | category                      | what it says                            |
# |---------------|-------------------------------|-----------------------------------------|
# | c_addr        | arithmetic                    | addr lies in this class's 16 MB window   |
# | c_align       | arithmetic, modulo            | addr is aligned to 4, 8 or 16            |
# | c_page        | bitwise, shift                | addr >> 24 is this class's page          |
# | c_len         | arithmetic range              | 1 <= len <= LMAX                         |
# | c_kind        | list                          | kind is one of four values               |
# | c_mask        | bitwise, and                  | bits of mask held at zero                |
# | c_mask_kind   | bitwise, xor, across fields   | the low nibble of mask is tied to kind   |
# | c_delta       | signed arithmetic             | -DMAX <= delta <= DMAX, and not zero     |
# | c_level       | signed arithmetic             | -VMAX <= level <= VMAX                   |
# | c_sum         | signed arithmetic, two fields | delta + level >= 0                       |
# | c_kind0       | implication                   | the first kind implies a single beat     |
#
# z3's bit vector comparisons, "%" and ">>" are signed by default, so the
# unsigned forms the logic variables imply are spelled UGE / ULE, URem and LShR.
# The two Int variables are signed, and use the plain operators.

import avl
from z3 import UGE, ULE, And, Implies, LShR, Or, URem


class item_base(avl.Object):
    """The variables and the eleven constraints.

    A class below is the constants it is written with; everything else is here."""

    LOW, HIGH = 0x00000000, 0xFFFFFFFF
    PAGE = 0x00
    ALIGN = 4
    LMAX = 4096
    KINDS = (0, 1, 2, 3)
    CLEAR = 0x00
    XOR = 0x00
    DMAX = 4096
    VMAX = 512

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Logic(0, width=32, fmt=hex)
        self.len = avl.Logic(0, width=16, fmt=hex)
        self.mask = avl.Logic(0, width=8, fmt=hex)
        self.kind = avl.Logic(0, width=8, fmt=hex)
        self.delta = avl.Int(0, width=16)
        self.level = avl.Int(0, width=16)

        # Read out of the class once, so that each constraint closes over the
        # constant rather than over the object.
        low, high, page, align = self.LOW, self.HIGH, self.PAGE, self.ALIGN
        lmax, kinds, clear, xr = self.LMAX, self.KINDS, self.CLEAR, self.XOR
        dmax, vmax, kind0 = self.DMAX, self.VMAX, self.KINDS[0]

        self.add_constraint(
            "c_addr", lambda a: And(UGE(a, low), ULE(a, high)), self.addr)
        self.add_constraint(
            "c_align", lambda a: URem(a, align) == 0, self.addr)
        self.add_constraint(
            "c_page", lambda a: LShR(a, 24) == page, self.addr)
        self.add_constraint(
            "c_len", lambda n: And(UGE(n, 1), ULE(n, lmax)), self.len)
        self.add_constraint(
            "c_kind", lambda k: Or([k == v for v in kinds]), self.kind)
        self.add_constraint(
            "c_mask", lambda m: (m & clear) == 0, self.mask)
        self.add_constraint(
            "c_mask_kind", lambda m, k: ((m ^ k) & 0x0F) == xr, self.mask, self.kind)
        self.add_constraint(
            "c_delta", lambda d: And(d >= -dmax, d <= dmax, d != 0), self.delta)
        self.add_constraint(
            "c_level", lambda v: And(v >= -vmax, v <= vmax), self.level)
        self.add_constraint(
            "c_sum", lambda d, v: (d + v) >= 0, self.delta, self.level)
        self.add_constraint(
            "c_kind0", lambda k, n: Implies(k == kind0, n == 1), self.kind, self.len)

    def check(self):
        """Every item is checked against all eleven constraints, in every
        flavour, so that a flavour drawing an illegal value fails rather than
        being reported as fast. Returns the item's contribution to the checksum."""
        addr, n = int(self.addr), int(self.len)
        mask, kind = int(self.mask), int(self.kind)
        delta, level = int(self.delta), int(self.level)

        assert self.LOW <= addr <= self.HIGH, f"c_addr violated : addr={addr:08x}"
        assert addr % self.ALIGN == 0, f"c_align violated : addr={addr:08x}"
        assert (addr >> 24) == self.PAGE, f"c_page violated : addr={addr:08x}"
        assert 1 <= n <= self.LMAX, f"c_len violated : len={n}"
        assert kind in self.KINDS, f"c_kind violated : kind={kind}"
        assert (mask & self.CLEAR) == 0, f"c_mask violated : mask={mask:02x}"
        assert ((mask ^ kind) & 0x0F) == self.XOR, (
            f"c_mask_kind violated : mask={mask:02x} kind={kind:02x}")
        assert -self.DMAX <= delta <= self.DMAX and delta != 0, (
            f"c_delta violated : delta={delta}")
        assert -self.VMAX <= level <= self.VMAX, f"c_level violated : level={level}"
        assert delta + level >= 0, f"c_sum violated : delta={delta} level={level}"
        assert kind != self.KINDS[0] or n == 1, f"c_kind0 violated : len={n}"

        return addr + n + mask + kind + delta + level


class item_0(item_base):
    """page 0x10, aligned to 8, len <= 16, kinds {9, 37, 52, 55}, mask & 0xc0 == 0, nibble 0xe, delta +/-4096, level +/-512"""

    LOW, HIGH = 0x10000000, 0x10ffffff
    PAGE = 0x10
    ALIGN = 8
    LMAX = 16
    KINDS = (9, 37, 52, 55)
    CLEAR = 0xc0
    XOR = 0x0e
    DMAX = 4096
    VMAX = 512


class item_1(item_base):
    """page 0x2f, aligned to 4, len <= 1024, kinds {7, 14, 25, 51}, mask & 0xc0 == 0, nibble 0x0, delta +/-4096, level +/-128"""

    LOW, HIGH = 0x2f000000, 0x2fffffff
    PAGE = 0x2f
    ALIGN = 4
    LMAX = 1024
    KINDS = (7, 14, 25, 51)
    CLEAR = 0xc0
    XOR = 0x00
    DMAX = 4096
    VMAX = 128


class item_2(item_base):
    """page 0x10, aligned to 8, len <= 16, kinds {15, 38, 47, 52}, mask & 0x10 == 0, nibble 0x0, delta +/-64, level +/-128"""

    LOW, HIGH = 0x10000000, 0x10ffffff
    PAGE = 0x10
    ALIGN = 8
    LMAX = 16
    KINDS = (15, 38, 47, 52)
    CLEAR = 0x10
    XOR = 0x00
    DMAX = 64
    VMAX = 128


class item_3(item_base):
    """page 0x10, aligned to 16, len <= 64, kinds {14, 28, 44, 63}, mask & 0xc0 == 0, nibble 0xf, delta +/-256, level +/-128"""

    LOW, HIGH = 0x10000000, 0x10ffffff
    PAGE = 0x10
    ALIGN = 16
    LMAX = 64
    KINDS = (14, 28, 44, 63)
    CLEAR = 0xc0
    XOR = 0x0f
    DMAX = 256
    VMAX = 128


class item_4(item_base):
    """page 0x20, aligned to 4, len <= 1024, kinds {15, 30, 44, 49}, mask & 0x10 == 0, nibble 0x5, delta +/-1024, level +/-32"""

    LOW, HIGH = 0x20000000, 0x20ffffff
    PAGE = 0x20
    ALIGN = 4
    LMAX = 1024
    KINDS = (15, 30, 44, 49)
    CLEAR = 0x10
    XOR = 0x05
    DMAX = 1024
    VMAX = 32


class item_5(item_base):
    """page 0x40, aligned to 8, len <= 4096, kinds {22, 47, 48, 58}, mask & 0x30 == 0, nibble 0x9, delta +/-1024, level +/-512"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 8
    LMAX = 4096
    KINDS = (22, 47, 48, 58)
    CLEAR = 0x30
    XOR = 0x09
    DMAX = 1024
    VMAX = 512


class item_6(item_base):
    """page 0x40, aligned to 8, len <= 4096, kinds {32, 55, 57, 63}, mask & 0x10 == 0, nibble 0xf, delta +/-256, level +/-512"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 8
    LMAX = 4096
    KINDS = (32, 55, 57, 63)
    CLEAR = 0x10
    XOR = 0x0f
    DMAX = 256
    VMAX = 512


class item_7(item_base):
    """page 0x11, aligned to 8, len <= 4096, kinds {26, 27, 43, 52}, mask & 0x80 == 0, nibble 0x2, delta +/-4096, level +/-512"""

    LOW, HIGH = 0x11000000, 0x11ffffff
    PAGE = 0x11
    ALIGN = 8
    LMAX = 4096
    KINDS = (26, 27, 43, 52)
    CLEAR = 0x80
    XOR = 0x02
    DMAX = 4096
    VMAX = 512


class item_8(item_base):
    """page 0x40, aligned to 8, len <= 256, kinds {7, 11, 33, 50}, mask & 0xc0 == 0, nibble 0x0, delta +/-4096, level +/-32"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 8
    LMAX = 256
    KINDS = (7, 11, 33, 50)
    CLEAR = 0xc0
    XOR = 0x00
    DMAX = 4096
    VMAX = 32


class item_9(item_base):
    """page 0x40, aligned to 16, len <= 4096, kinds {20, 46, 55, 63}, mask & 0xc0 == 0, nibble 0x5, delta +/-256, level +/-512"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 16
    LMAX = 4096
    KINDS = (20, 46, 55, 63)
    CLEAR = 0xc0
    XOR = 0x05
    DMAX = 256
    VMAX = 512


class item_10(item_base):
    """page 0x11, aligned to 16, len <= 4096, kinds {1, 15, 50, 63}, mask & 0x30 == 0, nibble 0xc, delta +/-1024, level +/-512"""

    LOW, HIGH = 0x11000000, 0x11ffffff
    PAGE = 0x11
    ALIGN = 16
    LMAX = 4096
    KINDS = (1, 15, 50, 63)
    CLEAR = 0x30
    XOR = 0x0c
    DMAX = 1024
    VMAX = 512


class item_11(item_base):
    """page 0x40, aligned to 16, len <= 16, kinds {18, 23, 30, 59}, mask & 0xc0 == 0, nibble 0x4, delta +/-256, level +/-128"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 16
    LMAX = 16
    KINDS = (18, 23, 30, 59)
    CLEAR = 0xc0
    XOR = 0x04
    DMAX = 256
    VMAX = 128


class item_12(item_base):
    """page 0x20, aligned to 16, len <= 4096, kinds {4, 31, 56, 61}, mask & 0x30 == 0, nibble 0xd, delta +/-4096, level +/-128"""

    LOW, HIGH = 0x20000000, 0x20ffffff
    PAGE = 0x20
    ALIGN = 16
    LMAX = 4096
    KINDS = (4, 31, 56, 61)
    CLEAR = 0x30
    XOR = 0x0d
    DMAX = 4096
    VMAX = 128


class item_13(item_base):
    """page 0x40, aligned to 16, len <= 4096, kinds {1, 23, 27, 35}, mask & 0x80 == 0, nibble 0xe, delta +/-64, level +/-32"""

    LOW, HIGH = 0x40000000, 0x40ffffff
    PAGE = 0x40
    ALIGN = 16
    LMAX = 4096
    KINDS = (1, 23, 27, 35)
    CLEAR = 0x80
    XOR = 0x0e
    DMAX = 64
    VMAX = 32


class item_14(item_base):
    """page 0x11, aligned to 4, len <= 4096, kinds {12, 36, 38, 41}, mask & 0x80 == 0, nibble 0x1, delta +/-64, level +/-32"""

    LOW, HIGH = 0x11000000, 0x11ffffff
    PAGE = 0x11
    ALIGN = 4
    LMAX = 4096
    KINDS = (12, 36, 38, 41)
    CLEAR = 0x80
    XOR = 0x01
    DMAX = 64
    VMAX = 32


class item_15(item_base):
    """page 0x20, aligned to 4, len <= 256, kinds {1, 2, 29, 56}, mask & 0x10 == 0, nibble 0x5, delta +/-1024, level +/-128"""

    LOW, HIGH = 0x20000000, 0x20ffffff
    PAGE = 0x20
    ALIGN = 4
    LMAX = 256
    KINDS = (1, 2, 29, 56)
    CLEAR = 0x10
    XOR = 0x05
    DMAX = 1024
    VMAX = 128


CLASSES = (
    item_0,
    item_1,
    item_2,
    item_3,
    item_4,
    item_5,
    item_6,
    item_7,
    item_8,
    item_9,
    item_10,
    item_11,
    item_12,
    item_13,
    item_14,
    item_15,
)
