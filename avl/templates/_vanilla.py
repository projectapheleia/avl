# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Vanilla (most common)

import cocotb

import avl


class VanillaDriver(avl.Driver):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.rst = avl.Factory.get_variable(f"{self.get_full_name()}.rst", None)


class VanillaMonitor(avl.Monitor):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.rst = avl.Factory.get_variable(f"{self.get_full_name()}.rst", None)


class VanillaSequencer(avl.Sequencer):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)


class VanillaSequence(avl.Sequence):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)
        self.n_items = avl.Factory.get_variable(f"{self.get_full_name()}.n_items", 1)

    async def body(self):
        self._parent_sequencer_.raise_objection()
        for _ in range(self.n_items):
            item = avl.SequenceItem("item", self)
            await self.start_item(item)
            item.randomize()
            await self.finish_item(item)
        self._parent_sequencer_.drop_objection()


class VanillaModel(avl.Model):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

    async def run_phase(self):
        while True:
            item = await self.item_port.blocking_get()
            self.item_export.write(item)


class VanillaScoreboard(avl.Scoreboard):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)


class VanillaAgentCfg(avl.Component):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

        self.is_active = avl.Factory.get_variable(f"{self.get_full_name()}.is_active", True)
        self.has_model = avl.Factory.get_variable(f"{self.get_full_name()}.has_model", True)
        self.has_scoreboard = avl.Factory.get_variable(
            f"{self.get_full_name()}.has_scoreboard", True
        )


class VanillaAgent(avl.Agent):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)
        self.cfg = VanillaAgentCfg("cfg", self)

        if self.cfg.is_active:
            self.sqr = VanillaSequencer("sqr", self)
            self.seq = VanillaSequence("seq", self.sqr)
            self.drv = VanillaDriver("drv", self)

            self.seq.set_sequencer(self.sqr)

        # Always have monitor
        self.mon = VanillaMonitor("mon", self)

        if self.cfg.has_model:
            self.model = VanillaModel("model", self)

        if self.cfg.has_scoreboard:
            self.sb = VanillaScoreboard("sb", self)

        if self.cfg.is_active:
            self.sqr.seq_item_export.connect(self.drv.seq_item_port)

        # Connect the monitor to the model and scoreboard
        if self.cfg.has_model:
            self.mon.item_export.connect(self.model.item_port)

            if self.cfg.has_scoreboard:
                self.mon.item_export.connect(self.sb.after_port)
                self.model.item_export.connect(self.sb.before_port)

    async def run_phase(self):
        self.raise_objection()

        # Start the sequence
        await self.seq.start()

        self.drop_objection()


class VanillaEnvCfg(avl.Component):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

        # Clock
        self.clock_freq_mHz = avl.Factory.get_variable(f"{self.get_full_name()}.clk_freq_mHz", 100)

        # Async Reset
        self.reset_ns = avl.Factory.get_variable(f"{self.get_full_name()}.reset_ns", 100)
        self.reset_high = avl.Factory.get_variable(f"{self.get_full_name()}.reset_high", False)

        # Sync Reset
        self.sreset_cycles = avl.Factory.get_variable(f"{self.get_full_name()}.sreset_cycles", 10)
        self.sreset_high = avl.Factory.get_variable(f"{self.get_full_name()}.sreset_high", False)

        # Timeout
        self.timeout_ns = avl.Factory.get_variable(f"{self.get_full_name()}.timeout_ns", None)

        # Ticker
        self.ticker_ns = avl.Factory.get_variable(f"{self.get_full_name()}.ticker_ns", None)

        # Agents
        self.n_agent = avl.Factory.get_variable(f"{self.get_full_name()}.n_agent", 1)


class VanillaEnv(avl.Env):
    def __init__(self, name: str, parent: avl.Component) -> None:
        super().__init__(name, parent)

        self.cfg = VanillaEnvCfg("cfg", self)
        self.agent = []
        for i in range(self.cfg.n_agent):
            self.agent.append(VanillaAgent(f"agent{i}", self))

        # Get handle to hdl / clk / resets via factory
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.rst = avl.Factory.get_variable(f"{self.get_full_name()}.rst", None)
        self.srst = avl.Factory.get_variable(f"{self.get_full_name()}.srst", None)

    async def run_phase(self):
        if self.clk is not None:
            cocotb.start_soon(self.clock(self.clk, self.cfg.clock_freq_mHz))

        if self.rst is not None:
            cocotb.start_soon(
                self.async_reset(self.rst, self.cfg.reset_ns, active_high=self.cfg.reset_high)
            )

        if self.srst is not None:
            cocotb.start_soon(
                self.sync_reset(self.clk, self.srst, self.cfg.sreset_cycles, active_high=self.cfg.sreset_high)
            )

        if self.cfg.timeout_ns is not None:
            cocotb.start_soon(self.timeout(self.cfg.timeout_ns))

        if self.cfg.ticker_ns is not None:
            cocotb.start_soon(self.ticker(self.cfg.ticker_ns, "Tempus Fugit"))


__all__ = [
    "VanillaDriver",
    "VanillaMonitor",
    "VanillaSequencer",
    "VanillaSequence",
    "VanillaModel",
    "VanillaScoreboard",
    "VanillaAgentCfg",
    "VanillaAgent",
    "VanillaEnvCfg",
    "VanillaEnv",
]
