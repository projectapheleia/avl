# Copyright 2024 Apheleia
#
# Description:
# Apheleia sequence item hierarchical path example


import avl
import cocotb


class example_item(avl.SequenceItem):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.value = None


class example_override_item(example_item):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Looks itself up using its own get_full_name(). For this to find the
        # value set below, get_full_name() must resolve to the same path that
        # was used to construct this item (the one Object.__new__ used to
        # find the factory override in the first place).
        self.value = avl.Factory.get_variable(f"{self.get_full_name()}.value", None)


class example_sequence(avl.Sequence):
    async def body(self):
        # The item is parented by the (not yet complete) sequence, not the
        # sequencer directly.
        self.item = example_item("item", self)
        await self.start_item(self.item)
        await self.finish_item(self.item)


class example_driver(avl.Driver):
    async def run_phase(self):
        while True:
            item = await self.seq_item_port.blocking_get()
            item.set_event("done")


class example_sequencer(avl.Sequencer):
    pass


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.driver = example_driver("driver", self)
        self.sequencer = example_sequencer("sequencer", self)

        self.sequencer.seq_item_export.connect(self.driver.seq_item_port)

    async def run_phase(self):
        self.raise_objection()

        # This is the path Object.__new__ builds when the item is
        # constructed: parent.get_full_name() + "." + name, where parent is
        # the sequence instance. set_override_by_instance() and
        # set_variable() must both target this path for the override /
        # value to reach an item nested inside a sequence.
        item_path = f"{self.sequencer.get_full_name()}.sequence.item"

        avl.Factory.set_override_by_instance(item_path, example_override_item)
        avl.Factory.set_variable(f"{item_path}.value", 0xDEAD)

        seq = example_sequence("sequence", self.sequencer)
        await seq.start()

        # The override applied correctly: it is always looked up against the
        # construction path above, regardless of any later re-parenting.
        assert isinstance(seq.item, example_override_item), (
            f"Factory override by instance did not apply, got {type(seq.item).__name__}"
        )

        # The item's own hierarchical path must agree with the path used to
        # construct/override it. This is the regression check: a SequenceItem
        # parented by a Sequence used to be silently re-parented to the
        # Sequencer, dropping the sequence's name from get_full_name() and
        # breaking this equality.
        assert seq.item.get_full_name() == item_path, (
            f"get_full_name() mismatch: expected {item_path!r}, got {seq.item.get_full_name()!r}"
        )

        # Consequence of the above: a variable set at the construction path
        # must be visible to the item's own get_variable() lookup.
        assert seq.item.value == 0xDEAD, (
            f"Expected value 0xDEAD, got {seq.item.value!r} : the item looked itself up "
            "at the wrong hierarchical path"
        )

        self.info(f"Sequence item hierarchy resolved consistently at {item_path}")

        self.drop_objection()


@cocotb.test
async def test(dut):
    e = example_env("env", None)
    await e.start()
