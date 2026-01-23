.SILENT:
MAKEFILES := $(shell find */* -type l -name Makefile)
SIMS      := $(patsubst %/Makefile,%/sim,$(MAKEFILES))
CLEANS    := $(patsubst %/Makefile,%/clean,$(MAKEFILES))

%sim: %Makefile
	rm -f $(dir $<).passed; \
	touch $(dir $<).failed; \
	$(MAKE) -C $(dir $<) sim > $(dir $<)/sim.log 2>&1; \
	if [ $$? -ne 0 ]; then \
		echo "$(dir $<) : FAILED"; \
	else \
		grep 'failure message=' $(dir $<)/results.xml > /dev/null 2>&1; \
		if [ $$? -ne 0 ]; then \
			echo "$(dir $<) : PASSED"; \
			touch $(dir $<).passed; \
			rm -f $(dir $<).failed; \
		else \
			echo "$(dir $<) : FAILED"; \
		fi \
	fi

%clean: %Makefile
	$(MAKE) -C $(dir $<) clean > /dev/null 2>&1
	rm -f $(dir $<).passed $(dir $<).failed

.PHONY: list
list: $(MAKEFILES)
	@$(foreach dep, $^, echo $(dep);)

.PHONY: sim
sim: $(SIMS)
	pass_count=$$(find . -name '*.passed' | wc -l); \
	fail_count=$$(find . -name '*.failed' | wc -l); \
	echo "$$pass_count tests passed, $$fail_count tests failed"; \
	if [[ $$fail_count > 0 ]]; then exit 1; fi

.PHONY: clean
clean: $(CLEANS)
	@echo "Clean complete"
