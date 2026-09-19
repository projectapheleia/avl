#!/usr/bin/env python3

# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library Mutation Testing

"""Mutation testing (functional qualification) for AVL.

Mutation testing measures the testbench, not the design. Artificial bugs are
injected into the RTL and the existing tests are re-run against each one. A
mutant the tests still pass is a hole in the verification environment.

Each mutation is written out as a complete, standalone copy of the source
carrying exactly one defect::

    rtl/example_hdl.sv          result = a + b;     the golden source
    mutants/1/example_hdl.sv    result = a - b;     mutant 1
    mutants/2/example_hdl.sv    result = a * b;     mutant 2

Six classes are a single swapped operator: ``arith``, ``bitwise``, ``compare``,
``logical``, ``shift`` and ``unary``. The other ten rewrite something larger,
and reach defects an operator swap cannot. ``pipeline`` gives a registered
signal an extra stage so that it arrives one cycle late - a timing defect rather
than a logical one, and the kind a scoreboard that is loose about when it
compares will happily miss. ``sign`` negates the value assigned to a signed
variable, modelling a sign that was dropped or applied the wrong way round.
``statement`` drops a registered assignment so its register holds, ``condition``
holds a branch open and shut, ``operand`` turns a non-commutative operator
around, ``width`` takes a bit off a declaration, ``array_packed`` and
``array_unpacked`` turn a declared range around, and ``blocking`` and
``nonblocking`` swap the two kinds of assignment where the difference can be
seen. ``--list-types`` prints them all with what each one does.

A mutant is ordinary RTL that happens to be wrong, so it builds and runs exactly
like the golden source on any simulator, and the testbench needs no knowledge of
mutation testing at all.

Sites are located with `pyslang <https://pypi.org/project/pyslang/>`_, whose
concrete syntax tree round trips back to the original source byte for byte. The
parser is used only to find the exact source span of each operator, and the
rewrite is a splice over that span, so formatting and comments survive.

Generation also writes ``mutations.html``, a report explaining each mutation in
its source context, and - where `yosys <https://yosyshq.net/yosys/>`_ is
installed - proves that each mutation actually changes the design. A mutant that
behaves identically to the golden source can never be detected by any testbench,
so counting it as a survivor would report a verification hole that is not there.
Those are called out and left out of the score.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path

# Mutation operators, grouped into the classes selectable with --types.
# Each entry maps a pyslang SyntaxKind to (original operator, mutated operator).
# An empty mutated operator deletes the operator, e.g. "!a" becomes "a".
MUTATIONS = {
    "arith": {
        "AddExpression": ("+", "-"),
        "SubtractExpression": ("-", "+"),
        "MultiplyExpression": ("*", "+"),
        "DivideExpression": ("/", "*"),
        "ModExpression": ("%", "/"),
    },
    "bitwise": {
        "BinaryAndExpression": ("&", "|"),
        "BinaryOrExpression": ("|", "&"),
        "BinaryXorExpression": ("^", "&"),
    },
    "compare": {
        "EqualityExpression": ("==", "!="),
        "InequalityExpression": ("!=", "=="),
        "LessThanExpression": ("<", "<="),
        "LessThanEqualExpression": ("<=", "<"),
        "GreaterThanExpression": (">", ">="),
        "GreaterThanEqualExpression": (">=", ">"),
    },
    "logical": {
        "LogicalAndExpression": ("&&", "||"),
        "LogicalOrExpression": ("||", "&&"),
    },
    "shift": {
        "LogicalShiftLeftExpression": ("<<", ">>"),
        "LogicalShiftRightExpression": (">>", "<<"),
    },
    "unary": {
        "UnaryLogicalNotExpression": ("!", ""),
        "UnaryBitwiseNotExpression": ("~", ""),
    },
}

# Pipeline defects are structural rather than a swapped operator: a registered
# assignment gains an extra stage, so the signal arrives one cycle late. The
# statement is rewritten through a new register,
#
#     y <= result;    ->    begin avl_pipe_1 <= result; y <= avl_pipe_1; end
#
# with a register declared alongside. Sized with $bits so the width does not have
# to be inferred, and initialised so that the extra stage does not push an X
# through the design out of reset.
PIPELINE = "pipeline"
PIPELINE_KIND = "NonblockingAssignmentExpression"

PIPELINE_BLOCKS = {"AlwaysBlock", "AlwaysFFBlock"}

# A constant assignment is the reset arm of a register, near enough. Delaying a
# constant models nothing anybody would call a pipeline bug.
PIPELINE_SKIP_RHS = {
    "IntegerLiteralExpression",
    "IntegerVectorExpression",
    "UnbasedUnsizedLiteralExpression",
    "StringLiteralExpression",
}

# The register is declared immediately above the always block it feeds, which is
# below every declaration that block could refer to. Declaring it at the top of
# the module instead would put $bits(target) ahead of the target's own
# declaration, and yosys - unlike Verilator - will not resolve that.
PIPELINE_DECL = (
    "logic [$bits({target})-1:0] {reg} = '0;\n"
    "\n{indent}"
)
PIPELINE_STMT = "begin {reg} <= {rhs}; {target} <= {reg}; end"

# Sign defects negate the value assigned to a signed variable,
#
#     y = a + 1;    ->    y = -(a + 1);
#
# which models a sign that was dropped or applied the wrong way round. Only
# signed variables are eligible: negating an unsigned one is not a sign error,
# it is a wrap, and the design would never have been written that way.
SIGN = "sign"
SIGN_KINDS = {"AssignmentExpression", "NonblockingAssignmentExpression"}
SIGN_STMT = "-({rhs})"

# Types that are signed unless declared otherwise. Everything else - logic, bit,
# reg - is unsigned unless it says "signed".
SIGNED_BY_DEFAULT = {
    "IntType",
    "IntegerType",
    "ByteType",
    "ShortIntType",
    "LongIntType",
}

# Negating '0 gives '0, and negating '1 is a curiosity rather than a defect.
# Every other constant is worth flipping.
SIGN_SKIP_RHS = {"UnbasedUnsizedLiteralExpression"}

# Array defects reverse a declared dimension,
#
#     logic [W-1:0] a;      ->    logic [0:W-1] a;      packed
#     logic a [0:N-1];      ->    logic a [N-1:0];      unpacked
#
# which models a range written the wrong way round. Packed and unpacked are
# separate classes because they break different things: reversing a packed
# dimension renumbers the bits, so it shows up through bit selects, while
# reversing an unpacked one reorders the elements, so it shows up through
# assignment patterns and iteration order.
ARRAY_PACKED = "array_packed"
ARRAY_UNPACKED = "array_unpacked"
ARRAY_KIND = "VariableDimension"

# Width defects take a bit off a packed declaration, modelling a bus declared
# one bit too narrow so that its top bit is quietly lost,
#
#     logic [7:0] x;   ->   logic [6:0] x;
#
# Narrowing on its own does not compile cleanly: every expression the signal
# takes part in is suddenly a bit short, and Verilator turns those width
# warnings into errors, so the mutant would fail to build and be scored as
# detected without a testbench having noticed anything. Each reference is
# therefore cast back to the original width, and each assignment to it cast down
# to the new one, which leaves the widths as they were everywhere except inside
# the signal itself - which is precisely the defect.
WIDTH = "width"
WIDTH_KIND = "VariableDimension"
WIDTH_READ = "{width}'({read})"
WIDTH_WRITE = "{width}'({rhs})"

# Condition defects hold a branch permanently open or permanently shut,
#
#     if (en) ...   ->   if (1'b1) ...   and   if (1'b0) ...
#
# which asks whether the tests exercise both arms and whether anything notices
# when one of them stops happening. Line coverage says the branch ran; this says
# whether its consequence is checked.
CONDITION = "condition"
CONDITION_KINDS = {"ConditionalStatement", "ConditionalExpression"}
CONDITION_VALUES = ("1'b1", "1'b0")
CONDITION_ALREADY = {"1'b1", "1'b0", "1", "0", "'1", "'0", "1'd1", "1'd0"}

# Statement defects drop a registered assignment, so the register holds instead
# of updating. The reset arm is left alone - dropping that is a register that is
# never reset, which is a different defect and usually an invisible one. Where pipeline says "late", this says "never": a dropped write, a
# missing enable, an update path nobody wired up. The statement is replaced by a
# null statement rather than removed, so that an if with no begin/end around it
# is still an if with a statement after it.
STATEMENT = "statement"
STATEMENT_KIND = "NonblockingAssignmentExpression"
STATEMENT_NULL = ";"

# Operand defects turn a non-commutative operator around,
#
#     a - b   ->   b - a
#
# keeping the operator and reversing the meaning, which is a bug the operator
# swaps cannot reach. Commutative operators are excluded: swapping the operands
# of an add or an and produces a mutant that cannot differ from the original.
OPERAND = "operand"
OPERAND_KINDS = {
    "SubtractExpression",
    "DivideExpression",
    "ModExpression",
    "LessThanExpression",
    "LessThanEqualExpression",
    "GreaterThanExpression",
    "GreaterThanEqualExpression",
    "LogicalShiftLeftExpression",
    "LogicalShiftRightExpression",
}

# Assignment defects swap the two kinds of assignment in a clocked block,
#
#     x <= a;   ->   x = a;      blocking
#     x = a;    ->   x <= a;     nonblocking
#
# which is the classic race: a blocking assignment in sequential logic hands the
# new value to whatever reads it next, a nonblocking one hands over the old one.
# Both are only offered where the target is read again later in the same block,
# because that is the only place the difference can be seen - and only in an
# edge triggered block, since a nonblocking assignment in combinational logic is
# a COMBDLY error rather than a defect.
BLOCKING = "blocking"
NONBLOCKING = "nonblocking"
BLOCKING_KIND = "NonblockingAssignmentExpression"
NONBLOCKING_KIND = "AssignmentExpression"

ALL_TYPES = [
    *MUTATIONS,
    PIPELINE,
    SIGN,
    ARRAY_PACKED,
    ARRAY_UNPACKED,
    WIDTH,
    CONDITION,
    STATEMENT,
    OPERAND,
    BLOCKING,
    NONBLOCKING,
]

# Every line a mutation changes is marked, so that a mutant turning up in an
# editor, a debugger or a waveform cannot be mistaken for the golden source.
MUTATION_MARK = "AVL MUTATION"
MUTATION_COMMENT = "/* " + MUTATION_MARK + " - {why} */"

# Dropped into every directory the tool creates. The output directory is emptied
# on each run, and --output is a path like any other, so the marker is how the
# next run tells a directory of its own mutants from one that holds a design.
OUTPUT_MARKER = ".avl-mutants"
OUTPUT_MARKER_TEXT = (
    "Written by avl-mutation-testing. Everything in this directory is deleted\n"
    "and regenerated on the next run. Remove this file to protect it.\n"
)

# Syntax contexts that look like mutable expressions but are elaboration time
# constants. Mutating a port width, a part select range or a parameter is a
# structural change or a compile error, not a design bug, so anything under
# these is skipped. A bit select with a variable index is deliberately absent:
# mem[wptr + 1] is real logic and worth mutating.
SKIP_CONTEXTS = {
    "VariableDimension",
    "RangeDimensionSpecifier",
    "SimpleRangeSelect",
    "AscendingRangeSelect",
    "DescendingRangeSelect",
    "CastExpression",
    "SignedCastExpression",
    "ParameterDeclaration",
    "TypeParameterDeclaration",
    "ParameterPortList",
    "ParameterValueAssignment",
    "TypeReference",
    "EnumType",
}

# Syntax contexts a reference cannot be wrapped in a cast, because what looks
# like a read of the signal is really a place the signal is driven from. The
# width class narrows a declaration and casts every reference back, so a signal
# reached through one of these is left alone entirely.
UNCASTABLE_CONTEXTS = {
    "NamedPortConnection",
    "OrderedPortConnection",
}


def _pyslang():
    """
    Import pyslang. It is a hard dependency, imported here rather than at module
    scope to keep its native extension out of processes that never mutate.

    :return: The pyslang.syntax module.
    :rtype: module
    """
    try:
        import pyslang.syntax as syntax
    except ImportError:
        sys.exit(
            "avl-mutation-testing requires pyslang, which should have been installed with AVL.\n"
            "  pip install --upgrade avl-core"
        )
    return syntax


def _kind(node) -> str:
    """
    Return the bare SyntaxKind name of a node, e.g. "AddExpression".

    The visitor passes both syntax nodes and tokens, and tokens carry a
    TokenKind, so the prefix is what distinguishes them.

    :param node: A pyslang syntax node or token.
    :return: The kind name, or an empty string for anything else.
    :rtype: str
    """
    kind = str(getattr(node, "kind", ""))
    return kind.split(".")[-1] if kind.startswith("SyntaxKind.") else ""


def _ancestors(node):
    """
    Yield the kind name of every ancestor of a node, innermost first.

    :param node: A pyslang syntax node.
    :return: Generator of ancestor kind names.
    """
    parent = node.parent
    while parent is not None:
        yield _kind(parent)
        parent = parent.parent


def _enclosing_module(node) -> str | None:
    """
    Return the name of the module a node sits in.

    :param node: A pyslang syntax node.
    :return: The module name, or None if the node is outside a module.
    :rtype: str | None
    """
    module = _module_of(node)
    return module.header.name.valueText if module is not None else None


def _module_of(node):
    """
    Return the ModuleDeclaration a node sits in.

    :param node: A pyslang syntax node.
    :return: The enclosing module declaration, or None.
    """
    parent = node.parent
    while parent is not None:
        if _kind(parent) == "ModuleDeclaration":
            return parent
        parent = parent.parent
    return None


def _is_signed(data_type) -> bool:
    """
    Return whether a declared type is signed.

    :param data_type: The type syntax node of a declaration or port header.
    :return: True if values of the type are signed.
    :rtype: bool
    """
    if data_type is None:
        return False

    signing = getattr(getattr(data_type, "signing", None), "valueText", "")
    if signing:
        return signing == "signed"

    return _kind(data_type) in SIGNED_BY_DEFAULT


def signed_variables(tree) -> dict[str, set[str]]:
    """
    Collect the signed variables of every module in a file, by module.

    This reads the declarations rather than elaborating the design, so it sees
    what is written in the file and nothing more. A variable whose signedness
    comes from a typedef or a parameterised type is not recognised, and is
    simply not offered as a site.

    :param tree: A parsed syntax tree.
    :return: Signed variable names, keyed by the module they are declared in.
    :rtype: dict[str, set[str]]
    """
    signed: dict[str, set[str]] = {}

    def visit(node):
        kind = _kind(node)

        if kind == "DataDeclaration":
            if not _is_signed(node.type):
                return
            names = [d.name.valueText for d in node.declarators]
        elif kind == "ImplicitAnsiPort":
            if not _is_signed(getattr(node.header, "dataType", None)):
                return
            names = [node.declarator.name.valueText]
        else:
            return

        module = _enclosing_module(node)
        if module is not None:
            signed.setdefault(module, set()).update(names)

    tree.root.visit(visit)
    return signed


def references(tree, src: str) -> dict[tuple[str, str], dict]:
    """
    Collect every reference to every identifier, by module and name.

    :param tree: A parsed syntax tree.
    :param src: The source text the tree came from.
    :type src: str
    :return: Per module and name, the spans that read it, the right hand sides
             that are assigned to it, whether any reference is selected, and
             whether any reference stands somewhere a cast cannot go.
    :rtype: dict[tuple[str, str], dict]
    """
    found: dict[tuple[str, str], dict] = {}

    def entry(node, name):
        return found.setdefault(
            (_enclosing_module(node), name),
            {"reads": [], "writes": [], "selected": False, "uncastable": False},
        )

    def assigned_to(node) -> bool:
        """Whether a node is the target of an assignment rather than a read."""
        parent = node.parent
        return _kind(parent) in SIGN_KINDS and parent.left is node

    def castable(node) -> bool:
        """
        Whether a reference can be wrapped in a cast where it stands.

        A port connection is the instantiation's half of an lvalue, and an
        output port driven by ``8'(sig)`` is a constant pin rather than a
        signal - Verilator calls it an electrical short and refuses to build.
        A reference buried inside the left hand side of an assignment, one
        element of a concatenation say, is an lvalue for the same reason.
        Neither position admits a cast, and which of a module's ports are
        outputs is not knowable from this file alone, so every port connection
        is treated as out of reach.
        """
        child = node
        parent = node.parent
        while parent is not None:
            if _kind(parent) in UNCASTABLE_CONTEXTS:
                return False
            if _kind(parent) in SIGN_KINDS and parent.left is child:
                return False
            child, parent = parent, parent.parent
        return True

    def visit(node):
        kind = _kind(node)

        if kind not in ("IdentifierName", "IdentifierSelectName"):
            return

        span = node.sourceRange
        text = src[span.start.offset : span.end.offset]

        # A selected reference cannot be cast without rewriting the select, so
        # the whole signal is put out of reach of the width class. It is still
        # a reference, and still tells the assignment classes that the target
        # is read below.
        if kind == "IdentifierSelectName":
            record = entry(node, text.split("[")[0].strip())
            record["selected"] = True
            if not assigned_to(node):
                record["reads"].append((span.start.offset, span.end.offset))
            return

        record = entry(node, text.strip())

        if assigned_to(node):
            rhs = node.parent.right.sourceRange
            record["writes"].append((rhs.start.offset, rhs.end.offset))
            return

        record["reads"].append((span.start.offset, span.end.offset))
        if not castable(node):
            record["uncastable"] = True

    tree.root.visit(visit)
    return found


def find_sites(path: str, types: list[str]) -> tuple[str, list[dict]]:
    """
    Parse a source file and locate every candidate mutation site.

    :param path: Path to the SystemVerilog source file.
    :type path: str
    :param types: Mutation classes to consider, keys of :data:`MUTATIONS`.
    :type types: list[str]
    :return: The source text and the candidate sites, in source order.
    :rtype: tuple[str, list[dict]]
    """
    syntax = _pyslang()

    tree = syntax.SyntaxTree.fromFile(path)

    # Errors only. pyslang reports warnings through the same list, and a
    # redefined macro or a mismatched end label is ordinary in real RTL and no
    # obstacle at all to finding the operators in a file.
    errors = [d for d in tree.diagnostics if d.isError()]
    if errors:
        sys.exit(f"{path}: {len(errors)} parse error(s); cannot mutate")

    src = Path(path).read_text()
    manager = tree.sourceManager
    signed = signed_variables(tree) if SIGN in types else {}

    # The width class needs to know where a signal is referenced so it can cast
    # each one; the assignment classes need to know whether the target is read
    # again below.
    refs = references(tree, src) if {WIDTH, BLOCKING, NONBLOCKING} & set(types) else {}

    wanted = {}
    for group in types:
        if group in MUTATIONS:
            wanted.update(MUTATIONS[group])

    sites: list[dict] = []

    def operator_site(node, kind):
        # A comparison that forms a branch decision belongs to the condition
        # class, which would otherwise generate the very same mutant. Only
        # handed over when condition was actually asked for, so that compare on
        # its own still reaches every comparison.
        if (
            CONDITION in types
            and kind in MUTATIONS["compare"]
            and "ConditionalPredicate" in set(_ancestors(node))
        ):
            return None

        old_op, new_op = wanted[kind]
        span = node.sourceRange
        start, end = span.start.offset, span.end.offset
        token = node.operatorToken.range

        # Rewrite the operator token by its own span rather than by a string
        # replace, so operands that happen to contain the operator text are
        # never touched.
        original = src[start:end]
        mutated = (
            original[: token.start.offset - start] + new_op + original[token.end.offset - start :]
        )

        return {
            "type": next(g for g in types if g in MUTATIONS and kind in MUTATIONS[g]),
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": token.start.offset,
            "op_end": token.end.offset,
            "operator": old_op,
            "mutated_operator": new_op,
            "original": " ".join(original.split()),
            "mutated": " ".join(mutated.split()),
            "_edits": [(token.start.offset, token.end.offset, new_op)],
        }

    def pipeline_site(node):
        # Only a whole signal can gain a stage. A bit select or an array element
        # would need its index delayed too, which is a different defect.
        if _kind(node.left) != "IdentifierName":
            return None
        if _kind(node.right) in PIPELINE_SKIP_RHS:
            return None

        block = node.parent
        while block is not None and _kind(block) not in PIPELINE_BLOCKS:
            block = block.parent
        if block is None:
            return None

        statement = node.parent
        if _kind(statement) != "ExpressionStatement":
            return None

        if _module_of(node) is None:
            return None

        # Match the always block's own indentation so the declaration lands
        # where a person would have put it.
        block_at = block.sourceRange.start.offset
        line_start = src.rfind("\n", 0, block_at) + 1
        indent = src[line_start:block_at]
        if indent.strip():
            indent = "    "

        span = statement.sourceRange
        start, end = span.start.offset, span.end.offset
        target = src[node.left.sourceRange.start.offset : node.left.sourceRange.end.offset].strip()
        rhs = src[node.right.sourceRange.start.offset : node.right.sourceRange.end.offset].strip()
        original = " ".join(src[start:end].split())

        return {
            "type": PIPELINE,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": None,
            "op_end": None,
            "operator": "<=",
            "mutated_operator": "<= delayed one cycle",
            "target": target,
            "original": original,
            "mutated": f"{target} delayed 1 cycle",
            # Filled in once the mutation has been numbered - the register is
            # named after the mutation so that two of them cannot collide.
            "_pipeline": {
                "target": target,
                "rhs": rhs,
                "decl_at": block_at,
                "indent": indent,
            },
        }

    def declared_name(node):
        """Best effort name of what a dimension belongs to, for the report."""
        parent = node.parent
        while parent is not None:
            kind = _kind(parent)
            if kind == "Declarator":
                return parent.name.valueText
            if kind == "ImplicitAnsiPort":
                return parent.declarator.name.valueText
            if kind == "DataDeclaration":
                return parent.declarators[0].name.valueText
            parent = parent.parent
        return "?"

    def clocked_block(node):
        """The enclosing always block, if it is edge triggered."""
        control = node.parent
        while control is not None and _kind(control) != "TimingControlStatement":
            control = control.parent
        if control is None:
            return None
        timing = getattr(control, "timingControl", None)
        if timing is None:
            return None
        edge = timing.sourceRange
        if "edge" not in src[edge.start.offset : edge.end.offset]:
            return None
        return control

    def assignment_site(node, group, replacement):
        if _kind(node.parent) != "ExpressionStatement":
            return None
        if _kind(node.left) != "IdentifierName":
            return None

        block = clocked_block(node)
        if block is None:
            return None

        target = src[node.left.sourceRange.start.offset : node.left.sourceRange.end.offset].strip()

        # Which kind of assignment this is only matters to whoever reads the
        # target next. If nothing after it reads the target, the two are
        # indistinguishable and the mutation is dead on arrival.
        #
        # "After it" means the begin/end it sits in, not the whole always block:
        # a reset arm and the arm beside it are different paths, and a read over
        # in the other one is never reached from here.
        statement = node.parent
        scope = statement
        while scope is not None and _kind(scope) != "SequentialBlockStatement":
            scope = scope.parent
        if scope is None:
            scope = block

        # A read, not merely an occurrence of the name. Searching the source
        # text counts the target in a comment, and counts a later assignment to
        # it - and neither of those can tell the two kinds of assignment apart,
        # so either one invents a mutation that no testbench could ever catch
        # and reports it as a hole in the verification.
        record = refs.get((_enclosing_module(node), target))
        after = statement.sourceRange.end.offset
        until = scope.sourceRange.end.offset
        if record is None or not any(after <= start < until for start, _ in record["reads"]):
            return None

        token = node.operatorToken.range
        span = node.sourceRange
        start, end = span.start.offset, span.end.offset
        original = " ".join(src[start:end].split())
        mutated = original.replace(node.operatorToken.valueText, replacement, 1)

        return {
            "type": group,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": token.start.offset,
            "op_end": token.end.offset,
            "operator": node.operatorToken.valueText,
            "mutated_operator": replacement,
            "target": target,
            "original": original,
            "mutated": " ".join(mutated.split()),
            "_edits": [(token.start.offset, token.end.offset, replacement)],
        }

    def condition_sites(node):
        predicate = getattr(node, "predicate", None)
        if predicate is None:
            return []

        span = predicate.sourceRange
        start, end = span.start.offset, span.end.offset
        original = " ".join(src[start:end].split())

        # A condition that is already constant has nothing to hold open.
        if original in CONDITION_ALREADY:
            return []

        # The reset arm of a clocked block is not a branch like the others.
        # Holding it open or shut leaves the reset edge sensitive but unused,
        # which is a malformed design rather than a defect - and one that
        # equivalence checking cannot read.
        control = node.parent
        while control is not None and _kind(control) != "TimingControlStatement":
            control = control.parent
        if control is not None:
            timing = getattr(control, "timingControl", None)
            if timing is not None:
                edge = timing.sourceRange
                edges = set(re.findall(r"\w+", src[edge.start.offset : edge.end.offset]))
                if edges & set(re.findall(r"\w+", original)):
                    return []

        made = []
        for value in CONDITION_VALUES:
            made.append(
                {
                    "type": CONDITION,
                    "line": manager.getLineNumber(span.start),
                    "start": start,
                    "end": end,
                    "op_start": start,
                    "op_end": end,
                    "operator": original,
                    "mutated_operator": value,
                    "original": original,
                    "mutated": value,
                    "_edits": [(start, end, value)],
                }
            )

        # Holding the branch constant asks whether both arms are exercised.
        # Nudging the comparisons the decision is built from asks the sharper
        # question: whether the tests sit on the boundary the branch turns on.
        def compared(inner):
            inner_kind = _kind(inner)
            if inner_kind not in MUTATIONS["compare"]:
                return
            old_op, new_op = MUTATIONS["compare"][inner_kind]
            inner_span = inner.sourceRange
            inner_start, inner_end = inner_span.start.offset, inner_span.end.offset
            token = inner.operatorToken.range
            text = src[inner_start:inner_end]
            swapped = (
                text[: token.start.offset - inner_start]
                + new_op
                + text[token.end.offset - inner_start :]
            )
            made.append(
                {
                    "type": CONDITION,
                    "line": manager.getLineNumber(inner_span.start),
                    "start": inner_start,
                    "end": inner_end,
                    "op_start": token.start.offset,
                    "op_end": token.end.offset,
                    "operator": old_op,
                    "mutated_operator": new_op,
                    "original": " ".join(text.split()),
                    "mutated": " ".join(swapped.split()),
                    "_edits": [(token.start.offset, token.end.offset, new_op)],
                }
            )

        predicate.visit(compared)
        return made

    def statement_site(node):
        statement = node.parent
        if _kind(statement) != "ExpressionStatement":
            return None

        # The reset arm assigns a constant, and dropping that models a register
        # that is never reset rather than one that never updates - a different
        # defect, and usually an invisible one in a two state simulator.
        if _kind(node.right) in PIPELINE_SKIP_RHS:
            return None

        block = node.parent
        while block is not None and _kind(block) not in PIPELINE_BLOCKS:
            block = block.parent
        if block is None:
            return None

        span = statement.sourceRange
        start, end = span.start.offset, span.end.offset
        original = " ".join(src[start:end].split())

        return {
            "type": STATEMENT,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": None,
            "op_end": None,
            "operator": "<=",
            "mutated_operator": "dropped",
            "original": original,
            "mutated": "dropped, the register holds",
            "_edits": [(start, end, STATEMENT_NULL)],
        }

    def operand_site(node):
        left_range, right_range = node.left.sourceRange, node.right.sourceRange
        left = src[left_range.start.offset : left_range.end.offset]
        right = src[right_range.start.offset : right_range.end.offset]

        # Identical operands swap to themselves.
        if left.strip() == right.strip():
            return None

        span = node.sourceRange
        start, end = span.start.offset, span.end.offset
        operator = node.operatorToken.valueText
        original = " ".join(src[start:end].split())

        return {
            "type": OPERAND,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": start,
            "op_end": end,
            "operator": operator,
            "mutated_operator": f"{operator} reversed",
            "original": original,
            "mutated": " ".join(f"{right.strip()} {operator} {left.strip()}".split()),
            "_edits": [
                (left_range.start.offset, left_range.end.offset, right.strip()),
                (right_range.start.offset, right_range.end.offset, left.strip()),
            ],
        }

    def width_site(node):
        # Ports are the module's contract with whatever instantiates it, and
        # narrowing one moves the mismatch to the instantiation - somewhere this
        # mutation cannot reach. Internal declarations only.
        declaration = node.parent
        while declaration is not None and _kind(declaration) not in ("DataDeclaration", "ImplicitAnsiPort"):
            declaration = declaration.parent
        if _kind(declaration) != "DataDeclaration":
            return None

        # An unpacked dimension hangs off the declarator; this is the packed one.
        if _kind(node.parent) == "Declarator":
            return None

        spec = getattr(node, "specifier", None)
        if _kind(spec) != "RangeDimensionSpecifier":
            return None
        selector = getattr(spec, "selector", None)
        if _kind(selector) != "SimpleRangeSelect":
            return None

        if len(declaration.declarators) != 1:
            return None
        name = declaration.declarators[0].name.valueText

        left_range, right_range = selector.left.sourceRange, selector.right.sourceRange
        left = src[left_range.start.offset : left_range.end.offset].strip()
        right = src[right_range.start.offset : right_range.end.offset].strip()

        # The cast needs a width, so both bounds have to be plain numbers. A
        # parameterised range is left alone rather than cast symbolically.
        if not (left.isdigit() and right.isdigit()):
            return None
        high, low = int(left), int(right)
        width = abs(high - low) + 1
        if width < 2:
            return None

        # Take the bit off whichever end is the most significant.
        narrowed = f"{high - 1}:{low}" if high > low else f"{high}:{low - 1}"

        # Narrowing works by casting every reference back to the original
        # width, so a signal with a reference that cannot carry a cast - a port
        # connection, or an element of a concatenation being assigned to - is
        # not a candidate. Casting one of those produces a mutant that does not
        # build, and a mutant that does not build scores as detected without a
        # testbench having noticed anything.
        record = refs.get((_enclosing_module(node), name))
        if record is None or record["selected"] or record["uncastable"]:
            return None

        # A read inside an assignment to the same signal would need the two
        # casts nested. Counters do this; they are simply skipped.
        for read_start, read_end in record["reads"]:
            if any(w0 <= read_start and read_end <= w1 for w0, w1 in record["writes"]):
                return None

        span = node.sourceRange
        start, end = span.start.offset, span.end.offset

        edits = [(selector.sourceRange.start.offset, selector.sourceRange.end.offset, narrowed)]
        for read_start, read_end in record["reads"]:
            edits.append(
                (read_start, read_end, WIDTH_READ.format(width=width, read=src[read_start:read_end]))
            )
        for write_start, write_end in record["writes"]:
            edits.append(
                (
                    write_start,
                    write_end,
                    WIDTH_WRITE.format(width=width - 1, rhs=src[write_start:write_end]),
                )
            )

        return {
            "type": WIDTH,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": selector.sourceRange.start.offset,
            "op_end": selector.sourceRange.end.offset,
            "operator": f"{left}:{right}",
            "mutated_operator": narrowed,
            "target": name,
            "original": f"{name} [{left}:{right}]",
            "mutated": f"{name} [{narrowed}], {width} bits -> {width - 1}",
            "_edits": edits,
        }

    def array_site(node):
        spec = getattr(node, "specifier", None)
        if _kind(spec) != "RangeDimensionSpecifier":
            return None

        # A sized dimension such as [4] carries a BitSelect, and there is no
        # range in it to turn around.
        selector = getattr(spec, "selector", None)
        if _kind(selector) != "SimpleRangeSelect":
            return None

        # A dimension hanging off a declarator is unpacked; one hanging off the
        # type is packed. They break different things, so they are separate
        # classes and only the requested one is offered.
        group = ARRAY_UNPACKED if _kind(node.parent) == "Declarator" else ARRAY_PACKED
        if group not in types:
            return None

        if "ParameterDeclaration" in set(_ancestors(node)):
            return None

        left_range = selector.left.sourceRange
        right_range = selector.right.sourceRange
        left = src[left_range.start.offset : left_range.end.offset].strip()
        right = src[right_range.start.offset : right_range.end.offset].strip()

        # [0:0] reversed is [0:0].
        if left == right:
            return None

        span = node.sourceRange
        start, end = span.start.offset, span.end.offset
        original = " ".join(src[start:end].split())
        name = declared_name(node)

        return {
            "type": group,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            "op_start": selector.sourceRange.start.offset,
            "op_end": selector.sourceRange.end.offset,
            "operator": f"{left}:{right}",
            "mutated_operator": f"{right}:{left}",
            "target": name,
            "original": f"{name} {original}",
            "mutated": f"{name} [{right}:{left}]",
            "_edits": [
                (
                    selector.sourceRange.start.offset,
                    selector.sourceRange.end.offset,
                    f"{right}:{left}",
                )
            ],
        }

    def sign_site(node):
        # Only a whole signed variable. A part select is unsigned in
        # SystemVerilog whatever it was carved out of, so negating one models
        # nothing.
        if _kind(node.left) != "IdentifierName":
            return None
        if _kind(node.right) in SIGN_SKIP_RHS:
            return None

        target = src[node.left.sourceRange.start.offset : node.left.sourceRange.end.offset].strip()
        module = _enclosing_module(node)
        if target not in signed.get(module, ()):
            return None

        span = node.sourceRange
        start, end = span.start.offset, span.end.offset
        right = node.right.sourceRange
        rhs = src[right.start.offset : right.end.offset].strip()
        original = " ".join(src[start:end].split())

        return {
            "type": SIGN,
            "line": manager.getLineNumber(span.start),
            "start": start,
            "end": end,
            # The replacement covers exactly the right hand side, so the report
            # can underline what changed in both the golden and the mutant.
            "op_start": right.start.offset,
            "op_end": right.end.offset,
            "operator": node.operatorToken.valueText,
            "mutated_operator": "negated",
            "target": target,
            "original": original,
            "mutated": f"{target} {node.operatorToken.valueText} -({rhs})",
            "_edits": [(right.start.offset, right.end.offset, SIGN_STMT.format(rhs=rhs))],
        }

    def visit(node):
        kind = _kind(node)

        # One node can carry more than one defect. A nonblocking assignment to a
        # signed register is a candidate for both sign and pipeline, and they
        # are different bugs, so both are offered.
        found = []
        if kind in SIGN_KINDS and SIGN in types:
            found.append(sign_site(node))
        if kind == PIPELINE_KIND and PIPELINE in types:
            found.append(pipeline_site(node))
        if kind == ARRAY_KIND and {ARRAY_PACKED, ARRAY_UNPACKED} & set(types):
            found.append(array_site(node))
        if kind == WIDTH_KIND and WIDTH in types:
            found.append(width_site(node))
        if kind in CONDITION_KINDS and CONDITION in types:
            found.extend(condition_sites(node))
        if kind == STATEMENT_KIND and STATEMENT in types:
            found.append(statement_site(node))
        if kind in OPERAND_KINDS and OPERAND in types:
            found.append(operand_site(node))
        if kind == BLOCKING_KIND and BLOCKING in types:
            found.append(assignment_site(node, BLOCKING, "="))
        if kind == NONBLOCKING_KIND and NONBLOCKING in types:
            found.append(assignment_site(node, NONBLOCKING, "<="))
        if kind in wanted and not SKIP_CONTEXTS & set(_ancestors(node)):
            found.append(operator_site(node, kind))

        for site in found:
            if site is None:
                continue
            site.update({"kind": kind, "module": _enclosing_module(node), "file": path})
            sites.append(site)

    tree.root.visit(visit)
    return src, _unique(sites)


def _signature(site: dict) -> tuple:
    """
    Return what makes a site's mutant distinct from every other site's.

    :param site: A candidate mutation site.
    :type site: dict
    :return: A hashable identity for the mutant the site would produce.
    :rtype: tuple
    """
    edits = site.get("_edits")
    if edits is not None:
        return (site["file"], tuple(sorted(edits)))

    # A pipeline site carries no edits until it has been numbered, because the
    # register it delays through is named after the mutation. The statement it
    # rewrites identifies it just as well.
    return (site["file"], site["type"], site["start"], site["end"])


def _unique(sites: list[dict]) -> list[dict]:
    """
    Drop any site that would produce a mutant another site already produces.

    One expression can be reached by more than one generator. A comparison
    inside a conditional expression that is itself the predicate of an if is
    offered once by each, and the second copy is the same mutant built twice: a
    simulation spent for nothing, and a second entry padding the score.

    :param sites: Candidate sites, in the order they were found.
    :type sites: list[dict]
    :return: The sites, the first of each duplicate kept.
    :rtype: list[dict]
    """
    seen = set()
    unique = []
    for site in sites:
        signature = _signature(site)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(site)
    return unique


def _interleave(queues: list[list[dict]]) -> list[dict]:
    """
    Take one from the front of each queue in turn until all are empty.

    :param queues: Queues to interleave. Consumed in place.
    :type queues: list[list[dict]]
    :return: The interleaved sites.
    :rtype: list[dict]
    """
    out: list[dict] = []
    while any(queues):
        for queue in queues:
            if queue:
                out.append(queue.pop(0))
    return out


def preference_order(sites: list[dict], types: list[str]) -> list[dict]:
    """
    Order the candidate sites so that variety comes before repetition.

    Defects of one sort tend to cluster - a file will have a run of adds long
    before its first comparison - so taking them in source order can exhaust the
    budget on a single class and never reach the rest. Instead every class is
    represented before any class appears twice, and within a class every
    operator is used before any operator is used twice. Classes are offered in
    the order they were asked for, and sites in source order within an operator,
    so the result is fully determined.

    :param sites: Candidate sites.
    :type sites: list[dict]
    :param types: Mutation classes, in the order they were requested.
    :type types: list[str]
    :return: The sites, most worth generating first.
    :rtype: list[dict]
    """
    grouped: dict[str, dict[str, list[dict]]] = {}
    for site in sorted(sites, key=lambda s: (s["file"], s["start"])):
        grouped.setdefault(site["type"], {}).setdefault(site["kind"], []).append(site)

    ordered = sorted(grouped, key=lambda t: types.index(t) if t in types else len(types))
    return _interleave([_interleave(list(grouped[t].values())) for t in ordered])


def select_sites(
    sites: list[dict], count: int | None, seed: int | None, types: list[str]
) -> list[dict]:
    """
    Reduce the candidate sites to the requested number of mutations.

    :param sites: Candidate sites in source order.
    :type sites: list[dict]
    :param count: Maximum number of mutations to generate, or None for all.
    :type count: int | None
    :param seed: Seed for random selection. If None the sites are taken in the
                 order :func:`preference_order` puts them in.
    :type seed: int | None
    :param types: Mutation classes, in the order they were requested.
    :type types: list[str]
    :return: The selected sites, in source order, numbered from 1.
    :rtype: list[dict]
    """
    chosen = list(sites)
    if count is not None and count < len(chosen):
        if seed is not None:
            chosen = random.Random(seed).sample(chosen, count)
        else:
            chosen = preference_order(chosen, types)[:count]

    chosen.sort(key=lambda s: (s["file"], s["start"]))
    for number, site in enumerate(chosen, start=1):
        site["id"] = number

        # A pipeline defect needs a register, and it is named after the mutation
        # so that the numbering has to be settled first.
        pipe = site.pop("_pipeline", None)
        if pipe is not None:
            register = f"avl_pipe_{number}"
            site["register"] = register
            site["_edits"] = [
                (
                    pipe["decl_at"],
                    pipe["decl_at"],
                    PIPELINE_DECL.format(
                        target=pipe["target"],
                        reg=register,
                        indent=pipe["indent"],
                    ),
                ),
                (
                    site["start"],
                    site["end"],
                    PIPELINE_STMT.format(reg=register, rhs=pipe["rhs"], target=pipe["target"]),
                ),
            ]

    return chosen


def apply_mutation(src: str, site: dict) -> str:
    """
    Return the source with exactly one mutation applied.

    An operator mutation is a single splice over the operator token. A pipeline
    mutation also inserts the register it delays through, so a site carries a
    list of edits rather than just one.

    :param src: The original source text.
    :type src: str
    :param site: The mutation site to apply.
    :type site: dict
    :return: The mutated source text.
    :rtype: str
    """
    out: list[str] = []
    pos = 0
    touched: list[tuple[int, int]] = []
    delta = 0
    for start, end, text in sorted(site["_edits"]):
        out.append(src[pos:start])
        out.append(text)
        pos = end
        touched.append((start + delta, start + delta + len(text)))
        delta += len(text) - (end - start)
    out.append(src[pos:])

    return _mark("".join(out), touched, explain(site))


def explain(site: dict) -> str:
    """
    Return the one line description that goes in the marker comment.

    :param site: The mutation site.
    :type site: dict
    :return: What was done, and to what.
    :rtype: str
    """
    return f"{site['type']}: {site['original']} -> {site['mutated']}"


def _comment_at(line: str) -> int:
    """
    Return where a marker should be inserted on a line.

    A trailing line comment would swallow anything put after it, so the marker
    goes in front of one if there is one, and at the end of the line otherwise.

    :param line: The line of source.
    :type line: str
    :return: The index to insert at.
    :rtype: int
    """
    quoted = False
    for i, char in enumerate(line):
        if char == '"' and (i == 0 or line[i - 1] != "\\"):
            quoted = not quoted
        elif not quoted and line.startswith("//", i):
            return len(line[:i].rstrip()) if line[:i].strip() else i
    return len(line.rstrip())


def _mark(text: str, touched: list[tuple[int, int]], why: str) -> str:
    """
    Put a marker comment on every line a mutation changed.

    A mutant is ordinary RTL, which makes it easy to mistake for the golden
    source when one turns up in a debugger or a waveform. The marker says which
    lines are not the design.

    :param text: The mutated source.
    :type text: str
    :param touched: Ranges of the mutated source that the edits wrote.
    :type touched: list[tuple[int, int]]
    :param why: The description to put in the comment.
    :type why: str
    :return: The mutated source, with the changed lines marked.
    :rtype: str
    """
    lines = text.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    marked: set[int] = set()
    for lo, hi in touched:
        for number, line in enumerate(lines):
            begin, finish = starts[number], starts[number] + len(line)

            # A deletion - the unary class removes its operator rather than
            # swapping it - leaves nothing behind to overlap, so it is the line
            # it was taken from that changed.
            if lo == hi:
                if begin <= lo <= finish:
                    marked.add(number)
                continue

            if begin >= hi or finish <= lo:
                continue
            # An insertion that runs on past the end of a line leaves only
            # whitespace behind on the next one; that line did not change.
            if not text[max(lo, begin) : min(hi, finish)].strip():
                continue
            marked.add(number)

    comment = MUTATION_COMMENT.format(why=why)
    for number in marked:
        at = _comment_at(lines[number])
        lines[number] = f"{lines[number][:at]}  {comment}{lines[number][at:]}"

    return "\n".join(lines)


def _shift(site: dict, offset: int) -> int:
    """
    Return how far an offset moves once the mutation's edits are applied.

    :param site: The mutation site.
    :type site: dict
    :param offset: An offset into the golden source.
    :type offset: int
    :return: The number of characters the offset moves by.
    :rtype: int
    """
    return sum(len(t) - (e - s) for s, e, t in site["_edits"] if s < offset)


def prepare_output(outdir: Path) -> None:
    """
    Make the output directory ready to be written into, clearing what is there.

    The directory is emptied on every run, so the tool refuses to touch one it
    did not write. ``--output`` is a path like any other, and a path typed one
    directory too high would otherwise take the design down with the mutants.

    :param outdir: Directory to write the mutant subdirectories into.
    :type outdir: Path
    """
    if outdir.exists():
        if not outdir.is_dir():
            sys.exit(f"{outdir}: --output exists and is not a directory")

        if not (outdir / OUTPUT_MARKER).exists():
            sys.exit(
                f"{outdir}: --output already exists and was not written by avl-mutation-testing.\n"
                "  The output directory is emptied on every run, so this one is left alone.\n"
                "  Point --output somewhere else, or remove the directory yourself first."
            )

        shutil.rmtree(outdir)

    outdir.mkdir(parents=True)
    (outdir / OUTPUT_MARKER).write_text(OUTPUT_MARKER_TEXT)


def write_mutants(sources: dict[str, str], sites: list[dict], outdir: Path) -> None:
    """
    Write one complete copy of the design per mutation.

    Every source file is copied into each mutant directory so that the build
    only has to swap one include path; the file that owns the mutation is the
    only one that differs from the golden source.

    :param sources: Source text keyed by path, as given on the command line.
    :type sources: dict[str, str]
    :param sites: The selected mutation sites.
    :type sites: list[dict]
    :param outdir: Directory to write the mutant subdirectories into.
    :type outdir: Path
    """
    for site in sites:
        target = outdir / str(site["id"])
        target.mkdir(parents=True, exist_ok=True)
        for path, src in sources.items():
            text = apply_mutation(src, site) if path == site["file"] else src
            (target / Path(path).name).write_text(text)


# Equivalence check. The two designs are built into a miter whose assert holds
# only while their outputs agree, and the SAT solver is asked to break it.
#
# Finding a counterexample proves the mutant behaves differently, which is the
# answer worth having and the only one that is sound. Failing to find one within
# the unrolling bound does not prove equivalence, so that outcome is reported as
# equivalent-within-N-cycles rather than as a proof.
EQUIV_SCRIPT = """
{read_gold}
prep -top {top} -flatten
async2sync
design -stash gold
{read_gate}
prep -top {top} -flatten
async2sync
design -stash gate
design -copy-from gold -as gold {top}
design -copy-from gate -as gate {top}
miter -equiv -flatten -make_assert gold gate miter
hierarchy -top miter
sat -prove-asserts -seq {cycles} -set-init-zero miter
"""

# "no model found" means the solver could not make the outputs differ.
EQUIV_VERDICT = re.compile(r"model found: (FAIL|SUCCESS)!")

DIFFERENT = "different"
EQUIVALENT = "equivalent"
UNKNOWN = "unknown"
TIMEOUT = "timeout"
SKIPPED = "skipped"


def yosys_available() -> bool:
    """
    Return whether yosys can be found on PATH.

    :return: True if yosys is installed.
    :rtype: bool
    """
    return shutil.which("yosys") is not None


def check_equivalence(
    sources: list[str], mutant_dir: Path, top: str, cycles: int, timeout: int
) -> str:
    """
    Ask yosys whether a mutant behaves differently from the golden design.

    :param sources: The golden source files.
    :type sources: list[str]
    :param mutant_dir: Directory holding this mutant's copy of the sources.
    :type mutant_dir: Path
    :param top: Name of the top module to compare.
    :type top: str
    :param cycles: How many cycles to unroll the miter over.
    :type cycles: int
    :param timeout: Seconds to allow the solver before giving up.
    :type timeout: int
    :return: One of DIFFERENT, EQUIVALENT, UNKNOWN or TIMEOUT.
    :rtype: str
    """
    script = EQUIV_SCRIPT.format(
        read_gold="\n".join(f"read_verilog -sv {Path(s).resolve()}" for s in sources),
        read_gate="\n".join(
            f"read_verilog -sv {(mutant_dir / Path(s).name).resolve()}" for s in sources
        ),
        top=top,
        cycles=cycles,
    )

    try:
        done = subprocess.run(
            ["yosys", "-p", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TIMEOUT
    except OSError:
        return UNKNOWN

    found = EQUIV_VERDICT.findall(done.stdout + done.stderr)
    if not found:
        return UNKNOWN
    return DIFFERENT if found[-1] == "FAIL" else EQUIVALENT


def run_equivalence(
    sources: list[str], sites: list[dict], outdir: Path, top: str | None, cycles: int, timeout: int
) -> None:
    """
    Record an equivalence verdict on every mutation, in place.

    A mutant that cannot be told apart from the golden design is dead weight: no
    testbench can ever catch it, so it would be reported as a survivor and read
    as a hole in the verification that is not really there.

    :param sources: The golden source files.
    :type sources: list[str]
    :param sites: The selected mutation sites.
    :type sites: list[dict]
    :param outdir: Directory holding the mutant subdirectories.
    :type outdir: Path
    :param top: Top module to compare, or None to use the mutated module.
    :type top: str | None
    :param cycles: How many cycles to unroll the miter over.
    :type cycles: int
    :param timeout: Seconds to allow the solver per mutation.
    :type timeout: int
    """
    print("\nEquivalence (yosys)")
    for site in sites:
        verdict = check_equivalence(
            sources, outdir / str(site["id"]), top or site["module"], cycles, timeout
        )
        site["equivalence"] = verdict

        note = {
            DIFFERENT: "differs from the golden design",
            EQUIVALENT: f"no difference within {cycles} cycles - cannot ever be detected",
            UNKNOWN: "yosys could not decide",
            TIMEOUT: f"gave up after {timeout}s",
        }[verdict]
        print(f"  {site['id']:>3}  {verdict:<11} {note}")

    equivalent = [s for s in sites if s["equivalence"] == EQUIVALENT]
    if equivalent:
        print(
            f"\n  {len(equivalent)} mutation(s) look equivalent and are excluded from the score.\n"
            "  Raise --equiv-cycles if you think the difference needs longer to show."
        )


REPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AVL Mutation Report</title>
<style>
:root {
  --navy: #0b2c52;
  --blue: #4a82c4;
  --blue-pale: #eef4fc;
  --grey: #838383;
  --grey-dark: #45505c;
  --bg: #eef1f5;
  --panel: #ffffff;
  --border: #dde3ea;
  --text: #26313d;
  --good: #1f7a44;
  --good-bg: #e6f4ec;
  --bad: #a3341f;
  --bad-bg: #fbeae6;
  --warn: #8a6100;
  --warn-bg: #fdf3e0;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--text);
  background: var(--bg);
}
.app-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1.25rem; background: var(--panel);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(20, 30, 50, 0.06);
  flex-wrap: wrap;
}
.app-header img { height: 34px; width: auto; display: block; }
.app-header h1 { font-size: 1.05rem; font-weight: 600; margin: 0; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 1.25rem; }
.lede { color: var(--grey-dark); font-size: 0.9rem; line-height: 1.5; max-width: 70ch; }
.cards { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1.25rem 0; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 6px;
  padding: 0.6rem 0.9rem; min-width: 8rem;
}
.card .n { font-size: 1.5rem; font-weight: 600; color: var(--navy); }
.card .l { font-size: 0.75rem; color: var(--grey); text-transform: uppercase; letter-spacing: 0.04em; }
.panel {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; margin-bottom: 1rem; overflow: hidden;
}
.panel-header {
  display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap;
  padding: 0.6rem 0.9rem; background: var(--blue-pale);
  border-bottom: 1px solid var(--border);
}
.panel-header .id {
  font-weight: 700; color: var(--panel); background: var(--navy);
  border-radius: 4px; padding: 0.05rem 0.45rem; font-size: 0.85rem;
}
.panel-header .where { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; }
.panel-header .type {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--grey-dark); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.05rem 0.5rem; background: var(--panel);
}
.verdict { margin-left: auto; font-size: 0.78rem; font-weight: 600; border-radius: 10px; padding: 0.1rem 0.6rem; }
.v-different { color: var(--good); background: var(--good-bg); }
.v-equivalent { color: var(--bad); background: var(--bad-bg); }
.v-unknown, .v-timeout, .v-skipped { color: var(--warn); background: var(--warn-bg); }
.body { padding: 0.9rem; }
.change {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9rem; margin-bottom: 0.7rem;
}
.change .op { font-weight: 700; padding: 0 0.15rem; border-radius: 3px; }
.change .from .op { background: var(--good-bg); color: var(--good); }
.change .to .op { background: var(--bad-bg); color: var(--bad); }
.note { font-size: 0.85rem; color: var(--grey-dark); line-height: 1.5; margin: 0 0 0.7rem; }
pre.src {
  margin: 0; padding: 0.6rem 0; overflow-x: auto; background: #fbfcfe;
  border: 1px solid var(--border); border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.82rem; line-height: 1.45;
}
pre.src .ln { display: inline-block; width: 3.5rem; padding-right: 0.8rem; text-align: right; color: var(--grey); user-select: none; }
pre.src .row { display: block; padding: 0 0.6rem; white-space: pre; }
pre.src .row.del { background: var(--good-bg); }
pre.src .row.add { background: var(--bad-bg); }
pre.src .row .mark { display: inline-block; width: 1rem; font-weight: 700; }
pre.src .row.del .mark { color: var(--good); }
pre.src .row.add .mark { color: var(--bad); }
pre.src .row .op { font-weight: 700; text-decoration: underline; }
footer { color: var(--grey); font-size: 0.78rem; padding: 0 1.25rem 2rem; max-width: 1100px; margin: 0 auto; }
footer code { background: var(--panel); border: 1px solid var(--border); border-radius: 3px; padding: 0.05rem 0.3rem; }
</style>
</head>
<body>
<header class="app-header">
  __LOGO__
  <h1>AVL Mutation Report</h1>
</header>
<div class="wrap">
  <p class="lede">
    Mutation testing measures the <strong>testbench</strong>, not the design. Each
    mutation below is an artificial bug written into a standalone copy of the RTL.
    Re-run the existing tests against each one: a mutation the tests still pass is
    a class of bug the verification environment cannot catch.
  </p>
  <div class="cards">__CARDS__</div>
  __MUTATIONS__
</div>
<footer>
  __SOURCES__<br>
  Generated by <code>avl-mutation-testing</code> on __WHEN__.
</footer>
</body>
</html>
"""


def _line_of(src: str, offset: int) -> int:
    """
    Return the 1 based line number an offset falls on.

    :param src: The source text.
    :type src: str
    :param offset: Byte offset into the source.
    :type offset: int
    :return: The line number.
    :rtype: int
    """
    return src.count("\n", 0, offset) + 1


def _render_lines(src: str, numbers, mark: str, css: str, op: tuple[int, int] | None) -> str:
    """
    Render the given source lines as rows of the snippet.

    The lines need not be contiguous. A pipeline mutation changes a statement
    and declares a register well above it, and showing everything in between
    would bury the two lines that matter.

    :param src: The source text the lines come from.
    :type src: str
    :param numbers: Line numbers to render, 1 based.
    :type numbers: iterable[int]
    :param mark: Gutter marker, "-", "+" or a space.
    :type mark: str
    :param css: Extra class for the rows, "del", "add" or "".
    :type css: str
    :param op: Offsets of the operator to underline, or None.
    :type op: tuple[int, int] | None
    :return: The rendered rows.
    :rtype: str
    """
    lines = src.split("\n")
    starts = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1

    rows = []
    for number in numbers:
        if not 1 <= number <= len(lines):
            continue
        text = lines[number - 1]
        base = starts[number - 1]

        if op is not None and base <= op[0] < base + len(text):
            lo, hi = op[0] - base, op[1] - base
            body = (
                html.escape(text[:lo])
                + f'<span class="op">{html.escape(text[lo:hi])}</span>'
                + html.escape(text[hi:])
            )
        else:
            body = html.escape(text)

        rows.append(
            f'<span class="row {css}"><span class="ln">{number}</span>'
            f'<span class="mark">{mark}</span>{body}</span>'
        )
    return "".join(rows)


def _snippet(src: str, site: dict, context: int = 3) -> str:
    """
    Render the mutated lines in context, golden above mutant.

    :param src: The golden source text.
    :type src: str
    :param site: The mutation site.
    :type site: dict
    :param context: Unchanged lines to show either side.
    :type context: int
    :return: The rendered snippet.
    :rtype: str
    """
    mutated = apply_mutation(src, site)
    first = _line_of(src, site["start"])
    last = _line_of(src, site["end"])

    # Every changed line of the mutant carries the marker comment, so the marker
    # is what says which lines to show. It is also steadier than counting
    # offsets, which the markers themselves shift.
    marked = [n for n, line in enumerate(mutated.split("\n"), start=1) if MUTATION_MARK in line]

    highlight = None
    if site["op_start"] is not None:
        highlight = (site["op_start"], site["op_end"])

    return (
        '<pre class="src">'
        + _render_lines(src, range(first - context, first), " ", "", None)
        + _render_lines(src, range(first, last + 1), "-", "del", highlight)
        + _render_lines(mutated, marked or range(first, last + 1), "+", "add", None)
        + _render_lines(src, range(last + 1, last + context + 1), " ", "", None)
        + "</pre>"
    )


def write_report(path: Path, sources: dict[str, str], sites: list[dict], types: list[str]) -> None:
    """
    Write the HTML report explaining every mutation.

    :param path: File to write.
    :type path: Path
    :param sources: Source text keyed by path.
    :type sources: dict[str, str]
    :param sites: The selected mutation sites.
    :type sites: list[dict]
    :param types: The mutation classes that were searched.
    :type types: list[str]
    """
    from avl.tools.coverage_analysis import logo

    counts = Counter(s["type"] for s in sites)
    verdicts = Counter(s.get("equivalence", SKIPPED) for s in sites)

    cards = [f'<div class="card"><div class="n">{len(sites)}</div><div class="l">mutations</div></div>']
    for group in types:
        if counts[group]:
            cards.append(
                f'<div class="card"><div class="n">{counts[group]}</div><div class="l">{group}</div></div>'
            )
    if verdicts[DIFFERENT]:
        cards.append(
            f'<div class="card"><div class="n">{verdicts[DIFFERENT]}</div><div class="l">proved different</div></div>'
        )
    if verdicts[EQUIVALENT]:
        cards.append(
            f'<div class="card"><div class="n">{verdicts[EQUIVALENT]}</div><div class="l">equivalent</div></div>'
        )

    explain = {
        DIFFERENT: "yosys found an input sequence that tells this mutant apart from the "
                   "golden design, so a testbench that exercises this logic can catch it.",
        EQUIVALENT: "yosys could not tell this mutant apart from the golden design. No "
                    "testbench can catch what does not change behaviour, so a survivor "
                    "here is not a verification hole. Excluded from the score.",
        UNKNOWN: "yosys could not decide. Treat the result from simulation with care.",
        TIMEOUT: "the solver ran out of time. Treat the result from simulation with care.",
        SKIPPED: "not checked. Install yosys to have each mutation proved different from "
                 "the golden design before it is simulated.",
    }

    blocks = []
    for site in sites:
        verdict = site.get("equivalence", SKIPPED)
        original, mutated = html.escape(site["original"]), html.escape(site["mutated"])
        op_from, op_to = html.escape(site["operator"]), html.escape(site["mutated_operator"] or "removed")

        blocks.append(f"""
  <section class="panel">
    <div class="panel-header">
      <span class="id">{site['id']}</span>
      <span class="where">{html.escape(Path(site['file']).name)}:{site['line']}</span>
      <span class="type">{html.escape(site['type'])}</span>
      <span class="verdict v-{verdict}">{verdict}</span>
    </div>
    <div class="body">
      <div class="change">
        <span class="from">{original}</span> &rarr;
        <span class="to">{mutated}</span>
        &nbsp;<span style="color:var(--grey)">({op_from} &rarr; {op_to})</span>
      </div>
      <p class="note">{explain[verdict]}</p>
      {_snippet(sources[site['file']], site)}
    </div>
  </section>""")

    listed = ", ".join(html.escape(p) for p in sources)
    html_text = (
        REPORT_TEMPLATE.replace("__LOGO__", logo)
        .replace("__CARDS__", "".join(cards))
        .replace("__MUTATIONS__", "".join(blocks))
        .replace("__SOURCES__", f"Mutated from {listed}, searching for {html.escape(','.join(types))}.")
        .replace("__WHEN__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text)


def report_sites(sites: list[dict]) -> None:
    """
    Print the mutation catalogue.

    :param sites: The selected mutation sites.
    :type sites: list[dict]
    """
    if not sites:
        print("No mutation sites found.")
        return

    # A design split across several files has file names of different lengths,
    # so the columns are sized to what is actually there.
    where = {s["id"]: f"{Path(s['file']).name}:{s['line']}" for s in sites}
    place = max(len(w) for w in where.values())
    width = max(len(s["original"]) for s in sites)

    for site in sites:
        print(
            f"  {site['id']:>3}  {where[site['id']]:<{place}} "
            f"{site['type']:<8} {site['original']:<{width}}  ->  {site['mutated']}"
        )
    print(f"\n{len(sites)} mutation(s)")


# An AVL log record, e.g. "  1800.00ns ERROR    sb   Field "result" ...". AVL
# logs an error and keeps going rather than aborting the test, so the log is
# where a scoreboard mismatch shows up; only fatal and critical stop the run.
LOG_RECORD = re.compile(r"^\s*\S+ns\s+(ERROR|CRITICAL|FATAL)\b", re.MULTILINE)


def _detected(results: Path, output: str) -> bool:
    """
    Return whether a run noticed anything wrong with the design.

    A mutant counts as detected if the testbench logged an error, if cocotb
    recorded a test failure, or if the run did not complete at all. The first of
    those is the usual one: an AVL scoreboard mismatch is an ERROR record, and
    AVL does not turn that into a cocotb failure by itself.

    :param results: Path to the cocotb results XML file.
    :type results: Path
    :param output: Combined stdout and stderr of the simulation.
    :type output: str
    :return: True if the run reported a problem or did not complete.
    :rtype: bool
    """
    if LOG_RECORD.search(output):
        return True

    if not results.exists():
        return True

    try:
        root = ET.parse(results).getroot()
    except ET.ParseError:
        return True

    return any(case.find("failure") is not None for case in root.iter("testcase"))


def grade(catalogue: Path, make: str, results: Path, var: str, cwd: Path, archive: Path | None) -> int:
    """
    Build and run the testbench once per mutation and report which were caught.

    The golden run comes first. If the testbench cannot pass the unmutated
    design there is nothing to measure, so that is a hard error.

    :param catalogue: Path to the JSON catalogue written by the generate step.
    :type catalogue: Path
    :param make: The make command used to run a single simulation.
    :type make: str
    :param results: Path to the cocotb results file, relative to ``cwd``.
    :type results: Path
    :param var: Make variable carrying the mutant to build.
    :type var: str
    :param cwd: Directory to run make in.
    :type cwd: Path
    :return: Process exit status; non-zero if any mutation survived.
    :rtype: int
    """
    sites = json.loads(catalogue.read_text())

    def run(mutant: int, name: str) -> bool:
        (cwd / results).unlink(missing_ok=True)
        done = subprocess.run(
            f"{make} {var}={mutant}",
            shell=True,
            cwd=cwd,
            env=dict(os.environ),
            capture_output=True,
            text=True,
        )
        output = done.stdout + done.stderr

        # Keep each run's log and results so a surprising verdict can be looked
        # into afterwards without re-running the campaign.
        if archive is not None:
            target = archive / name
            target.mkdir(parents=True, exist_ok=True)
            (target / "sim.log").write_text(output)
            if (cwd / results).exists():
                shutil.copyfile(cwd / results, target / results.name)

        return _detected(cwd / results, output)

    print(f"Mutation regression: {len(sites)} mutation(s)\n")

    print("Golden design")
    if run(0, "golden"):
        print("  FAILED - the testbench does not pass the unmutated design.")
        print("  Fix that first; every mutant would otherwise score as detected.")
        if archive is not None:
            print(f"  Log: {archive / 'golden' / 'sim.log'}")
        return 2
    print("  passed\n")

    survivors = []
    equivalent = []
    places = {s["id"]: f"{Path(s['file']).name}:{s['line']}" for s in sites}
    place = max([len(p) for p in places.values()] + [len("WHERE")])
    width = max(len(f"{s['original']} -> {s['mutated']}") for s in sites) if sites else 0

    header = f"  {'ID':>3}  {'WHERE':<{place}} {'MUTATION':<{width}}  STATUS"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for site in sites:
        caught = run(site["id"], str(site["id"]))
        change = f"{site['original']} -> {site['mutated']}"

        # A mutant yosys could not tell apart from the golden design is not a
        # hole in the testbench - there is nothing there to catch - so it is
        # called out separately and left out of the score.
        if not caught and site.get("equivalence") == EQUIVALENT:
            status = "EQUIVALENT"
            equivalent.append(site)
        elif caught:
            status = "DETECTED"
        else:
            status = "SURVIVED"
            survivors.append(site)

        print(f"  {site['id']:>3}  {places[site['id']]:<{place}} {change:<{width}}  {status}")

    scored = len(sites) - len(equivalent)
    detected = scored - len(survivors)
    score = 100.0 * detected / scored if scored else 100.0

    print("  " + "-" * (len(header) - 2))
    print(
        f"  {detected} detected, {len(survivors)} survived"
        + (f", {len(equivalent)} equivalent (not scored)" if equivalent else "")
    )
    print(f"  Score {score:.1f}% ({detected}/{scored})")

    if archive is not None:
        print(f"\n  Logs: {archive}/<id>/sim.log")

    # Written beside the catalogue so that whatever runs the campaign can read
    # the outcome rather than parse it back out of the log.
    (catalogue.parent / "summary.json").write_text(
        json.dumps(
            {
                "mutations": len(sites),
                "detected": detected,
                "survived": len(survivors),
                "equivalent": len(equivalent),
                "scored": scored,
                "score": round(score, 1),
            },
            indent=2,
        )
        + "\n"
    )

    if survivors:
        print("\nSurvivors are holes in the testbench:")
        for site in survivors:
            print(f"  {Path(site['file']).name}:{site['line']}  {site['original']} -> {site['mutated']}")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Generate RTL mutations and grade the testbench that should catch them.")
    parser.add_argument("--source", nargs="+", type=str, help="SystemVerilog source file(s) to mutate.")
    parser.add_argument("--output", type=str, help="Directory to write the mutants into.", default="mutants")
    parser.add_argument("--count", type=int, help="Number of mutations to generate. Default is all candidates.", default=None)
    parser.add_argument(
        "--types",
        type=str,
        help=f"Comma separated mutation classes: {','.join(ALL_TYPES)}. Default is all.",
        default=",".join(ALL_TYPES),
    )
    parser.add_argument("--seed", type=int, help="Seed for random site selection. Default takes the first --count in source order.", default=None)
    parser.add_argument("--json", type=str, help="Write the mutation catalogue to this JSON file.", default=None)
    parser.add_argument("--html", type=str, help="HTML report explaining the mutations. Default <output>/mutations.html.", default=None)
    parser.add_argument("--no-equiv", action="store_true", help="Skip the yosys equivalence check even if yosys is installed.")
    parser.add_argument("--equiv-cycles", type=int, help="Cycles to unroll the equivalence miter over. Default 8.", default=8)
    parser.add_argument("--equiv-timeout", type=int, help="Seconds to allow the solver per mutation. Default 60.", default=60)
    parser.add_argument("--top", type=str, help="Top module to compare. Default is the module the mutation is in.", default=None)
    parser.add_argument("--list", action="store_true", help="List the mutation sites without writing anything.")
    parser.add_argument("--list-types", action="store_true", help="List the available mutation classes and exit.")
    parser.add_argument("--grade", action="store_true", help="Build and run the testbench once per mutation and report which were caught.")
    parser.add_argument("--make", type=str, help="Command used to run one simulation when grading.", default="make sim")
    parser.add_argument("--directory", type=str, help="Directory to run make in when grading.", default=".")
    parser.add_argument("--results", type=str, help="cocotb results file inspected when grading.", default="results.xml")
    parser.add_argument("--var", type=str, help="Make variable naming the mutant to build.", default="AVL_MUTANT")
    parser.add_argument("--archive", type=str, help="Directory to keep each run's log and results in when grading.", default=None)

    args = parser.parse_args()

    if args.list_types:
        for group, ops in MUTATIONS.items():
            print(f"{group}:")
            for kind, (old, new) in ops.items():
                arrow = f"{old} -> {new}" if new else f"{old} -> (removed)"
                print(f"  {arrow:<18} {kind}")
        print(f"{PIPELINE}:")
        print(f"  {'<= (+1 cycle)':<18} {PIPELINE_KIND}")
        print("    A registered signal gains an extra pipeline stage, so it")
        print("    arrives one cycle late. Only whole signals assigned from")
        print("    something other than a constant are eligible.")
        print(f"{ARRAY_PACKED}:")
        print(f"  {'[W-1:0] -> [0:W-1]':<18} {ARRAY_KIND}")
        print("    A packed dimension is turned around, renumbering the bits.")
        print("    Shows up wherever the signal is bit selected.")
        print(f"{ARRAY_UNPACKED}:")
        print(f"  {'[0:N-1] -> [N-1:0]':<18} {ARRAY_KIND}")
        print("    An unpacked dimension is turned around, reordering the")
        print("    elements. Shows up through assignment patterns and")
        print("    iteration order.")
        print(f"{BLOCKING}:")
        print(f"  {'x <= a;  ->  x = a;':<18} {BLOCKING_KIND}")
        print("    A nonblocking assignment becomes blocking, so whatever reads")
        print("    the target next in the same block sees the new value rather")
        print("    than the old one. Edge triggered blocks only, and only where")
        print("    the target is read again later - nowhere else can tell.")
        print(f"{NONBLOCKING}:")
        print(f"  {'x = a;  ->  x <= a;':<18} {NONBLOCKING_KIND}")
        print("    The same swap the other way. Combinational blocks are")
        print("    excluded: a nonblocking assignment there is a COMBDLY error,")
        print("    not a defect.")
        print(f"{CONDITION}:")
        print("  if (c) -> if (1'b1)  ConditionalStatement/ConditionalExpression")
        print("    A branch is held permanently open, and permanently shut, so")
        print("    each condition yields two mutations. Asks whether both arms")
        print("    are exercised and whether anything checks the consequence.")
        print(f"{STATEMENT}:")
        print(f"  {'y <= a;  ->  ;':<18} {STATEMENT_KIND}")
        print("    A registered assignment is dropped, so the register holds")
        print("    instead of updating. Clocked blocks only, where a missing")
        print("    assignment legally means retain.")
        print(f"{OPERAND}:")
        print(f"  {'a - b  ->  b - a':<18} {'non-commutative binary expressions'}")
        print("    The operands of a non-commutative operator are swapped. The")
        print("    operator is kept and the meaning reversed. Commutative")
        print("    operators are excluded; swapping those changes nothing.")
        print(f"{WIDTH}:")
        print(f"  {'[7:0] -> [6:0]':<18} {WIDTH_KIND}")
        print("    A packed declaration loses its top bit. Every reference is")
        print("    cast back to the original width and every assignment cast")
        print("    down to the new one, so only the signal itself narrows and")
        print("    the design still compiles without width warnings. Internal")
        print("    declarations with literal bounds only, and only where every")
        print("    reference can carry a cast - a bit select cannot, and nor")
        print("    can a port connection or a concatenation being assigned to.")
        print(f"{SIGN}:")
        print(f"  {'x = -(x)':<18} {'/'.join(sorted(SIGN_KINDS))}")
        print("    The value assigned to a signed variable is negated. Only")
        print("    variables declared signed, or of a type that is signed by")
        print("    default, are eligible.")
        return 0

    if args.grade:
        if not args.json:
            parser.error("--grade needs --json pointing at the catalogue written by the generate step")
        return grade(
            Path(args.json),
            args.make,
            Path(args.results),
            args.var,
            Path(args.directory),
            Path(args.archive) if args.archive else None,
        )

    if not args.source:
        parser.error("--source is required")

    types = [t.strip() for t in args.types.split(",") if t.strip()]
    unknown = [t for t in types if t not in ALL_TYPES]
    if unknown:
        parser.error(f"unknown mutation type(s): {','.join(unknown)}. Choose from {','.join(ALL_TYPES)}")

    sources = {}
    candidates = []
    for path in args.source:
        src, sites = find_sites(path, types)
        sources[path] = src
        candidates.extend(sites)

    selected = select_sites(candidates, args.count, args.seed, types)

    if args.count is not None and len(selected) < args.count:
        print(
            f"Warning: asked for {args.count} mutation(s) but only {len(selected)} "
            f"site(s) of type {','.join(types)} were found.",
            file=sys.stderr,
        )

    report_sites(selected)

    if args.list:
        return 0

    outdir = Path(args.output)
    prepare_output(outdir)
    write_mutants(sources, selected, outdir)

    # Prove each mutation actually changes the design before anyone spends
    # simulation time on it. Optional: without yosys the flow still works, it
    # just cannot tell a real survivor from an equivalent mutant.
    if args.no_equiv or not selected:
        for site in selected:
            site["equivalence"] = SKIPPED
    elif not yosys_available():
        for site in selected:
            site["equivalence"] = SKIPPED
        print("\nyosys not found - skipping the equivalence check.")
        print("Install it to have each mutation proved different from the golden design.")
    else:
        run_equivalence(
            list(sources), selected, outdir, args.top, args.equiv_cycles, args.equiv_timeout
        )

    report = Path(args.html) if args.html else outdir / "mutations.html"
    write_report(report, sources, selected, types)
    print(f"\nReport: {report}")

    if args.json:
        catalogue = Path(args.json)
        catalogue.parent.mkdir(parents=True, exist_ok=True)
        public = [{k: v for k, v in s.items() if not k.startswith("_")} for s in selected]
        catalogue.write_text(json.dumps(public, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
