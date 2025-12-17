# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb


class example_env(avl.Env):

    def test_init(self):
        self.info("Testing memory init operations...")

        # Test 1 : Uninitialized memory returns zero
        mem = avl.Memory(width=32)
        mem.add_range(0x0000, 0x1000)

        assert mem.read(0x0000) == 0
        assert mem.read(0x0ff8) == 0
        self.info("Test 1 passed: Uninitialized memory returns zero")

         # Test 2 : Uninitialized memory returns 1's
        mem = avl.Memory(width=32)
        mem.set_init_fn(lambda address: 255)
        mem.add_range(0x0000, 0x1000)

        assert mem.read(0x0000) == (1 << 32)-1
        assert mem.read(0x0ff8) == (1 << 32)-1
        self.info("Test 2 passed: Uninitialized memory returns zero")

        # Test 3 : Uninitialized memory returns address
        mem = avl.Memory(width=32)
        mem.set_init_fn(lambda address, w=int(mem.width/8): ((address & ~(w - 1)) >> (8 * (address & (w - 1)))) & 0xFF)
        mem.add_range(0x0000, 0x1000)

        assert mem.read(0x0000) == 0x0000
        assert mem.read(0x0ff8) == 0x0ff8
        self.info("Test 3 passed: Uninitialized memory returns address")

    def test_range(self):
        self.info("Testing memory range operations...")

        mem = avl.Memory(width=32)
        mem.add_range(0x0000, 0x1000)

        # Test 1 : Of range fails
        try:
            mem.read(0x2000)
        except KeyError:
            self.info("Test 1 passed: Out of range access correctly raised KeyError")

    def test_little_endian(self):
        self.info("Testing little-endian memory operations...")

        mem = avl.Memory(width=32)
        mem.set_endianness('little')
        mem.add_range(0x0000, 0x1000)

        # Test 1 : Write and read back in little-endian
        mem.write(0x0000, 0x12345678)
        assert mem.read(0x0000, 1) == 0x78
        assert mem.read(0x0000, 2) == 0x5678
        assert mem.read(0x0000, 4) == 0x12345678
        self.info("Test 1 passed: Little-endian write and read back successful.")

        # Test 2 : Write little-endian and read back
        mem.write(0x0100, 0x12, 1)
        assert mem.read(0x0100, 1) == 0x12

        mem.write(0x0101, 0x34, 1)
        assert mem.read(0x0100, 2) == 0x3412

        mem.write(0x0102, 0x5678, 2)
        assert mem.read(0x0100, 4) == 0x56783412
        self.info("Test 2 passed: Little-endian write and read back successful.")

        # Test 3 : Write with strobe
        mem.write(0x0200, 0xdeadbeef, strobe=0b11)
        assert mem.read(0x0200, 4) == 0xbeef
        mem.write(0x0200, 0xcafebabe, strobe=0b1000)
        assert mem.read(0x0200, 4) == 0xca00beef
        self.info("Test 3 passed: Little-endian write strobe and read back successful.")

        # Test 4 : Rotation
        mem.write(0x0300, 0x76543210, 4)
        mem.write(0x0304, 0xfedcba98, 4)
        assert mem.read(0x0300, 4) == 0x76543210
        assert mem.read(0x301, 4, rotated=False) == 0x98765432
        assert mem.read(0x301, 4, rotated=True) == 0x76543210
        assert mem.read(0x302, 4, rotated=True) == 0x76543210
        assert mem.read(0x303, 4, rotated=True) == 0x76543210

        assert mem.read(0x0300, 1, rotated=True) == 0x00000010
        assert mem.read(0x0301, 1, rotated=True) == 0x00003200
        assert mem.read(0x0302, 1, rotated=True) == 0x00540000
        assert mem.read(0x0303, 1, rotated=True) == 0x76000000

        assert mem.read(0x0300, 2, rotated=True) == 0x00003210
        assert mem.read(0x0301, 2, rotated=True) == 0x00543200
        assert mem.read(0x0302, 2, rotated=True) == 0x76540000
        assert mem.read(0x0303, 2, rotated=True) == 0x76000010

        assert mem.read(0x0300, 3, rotated=True) == 0x00543210
        assert mem.read(0x0301, 3, rotated=True) == 0x76543200
        assert mem.read(0x0302, 3, rotated=True) == 0x76540010
        assert mem.read(0x0303, 3, rotated=True) == 0x76003210

        mem.write(0x0401, 0x76543210, strobe=0b0010, rotated=True)
        assert mem.read(0x0400, 4) == 0x00003200
        mem.write(0x0402, 0xdeadbeef, strobe=0b1101, rotated=True)
        assert mem.read(0x0400, 4) == 0xdead32ef

        self.info("Test 4 passed: Little-endian rotation successful.")

    def test_big_endian(self):
        self.info("Testing big-endian memory operations...")

        mem = avl.Memory(width=32)
        mem.set_endianness('big')
        mem.add_range(0x0000, 0x1000)

        # Test 1 : Write and read back in little-endian
        mem.write(0x0000, 0x12345678)
        assert mem.read(0x0000, 1) == 0x12000000
        assert mem.read(0x0000, 2) == 0x12340000
        assert mem.read(0x0000, 4) == 0x12345678
        self.info("Test 1 passed: Big-endian write and read back successful.")

        # Test 2 : Write big-endian and read back
        mem.write(0x0100, 0x12, 1)
        assert mem.read(0x0100, 1) == 0x12000000

        mem.write(0x0101, 0x34, 1)
        assert mem.read(0x0100, 2) == 0x12340000

        mem.write(0x0102, 0x5678, 2)
        assert mem.read(0x0100, 4) == 0x12345678
        self.info("Test 2 passed: Big-endian write and read back successful.")

        # Test 3 : Write with strobe
        mem.write(0x0200, 0xdeadbeef, strobe=0b1100)
        assert mem.read(0x0200, 4) == 0xdead0000
        mem.write(0x0200, 0xcafebabe, strobe=0b0001)
        assert mem.read(0x0200, 4) == 0xdead00be
        self.info("Test 3 passed: Big-endian write strobe and read back successful.")

        # Test 4 : Rotation
        mem.write(0x0300, 0x76543210, 4)
        mem.write(0x0304, 0xfedcba98, 4)
        assert mem.read(0x0300, 4) == 0x76543210
        assert mem.read(0x301, 4, rotated=False) == 0x543210fe
        assert mem.read(0x301, 4, rotated=True) == 0x76543210
        assert mem.read(0x302, 4, rotated=True) == 0x76543210
        assert mem.read(0x303, 4, rotated=True) == 0x76543210

        assert mem.read(0x0300, 1, rotated=True) == 0x76000000
        assert mem.read(0x0301, 1, rotated=True) == 0x00540000
        assert mem.read(0x0302, 1, rotated=True) == 0x00003200
        assert mem.read(0x0303, 1, rotated=True) == 0x00000010

        assert mem.read(0x0300, 2, rotated=True) == 0x76540000
        assert mem.read(0x0301, 2, rotated=True) == 0x00543200
        assert mem.read(0x0302, 2, rotated=True) == 0x00003210
        assert mem.read(0x0303, 2, rotated=True) == 0x76000010

        assert mem.read(0x0300, 3, rotated=True) == 0x76543200
        assert mem.read(0x0301, 3, rotated=True) == 0x00543210
        assert mem.read(0x0302, 3, rotated=True) == 0x76003210
        assert mem.read(0x0303, 3, rotated=True) == 0x76540010

        mem.write(0x0401, 0x76543210, strobe=0b0100, rotated=True)
        assert mem.read(0x0400, 4) == 0x00540000
        mem.write(0x0402, 0xdeadbeef, strobe=0b1011, rotated=True)
        assert mem.read(0x0400, 4) == 0xde54beef

        self.info("Test 4 passed: Big-endian rotation successful.")

    def test_import_export(self, fmt="vhex"):
        self.info(f"Testing memory import/export with format {fmt}...")

        for e in ["little", "big"]:
            mem0 = avl.Memory(width=32)
            mem0.add_range(0x0000, 0x1000)
            mem0.set_endianness(e)

            mem1 = avl.Memory(width=32)
            mem1.add_range(0x0000, 0x1000)
            mem1.set_endianness(e)

            # Write some data
            mem0.write(0x0100, 0x01234567)
            mem0.write(0x0104, 0x89abcdef)

            mem0.write(0x0200, 0xcafebabe)

            # Export to file
            mem0.export_to_file("test_export." + fmt, fmt=fmt)

            # Import from file
            mem1.import_from_file("test_export." + fmt, fmt=fmt)

            # Verify loaded values
            assert mem1.read(0x0100, 4) == mem0.read(0x0100, 4) == 0x01234567
            assert mem1.read(0x0200, 4) == mem0.read(0x0200, 4) == 0xcafebabe

            self.info(f"Test passed: {e} Endian Memory loaded from {fmt} file successfully.")

    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.test_init()

        self.test_range()

        self.test_little_endian()

        self.test_big_endian()

        for fmt in ["vhex", "vbin", "csv", "json", "ihex", "srec", "ti-txt", "vmem"]:
            self.test_import_export(fmt=fmt)

@cocotb.test
async def test(dut):
    _ = example_env("env", None)

