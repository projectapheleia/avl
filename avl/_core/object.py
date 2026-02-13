# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Object Base Class

from __future__ import annotations

import copy
import warnings
from collections.abc import MutableMapping, MutableSequence, Set
from typing import TYPE_CHECKING, Any, TypeVar

import tabulate
from z3 import BitVecNumRef, BoolRef, IntNumRef, Optimize, fpToIEEEBV, is_fp, sat

from .factory import Factory
from .log import Log
from .struct import Struct
from .var import Var

if TYPE_CHECKING:
    from .component import Component

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

    def debug(self, msg: str, group: str = None) -> None:
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

    def info(self, msg: str, group: str = None) -> None:
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

    def warn(self, msg: str, group: str = None) -> None:
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

    def warning(self, msg: str, group: str = None) -> None:
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

    def error(self, msg: str, group: str = None) -> None:
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

    def critical(self, msg: str, group: str = None) -> None:
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

    def fatal(self, msg: str, group: str = None) -> None:
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

            # Apply class wide constraints
            for truth_value, add_fn in [(True, solver.add),
                                        (False, lambda expr: solver.add_soft(expr, weight=100))]:
                for fn, args in self._constraints_[truth_value].values():
                    _args = [resolve_arg(a) for a in args]
                    add_fn(fn(*_args))

            # Find constraints local to variables
            for v in vars:
                if any(v._constraints_.values()):
                    constrained_vars[v._idx_] = v

            # Apply constraints local to variables
            for v in constrained_vars.values():
                v._apply_constraints_(solver)

            return solver

        def cast(solver):
            cast_values = {}
            if solver.check() == sat:
                model = solver.model()
                for var in model.decls():
                    try:
                        v = Var._lookup_[int(var.name())]
                    except Exception:
                        continue

                    if v is not None:
                        val = model.eval(var(), model_completion=True)

                        if is_fp(val):
                            bv = model.eval(fpToIEEEBV(val))
                            cast_values[v._idx_] = bv
                        elif isinstance(val, IntNumRef| BitVecNumRef):
                            cast_values[v._idx_] = val.as_long()
                        else:
                            cast_values[v._idx_] = val
            else:
                raise Exception("Failed to randomize")

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
            if Var._lookup_[v._idx_]._auto_random_:
                vars.append(Var._lookup_[v._idx_])

                # Create the random / z3 variable
                # Done only when randomization is called to speed up non-randomized object creation
                if v._rand_ is None:
                    v._rand_ = v._z3_()

        var_ids = [v._idx_ for v in vars]

        # Create Solver
        solver = new_solver()

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

        # Add randomization and solve
        solver.push()
        values = cast(solver)
        solver.pop()

        # Assign values to Var objects - only for those within this class
        for k in var_ids:
            var = Var._lookup_[k]
            if k in values:
                var.value = values[k]
            else:
                var.value = var._random_value_()

        # User defined post-randomization function
        self.post_randomize()

__all__ = ["Object"]
