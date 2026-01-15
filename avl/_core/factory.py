# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Factory
import fnmatch
import re
from collections.abc import Callable
from typing import Any

import tabulate


class Factory:
    _by_type = {}

    _by_instance = {}
    _by_instance_regex = None
    _by_instance_overrides: dict[str, Any] = {}

    _variables = {}
    _variables_regex = None
    _variables_overrides: dict[str, Any] = {}

    _sentinal = object()
    _fmt = "grid"

    @staticmethod
    def _compile_regex(mapping: dict[str, Callable]) -> tuple[re.Pattern | None, dict[str, Callable]]:
        """
        Compile glob patterns into a single regex with named groups.

        :param mapping: A dictionary mapping glob patterns to handlers.
        :type mapping: Dict[str, Callable]
        :return: A tuple containing the compiled regex and a mapping from group names to handlers.
        :rtype: tuple[Optional[re.Pattern], Dict[str, Callable]]
        """
        if not mapping:
            return None, {}

        # Sort once by specificity (most specific first)
        sorted_patterns = sorted(
            mapping.keys(),
            key=Factory.specificity,
            reverse=True,
        )

        group_to_handler: dict[str, Callable] = {}
        regex_parts = []

        for i, glob in enumerate(sorted_patterns):
            group_name = f"g{i}"
            regex = fnmatch.translate(glob)
            regex_parts.append(f"(?P<{group_name}>{regex})")
            group_to_handler[group_name] = mapping[glob]

        return re.compile("|".join(regex_parts)), group_to_handler

    def __str__(self) -> str:
        """
        Return a string representation of the Factory.

        :return: String representation of the Factory.
        :rtype: str
        """

        s = "\n========== FACTORY TOPOLOGY ==========\n"

        if Factory._by_type:
            s += "\nType Overrides:\n"
            rows = [(k, getattr(v, "__name__", v)) for k, v in Factory._by_type.items()]
            s += tabulate.tabulate(rows, headers=["Original", "Override"], tablefmt=Factory._fmt)

        if Factory._by_instance:
            s += "\nInstance Overrides:\n"
            rows = [(k, getattr(v, "__name__", v)) for k, v in Factory._by_instance.items()]
            s += tabulate.tabulate(rows, headers=["Original", "Override"], tablefmt=Factory._fmt)

        if Factory._variables:
            s += "\nVariables:\n"
            s += tabulate.tabulate(Factory._variables.items(), headers=["Original", "Override"], tablefmt=Factory._fmt)

        s += "\n======================================\n"
        return s

    @staticmethod
    def print_factory() -> None:
        """
        Print the current factory topology including:
            - Type overrides
            - Instance overrides
            - Config variables
        """
        print(Factory())

    @staticmethod
    def specificity(pattern : str) -> tuple[float, int]:
        """
        Calculate specificity score for a pattern (higher = more specific)
        This function evaluates the pattern based on the number of literal characters,
        wildcards, and character classes. The more literal characters, the more specific the pattern.
        Wildcards reduce specificity, while character classes add a bit of specificity.

        :param pattern: The pattern to evaluate.
        :type pattern: str
        :return: Specificity score.
        :rtype: tuple[float, int]
        """
        # Count literal characters (non-wildcards)
        literal_chars = len(re.sub(r'[*?[\]]', '', pattern))

        # Penalize wildcards (less specific)
        wildcards = pattern.count('*') + pattern.count('?')

        # Character classes are somewhat specific
        char_classes = len(re.findall(r'\[[^\]]+\]', pattern))

        # Specificity score: literal chars - wildcards + partial credit for char classes
        score = literal_chars - wildcards + char_classes * 0.5

        return (score, len(pattern))

    @staticmethod
    def set_override_by_type(original: Any, override: Any) -> None:
        """
        Set an override for a type.

        :param original: The original type to override.
        :type original: type
        :param override: The override type.
        :type override: type
        """
        if original.__name__ not in Factory._by_type:
            Factory._by_type[original.__name__] = override

    @staticmethod
    def set_override_by_instance(path: str, override: Any) -> None:
        """
        Set an override by instance path.

        :param path: The instance path to override.
        :type path: str
        :param override: The override type.
        :type override: type
        """
        if path not in Factory._by_instance:
            Factory._by_instance[path] = override

        # Compile patterns after adding a new override
        Factory._by_instance_regex, Factory._by_instance_overrides = (Factory._compile_regex(Factory._by_instance))

    @staticmethod
    def get_by_type(original: type) -> type:
        """
        Get the override for a type if it exists, otherwise return the original type.

        :param original: The original type.
        :type original: type
        :return: The override type or the original type.
        :rtype: type
        """
        return Factory._by_type.get(original.__name__, original)

    @staticmethod
    def get_by_instance(original: type, path: str) -> type:
        """
        Get the override by instance path if it exists, otherwise return the original type.

        :param original: The original type.
        :type original: type
        :param path: The instance path to look up.
        :type path: str
        :return: The override type or the original type.
        :rtype: type
        """
        if Factory._by_instance_regex is None:
            return original

        match = Factory._by_instance_regex.match(path)
        if match is not None and match.lastgroup is not None:
            return Factory._by_instance_overrides[match.lastgroup]

        return original

    @staticmethod
    def get_factory_override(original: type, path: str) -> type:
        """
        Get the override for a type, name, and instance path.

        :param original: The original type.
        :type original: type
        :param name: The name to look up.
        :type name: str
        :param path: The instance path to look up.
        :type path: str
        :return: The override type or the original type.
        :rtype: type
        """
        retval = Factory.get_by_type(original)

        if path is not None:
            retval = Factory.get_by_instance(retval, path)

        return retval

    @staticmethod
    def set_variable(path: str, value: Any, allow_override=False) -> None:
        """
        Set a variable. This is equivalent to setting a value in the UVM config_db.

        :param path: The path to the variable.
        :type path: str
        :param value: The value to set for the variable.
        :type value: Any
        :param allow_override: Allow existing variable to be overridden
        :type allow_override: bool
        """
        if path not in Factory._variables or allow_override:
            Factory._variables[path] = value

        # Compile patterns after adding a new override
        Factory._variables_regex, Factory._variables_overrides = (Factory._compile_regex(Factory._variables))

    @staticmethod
    def get_variable(path: str, default: Any=_sentinal) -> Any:
        """
        Get the value of a variable by its path if it exists, otherwise return the default value.

        :param default: The default value to return if no match is found.
        :type default: Any
        :param path: The path to the variable.
        :type path: str
        :raises KeyError: when there is no match and no default
        :return: The value of the variable or the default value.
        :rtype: Any
        """

        match = Factory._variables_regex.match(path) if Factory._variables_regex else None

        if match is not None and match.lastgroup is not None:
            return Factory._variables_overrides[match.lastgroup]
        elif default is not Factory._sentinal:
            return default
        else:
            raise KeyError(f"No variable in the factory matches Path argument ({path}), \
                and no default value is provided.")

__all__ = ["Factory"]
