# Copyright 2024 Apheleia
#
# Description:
# Apheleia coverage example


import os
import random

import avl
import cocotb


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.a = 0
        self.b = 0

        self.cg = avl.Covergroup("cg", self)

        self.cp_a = self.cg.add_coverpoint("cp_a", lambda: self.a)
        self.cp_a.add_bin("a", range(0,20), stats=True)

        self.cp_b = self.cg.add_coverpoint("cp_b", lambda: self.b)
        self.cp_b.add_bin("b", range(0,20), stats=True)

        self.cp_c = self.cg.add_coverpoint("cp_c", lambda: self.a + self.b)
        for i in range(0,40):
            self.cp_c.add_bin(f"c{i}", i)

    async def run_phase(self):
        """
        Run phase for the example environment.
        """
        for i in range(8):
            self.cg.clear()

            for _ in range(random.choice([0, 1, random.randint(5, 10)])):
                self.a = random.randint(0, 15)
                self.b = random.randint(5, 19)
                self.cg.sample()
            df = self.cg.report(full=True)
            df.to_json(f"coverage_{i}.json", mode="w", orient="records")

    async def report_phase(self):
        """
        Report phase for the example environment.
        """
        self.info("Removing combined coverage")
        avl.Coverage().remove_covergroup(self.cg)

        self.info("Generating html report")
        os.system("avl-coverage-analysis --path . --output html --merge --rank --stats")


@cocotb.test
async def my_test(dut):
    e = example_env("env", None)
    await e.start()
