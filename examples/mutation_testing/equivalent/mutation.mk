# A negative test for the equivalence check. Two mutations: the add of zero is
# a no-op that no testbench could ever catch, and the xor is an ordinary defect
# that should be. Needs yosys - without it the no-op cannot be told apart from
# a real hole in the testbench.
MUTATION_TYPES    := arith,bitwise
MUTATION_COUNT    := 2
MUTATION_REQUIRES := yosys
