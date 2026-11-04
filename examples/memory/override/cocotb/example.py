# Copyright 2026 Apheleia
#
# Description:
# Apheleia memory factory override and comparison example


import avl
import cocotb


class memory_A(avl.Memory):
    """A memory the factory should replace."""

    def __init__(self, width=32, name="memory", parent=None):
        super().__init__(width=width, name=name, parent=parent)
        self.error("memory_A should have been overridden by memory_B")


class memory_B(memory_A):
    """The replacement. It keeps the Memory interface and adds a marker."""

    def __init__(self, width=32, name="memory", parent=None):
        avl.Memory.__init__(self, width=width, name=name, parent=parent)
        self.marker = "memory_B"
        self.info("memory_B successfully overridden memory_A")


class example_env(avl.Env):

    def test_override_by_type(self):
        self.info("Testing memory factory override by type...")

        # Test 1 : A memory built by width, without a name, takes the type override
        mem = memory_A(width=32)
        if type(mem) is not memory_B:
            self.error(f"Expected memory_B, got {type(mem).__name__}")
        if mem.marker != "memory_B":
            self.error("memory_B constructor did not run")

        # Test 2 : The replacement still is a memory
        mem.add_range(0x0000, 0x1000)
        mem.write(0x0010, 0x12345678)
        if mem.read(0x0010) != 0x12345678:
            self.error("Overridden memory lost its contents")

        # Test 3 : Name and parent land on the memory like on any object
        mem = memory_A(width=32, name="mem", parent=self)
        if mem.get_full_name() != f"{self.get_full_name()}.mem":
            self.error(f"Unexpected full name {mem.get_full_name()}")

        # Test 4 : A memory of another type is left alone
        plain = avl.Memory(width=32)
        if type(plain) is not avl.Memory:
            self.error(f"Expected avl.Memory, got {type(plain).__name__}")

        self.info("Test passed: memory factory override by type")

    def test_compare(self):
        self.info("Testing memory comparison...")

        def make():
            mem = avl.Memory(width=32)
            mem.add_range(0x0000, 0x1000)
            mem.write(0x0100, 0x01234567)
            mem.write(0x0104, 0x89abcdef)
            mem.write(0x0201, 0xaa, 1)
            return mem

        mem0 = make()
        mem1 = make()

        # Test 1 : Same writes, same contents
        if not mem0.compare(mem1, verbose=True):
            self.error("Identical memories compared different")

        # Test 2 : A read initializes bytes lazily; contents are still the same,
        #          and the compare itself touches neither memory
        mem1.read(0x0300)
        before0, before1 = dict(mem0.memory), dict(mem1.memory)
        if not mem0.compare(mem1):
            self.error("A lazily initialized byte made the memories differ")
        if mem0.memory != before0 or mem1.memory != before1:
            self.error("compare changed the contents of a memory")

        # Tests 3 and 4 : compare reports each reason as an error, so three
        #                 ERROR lines are expected in the log of this example
        # Test 3 : One byte differs
        mem1.write(0x0102, 0xff, 1)
        if mem0.compare(mem1):
            self.error("A differing byte was not detected")

        # Test 4 : Width and endianness are part of the comparison
        mem2 = avl.Memory(width=64)
        if mem0.compare(mem2):
            self.error("A width mismatch was not detected")
        mem3 = make()
        mem3.set_endianness("big")
        if mem0.compare(mem3):
            self.error("An endianness mismatch was not detected")

        self.info("Test passed: memory comparison")

    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.test_override_by_type()

        self.test_compare()


@cocotb.test
async def test(dut):
    avl.Factory.set_override_by_type(memory_A, memory_B)

    e = example_env("env", None)
    await e.start()
