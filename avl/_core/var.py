# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Base Class

from __future__ import annotations

import inspect
import os
import warnings
import weakref
from collections.abc import Callable
from typing import Any

from z3 import FP, BitVecNumRef, Bool, BoolRef, IntNumRef, Optimize, Solver, fpToIEEEBV, is_fp, sat, z3util

# Resolved from the partially initialised package - urandom_range is defined at
# the top of _core/__init__.py, above the import that pulls this module in.
from . import urandom_range


class Var:
    _deprecated_name_warning_ = True
    _count_ = 0
    _lookup_ = weakref.WeakValueDictionary()
    _AVL_CONSTRAINT_DEBUG_ = os.environ.get("AVL_CONSTRAINT_DEBUG") is not None

    # Defaults that an instance does not store for itself. A testbench builds a
    # fresh item per transaction, and an item is a field object per field, so
    # anything stored here rather than in __init__ is one store fewer per field
    # per transaction - which is most of what building an item costs. See
    # benchmarks/create_and_send. Each reads through the class until something
    # gives the instance its own:
    #
    #   _constraints_   created by add_constraint, on the fields that get one
    #   _idx_           assigned by _register_, when a solve first needs it
    #   _rand_          assigned per randomization
    #   _file_ etc.     only recorded under AVL_CONSTRAINT_DEBUG
    #   width, _mask_   set by __init__ where a width was given, and otherwise
    #                   the fixed width of the class - see Logic
    _constraints_ = None
    _rand_ = None
    _idx_ = -1
    _file_ = None
    _line_ = None
    _varname_ = None
    name = "**deprecated**"

    # The format applied when a variable is given none. Per class, because Logic
    # prints as hex where everything else prints as str.
    _fmt_default_ = str

    # z3 variables are pooled by their sort and their position in the solve,
    # rather than created one per Var instance. A testbench builds a fresh item
    # per transaction, so anything derived from a per instance z3 variable - the
    # constraint expressions, the per bit randomization clauses, the analysis of
    # which bits the constraints pin - would have to be rebuilt for every single
    # randomization. Pooling makes all of it reusable by the next object of the
    # same shape.
    #
    # Two objects sharing a z3 variable is safe because a randomization builds
    # its own solver and solves alone; two of them are never in the same one.
    _z3_pool_: dict[str, Any] = {}

    @staticmethod
    def _pooled_z3_(name: str, factory: Callable[[], Any]) -> Any:
        """The pooled z3 variable of this name, created on first use.

        :param name: Pooled name - see _z3_name_.
        :type name: str
        :param factory: Builds the variable if the pool does not hold it yet.
        :type factory: Callable
        :return: The z3 variable.
        :rtype: Any
        """
        variable = Var._z3_pool_.get(name)
        if variable is None:
            variable = factory()
            Var._z3_pool_[name] = variable
        return variable

    def _register_(self) -> int:
        """
        Give this variable its index in Var._lookup_, if it has not got one.

        Only a randomization reads _idx_ and _lookup_, and only for the variables
        taking part in the solve, so an index is handed out on first use rather
        than to every variable that is ever built. Idempotent, so a variable
        randomized repeatedly keeps the index it was given.

        :return: The index of this variable.
        :rtype: int
        """
        if self._idx_ < 0:
            Var._lookup_[Var._count_] = self
            self._idx_ = Var._count_
            Var._count_ += 1
        return self._idx_

    def __copy__(self) -> Var:
        """
        Copy the Var - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = self.__class__(self.value, auto_random=self._auto_random_, fmt=self._fmt_)
        new_obj._constraints_ = self._copied_constraints_()
        return  new_obj

    def _copied_constraints_(self) -> dict|None:
        """
        This variable's constraints, for a copy of it to take over.

        None where the variable has none, which is what a variable that was never
        constrained carries - see the class attributes above.

        :return: A copy of the constraints, or None.
        :rtype: dict, optional
        """
        if self._constraints_ is None:
            return None
        return {k: v.copy() for k, v in self._constraints_.items()}

    def __deepcopy__(self, memo) -> Var:
        """
        Deep copy the Var - always make a copy to ensure randomness is preserved.

        :param memo: Dictionary to keep track of already copied objects.
        :type memo: dict
        :return: Deep copied Var.
        :rtype: Var
        """
        new_obj = self.__copy__()
        memo[id(self)] = new_obj
        return new_obj

    def _extract_varname_(self, code_context):
        """Parse 'my_var = Var(42)' to extract 'my_var'."""
        if code_context:
            line = code_context[0].strip()
            if '=' in line:
                return line.split('=')[0].strip()
        return None

    def _extract_caller_frame_(self):
        """Walk up the stack past any __init__ frames to find the real caller."""
        for frame_info in inspect.stack():
            # Skip frames that are __init__ methods (including super().__init__)
            if frame_info.function == '__init__':
                continue
            # Skip frames from this file (internal)
            if frame_info.filename == __file__:
                continue
            return frame_info
        return None

    def __init__(self, *args, auto_random: bool = True, fmt: Callable[..., str]|None = None,
                 width: int|None = None) -> None:
        """
        Initialize an instance of the class.

        This is the only __init__ in the hierarchy for every fixed point type -
        Logic and the classes below it do not define one, because a constructor
        frame per level is a real cost when a testbench builds a field object per
        field per transaction. What such a class provides instead is class
        attributes: its width and mask where they are fixed, and its _fmt_default_.

        :param value: The value associated with the instance.
        :type value: Any
        :param auto_random: Flag to enable or disable automatic randomness. Defaults to True.
        :type auto_random: bool, optional
        :param fmt: Format of the variable. Defaults to the class's _fmt_default_.
        :type fmt: Callable, optional
        :param width: Width of the variable in bits, for the types that have one.
            Defaults to the width of the class.
        :type width: int, optional
        :raises ValueError: If a width is given and is not a positive integer.
        """

        if len(args) > 1 and self.__class__._deprecated_name_warning_:
            warnings.warn(
                "Passing 'name' as a positional argument is deprecated",
                DeprecationWarning,
                stacklevel=2
            )
            self.__class__._deprecated_name_warning_ = False
        assert len(args) == 1 or len(args) == 2, f"Unsupported number of args: {args}"

        # The width, and the mask derived from it, before the value - _cast_ needs
        # both. A class whose width is fixed carries the pair as class attributes
        # and nothing is stored here; the two must always agree, so they are only
        # ever set together.
        if width is not None:
            if not isinstance(width, int) or width <= 0:
                raise ValueError("Width must be a positive integer.")
            self.width = int(width)
            self._mask_ = (1 << width) - 1

        self._auto_random_ = auto_random
        self._fmt_ = self._fmt_default_ if fmt is None else fmt

        # Straight to _value_, rather than through the value property, which
        # would reach the same _cast_ by a longer route.
        self._value_ = self._cast_(args[-1])

        # Everything else - the lookup index, the constraints, the z3 variable and
        # the debug fields - is left to the class attributes until something needs
        # it. See the comment on them, and _register_.
        if Var._AVL_CONSTRAINT_DEBUG_:
            frame = self._extract_caller_frame_()
            if frame:
                self._file_ = frame.filename
                self._line_ = frame.lineno
                self._varname_ = self._extract_varname_(frame.code_context)

    @property
    def value(self):
        """
        Property to abstract the value and ensure it's always cast when assigned
        """
        return self._value_

    @value.setter
    def value(self, v):
        """
        Setter property to enforce wraps etc. when assigned directly

        :param v: The Value to assig
        :type v : Andy
        """
        self._value_ = self._cast_(v)

    def _cast_(self, other: Any) -> Any:
        """
        Cast the other value to the type of this variable's value.

        :param other: The value to cast.
        :type other: Any
        :return: The casted value.
        :rtype: Any
        """
        v = other.value if isinstance(other, type(self)) else other
        return type(self.value)(v)

    def _wrap_(self, result):
        """
        Wrap the result in an Var instance.

        :param result: The result to wrap.
        :type result: Any
        :return: An Var instance with the result.
        :rtype: Var
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

    def _range_(self) -> tuple[Any, Any]:
        """
        Get the range of the variable.

        :return: A tuple containing the minimum and maximum values of the variable.
        :rtype: tuple[Any, Any]
        """
        raise NotImplementedError("Var does not implement _range_ method. Please override in subclass.")

    def _z3_name_(self, ordinal: int) -> str:
        """
        The pooled name for a variable at this position in a solve.

        The name carries the variable's sort as well as its position, so that two
        variables of different sorts at the same position cannot share a pooled
        entry. The class name is distinct per sort for every type except Logic,
        which covers every width with one class and so overrides this.

        :param ordinal: Position of the variable within the randomization.
        :type ordinal: int
        :return: The name.
        :rtype: str
        """
        return f"v{ordinal}_{type(self).__name__}"

    def _z3_(self, name: str) -> BoolRef | IntNumRef | BitVecNumRef | FP:
        """
        Return the Z3 representation of the variable.

        :param name: Pooled name to give it - see _z3_name_.
        :type name: str
        :return: The Z3 representation of the variable.
        :rtype: BoolRef | IntNumRef | BitVecNumRef | RatNumRef
        """
        raise NotImplementedError("Var does not implement _z3_ method. Please override in subclass.")

    def _random_value_(self, bounds: tuple[int, int]|None = None) -> Any:
        """
        Get a random value for the variable within the specified bounds.

        :param bounds: Optional tuple containing the minimum and maximum bounds for the random value.
        :type bounds: tuple[int, int], optional
        :return: A random value within the specified bounds.
        :rtype: Any
        """
        if bounds is None:
            bounds = self._range_()
        return urandom_range(bounds[0], bounds[1])

    # Binary arithmetic
    def __add__(self, other): return self._wrap_(self._cast_(self.value + other))
    def __sub__(self, other): return self._wrap_(self._cast_(self.value - other))
    def __mul__(self, other): return self._wrap_(self._cast_(self.value * other))
    def __truediv__(self, other): return self._wrap_(self._cast_(self.value / other))
    def __floordiv__(self, other): return self._wrap_(self._cast_(self.value // other))
    def __mod__(self, other): return self._wrap_(self._cast_(self.value % other))
    def __pow__(self, other): return self._wrap_(self._cast_(self.value ** other))
    def __divmod__(self, other):
        a = self.value
        b = other.value if isinstance(other, Var) else other
        return tuple(self._wrap_(x) for x in divmod(a, b))

    def __iadd__(self, other):
        self.value = self._cast_(self.value + other)
        return self

    def __isub__(self, other):
        self.value = self._cast_(self.value - other)
        return self

    def __imul__(self, other):
        self.value = self._cast_(self.value * other)
        return self

    def __itruediv__(self, other):
        self.value = self._cast_(self.value / other)
        return self

    def __ifloordiv__(self, other):
        self.value = self._cast_(self.value // other)
        return self

    def __imod__(self, other):
        self.value = self._cast_(self.value % other)
        return self

    def __ipow__(self, other):
        self.value = self._cast_(self.value ** other)
        return self

    def __radd__(self, other): return self._wrap_(self._cast_(other + self.value))
    def __rsub__(self, other): return self._wrap_(self._cast_(other - self.value))
    def __rmul__(self, other): return self._wrap_(self._cast_(other * self.value))
    def __rtruediv__(self, other): return self._wrap_(self._cast_(other / self.value))
    def __rfloordiv__(self, other): return self._wrap_(self._cast_(other // self.value))
    def __rmod__(self, other): return self._wrap_(self._cast_(other % self.value))
    def __rpow__(self, other): return self._wrap_(self._cast_(other ** self.value))
    def __rdivmod__(self, other):
        a = other.value if isinstance(other, Var) else other
        b = self.value
        return tuple(self._wrap_(x) for x in divmod(a, b))

    # Bitwise
    def __and__(self, other): return self._wrap_(self._cast_(self.value & other))
    def __or__(self, other): return self._wrap_(self._cast_(self.value | other))
    def __xor__(self, other): return self._wrap_(self._cast_(self.value ^ other))
    def __lshift__(self, other): return self._wrap_(self._cast_(self.value << other))
    def __rshift__(self, other): return self._wrap_(self._cast_(self.value >> other))

    def __iand__(self, other):
        self.value = self._cast_(self.value & other)
        return self

    def __ior__(self, other):
        self.value = self._cast_(self.value | other)
        return self

    def __ixor__(self, other):
        self.value = self._cast_(self.value ^ other)
        return self

    def __ilshift__(self, other):
        self.value = self._cast_(self.value << other)
        return self

    def __irshift__(self, other):
        self.value = self._cast_(self.value >> other)
        return self

    def __rand__(self, other): return self._wrap_(self._cast_(other & self.value))
    def __ror__(self, other): return self._wrap_(self._cast_(other | self.value))
    def __rxor__(self, other): return self._wrap_(self._cast_(other ^ self.value))
    def __rlshift__(self, other): return self._wrap_(self._cast_(other << self.value))
    def __rrshift__(self, other): return self._wrap_(self._cast_(other >> self.value))

    # Unary
    def __neg__(self): return self._wrap_(-self.value)
    def __pos__(self): return self._wrap_(+self.value)
    def __abs__(self): return self._wrap_(abs(self.value))
    def __invert__(self): return self._wrap_(~self.value)

    # Comparison
    def __eq__(self, other): return self.value == other
    def __ne__(self, other): return not self.__eq__(other)
    def __lt__(self, other): return self.value < other
    def __le__(self, other): return self.__lt__(other) or self.__eq__(other)
    def __gt__(self, other): return not self.__le__(other)
    def __ge__(self, other): return not self.__lt__(other)

    # Conversion
    def __int__(self): return int(self.value)
    def __float__(self): return float(self.value)
    def __index__(self): return int(self.value)
    def __bool__(self): return bool(self.value)

    # String / representation
    def __repr__(self): return self._fmt_(self.value)
    def __str__(self): return self._fmt_(self.value)

    def __format__(self, format_spec):
        # Delegate formatting to the underlying int value
        return format(self.value, format_spec)

    # Hashing
    def __hash__(self): return hash(self.value)

    def get_min(self) -> int:
        """
        Get the minimum value that can be represented by this variable.

        :return: The minimum value based on the sign and width of the variable.
        :rtype: int
        """
        return self._range_()[0]

    def get_max(self) -> int:
        """
        Get the maximum value that can be represented by this variable.

        :return: The maximum value.
        :rtype: int
        """
        return self._range_()[1]

    def add_constraint(
        self, name: str, constraint: BoolRef, hard: bool = True, target: dict|None = None
    ):
        """
        Add a constraint to the object.

        :param name: The name of the constraint.
        :type name: str
        :param constraint: The constraint function to add.
        :type constraint: function
        :param hard: Flag to indicate if the constraint is hard or soft. Defaults to True.
        :type hard: bool, optional
        :param target: The target dictionary to store the constraint. Defaults to None.
        :type target: dict, optional
        """
        if not self._auto_random_:
            raise ValueError("Cannot add constraints to non-random variables")

        if target is None:
            # First constraint on this variable - see the class attributes.
            constraints = self._constraints_
            if constraints is None:
                constraints = self._constraints_ = {True : {}, False: {}}

            if name in constraints[hard]:
                warnings.warn(f"Overriding existing constraint : {name}",
                              UserWarning,
                              stacklevel=2)

            constraints[hard][name] = constraint
        else:
            if name in target:
                warnings.warn(f"Overriding existing constraint : {name}",
                              UserWarning,
                              stacklevel=2)

            target[name] = constraint

    def remove_constraint(self, name: str) -> None:
        """
        Remove a constraint from the object.

        :param name: The name of the constraint to remove.
        :type name: str
        """
        if not self._auto_random_:
            raise ValueError("Cannot remove constraints from non-random variables")

        if self._constraints_ is None:
            return

        if name in self._constraints_[True]:
            del self._constraints_[True][name]

        if name in self._constraints_[False]:
            del self._constraints_[False][name]

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

    def _apply_constraints_(self, solver : Optimize) -> None:
        """
        Apply the constraints to the solver.

        Randomization is applied separately, by _apply_randomization_, so that
        the hard constraints can be examined on their own first - see
        Object._free_bits_.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        """
        constraints = self._constraints_
        if constraints is None:
            return False

        for c in constraints[True].values():
            solver.add(c(self._rand_))

        for c in constraints[False].values():
            solver.add_soft(c(self._rand_), weight="100")

        return any(constraints.values())

    def _apply_randomization_(self, solver : Optimize, free_bits : list[int]|None = None,
                              record : list|None = None) -> None:
        """
        Add the soft constraints that spread this variable over its legal values.

        A type with no spreading of its own leaves the solver to return whichever
        legal value it finds first. The types that do it bit by bit - Logic and its
        subclasses, and Float - override this.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param free_bits: The bits to constrain, for the types that work bit by
            bit. None means every bit.
        :type free_bits: list[int], optional
        :param record: When given, the (bit, value) pairs asked for are appended to
            it, so the clause plan can be settled against what the solver grants.
        :type record: list, optional
        """
        pass

    def randomize(self, hard: list|None = None, soft: list|None = None) -> None:
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

        def new_solver():
            solver = Optimize()
            self._apply_constraints_(solver)
            self._apply_randomization_(solver)

            return solver

        def cast(solver, obj):
            if solver.check() == sat:
                model = solver.model()
                val = model.eval(obj.value() if hasattr(obj, "value") else obj, model_completion=True)
                if is_fp(val):
                    bv = model.eval(fpToIEEEBV(val))
                    cast_value = bv
                elif isinstance(val, (IntNumRef | BitVecNumRef)):
                    cast_value = val.as_long()
                else:
                    cast_value = val
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
                        for t in core:
                            idx = int(str(t)[1:])
                            constraint = assertions[idx]
                            vars_in_constraint = z3util.get_vars(constraint)

                            msg += f"\tCONFLICTING CONSTRAINT: {constraint}\n"
                            for v in vars_in_constraint:
                                msg += (f"\t\tVariable {v} == {self._varname_} "
                                        f"({self._file_}:{self._line_})\n")

                raise Exception(msg)
            return cast_value

        # Create rand / z3 variable. The only variable in this solve, so it takes
        # position 0 - reassigned each time, for the same reason as in
        # Object.randomize: it may have been given another position there.
        if self._auto_random_:
            self._rand_ = self._z3_(self._z3_name_(0))

        # User defined pre-randomization function
        self.pre_randomize()

        # Create a new solver
        solver = new_solver()

        if hard is not None:
            for c in hard:
                solver.add(c(self._rand_))
        if soft is not None:
            for c in soft:
                solver.add_soft(c(self._rand_), weight="1000")

        solver.push()

        # Assign value
        self.value = cast(solver, self._rand_)

        solver.pop()

        # User defined post-randomization function
        self.post_randomize()

__all__ = ["Var"]
