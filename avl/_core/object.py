# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Object Base Class

from __future__ import annotations

import copy
import os
import random
import warnings
from collections.abc import Callable, MutableMapping, MutableSequence, Set
from typing import Any, TypeVar

import tabulate
from z3 import (BitVecNumRef, BitVecRef, Bool, BoolRef, Extract, IntNumRef, Optimize, Solver,
                fpToIEEEBV, is_fp, sat, z3util)

from .factory import Factory
from .log import Log
from .struct import Struct
from .var import Var

def _var_finder_(obj: Any, memo: dict[int, Any], conversion: dict[Any, Any] = None, do_copy : bool=False, do_deepcopy : bool=False) -> Any:
    """
    Recursively find and copy Var objects in the given object.
    This function handles lists, tuples, sets, and dictionaries, and can optionally perform deep copies.

    :param obj: The object to search for Var instances.
    :type obj: Any
    :param memo: A dictionary to keep track of already processed objects to avoid infinite recursion.
    :type memo: dict[int, Any]
    :param conversion: A dictionary to store conversions of Var objects.
    :type conversion: dict[Any, Any], optional
    :param deepcopy: Whether to perform a deep copy of the Var objects.
    :type deepcopy: bool
    :return: A new object with Var instances replaced by copies.
    :rtype: Any
    """
    obj_id = id(obj)
    if obj_id in memo:
        return memo[obj_id]

    if isinstance(obj, Var):
        if do_deepcopy:
            new_obj = copy.deepcopy(obj, memo)
        elif do_copy:
            new_obj = copy.copy(obj)
        else:
            new_obj = obj
        conversion[obj_id] = new_obj
        memo[obj_id] = new_obj
        return new_obj

    elif isinstance(obj, MutableSequence):
        new_list = [_var_finder_(item, memo, conversion, do_copy, do_deepcopy) for item in obj]
        memo[obj_id] = new_list
        return new_list

    elif isinstance(obj, tuple):
        temp = [_var_finder_(item, memo, conversion, do_copy, do_deepcopy) for item in obj]
        new_tuple = tuple(temp)
        memo[obj_id] = new_tuple
        return new_tuple

    elif isinstance(obj, Set):
        new_set = {_var_finder_(item, memo, conversion, do_copy, do_deepcopy) for item in obj}
        memo[obj_id] = new_set
        return new_set

    elif isinstance(obj, MutableMapping):
        new_dict = type(obj)()
        memo[obj_id] = new_dict
        for k, v in obj.items():
            new_k = _var_finder_(k, memo, conversion, do_copy, do_deepcopy)
            new_v = _var_finder_(v, memo, conversion, do_copy, do_deepcopy)
            new_dict[new_k] = new_v
        return new_dict

    elif isinstance(obj, Struct):
        new_struct = type(obj)()
        memo[obj_id] = new_struct
        for name, _ in obj._fields_:
            value = getattr(obj, name)
            new_v = _var_finder_(value, memo, conversion, do_copy, do_deepcopy)
            setattr(new_struct, name, new_v)
        return new_struct

    elif isinstance(obj, Object):
        memo[obj_id] = obj
        return obj

    else:
        if do_deepcopy:
            try:
                try:
                    copied = copy.deepcopy(obj, memo)
                except Exception as e:
                    warnings.warn(f"Attempt to deepcopy unsupported object (returning original) {e} : {obj}",
                                  UserWarning,
                                  stacklevel=2)
                    copied = obj
                memo[obj_id] = copied
                return copied
            except RecursionError:
                raise
        else:
            return obj

def _patch_constraints_(obj : Object, new_obj : Object, conversion: dict[Any, int]) -> None:
    """
    Patch the constraints of the original object to the new object.
    This function updates the constraints of the new object by converting
    the Var objects in the constraints to their corresponding copies
    in the new object.

    :param obj: The original Object whose constraints are to be patched.
    :type obj: Object
    :param new_obj: The new Object to which the constraints will be applied.
    :type new_obj: Object
    :param conversion: A dictionary mapping the id of Var objects in the original object
                      to their corresponding copies in the new object.
    :type conversion: dict[Any, int]
    """
    new_obj._constraints_ = {True: {}, False: {}}
    for truth_value in (True, False):
        for k, v in obj._constraints_[truth_value].items():
            new_v = [conversion[id(o)] for o in v[1]]
            new_obj._constraints_[truth_value][k] = (v[0], new_v)


TObject = TypeVar("TObject", bound="Object")

class Object:

    def __copy__(self) -> Object:
        cls = self.__class__
        new_obj = cls.__new__(cls)

        # Copy the class - creating new copies of Var objects and reference to all else
        memo = {}
        conversion = {}
        for key, value in self.__dict__.items():
            if key != "_constraints_":
                setattr(new_obj, key, _var_finder_(value, memo, conversion, do_copy=True))

        # Patch the constraints
        _patch_constraints_(self, new_obj, conversion)

        return new_obj

    def __deepcopy__(self, memo: dict[int, Any]) -> Object:
        obj_id = id(self)
        if obj_id in memo:
            return memo[obj_id]

        cls = self.__class__
        new_obj = cls.__new__(cls)
        memo[obj_id] = new_obj

        # Copy the class - creating new copies of Var objects and deep copies of all else
        conversion = {}
        for key, value in self.__dict__.items():
            if key != "_constraints_":
                setattr(new_obj, key, _var_finder_(value, memo, conversion, do_deepcopy=True))

        # Patch the constraints
        _patch_constraints_(self, new_obj, conversion)

        return new_obj

    def __new__(cls, *args: Any, **kwargs: Any) -> TObject:
        """
        Create a new instance of Object or its subclass.

        :param args: Variable length argument list.
        :type args: list
        :param kwargs: Arbitrary keyword arguments.
        :type kwargs: dict
        :return: New instance of Object or its subclass.
        :rtype: object
        """
        # If no arguments are provided, create a default instance
        if not args and not kwargs:
            return super().__new__(cls)

        if args:
            name = args[0]
            parent = args[1] if len(args) > 1 else None
        else:
            # Handle keyword arguments
            name = kwargs.get('name')
            parent = kwargs.get('parent')

        # Validate we have required parameters
        if name is None:
            raise TypeError(f"{cls.__name__} requires 'name' parameter")
        path = name

        # No factory for hidden Objects
        if name.startswith("_"):
            return super().__new__(cls)

        if parent is not None:
            path = f"{parent.get_full_name()}.{name}"

        target_cls = Factory.get_factory_override(cls, path)
        obj = super().__new__(target_cls)

        if target_cls is not cls and not issubclass(target_cls, cls):
            obj.__init__(*args, **kwargs)

        return obj

    def __init__(self, name: str, parent: Object|None) -> None:
        """
        Initialize Object.

        :param name: Name of the object.
        :type name: str
        :param parent: Parent object.
        :type parent: Object, optional
        """
        self.name = name
        self._parent_ = parent

        # Field attributes
        self._field_attributes_ = {}

        # Randomness and constraints
        self._constraints_ = {True : {}, False: {}}

        # Table format for string representation
        self._table_fmt_ = "grid"
        self._table_transpose_ = False
        self._table_recurse_ = True

    def __str__(self) -> str:
        """
        Return a string representation of the Object.

        :return: String representation of the object.
        :rtype: str
        """
        def format_value(val, indent=0, fmt=str):
            prefix = '  ' * indent

            # If top-level list with 1 item, unwrap it
            if indent == 0 and isinstance(val, list) and len(val) == 1 and isinstance(val[0], dict):
                val = val[0]

            if isinstance(val, MutableMapping):
                lines = []
                for k, v in val.items():
                    if isinstance(v, MutableMapping | MutableSequence):
                        lines.append(f"{prefix}{k}:")
                        lines.append(format_value(v, indent + 1, fmt))
                    else:
                        lines.append(f"{prefix}{k}: {fmt(v)}")
                return '\n'.join(lines)

            elif isinstance(val, MutableSequence | Set | tuple):
                lines = []
                for item in val:
                    if isinstance(item, MutableMapping | MutableSequence | Set | tuple):
                        lines.append(f"{prefix}-")
                        lines.append(format_value(item, indent + 1, fmt))
                    else:
                        lines.append(f"{prefix}{fmt(item)}")
                return '\n'.join(lines)

            else:
                return f"{prefix}{fmt(val)}"

        values = []
        for k, v in self.__dict__.items():
            if callable(v):
                continue

            if k.startswith("_"):
                continue

            if k in self._field_attributes_:
                if self._field_attributes_[k]["fmt"] is None:
                    continue
                _fmt_ = self._field_attributes_[k]["fmt"]
            else:
                _fmt_ = str

            if isinstance(v, Object):
                if self._table_recurse_:
                  values.append([k,v])
                else:
                  values.append([k, f"type({v.__class__.__name__}) at {hex(id(v))}"])
            elif isinstance(v, (Set | MutableSequence | tuple)):
                values.append([f"{k}", format_value(v, fmt=_fmt_)])
            elif isinstance(v, MutableMapping):
                values.append([f"{k}", format_value(v, fmt=_fmt_)])
            else:
                values.append([k, _fmt_(v)])

        if self._table_transpose_:
          values = list(map(list, zip(*values, strict=False)))
        return tabulate.tabulate(values, headers=[], tablefmt=self._table_fmt_)

    def set_name(self, name: str):
        """
        Set the name of the object.

        :param name: Name to set.
        :type name: str
        """
        self.name = name

    def get_name(self) -> str:
        """
        Get the name of the object.

        :return: Name of the object.
        :rtype: str
        """
        return self.name

    def get_full_name(self) -> str:
        """
        Get the full hierarchical name of the component.

        :return: Full name of the component.
        :rtype: str
        """
        if self._parent_ is not None:
            return self._parent_.get_full_name() + "." + self.name
        else:
            return self.name

    def set_parent(self, parent: Object|None) -> None:
        """
        Set the parent of the component.

        :param parent: Parent component.
        :type parent: Object, optional
        """
        self._parent_ = parent

    def get_parent(self) -> Object|None:
        """
        Get the parent of the component.

        :return: Parent component.
        :rtype: Object, optional
        """
        return self._parent_

    def set_field_attributes(self, name: str, fmt: Callable[..., str] = str, compare: bool = True) -> None:
        """
        Set attributes for a field.

        :param name: Field name.
        :type name: str
        :param fmt: Format of the field.
        :type fmt: type
        :param compare: Whether to compare the field.
        :type compare: bool
        """
        self._field_attributes_[name] = {"fmt": fmt, "compare": compare}

    def get_field_attributes(self, name: str) -> dict[str, Any]:
        """
        Get attributes for a field.

        :param name: Field name.
        :type name: str
        :return: Field attributes.
        :rtype: tuple
        """
        return self._field_attributes_[name]

    def remove_field_attributes(self, name: str) -> None:
        """
        Remove attributes for a field.

        :param name: Field name.
        :type name: str
        """
        del self._field_attributes_[name]

    def set_table_fmt(self, fmt: str|None = None, transpose : bool|None = None, recurse : bool|None = None) -> None:
        """
        Set the table format for string representation.

        :param fmt: Table format.
        :type fmt: str
        :param transpose: Whether to transpose the table.
        :type transpose: bool
        :param recurse: Whether to recurse into Object fields.
        :type recurse: bool
        """
        if fmt is not None:
            self._table_fmt_ = fmt
        if transpose is not None:
            self._table_transpose_ = transpose
        if recurse is not None:
            self._table_recurse_ = recurse

    def debug(self, msg: str, group: str|None = None) -> None:
        """
        Logs a debug message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.debug(msg, group)

    def info(self, msg: str, group: str|None = None) -> None:
        """
        Logs an info message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.info(msg, group)

    def warn(self, msg: str, group: str|None = None) -> None:
        """
        Logs a warning message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.warn(msg, group)

    def warning(self, msg: str, group: str|None = None) -> None:
        """
        Logs a warning message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.warning(msg, group)

    def error(self, msg: str, group: str|None = None) -> None:
        """
        Logs an error message.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.error(msg, group)

    def critical(self, msg: str, group: str|None = None) -> None:
        """
        Logs a critical message.
        Instantly stops the simulation by raising a SimFailure exception.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.critical(msg, group)

    def fatal(self, msg: str, group: str|None = None) -> None:
        """
        Logs a fatal message and raises a SimFailure exception.
        Instantly stops the simulation by raising a SimFailure exception.

        :param msg: Message to be logged.
        :type msg: str
        :param group: Group to which the message belongs.
        :type group: str
        """
        if group is None:
            group = self.get_full_name()
        Log.fatal(msg, group)

    def compare(self, rhs: Object, verbose: bool = False, bidirectional: bool = True) -> bool:
        """
        Compare this object with another Object.

        :param rhs: Object to compare with.
        :type rhs: Object
        :param verbose: Whether to print comparison details.
        :type verbose: bool
        :param bidirectional: Whether to perform bidirectional comparison.
        :type bidirectional: bool
        :return: 1 if comparison passed, 0 otherwise.
        :rtype: int
        """
        retVal = True

        for k, v in self.__dict__.items():
            if callable(v):
                continue

            if k.startswith("_"):
                continue

            if k in self._field_attributes_:
                if not self._field_attributes_[k]["compare"]:
                    continue

            if k not in rhs.__dict__:
                self.error(f'Field "{k}" not found in rhs')
                retVal = False

            if hasattr(v, "compare") and callable(v.compare):
                if not v.compare(rhs.__dict__[k]):
                    self.error(f'Field "{k}" comparison failed ({v} != {rhs.__dict__[k]})')
                    retVal = False
                elif verbose:
                    self.info(f'Field "{k}" comparison passed ({v} == {rhs.__dict__[k]})')
            else:
                if v != rhs.__dict__[k]:
                    self.error(f'Field "{k}" comparison failed ({v} != {rhs.__dict__[k]})')
                    retVal = False
                elif verbose:
                    self.info(f'Field "{k}" comparison passed ({v} == {rhs.__dict__[k]})')

        if bidirectional:
            rhs.compare(self, verbose, False)

        return retVal

    def add_constraint(
        self, name: str, constraint: BoolRef, *args: Any, hard: bool = True, target: dict|None = None
    ) -> None:
        """
        Add a constraint to the object.

        :param name: Name of the constraint.
        :type name: str
        :param constraint: The constraint function to add.
        :type constraint: z3.constraint
        :param args: Additional arguments for the constraint.
        :type args: list
        :param hard: Whether the constraint is hard (default: True).
        :type hard: bool
        :param target: Optional target dictionary to store the constraint.
        :type target: dict, optional
        """
        # Add the constraint
        if target is None:
            if name in self._constraints_[hard]:
                warnings.warn(f"Overriding existing constraint : {name}",
                              UserWarning,
                              stacklevel=2)

            self._constraints_[hard][name] = (constraint, [*args])
        else:
            if name in target[hard]:
                warnings.warn(f"Overriding existing constraint : {name}",
                              UserWarning,
                              stacklevel=2)

            target[hard][name] = (constraint, [*args])

    def remove_constraint(self, name: str) -> None:
        """
        Remove a constraint from the object.

        :param constraint: The constraint function to remove.
        :type constraint: function
        """
        for t in [True, False]:
            if name in self._constraints_[t]:
                del self._constraints_[t][name]

    # Randomizations of one constraint shape before the free bit analysis is worth
    # the solve it costs. An object randomized once - a sequence item, typically -
    # never pays for it; a loop that keeps building the same item pays once.
    _FREE_BITS_AFTER_ = 4

    # Randomizations spent measuring which of a variable's soft clauses the
    # constraints actually grant, before its clause plan is frozen. Measuring costs
    # one shift and compare per clause, and only over this many solves.
    _CALIBRATE_FOR_ = 16

    # How much of the gap between a variable's budget and the number of clauses
    # the last solve granted it each measurement closes.
    _CALIBRATE_RATE_ = 0.5

    # How often a free bit's clause must be granted for it to count as reliable
    # rather than contested. A bit no other constraint reaches is granted every time.
    # A bit whose value another variable decides is granted only when the random draw
    # happens to agree with that variable, which for a single bit is about half the
    # time. The two are far apart, so this sits between them, near the top.
    _ALWAYS_GRANTED_ = 0.95

    # Constraint shape -> the analysis of it. Shared by every object, because the
    # answer depends on the constraint expressions and the z3 variables they are
    # built over, both of which are now shared between objects of the same shape.
    # The asserted expressions are held alongside the result to keep their ASTs
    # alive, so z3 cannot recycle an AST id underneath a key.
    _free_bits_cache_: dict = {}

    def _free_bits_(self, hard : list, soft : list,
                    constrained_vars : dict) -> tuple[dict[int, list[int]], dict]:
        """
        The bits of each variable that the hard constraints leave a choice about.

        Randomization asks every bit, softly, to match a random draw. A bit the
        constraints pin to one value can never be traded against anything - its
        clause is either always satisfied or always violated - so dropping it
        moves every candidate solution's cost by the same amount and leaves the
        distribution exactly as it was. What it does change is how much the MaxSMT
        search has to carry: constraints that bound a 32 bit field to a few
        thousand pin two thirds of its bits.

        Only the hard constraints decide which bits are free. The soft ones are
        taken for the cache key alone, because the entry also carries the clause
        plan - and that does depend on them, since a soft constraint competes with
        the randomization clauses for the same objective. Keying on both keeps one
        shape's plan away from another that merely shares its hard constraints.

        :param hard: The hard constraints in force, as z3 expressions.
        :type hard: list
        :param soft: The soft constraints in force, as z3 expressions. Part of the
            cache key, not of the analysis.
        :type soft: list
        :param constrained_vars: The variables taking part in the solve.
        :type constrained_vars: dict
        :return: Free bits per pooled z3 variable, and the cache entry for this
            constraint shape - which also carries the clause budget, see
            _clause_plan_. A variable absent from the free bits should be
            randomized in full.
        :rtype: tuple[dict[int, list[int]], dict]
        """
        # Identity of the constraint shape. z3 hash conses, so rebuilding the same
        # expression over the same variables yields the same AST and the same id -
        # but only while that AST is alive, and an id is reused once it is not. So
        # both maps below hold on to the expressions they were keyed by. Without
        # that the ids churn from one randomization to the next, and worse, a
        # recycled id could match a key it has nothing to do with.
        #
        # The ids are only shared between objects at all because the z3 variables
        # are pooled - see Var._pooled_z3_.
        key = (tuple(sorted(e.get_id() for e in hard)),
               tuple(sorted(e.get_id() for e in soft)),
               tuple(sorted(v._rand_.get_id() for v in constrained_vars.values())))

        entry = Object._free_bits_cache_.get(key)
        if entry is None:
            # First sighting: keep the expressions, so that the next randomization
            # of this shape rebuilds them onto the same ASTs and lands on this key.
            # Both lists are held, since both were keyed on.
            entry = Object._free_bits_cache_[key] = {"count": 1, "exprs": (hard, soft),
                                                     "free": None, "plan": None,
                                                     "calib": None}
            return {}, entry

        if entry["free"] is not None:
            return entry["free"], entry

        entry["count"] += 1
        if entry["count"] <= self._FREE_BITS_AFTER_:
            return {}, entry

        # Name every bit with a boolean and ask z3 which of them its constraints
        # force. One solve for the lot - asking bit by bit is an order of magnitude
        # more expensive.
        solver = Solver()
        solver.add(hard)

        names = {}
        for v in constrained_vars.values():
            width = getattr(v, "width", None)
            if width is None or not isinstance(v._rand_, BitVecRef):
                continue
            for b in range(width):
                name = f"fb_{v._rand_}_{b}"
                names[name] = (v._rand_.get_id(), b)
                solver.add(Bool(name) == (Extract(b, b, v._rand_) == 1))

        free = {}
        if names:
            result, consequences = solver.consequences([], [Bool(n) for n in names])
            if result == sat:
                pinned = set()
                for implication in consequences:
                    literal = implication.arg(1)
                    if literal.decl().name() == "not":
                        literal = literal.arg(0)
                    pinned.add(str(literal))

                for name, (rand_id, b) in names.items():
                    if name not in pinned:
                        free.setdefault(rand_id, []).append(b)

                # A variable pinned outright has no entry above, which would
                # otherwise read as "randomize every bit".
                for v in constrained_vars.values():
                    if hasattr(v, "width") and isinstance(v._rand_, BitVecRef):
                        free.setdefault(v._rand_.get_id(), [])

        entry["free"] = free
        return free, entry

    def _clause_plan_(self, entry : dict, free_bits : dict) -> dict[int, tuple]:
        """
        Which bits of each variable are worth a randomization clause.

        The free bit analysis drops the bits the constraints pin to a constant - the
        bits with no choice at all. What it cannot see is that the bits it leaves may
        still not be free to combine: constraints routinely allow far fewer
        combinations of them than their count suggests. Twelve free bits span 4096
        combinations, so on a field the constraints hold to a few hundred legal
        values, the combination a clause per free bit describes is usually not one
        of the legal ones.

        This is a matter of degree rather than kind, and it is not settled by how
        many variables a constraint mentions. A single variable range leaves it mild
        - 1000 <= a <= 2000 forbids about half the combinations of the eleven bits it
        leaves unpinned. Constraints that tie variables to each other make it severe:
        a field built bitwise out of two others has no freedom left at all once they
        are chosen, however few of its bits are pinned outright.

        The surplus is not merely wasted. Asking for a combination that is not legal
        means some of those clauses have to be given up, and core guided MaxSMT gives
        them up a core at a time: it finds a set of soft clauses that cannot all hold
        alongside the hard constraints, relaxes it, and solves again. So the search
        runs a round per core, and the number of rounds grows with how many clauses
        must be given up in total - which is the bulk of the cost of a randomization.
        Clauses that can all be satisfied together take part in no core, so removing
        them would save nothing. Only the contested bits are worth rationing.

        Which bits those are is not worth deriving up front - it is a property of
        the whole constraint system - but it is cheap to observe, because the
        solution to compare against is already in hand once the solve is done. So
        over the first few randomizations of a constraint shape each bit is asked
        about and its answer noted, and the plan below is then frozen. Steady state
        pays nothing to maintain it.

        The plan per variable is (reliable, contested, k): the free bits granted so
        reliably that they are always asked about, the free bits that are not, and
        how many of the latter to draw each time. Both are drawn from the free bits,
        so neither is pinned - "pinned" stays reserved for a bit the hard constraints
        force to one value, which the free bit analysis has already removed.

        A variable ends up with an empty contested list, and so is asked about
        exactly as it was before, when there is nothing worth rationing: either every
        bit is reliable, or the budget covers the contested ones anyway. Single
        variable constraints tend to land there - the range above does, its contested
        bits being too few to be worth rationing - but nothing guarantees it. What
        decides is the measurement, not the shape of the constraints.

        A plan describes a solve of the object's own constraints and nothing else.
        The cache key does not cover constraints passed to randomize(), and a plan
        cannot be carried across them the way the pinned bits can, so randomize()
        only reaches for a plan - or teaches one - when it was called without them.
        See the comment at the call site.

        :param entry: Cache entry for this constraint shape, from _free_bits_.
        :type entry: dict
        :param free_bits: Free bits per pooled z3 variable.
        :type free_bits: dict
        :return: (reliable, contested, k) per pooled z3 variable.
        :rtype: dict[int, tuple]
        """
        plan = entry["plan"]
        if plan is None:
            # Ask about everything while measuring, so every bit gets an answer,
            # and so a shape that is never measured behaves as it did before.
            plan = entry["plan"] = {i: (b, (), 0) for i, b in free_bits.items()}
            entry["calib"] = {i: {"budget": float(len(b)), "n": 0, "free": b,
                                  "grant": dict.fromkeys(b, 0),
                                  "asked": dict.fromkeys(b, 0)}
                              for i, b in free_bits.items()}
        return plan

    def _settle_plan_(self, entry : dict, record : list, values : dict) -> None:
        """
        Fold what the solver granted back into each variable's clause plan.

        :param entry: Cache entry for this constraint shape, from _free_bits_.
        :type entry: dict
        :param record: (variable, pooled z3 id, clauses asked for) per variable.
        :type record: list
        :param values: The solved values, keyed by Var index.
        :type values: dict
        """
        calib = entry["calib"]

        settled = True
        for var, rand_id, asked in record:
            value = values.get(var._idx_)
            state = calib.get(rand_id)
            if state is None or not asked or not isinstance(value, int):
                continue

            grant, asked_count = state["grant"], state["asked"]
            granted = 0
            for b, want in asked:
                asked_count[b] += 1
                if ((value >> b) & 1) == want:
                    grant[b] += 1
                    granted += 1

            # Aim one clause above what was granted rather than at it, so a budget
            # that has been cut too far can still climb back.
            state["n"] += 1
            state["budget"] += self._CALIBRATE_RATE_ * (
                min(len(state["free"]), granted + 1) - state["budget"])

            # Applied while still measuring as well as after, so that what is
            # granted is measured under the plan it is being used to choose. Left
            # to converge against the full set of bits it would settle high, on a
            # count only the full set can grant.
            entry["plan"][rand_id] = self._settled_plan_(state)

            if state["n"] < self._CALIBRATE_FOR_:
                settled = False

        if settled:
            entry["calib"] = None

    def _settled_plan_(self, state : dict) -> tuple:
        """
        Turn a variable's measurements into the plan described by _clause_plan_.

        :param state: Calibration state for one variable.
        :type state: dict
        :return: (reliable, contested, k).
        :rtype: tuple
        """
        free, grant, asked = state["free"], state["grant"], state["asked"]
        reliable, contested = [], []
        for b in free:
            # A bit not asked about yet has said nothing, so it counts as contested
            # until it has.
            granted_always = asked[b] and grant[b] >= asked[b] * self._ALWAYS_GRANTED_
            (reliable if granted_always else contested).append(b)

        # The reliable bits are already covered, so the budget only has to stretch
        # over the rest. At least one, so a variable is never left unspread.
        k = max(1, round(state["budget"]) - len(reliable))
        if k >= len(contested):
            # Nothing to ration - ask about every free bit, as before.
            return (free, (), 0)
        return (reliable, contested, k)

    def pre_randomize(self) -> None:
        """
        Pre-randomization function.
        """
        pass

    def post_randomize(self) -> None:
        """
        Post-randomization function.
        """
        pass

    def randomize(self, hard: list[BoolRef]|None = None, soft: list[BoolRef]|None = None) -> None:
        """
        This method randomizes the value of the variable by considering hard and soft constraints.
        It uses an optimization solver to find a suitable value that satisfies the constraints.

        :param hard: Optional list of hard constraints to be added. Each constraint is a tuple where the first element is the constraint expression and the second element is the constraint value.
        :type hard: list, optional
        :param soft: Optional list of soft constraints to be added. Each constraint is a tuple where the first element is the constraint expression and the second element is the constraint value.
        :type soft: list, optional

        Hard and soft constraints follow the SV naming convention.
        Hard constraints must be satisfied, otherwise an error is raised.
        Soft constraints will attempt to be satisfied, but if not, the solver will
        return a solution that minimizes the number of unsatisfied constraints.

        :raises ValueError: If an unknown variable is encountered in the model.
        :raises Exception: If the solver fails to randomize the variable.
        """
        def resolve_arg(a : Any) -> Any:
            nonlocal var_ids, constrained_vars

            if not isinstance(a, Var):
                return a
            elif not a._auto_random_ or a._idx_ not in var_ids:
                return a.value
            else:
                constrained_vars[a._idx_] = a
                return a._rand_

        def new_solver() -> Optimize:
            nonlocal vars, constrained_vars

            solver = Optimize()

            def is_solver_var(a : Any) -> bool:
                return isinstance(a, Var) and a._auto_random_ and a._idx_ in var_ids

            def add_soft(expr : BoolRef) -> None:
                # Kept as well as asserted: a soft constraint competes with the
                # randomization clauses for the same objective, so it belongs in the
                # constraint shape that the clause plan is cached against. It is not
                # part of the free bit analysis, which only asks what is legal.
                static_soft.append(expr)
                solver.add_soft(expr, weight=100)

            # Apply class wide constraints
            for truth_value, add_fn in [(True, solver.add), (False, add_soft)]:
                for fn, args in self._constraints_[truth_value].values():
                    # Skip: no solver var → constraint may collapse to Python False → UNSAT.
                    if not any(is_solver_var(a) for a in args):
                        continue
                    _args = [resolve_arg(a) for a in args]
                    add_fn(fn(*_args))

            # Find constraints local to variables. A variable that was never
            # constrained carries None rather than a pair of empty dictionaries -
            # see Var's class attributes.
            for v in vars:
                if v._constraints_ is not None and any(v._constraints_.values()):
                    constrained_vars[v._idx_] = v

            # Apply constraints local to variables
            for v in constrained_vars.values():
                v._apply_constraints_(solver)

            return solver

        def cast(solver):
            cast_values = {}
            if solver.check() == sat:
                model = solver.model()

                # A pooled z3 name no longer identifies the variable it belongs
                # to, so read the values off the variables of this solve rather
                # than off the model's declarations. Anything the solver never saw
                # is left out, and drawn directly below instead.
                declared = {d.name() for d in model.decls()}
                for v in constrained_vars.values():
                    if str(v._rand_) not in declared:
                        continue

                    val = model.eval(v._rand_, model_completion=True)

                    if is_fp(val):
                        bv = model.eval(fpToIEEEBV(val))
                        cast_values[v._idx_] = bv
                    elif isinstance(val, IntNumRef| BitVecNumRef):
                        cast_values[v._idx_] = val.as_long()
                    else:
                        cast_values[v._idx_] = val
            else:
                msg = "Failed to randomize\n"
                if os.environ.get("AVL_CONSTRAINT_DEBUG") is not None:
                    s = Solver()
                    assertions = list(solver.assertions())
                    trackers = [Bool(f"p{i}") for i in range(len(assertions))]

                    for t, c in zip(trackers, assertions, strict=True):
                        s.assert_and_track(c, t)

                    if s.check() != sat:
                        core = s.unsat_core()
                        by_name = {str(x._rand_): x for x in constrained_vars.values()}
                        for t in core:
                            idx = int(str(t)[1:])
                            constraint = assertions[idx]
                            vars_in_constraint = z3util.get_vars(constraint)

                            msg += f"\tCONFLICTING CONSTRAINT: {constraint}\n"
                            for v in vars_in_constraint:
                                var = by_name.get(str(v))
                                if var is None:
                                    continue
                                msg += (f"\t\tVariable {v} == {var._varname_} "
                                        f"({var._file_}:{var._line_})\n")
                raise Exception(msg)

            return cast_values

        # User defined pre-randomization function
        self.pre_randomize()

        # Collect all Var objects in randomization
        memo = {}
        conversion = {}
        vars = []
        constrained_vars = {} # Dict to avoid multiple matching entries

        for key, value in self.__dict__.items():
            if key != "_constraints_":
                _var_finder_(value, memo, conversion)

        for v in conversion.values():
            if v._auto_random_:
                # Give the variable its index in Var._lookup_. A variable is not
                # given one when it is built, because a solve is the only thing
                # that reads it - see Var._register_. The values below are keyed
                # by it, so it has to exist before the solve, and the variable it
                # names is this one: the finder above was asked for the variables
                # themselves rather than copies of them.
                v._register_()
                vars.append(v)

                # Create the random / z3 variable
                # Done only when randomization is called to speed up non-randomized object creation
                #
                # The name comes from the variable's position in this solve, so
                # that the next object of the same shape gets the same z3
                # variables and can reuse everything built from them.
                #
                # Assigned every time rather than once per Var, because the same
                # Var can appear in more than one randomization - shared between
                # two objects, or randomized on its own as well - and at a
                # different position each time. Keeping a stale name would alias
                # it onto whichever field now holds that position.
                v._rand_ = v._z3_(v._z3_name_(len(vars) - 1))

        var_ids = [v._idx_ for v in vars]

        # Create Solver. The soft constraints are collected as they are asserted,
        # because Optimize.assertions() reports only the hard ones.
        static_soft = []
        solver = new_solver()

        # The soft constraints local to the variables, which _apply_constraints_
        # asserted without reporting back. Rebuilding them here lands on the same
        # ASTs - z3 hash conses - so they identify the shape just as well. Empty for
        # anything without variable local soft constraints, which is the usual case.
        static_soft += [c(v._rand_)
                        for v in constrained_vars.values()
                        if v._constraints_ is not None
                        for c in v._constraints_[False].values()]

        # The hard constraints of this object alone, before anything dynamic is
        # added. Working the free bits out from these keeps the answer cacheable,
        # and stays correct when a dynamic constraint narrows things further: that
        # can only pin more bits, and a clause on an already pinned bit is merely
        # the wasted effort this removes, never a wrong answer.
        static_hard = list(solver.assertions())

        # Add dynamic constraints
        if hard is not None:
            for c in hard:
                fn, *args = c
                _args = [resolve_arg(a) for a in args]
                solver.add(fn(*_args))

        if soft is not None:
            for c in soft:
                fn, *args = c
                _args = [resolve_arg(a) for a in args]
                solver.add_soft(fn(*_args), weight=1000)

        # Spread the variables taking part in the solve. Everything else is drawn
        # directly, below.
        free_bits, entry = self._free_bits_(static_hard, static_soft, constrained_vars)

        # Which bits each variable is worth a clause on, and - while that is still
        # being measured - somewhere to note what was asked for. There is nothing
        # to plan until the free bits are known.
        #
        # Dynamic constraints are left out of this entirely. They are absent from
        # the cache key, so a plan cannot tell one set of them from another or from
        # none at all - and unlike the pinned bit analysis above, a plan cannot be
        # carried across regardless. Pinning a bit only ever removes a clause whose
        # effect was constant; declining to ask about a contested bit changes which
        # solutions are optimal, so a plan measured under a dynamic constraint
        # describes a different solve to one without it. Such a solve therefore
        # neither uses a plan nor teaches one, and asks about every free bit exactly
        # as it did before plans existed.
        static_only = not hard and not soft
        plan = self._clause_plan_(entry, free_bits) if free_bits and static_only else None
        record = [] if plan is not None and entry["calib"] is not None else None

        for v in constrained_vars.values():
            rand_id = v._rand_.get_id()
            bits = free_bits.get(rand_id)

            if plan is not None:
                chosen = plan.get(rand_id)
                if chosen is not None:
                    reliable, contested, k = chosen
                    # The common case is nothing to ration, and then the plan is
                    # the free bits themselves - no list built per randomization.
                    bits = (reliable if not contested
                            else reliable + random.sample(contested, k))

            if record is None:
                v._apply_randomization_(solver, bits)
            else:
                asked = []
                v._apply_randomization_(solver, bits, asked)
                record.append((v, rand_id, asked))

        # Add randomization and solve
        solver.push()
        values = cast(solver)
        solver.pop()

        # Assign values to Var objects - only for those within this class. The
        # variables are already in hand, so they are taken from there rather than
        # looked up by index in Var._lookup_, which would return these same ones.
        for var in vars:
            if var._idx_ in values:
                var.value = values[var._idx_]
            else:
                var.value = var._random_value_()

        # Settle the clause budget against what this solve granted.
        if record is not None:
            self._settle_plan_(entry, record, values)

        # User defined post-randomization function
        self.post_randomize()

__all__ = ["Object"]
