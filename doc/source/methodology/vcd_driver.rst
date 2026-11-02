.. _vcd_driver:

avl.VcdDriver
=============

.. inheritance-diagram:: avl._core.vcd_driver
    :parts: 1

A driver whose stimulus is a `Value Change Dump <https://en.wikipedia.org/wiki/Value_change_dump>`_ rather than a sequence. \
The capture may come from an earlier simulation, from a different testbench, or from a logic analyser on real silicon; \
the driver replays it onto the DUT and the monitor, model and scoreboard check the result exactly as they would under \
a sequence driven test.

The VCD is read by :doc:`avl.Vcd </modules/avl._core.vcd>`, a small dependency free reader that is also available on its own \
for inspecting a capture - looking a signal up, asking for its value at a time, or listing the edges of a clock.

The driver has two modes. Signals bound directly to the driver are **timed**; signals bound to a clock group are **clocked**. \
A driver may hold both, though see the note on mixing them below.

Setting up a replay
-------------------

Create the driver in ``build_phase`` and load the capture before binding signals \
in ``connect_phase``. For example, an agent can replay the adder capture as follows:

.. code-block:: python

    class replay_agent(avl.Agent):
        async def build_phase(self):
            self.drv = avl.VcdDriver("drv", self)

        async def connect_phase(self):
            hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)
            self.drv.load("capture.vcd")
            self.drv.add_scope("adder", hdl, exclude=("valid_out", "c"))

The test must supply the HDL handle through the factory. The capture path is \
relative to the simulation's working directory unless an absolute path is used. \
Alternatively, set ``*.drv.vcd_file`` through the factory before creating the \
driver; the file is then loaded on first use. No sequence is needed.

A VCD does not record signal directions. Bind only the DUT inputs, and exclude \
captured outputs when using ``add_scope()``. The scope name refers to the hierarchy \
in the capture; the HDL handle refers to the design being tested.

Timed mode
----------

Every signal bound with ``add_signal()`` is driven at exactly the time the file records each of its changes. The capture's \
own clock and reset are bound like anything else, so the testbench generates nothing of its own and the capture's \
timeline becomes the testbench's timeline.

.. code-block:: python

    async def connect_phase(self):
        for name in ("clk", "rst_n", "valid_in", "a", "b"):
            self.drv.add_signal(f"adder.{name}", getattr(self.hdl, name))

Times are converted from the file's ``$timescale`` into simulator steps. If the file is finer than the simulator's \
precision the driver warns once and rounds.

To bind a whole scope as the examples do, use ``add_scope()`` with output exclusions; see :ref:`vcd_driver_configuration`.

Clocked mode
------------

``add_clock()`` names a clock in the VCD and the HDL clock the testbench drives in its place, with \
:meth:`avl.Env.clock <avl._core.env.Env.clock>` or however it likes. The signals added to the returned group are driven \
after each edge of the testbench clock with the values the capture shows being sampled at the matching edge of its own \
clock. The DUT sees the same value on the same cycle as it did in the capture, however fast the testbench chooses to \
clock it - the example below replays a 50 MHz capture at 100 MHz.

.. code-block:: python

    async def connect_phase(self):
        grp = self.drv.add_clock("adder.clk", self.hdl.clk)
        for name in ("rst_n", "valid_in", "a", "b"):
            grp.add_signal(f"adder.{name}", getattr(self.hdl, name))

The value a cycle *sampled* is the value immediately before the clock edge, which is what a flop clocked by that edge \
saw. A change the file records at the same timestamp as the edge belongs to the following cycle, as it does in the \
simulator that wrote it. The first cycle's values are driven as soon as the run phase starts, so they are present at \
the first edge of the testbench clock; every later cycle's values are driven after the edge before it, like any other \
driver. A design with several clocks takes one group per clock.

Which mode
----------

Timed mode is the faithful one: the DUT sees exactly what the capture recorded, at exactly the intervals it recorded \
it. Clocked mode is the useful one whenever the testbench needs to own the clock - to run the design at a different \
frequency, to use the testbench's own clock and reset infrastructure, or because the capture's inputs change on the \
same timestamp as the clock edge that samples them. That last case is common in captures from cocotb testbenches, \
whose drivers write after ``RisingEdge``; replayed in timed mode, the input and clock changes land in the same \
simulator step and the flop may sample the new value where the original sampled the old. Clocked mode does not have \
the race, because the driver never drives the clock.

Mixing the modes in one driver is allowed but the two timelines are independent: the timed signals follow the file's \
timestamps and the clocked signals follow the testbench clock. They only line up if the testbench clock has the same \
period, and the same phase, as the one in the capture.

.. _vcd_driver_configuration:

Configuration
-------------

================================  ==================================================================================
Factory variable                  Purpose
================================  ==================================================================================
``<driver>.vcd_file``             Path of the VCD to replay. ``load()`` may be called instead.
``<driver>.objection``            Hold an objection to the run phase until playback is complete (default ``True``).
================================  ==================================================================================

Use ``set_window(start, end, unit)`` to select part of a capture; see :ref:`vcd_driver_completion` for examples.

Signals are named by their full hierarchical name in the VCD, or by any trailing part of it that is unambiguous: \
``dut.a`` or ``a`` for ``tb.dut.a``. Vectors carrying ``x`` or ``z`` are driven as binary strings, so a four state \
simulator receives them as recorded; a two state simulator treats them as it treats any other unknown.

A simulator that dumps a bus bit by bit declares ``a [3]``; the reader keeps it as ``a[3]``, \
and ``add_scope()`` drives it as element 3 of ``a`` where the handle can be indexed.

A capture of a running design records its outputs alongside its inputs, and a driver must not fight the DUT for \
them. ``add_scope()`` - on the driver for timed mode, on a group for clocked - binds every signal declared directly \
in a VCD scope to the signal of the same name under an HDL handle, and ``exclude`` names the ones to leave alone:

.. code-block:: python

    # Timed: everything in the scope but the outputs
    self.drv.add_scope("adder", self.hdl, exclude=("valid_out", "c"))

    # Clocked: the same, and the group's clock is left out as well
    grp = self.drv.add_clock("adder.clk", self.hdl.clk)
    grp.add_scope("adder", self.hdl, exclude=("valid_out", "c"))

A signal the HDL handle does not have is skipped with a warning. Direction is not recorded in a VCD, so the outputs \
have to be named; the alternative is to bind the inputs one by one with ``add_signal()``.

For run phase objections, the ``done`` event and draining pipeline results, see :ref:`vcd_driver_completion`.

Inspecting a capture
--------------------

Use ``avl.Vcd`` to inspect a capture without starting a simulation. The reader \
loads the whole file into memory, so memory usage grows with the capture size.

.. code-block:: python

    capture = avl.Vcd("capture.vcd")
    print(capture.timescale)
    print([signal.name for signal in capture.scope("adder")])

    a = capture.lookup("adder.a")
    print(a.value_at(100))
    print(a.value_at(100, inclusive=False))
    print(capture.lookup("adder.clk").edges())

Query times are integer multiples of the declared VCD timescale. \
``value_at()`` includes changes at the requested timestamp by default; \
``inclusive=False`` returns the value before that timestamp. It returns ``None`` \
when no value has been recorded yet. Fully known logic values are integers; \
values containing ``x`` or ``z`` are binary strings. Aliases share their recorded \
changes. Signal lookup accepts a full name or an unambiguous trailing name.

.. _vcd_driver_completion:

Replaying a window and waiting for completion
---------------------------------------------

Configure a window before the run phase to select part of a capture:

.. code-block:: python

    self.drv.set_window(start=100, end=500, unit="ns")

Timed replay applies the recorded state at 100 ns when playback starts, then \
replays the next 400 ns of changes. Clocked replay selects clock edges within \
the window, including both endpoints. A window restores driven inputs only; \
the testbench must arrange any reset or internal DUT state needed by that segment.

By default, the driver holds a run phase objection until playback completes, sets \
its ``done`` event, and drops the objection. In clocked mode it waits for the edge \
that samples the final frame before reporting completion. Pipeline results may \
need additional clock cycles, supplied by idle cycles at the end of the capture \
or by an environment that keeps the clock running and holds its own objection.

Another component can wait for playback to finish in its run phase:

.. code-block:: python

    await self.drv.done.wait()

If that component needs additional cycles to collect results, it must raise its \
own objection before waiting and drop it after collecting those results. This \
keeps the run phase active after the driver's objection is dropped.

Example
-------

Both examples replay the same capture, ``examples/vcd_driver/stimulus/adder.vcd``, onto the adder used by the \
:ref:`methodology` examples: a hundred additions with idle cycles between them, written by ``gen_stimulus.py`` \
alongside it. The capture holds the adder's outputs as well as its inputs, as a real one would; both examples bind \
the whole scope and exclude the outputs. The monitor packages every valid cycle, the model predicts ``a + b`` and \
the scoreboard checks it, requiring all hundred to have been compared.

Timed - the capture drives everything, clock and reset included:

.. literalinclude:: ../../../examples/vcd_driver/timed/cocotb/example.py
    :language: python

Clocked - the testbench drives the clock, at twice the capture's frequency, and the capture follows it cycle for cycle:

.. literalinclude:: ../../../examples/vcd_driver/clocked/cocotb/example.py
    :language: python
