# Two pipeline stages, each read by the stage below it. Turning either handover
# into a blocking assignment collapses a stage, so the answer arrives a cycle
# early. The two assignments nothing reads again are not offered - a blocking
# and a nonblocking assignment are indistinguishable there.
MUTATION_TYPES := blocking
MUTATION_COUNT := 2
