# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library random number helpers

"""Random draws on the hot paths of variable randomization."""

from __future__ import annotations

import random


def urandom_range(lo: int, hi: int) -> int:
    """
    Return a uniformly distributed random integer in the inclusive range [lo, hi].

    Equivalent to ``random.randint(lo, hi)`` but several times faster. ``randint``
    defers to ``randrange``, which revalidates its arguments on every call, where
    ``getrandbits`` is a direct call into the underlying Mersenne Twister. Every
    variable that falls back to a direct draw goes through here.

    :param lo: The inclusive lower bound.
    :type lo: int
    :param hi: The inclusive upper bound.
    :type hi: int
    :return: A random integer in [lo, hi].
    :rtype: int
    """
    span = hi - lo + 1

    # A power of two spans exactly the draws of that many bits.
    if span & (span - 1) == 0:
        return lo + random.getrandbits(span.bit_length() - 1)

    # Otherwise draw the smallest number of bits covering the span and reject
    # what falls outside it. Less than half of the range is ever rejected, so
    # this averages under two draws.
    bits = span.bit_length()
    while True:
        drawn = random.getrandbits(bits)
        if drawn < span:
            return lo + drawn


__all__ = ["urandom_range"]
