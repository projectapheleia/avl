Randomization Performance
=========================

Constrained randomization has two main costs: constructing the Z3 expressions and
solving them. AVL reduces both costs when objects with the same field and constraint
shape are randomized repeatedly.

The optimizations preserve all hard constraints, so every returned value remains
legal. They do not all make the same guarantee about distribution:

- pooling Z3 variables and clauses changes how expressions are constructed, not the
  constraints that are solved;
- omitting clauses for bits fixed by hard constraints preserves the optimization
  objective exactly;
- rationing clauses for contested bits is a heuristic. It can change which legal
  values are preferred and is therefore checked by distribution-quality benchmarks.

The exact performance gain depends on the constraint shape, Z3 version, simulator
and host system. The `benchmark suite
<https://github.com/projectapheleia/avl/tree/main/benchmarks>`_ can be used to measure
the current version in a specific environment.


Sources of randomization cost
-----------------------------

AVL adds a soft constraint for each randomized bit. Each clause asks the bit to
match a random draw. Z3 optimizes these requests alongside any user-defined soft
constraints, subject to the hard constraints. This introduces variation instead of
repeatedly returning the solver's preferred legal model. It aims to spread the
results; it does not guarantee a uniform distribution over an arbitrary constrained
domain.

A four-field object containing 32-bit variables can therefore add 128 randomization
clauses to every solve. Before pooling, a fresh object also created fresh Z3 symbols,
so its per-bit clauses and any analysis based on those symbols could not be reused.

AVL now performs the following work for each randomization:

- look up pooled Z3 variables and per-bit clauses;
- construct and add the object's hard and soft constraints;
- select the randomization clauses needed for this solve;
- create and run a solver, then read its model.

The random draw, constraint functions, solver and model remain local to each call.


Pooled Z3 variables
-------------------

A Z3 variable is named from its position and sort within a solve rather than from
the :doc:`avl.Var </modules/avl._core.var>` instance that owns it. For example, a
16-bit bit vector at position 0 uses ``v0_l16``, while a 32-bit bit vector at the
same position uses ``v0_l32``.

The symbols are held in a process-wide pool. A later object with the same field
shape can reuse them and the per-bit clauses built from them. Hard constraint
functions are still evaluated for every randomization, although Z3 can reuse
hash-consed expressions built over the pooled symbols.


Why pooling is safe
~~~~~~~~~~~~~~~~~~~

A Z3 variable is a symbol in a formula, not storage for a value. Its value exists
only in the model produced by a particular solver.

:any:`Object.randomize` creates a fresh ``Optimize`` instance, adds one object's
constraints, solves them and copies the model values back to that object. Reusing a
symbol in another solver does not carry a value or assertion between the two solves.

Fields within one solve remain distinct because their positions differ. Fields of
different Z3 sorts also have different pooled names. When an external object's field
is used as a constraint argument, AVL substitutes its current value rather than its
Z3 symbol. Nested :doc:`avl.Object </modules/avl._core.object>` instances are
randomized separately and are not traversed as part of their parent's solve.

The position of a variable is recalculated for every randomization. This matters
when the same ``Var`` is shared between objects or is randomized both independently
and as part of an object. Its ``_rand_`` attribute is internal state associated with
the most recent solve and should not be treated as a stable identity.

:any:`Var.randomize` also uses pooled symbols, but does not use the object-level bit
analysis described below. A standalone variable remains the only variable in its
solve and uses position 0.


Omitting clauses for pinned bits
--------------------------------

Some hard constraints force individual bits to one value in every legal solution.
For example, constraining a 32-bit field to the inclusive range 100 through 5000
forces bits 13 and above to zero.

After a constraint shape has been seen repeatedly, AVL asks Z3 which bits are
pinned and caches the result. Randomization clauses are then added only for the
remaining free bits.

Removing a pinned-bit clause cannot change which solutions are optimal. If bit
``b`` is pinned to ``p``, a randomization clause requesting ``b == r`` has one of
two effects:

- when ``r == p``, every legal solution satisfies the clause;
- when ``r != p``, every legal solution violates the clause.

The clause therefore contributes the same fixed amount to every legal candidate.
Removing it changes all candidate scores equally and leaves their ordering
unchanged. This argument does not depend on the weights of any other soft
constraints.

Only the static hard constraints attached to the object and its variables take part
in the pinned-bit analysis. A hard constraint supplied to ``randomize(hard=...)``
can only reduce the legal set, so a previously pinned bit remains pinned. If the
dynamic constraint pins an additional bit, that bit still receives a harmless
constant randomization clause.

Floating-point variables are not included in this analysis because their solver
variables have a floating-point sort rather than a bit-vector sort. Their auxiliary
IEEE bit vectors continue to receive a clause for every bit.


Rationing contested clauses
---------------------------

A free bit can vary across legal solutions without being independently selectable.
For example, the range 1000 through 2000 leaves eleven bits unpinned, but permits
only about half of their 2048 possible combinations. Dependencies between variables
can restrict the combinations further.

Requesting every free bit can therefore describe an illegal combination. Z3 must
then relax some of the soft requests while finding an optimum. Benchmarking shows
that constraint shapes with more rejected randomization clauses generally take
longer to solve.

AVL measures how often each free-bit request is granted during the first few
randomizations of a constraint shape. It then records a plan containing:

- reliable bits, whose clauses continue to be requested every time;
- contested bits, from which a random subset is requested;
- the number of contested bits to request in each solve.

If every bit is reliable, or the budget covers all contested bits, the plan retains
every free-bit clause. Whether this happens depends on the measured constraint
system, not simply on whether each constraint mentions one variable or several.

The static soft constraints attached to the object and its variables are part of
the cache key because they compete with randomization clauses in the same
optimization objective. Different static soft constraints therefore receive
separate plans.

Constraints supplied through either ``randomize(hard=...)`` or
``randomize(soft=...)`` are not part of that key. A solve using either form of
dynamic constraint does not use or update a cached clause plan; it requests every
free bit. Pinned-bit analysis remains safe for these solves as described above.


Distribution implications
~~~~~~~~~~~~~~~~~~~~~~~~~

Clause rationing is a performance heuristic, not a distribution-preserving
identity. It changes the set of soft requests and can therefore change which legal
solutions are optimal. Hard constraints still determine legality, but the selected
clauses influence how frequently different legal values appear.

The benchmark suite measures both runtime and distribution quality. Its untimed
quality run records the generated values and reports distinct-value coverage,
normalized entropy and per-bit skew. ``make quality`` fails when the selected AVL
results fall outside the configured quality thresholds.

For troubleshooting or comparison, setting ``Object._ALWAYS_GRANTED_`` to ``0.0``
makes every measured free bit reliable. This restores a clause for every free bit
and disables contested-bit rationing. This is an internal tuning attribute rather
than part of the stable public API.


Running the benchmarks
----------------------

The benchmark suite creates a fresh item for each randomization and compares AVL
with equivalent SystemVerilog and pyuvm/pyvsc implementations. Timing runs subtract
a baseline with randomization disabled. Quality runs are separate so recording the
generated values does not affect timing.

From the repository root, run:

.. code-block:: bash

    make -C benchmarks bench

To run only the distribution checks:

.. code-block:: bash

    make -C benchmarks quality

Reports are written beneath ``benchmarks/results/``. When publishing measurements,
record the AVL revision, simulator and Z3 versions, benchmark options, operating
system and host hardware so that absolute timings and speedups can be interpreted
and reproduced.
