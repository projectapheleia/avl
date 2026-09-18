# Two blocking temporaries read by the registered output below them. Turning
# either into a nonblocking assignment hands the output the previous cycle's
# value instead of this one.
MUTATION_TYPES := nonblocking
MUTATION_COUNT := 2
