# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb


class example_env(avl.Env):

    async def blocking_pop_test(self, lst : avl.List) -> None:
        cocotb.start_soon(self.delayed_push(lst, 10, 42))
        r = await self.blocking(lst)

        assert(r == 42)
        assert(cocotb.utils.get_sim_time(unit="ns") == 10)

    async def blocking_pop_after_drain_test(self, drain) -> None:
        """
        A list emptied by any means must still block on blocking_pop.

        Draining the list used to leave the push event set, so blocking_pop
        returned immediately and popped from an empty list (IndexError).
        """
        t0 = cocotb.utils.get_sim_time(unit="ns")

        lst = avl.List()
        lst.append(0)
        drain(lst)
        assert(len(lst) == 0)

        cocotb.start_soon(self.delayed_push(lst, 10, 42))
        r = await self.blocking(lst)

        assert(r == 42)
        assert(cocotb.utils.get_sim_time(unit="ns") == t0 + 10)

    async def blocking_pop_shared_test(self, lst : avl.List) -> None:
        """
        Two consumers waiting on a single push must not both be released.
        """
        t0 = cocotb.utils.get_sim_time(unit="ns")

        a = cocotb.start_soon(self.blocking(lst))
        b = cocotb.start_soon(self.blocking(lst))

        cocotb.start_soon(self.delayed_push(lst, 10, 42))
        cocotb.start_soon(self.delayed_push(lst, 20, 43))

        assert({await a, await b} == {42, 43})
        assert(cocotb.utils.get_sim_time(unit="ns") == t0 + 20)

    async def blocking(self, lst : avl.List) -> int:
        return await  lst.blocking_pop()

    async def delayed_push(self, lst : avl.List, d, v) -> None:
        await cocotb.triggers.Timer(d, "ns")
        lst.append(v)

    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Start with empty list
        lst = avl.List()
        assert(len(lst) == 0)

        # Check push
        for i in range(10):
            lst.append(i)
        assert(len(lst) == 10)

        # Check pop
        for i in range(10):
            assert(lst.pop(0) == i)

        # Check empty
        assert(not lst)

        # Check init
        lst = avl.List(0, 1, 2)
        assert(len(lst) == 3)

        # Check extend
        lst.extend([3, 4, 5])
        assert(len(lst) == 6)

        # Check insert
        lst.insert(0, -1)
        assert(lst[0] == -1)

        # Check remove
        lst.remove(3)
        assert(len(lst) == 6 and lst[4] == 4)

        # Check clear
        lst.clear()
        assert(len(lst) == 0 and not lst)

    async def run_phase(self):
        self.raise_objection()

        lst = avl.List()
        await self.blocking_pop_test(lst)

        # A list emptied by clear/pop/remove must block again
        await self.blocking_pop_after_drain_test(lambda lst: lst.clear())
        await self.blocking_pop_after_drain_test(lambda lst: lst.pop())
        await self.blocking_pop_after_drain_test(lambda lst: lst.remove(0))

        # A list constructed with elements must not block
        assert(await avl.List(42).blocking_pop() == 42)

        # Only one waiter is released per push
        await self.blocking_pop_shared_test(avl.List())

        self.drop_objection()

@cocotb.test
async def test(dut):
    e = example_env("env", None)
    await e.start()
