# Copyright 2026 Apheleia
#
# Description:
# Apheleia mutation testing example - synchronous FIFO
#
# This is an ordinary AVL testbench and knows nothing about mutation testing.
# avl-mutation-testing generates mutated copies of the RTL from the golden
# source, and the Makefile chooses which copy to build:
#
#   make sim                   golden design
#   make sim AVL_MUTANT=2      build and run mutant 2
#   make mutation_regression   every mutant in turn, scored

import avl
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge


class fifo_item(avl.SequenceItem):
    """Stimulus - what to ask of the FIFO on one cycle."""

    def __init__(self, name, parent_sequence):
        super().__init__(name, parent_sequence)

        self.data = avl.Uint8(0, fmt=str)
        self.do_push = avl.Bool(False, fmt=str)
        self.do_pop = avl.Bool(False, fmt=str)

class fifo_data_item(avl.SequenceItem):
    """Payload - one word in or out, as seen by the scoreboard."""

    def __init__(self, name, parent_sequence):
        super().__init__(name, parent_sequence)

        self.data = avl.Uint8(0, fmt=str)

class fifo_sequence(avl.Sequence):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.n_items = avl.Factory.get_variable(f"{self.get_full_name()}.n_items", 400)
        self.drain_cycles = avl.Factory.get_variable(f"{self.get_full_name()}.drain_cycles", 32)

    async def body(self):
        self._parent_sequencer_.raise_objection()

        for _ in range(self.n_items):
            item = fifo_item("item", self)
            await self.start_item(item)
            item.randomize()
            await self.finish_item(item)

        # Drain. Without this the test ends with words still in the FIFO, which
        # the scoreboard rightly reports as outstanding. Comfortably more pops
        # than the FIFO is deep, and the driver drops the ones it cannot use.
        for _ in range(self.drain_cycles):
            item = fifo_item("item", self)
            await self.start_item(item)
            item.do_push.value = False
            item.do_pop.value = True
            await self.finish_item(item)

        self._parent_sequencer_.drop_objection()

class fifo_sequencer(avl.Sequencer):
    def __init__(self, name, parent):
        super().__init__(name, parent)

class fifo_driver(avl.Driver):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def reset(self):
        self.hdl.push.value = 0
        self.hdl.pop.value = 0
        self.hdl.wdata.value = 0

    async def run_phase(self):
        await self.reset()

        await RisingEdge(self.hdl.clk)
        while True:
            item = await self.seq_item_port.blocking_get()

            while True:
                await RisingEdge(self.hdl.clk)
                if self.hdl.rst_n.value == 0:
                    await self.reset()
                else:
                    break

            # Only ask for what the FIFO says it can take, so the golden design
            # is never pushed when full or popped when empty. A mutation that
            # corrupts the flags will drag the stimulus off the golden path,
            # which is itself a detection.
            push = bool(item.do_push.value) and not int(self.hdl.full.value)
            pop = bool(item.do_pop.value) and not int(self.hdl.empty.value)

            self.hdl.push.value = int(push)
            self.hdl.pop.value = int(pop)
            self.hdl.wdata.value = item.data.value
            item.set_event("done")

class fifo_monitor(avl.Monitor):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # A FIFO's reference model is the identity on an ordered stream, so the
        # pushed words are written straight to the scoreboard as expected data
        # and the popped words as actual. Both carry the same item name because
        # compare() checks the name along with the fields.
        self.push_export = avl.Port("push_export", self)
        self.pop_export = avl.Port("pop_export", self)

        self.cg = avl.Covergroup("cg", self)
        self.cp_full = self.cg.add_coverpoint("cp_full", lambda: self.hdl.full.value)
        self.cp_full.add_bin("full", 1)
        self.cp_full.add_bin("not_full", 0)

        self.cp_empty = self.cg.add_coverpoint("cp_empty", lambda: self.hdl.empty.value)
        self.cp_empty.add_bin("empty", 1)
        self.cp_empty.add_bin("not_empty", 0)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def run_phase(self):
        while True:
            # Sample mid cycle. Everything the RTL will capture on the coming
            # rising edge is stable here, and the pointers have not moved since
            # the last one, so the combinational rdata is still the head word.
            await FallingEdge(self.hdl.clk)

            if self.hdl.rst_n.value == 0:
                continue

            if self.hdl.push.value == 1 and self.hdl.full.value == 0:
                item = fifo_data_item("item", None)
                item.data.value = int(self.hdl.wdata.value)
                self.push_export.write(item)

            if self.hdl.pop.value == 1 and self.hdl.empty.value == 0:
                item = fifo_data_item("item", None)
                item.data.value = int(self.hdl.rdata.value)
                self.pop_export.write(item)

            self.cg.sample()

    async def report_phase(self):
        print(self.cg.report(full=True))

class fifo_scoreboard(avl.Scoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.set_min_compare_count(50)

class fifo_agent(avl.Agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.sqr = fifo_sequencer("sqr", self)
        self.seq = fifo_sequence("seq", self.sqr)
        self.drv = fifo_driver("drv", self)
        self.mon = fifo_monitor("mon", self)
        self.sb = fifo_scoreboard("sb", self)

        self.seq.set_sequencer(self.sqr)

    async def connect_phase(self):
        self.sqr.seq_item_export.connect(self.drv.seq_item_port)

        self.mon.push_export.connect(self.sb.before_port)
        self.mon.pop_export.connect(self.sb.after_port)

    async def run_phase(self):
        self.raise_objection()
        await self.seq.start()
        self.drop_objection()

class fifo_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.agent = fifo_agent("agent", self)

    async def connect_phase(self):
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.rst = avl.Factory.get_variable(f"{self.get_full_name()}.rst", None)
        self.clk_freq_mhz = avl.Factory.get_variable(f"{self.get_full_name()}.clk_freq_mhz", 100)
        self.reset_ns = avl.Factory.get_variable(f"{self.get_full_name()}.reset_ns", 100)
        self.timeout_ns = avl.Factory.get_variable(f"{self.get_full_name()}.timeout_ns", 100000)

    async def run_phase(self):
        cocotb.start_soon(self.clock(self.clk, self.clk_freq_mhz))
        cocotb.start_soon(self.async_reset(self.rst, self.reset_ns, active_high=False))
        cocotb.start_soon(self.timeout(self.timeout_ns))

@cocotb.test
async def test(dut):
    avl.PhaseManager.add_phase("BUILD", after=None, top_down=True)
    avl.PhaseManager.add_phase("CONNECT", after=avl.PhaseManager.get_phase("BUILD"), top_down=True)

    avl.Factory.set_variable('*.hdl', dut)
    avl.Factory.set_variable('*.clk', dut.clk)
    avl.Factory.set_variable('*.rst', dut.rst_n)
    avl.Factory.set_variable('env.timeout_ns', 100000)
    avl.Factory.set_variable('env.clk_freq_mhz', 100)
    avl.Factory.set_variable('*.n_items', 400)

    e = fifo_env('fifo_env', None)
    await e.start()
