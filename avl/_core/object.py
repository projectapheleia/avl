# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Object Base Class

from __future__ import annotations

import copy
import os
import random
import warnings
from collections.abc import MutableMapping, MutableSequence, Set
from typing import TYPE_CHECKING, Any

import tabulate
from z3 import BitVecNumRef, BoolRef, BV2Int, IntNumRef, Optimize, RatNumRef, sat

from .factory import Factory
from .int import Int
from .log import Log
from .struct import Struct
from .var import Var

if TYPE_CHECKING:
    from .component import Component

from itertools import islice

# Batch size for constraint min / max calculations
# Too big and the constraints won't solve
# Too small and you get a performance drop
if "AVL_CONSTRAINT_BATCH_SIZE" in os.environ:
    CONSTRAINT_BATCH_SIZE = int(os.environ["AVL_CONSTRAINT_BATCH_SIZE"])
else:
    CONSTRAINT_BATCH_SIZE = None

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
        new_list = []
        memo[obj_id] = new_list
        new_list.extend(_var_finder_(item, memo, conversion, do_copy, do_deepcopy) for item in obj)
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

    else:
        if do_deepcopy:
            try:
                copied = copy.deepcopy(obj, memo)
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

class Object:

    # Logger - Make all logger functions available in class to simplify code
    # Class level to improve performance (slightly)
    debug = Log.debug
    info = Log.info
    warn = Log.warn
    warning = Log.warning
    error = Log.error
    critical = Log.critical
    fatal = Log.fatal

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

    def __new__(cls, *args: Any, **kwargs: Any) -> Object:
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

        name = args[0]
        parent = args[1]
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

    def __init__(self, name: str, parent: Component) -> None:
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
        self._frozen_constraints_ = False
        self._solver_ = None

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

    def set_name(self, name: str) -> str:
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

    def set_parent(self, parent="Component") -> None:
        """
        Set the parent of the component.

        :param parent: Parent component.
        :type parent: Component
        """
        self._parent_ = parent

    def get_parent(self) -> Component:
        """
        Get the parent of the component.

        :return: Parent component.
        :rtype: Component
        """
        return self._parent_

    def set_field_attributes(self, name: str, fmt: str = str, compare: bool = True) -> None:
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

    def set_table_fmt(self, fmt: str = None, transpose : bool = None, recurse : bool = None) -> None:
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
        self, name: str, constraint: BoolRef, *args: Any, hard: bool = True, target: dict = None
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

    def freeze_constraints(self) -> None:
        """
        Freeze the constraints of the object, preventing further modifications.
        This is useful to ensure that the constraints are not changed after they have been set.
        Freeze will take effect when next randomization is called.
        """
        self._frozen_constraints_ = True

    def unfreeze_constraints(self) -> None:
        """
        Unfreeze the constraints of the object, allowing modifications again.
        This is useful to allow changes to the constraints after they have been frozen.
        """
        self._frozen_constraints_ = False
        self._solver_ = None

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

    def randomize(self, hard: list[BoolRef] = None, soft: list[BoolRef] = None) -> None:
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
        def resolve_arg(a : Any, var_ids : list[int], constrained_vars : dict[int, Var]) -> Any:
            if not isinstance(a, Var):
                return a
            elif not a._auto_random_ or a._idx_ not in var_ids:
                return a.value
            else:
                constrained_vars[a._idx_] = a
                return a._rand_

        def new_solver(constraints : dict[bool, dict], vars : list [Var], var_ids : list[int], constrained_vars : dict[int, Var]) -> Optimize:
            solver = Optimize()

            for truth_value, add_fn in [(True, solver.add), (False, lambda expr: solver.add_soft(expr, weight=100))]:
                for fn, args in constraints[truth_value].values():
                    _args = [resolve_arg(a, var_ids, constrained_vars) for a in args]
                    add_fn(fn(*_args))

            for v in vars:
                if v._apply_constraints(solver):
                    constrained_vars[v._idx_] = v

            return solver

        def cast(solver):
            cast_values = {}
            if solver.check() == sat:
                model = solver.model()
                for var in model.decls():
                    v = Var._lookup_[int(var.name())]
                    val = model.eval(var(), model_completion=True)

                    if isinstance(val, RatNumRef):
                        cast_values[v._idx_] = v._cast_(val.as_decimal(20).rstrip("?"))
                    elif isinstance(val, IntNumRef| BitVecNumRef):
                        cast_values[v._idx_] = v._cast_(val.as_long())
                    else:
                        cast_values[v._idx_] = v._cast_(val)
            else:
                raise Exception("Failed to randomize")
            return cast_values

        def optimize(solver, fn, constrained_vars, values):
            def batched(iterable, n):
                it = iter(iterable)

                if n is None:
                    yield list(it)
                    return

                while True:
                    batch = list(islice(it, n))
                    if not batch:
                        break
                    yield batch

            for batch in batched(list(constrained_vars.values()), CONSTRAINT_BATCH_SIZE):
                solver.push()
                for v in batch:
                    if isinstance(v, Int):
                        fn(BV2Int(v._rand_, is_signed=True))
                    else:
                        fn(v._rand_)
                model = cast(solver)
                for k, val in model.items():
                    if k in constrained_vars:
                        values[k] = val
                solver.pop()

        # User defined pre-randomization function
        self.pre_randomize()

        if not self._frozen_constraints_ or self._solver_ is None or hard is not None or soft is not None:
            # Collect all Var objects in randomization
            memo = {}
            conversion = {}
            vars = []
            constrained_vars = {} # Dict to avoid multiple matching entries

            for key, value in self.__dict__.items():
                if key != "_constraints_":
                    _var_finder_(value, memo, conversion)
            for v in conversion.values():
                if Var._lookup_[v._idx_]._auto_random_:
                    vars.append(Var._lookup_[v._idx_])

                    # Create the random / z3 variable
                    # Done only when randomization is called to speed up non-randomized object creation
                    if v._rand_ is None:
                        v._rand_ = v._z3_()

            var_ids = [v._idx_ for v in vars]

            # Create Solver
            solver = new_solver(constraints=self._constraints_, vars=vars, var_ids=var_ids, constrained_vars=constrained_vars)

            # Add dynamic constraints
            if hard is not None:
                for c in hard:
                    fn, *args = c
                    _args = [resolve_arg(a, var_ids, constrained_vars) for a in args]
                    solver.add(fn(*_args))

            if soft is not None:
                for c in soft:
                    fn, *args = c
                    _args = [resolve_arg(a, var_ids, constrained_vars) for a in args]
                    solver.add_soft(fn(*_args), weight=1000)

            # Calculate min / max values of variables
            max_values = {v._idx_: v.get_max() for v in vars}
            optimize(solver=solver, fn=solver.maximize, constrained_vars=constrained_vars, values=max_values)

            min_values = {v._idx_: v.get_min() for v in vars}
            optimize(solver=solver, fn=solver.minimize, constrained_vars=constrained_vars, values=min_values)

        else:
            # Use existing solver and ranges
            solver = self._solver_
            min_values = self._min_values_
            max_values = self._max_values_
            vars = self._vars_
            var_ids = self._var_ids_

        # Add randomization and solve
        solver.push()
        for k,v in min_values.items():
            var = Var._lookup_[k]
            val = var._random_value_(bounds=(min(v, max_values[k]), max(v, max_values[k])))
            solver.add_soft(var._rand_ >= val, weight=100)
            solver.add_soft(var._rand_ <= val, weight=100)

            if random.choice([True, False]):
                solver.add_soft(var._rand_ != var.value, weight=100)

        values = cast(solver)
        solver.pop()

        # Assign values to Var objects - only for those within this class
        for k, v in values.items():
            var = Var._lookup_[k]
            if var in vars:
                var.value = v

        # Save the solver and min/max values for future use
        if self._frozen_constraints_ and self._solver_ is None and hard is None and soft is None:
            self._solver_ = solver
            self._min_values_ = min_values
            self._max_values_ = max_values
            self._vars_ = vars
            self._var_ids_ = var_ids

        # User defined post-randomization function
        self.post_randomize()

__all__ = ["Object"]
