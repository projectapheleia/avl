# The design is split across rtl/example_hdl.sv, rtl/alu_arith.sv and
# rtl/alu_logic.sv. GOLDEN_RTL picks up all of them, so mutations land in
# whichever file holds the site.
#
# Five mutations across four classes: the add and the subtract in the arith
# unit, the and in the logic unit, the zero flag comparison in the top, and an
# extra cycle of delay on one of the output registers.
MUTATION_TYPES := arith,compare,bitwise,pipeline
MUTATION_COUNT := 5
