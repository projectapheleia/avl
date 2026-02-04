# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Phase Manager

from .phase import Phase


class PhaseManager:
    _first: Phase | None = None
    _current: Phase | None = None
    _phases: dict[str, Phase] = {}

    @staticmethod
    def get_phase(name: str) -> Phase:
        """
        Gets a phase by name.

        :param name: Name of the phase.
        :type name: str
        :returns: The phase with the given name.
        :rtype: Phase
        """
        uname = name.upper()
        if uname not in PhaseManager._phases.keys():
            raise ValueError(f"Phase {name} does not exist")
        return PhaseManager._phases[uname]

    @staticmethod
    def add_phase(name, after: Phase|None = None, top_down: bool = True) -> Phase:
        """
        Adds a phase to the manager.

        :param name: Name of the phase.
        :type name: str
        :param after: The phase to add after (optional).
        :type after: Phase
        :param top_down: Indicates if the phase is top-down (default is True).
        :type top_down: bool
        :returns: The added phase.
        :rtype: Phase
        """
        if PhaseManager._current is not None and PhaseManager._current != PhaseManager._first:
            raise ValueError("Cannot add phase while not at the first phase")

        uname = name.upper()
        if uname in PhaseManager._phases.keys():
            raise ValueError(f"Phase {name} already exists")

        PhaseManager._phases[uname] = Phase(uname, top_down=top_down)

        if after is not None:
            PhaseManager._phases[uname].insert(after)
        else:
            if PhaseManager._first is not None:
                PhaseManager._phases[uname].next = PhaseManager._first
                PhaseManager._first.prev = PhaseManager._phases[uname]
            PhaseManager._first = PhaseManager._phases[uname]

        PhaseManager._current = PhaseManager._first
        return PhaseManager._phases[uname]

    @staticmethod
    def remove_phase(name: str) -> None:
        """
        Removes a phase from the manager.

        :param name: Name of the phase.
        :type name: str
        """
        if PhaseManager._current is not None and PhaseManager._current != PhaseManager._first:
            raise ValueError("Cannot remove phase while not at the first phase")

        uname = name.upper()
        if uname not in PhaseManager._phases.keys():
            raise ValueError(f"Phase {name} does not exist")

        phase = PhaseManager._phases[uname]
        phase.remove()

        if phase == PhaseManager._first:
            PhaseManager._first = phase.next
        PhaseManager._current = PhaseManager._first
        PhaseManager._phases.pop(uname)

    @staticmethod
    def next() -> Phase|None:
        """
        Moves to the next phase.

        :returns: The next phase.
        :rtype: Phase
        """
        assert PhaseManager._current is not None
        PhaseManager._current = PhaseManager._current.next
        return PhaseManager._current

    @staticmethod
    def prev() -> Phase|None:
        """
        Moves to the previous phase.

        :returns: The previous phase.
        :rtype: Phase
        """
        assert PhaseManager._current is not None
        PhaseManager._current = PhaseManager._current.prev
        return PhaseManager._current


__all__ = ["PhaseManager"]
