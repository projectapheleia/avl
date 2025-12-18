# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Factory
import fnmatch
import re
import tabulate
from typing import Any


class Factory:
    _by_type = {}
    _by_instance = {}
    _variables = {}
    _sentinal = object()
    _fmt = "grid"

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
    def specificity(pattern : str) -> int:
        """
        Calculate specificity score for a pattern (higher = more specific)
        This function evaluates the pattern based on the number of literal characters,
        wildcards, and character classes. The more literal characters, the more specific the pattern.
        Wildcards reduce specificity, while character classes add a bit of specificity.

        :param pattern: The pattern to evaluate.
        :type pattern: str
        :return: Specificity score.
        :rtype: int
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

    @staticmethod
    def get_by_type(original: type) -> type:
        """
        Get the override for a type if it exists, otherwise return the original type.

        :param original: The original type.
        :type original: type
        :return: The override type or the original type.
        :rtype: type
        """
        if original.__name__ in Factory._by_type:
            return Factory._by_type[original.__name__]
        else:
            return original

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
        matches = [value for value in Factory._by_instance if fnmatch.fnmatch(path, value)]

        if matches:
            closest_match = max(matches, key=Factory.specificity)
            return Factory._by_instance[closest_match]
        else:
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
        matches = [value for value in Factory._variables if fnmatch.fnmatch(path, value)]

        if matches:
            closest_match = max(matches, key=Factory.specificity)
            return Factory._variables[closest_match]
        elif default is not Factory._sentinal:
            return default
        else:
            raise KeyError(f"No variable in the factory matches Path argument ({path}), \
                and no default value is provided.")


__all__ = ["Factory"]
