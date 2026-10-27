# Copied from color's Makefile, which came from security's, font's and model's.
# SUITE, PROJECT and the dependency list are what changed; color's oracle
# section and its fuzz rules are removed rather than renamed (nothing here
# parses untrusted input yet, and a gate that names nothing it checks is worse
# than absent).
#
# What this library adds to the usual set is the shape family's determinism and
# structure gates (no fused multiply-adds, no x87, no libm, and dependencies
# only on the libraries EDGES_ALLOWED names), each in TEST_GATES and each shown
# to fail by check-gates:
#
#   check-fp-contract  every compile-flag set names -ffp-contract=off
#   check-edges        #includes and NEEDED entries stay inside EDGES_ALLOWED
#   check-libm         no libm function is referenced or defined
#   check-no-x87       no x87 instruction in the objects (the i686 arm is run
#                      by suite/tools/xarch/shape.sh, which needs a cross compiler)
#   check-gates        plants a violation for each of the above and requires
#                      the gate to fail on it, and to pass its control
#
# The test-executable rules keep section 6's shape: the static archive is a
# normal prerequisite of every test because the recipe links it, and the .so
# is order-only because check-symbols wants it and the tests do not link it.

SUITE := ghoti.io
PROJECT := math

# The libraries this one depends on, by the end of the milestone: the fourth
# field of its line in suite/libraries.txt, without the optional ones.
# Each is found by pkg-config and is a hard error when it is not.
DEPS := cutil

# The libraries whose headers this one may include and whose shared objects it
# may link (check-edges), as a regular expression alternation. Itself is always
# allowed. It is wider than DEPS where a dependency's own public headers
# include a further library (AD-2: transitive reach is not a manifest edge, but
# it is not a violation to include what a dependency's header already pulls in).
EDGES_ALLOWED := cutil

# no, for every library: nothing is exempt from check-libm (AD-22, amended
# 2026-10-18: math supplies sqrt, floor and the rest itself, so its own objects
# are judged too). Anything else fails check-gates.
LIBM_EXEMPT := no

BUILD ?= release
MAJOR_VERSION := 0
MINOR_VERSION := 0.0
VERSION_MINOR_ONLY := $(word 1,$(subst ., ,$(MINOR_VERSION)))
VERSION_PATCH_ONLY := $(or $(word 2,$(subst ., ,$(MINOR_VERSION))),0)
VERSION := $(MAJOR_VERSION).$(MINOR_VERSION)

# Names this build everywhere: the .pc file, the install directory, the soname
# and the symbol token. Defaults to the major version. Override for a build
# that wants its own identity: make BRANCH=-dev
BRANCH ?= -$(MAJOR_VERSION)

ifeq ($(BRANCH),-$(MAJOR_VERSION))
VERSION_STRING := $(VERSION)
else
VERSION_STRING := $(VERSION)$(BRANCH)
endif

# override: BRANCH may have come from the command line, and a command-line
# variable otherwise beats a plain assignment. Without it, `make BRANCH=-dev
# BUILD=debug` produced a debug build carrying the release token.
ifeq ($(BUILD),debug)
    override BRANCH := $(BRANCH)-debug
    override VERSION_STRING := $(VERSION_STRING)-debug
endif

# Decided here, before the platform rewrite below. `BUILD := linux/$(BUILD)`
# is a plain assignment, so a command-line BUILD=debug stays "debug" and an
# environment BUILD=debug becomes "linux/debug". Testing it up here is true
# in both cases. Release is -O2 because that is what ships.
ifeq ($(BUILD),debug)
OPT_CFLAGS := -O0
else
OPT_CFLAGS := -O2
endif

# The shared object records only the libraries it uses (AD-2: transitive reach
# does not count). pkg-config --libs of a dependency lists that dependency's own
# dependencies too (image brings compress and security), and without this they
# would all appear in NEEDED, where check-edges rightly refuses them.
ifeq ($(shell uname -s),Linux)
AS_NEEDED := -Wl,--as-needed
else
AS_NEEDED :=
endif

BASE_NAME := lib$(SUITE)-$(PROJECT)$(BRANCH).so
LIBVER_SYMBOL := $(shell echo "ghotiio_$(PROJECT)$(BRANCH)" | sed 's/[.-]/_/g')
BASE_NAME_PREFIX := lib$(SUITE)-$(PROJECT)$(BRANCH)
SO_NAME := $(BASE_NAME).$(MAJOR_VERSION)
STATIC_TARGET := $(BASE_NAME_PREFIX).a
ENV_VARS :=

# Do not assign PKG_CONFIG_PATH. Make exports an inherited variable with
# whatever value the makefile last gave it, so overwriting it handed every
# sub-make a different path from the parent's.
PKG_CONFIG_PATH_ENV := $(PKG_CONFIG_PATH)

UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S), Linux)
	OS_NAME := Linux
	LIB_EXTENSION := so
	OS_SPECIFIC_CXX_FLAGS := -shared
	OS_SPECIFIC_LIBRARY_NAME_FLAG := -Wl,-soname,$(SO_NAME)
	TARGET := $(SO_NAME).$(MINOR_VERSION)
	EXE_EXTENSION :=
	PC_INSTALL_PATH := /usr/local/share/pkgconfig
	INCLUDE_INSTALL_PATH := /usr/local/include
	LIB_INSTALL_PATH := /usr/local/lib
	PC_INCLUDE_DIR := $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
	PC_LIB_DIR := $(LIB_INSTALL_PATH)/$(SUITE)
	override BUILD := linux/$(BUILD)

else ifeq ($(UNAME_S), Darwin)
	OS_NAME := Mac
	LIB_EXTENSION := dylib
	OS_SPECIFIC_CXX_FLAGS := -shared
	OS_SPECIFIC_LIBRARY_NAME_FLAG := -Wl,-install_name,$(BASE_NAME_PREFIX).dylib
	TARGET := $(BASE_NAME_PREFIX).dylib
	EXE_EXTENSION :=
	PC_INSTALL_PATH := /usr/local/share/pkgconfig
	INCLUDE_INSTALL_PATH := /usr/local/include
	LIB_INSTALL_PATH := /usr/local/lib
	PC_INCLUDE_DIR := $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
	PC_LIB_DIR := $(LIB_INSTALL_PATH)/$(SUITE)
	override BUILD := mac/$(BUILD)

# TODO(windows): the Windows branches in this file were adapted from color's
# and font's and have never been run for this library. suite/tools/xwin/shape.sh
# runs the cross-target hash fixture under wine, not this Makefile.
else ifeq ($(findstring MINGW32_NT,$(UNAME_S)),MINGW32_NT)
	OS_NAME := Windows
	LIB_EXTENSION := dll
	OS_SPECIFIC_CXX_FLAGS := -shared
	OS_SPECIFIC_LIBRARY_NAME_FLAG = -Wl,--out-implib,$(APP_DIR)/$(BASE_NAME_PREFIX).dll.a
	TARGET := $(BASE_NAME_PREFIX).dll
	EXE_EXTENSION := .exe
	PC_INSTALL_PATH := /mingw32/lib/pkgconfig
	INCLUDE_INSTALL_PATH := /mingw32/include
	LIB_INSTALL_PATH := /mingw32/lib
	BIN_INSTALL_PATH := /mingw32/bin
	PC_INCLUDE_DIR = $(shell cygpath -m $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH))
	PC_LIB_DIR = $(shell cygpath -m $(LIB_INSTALL_PATH)/$(SUITE))
	override BUILD := win32/$(BUILD)

else ifeq ($(findstring MINGW64_NT,$(UNAME_S)),MINGW64_NT)
	OS_NAME := Windows
	LIB_EXTENSION := dll
	OS_SPECIFIC_CXX_FLAGS := -shared
	OS_SPECIFIC_LIBRARY_NAME_FLAG = -Wl,--out-implib,$(APP_DIR)/$(BASE_NAME_PREFIX).dll.a
	TARGET := $(BASE_NAME_PREFIX).dll
	EXE_EXTENSION := .exe
	PC_INSTALL_PATH := /mingw64/lib/pkgconfig
	INCLUDE_INSTALL_PATH := /mingw64/include
	LIB_INSTALL_PATH := /mingw64/lib
	BIN_INSTALL_PATH := /mingw64/bin
	PC_INCLUDE_DIR = $(shell cygpath -m $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH))
	PC_LIB_DIR = $(shell cygpath -m $(LIB_INSTALL_PATH)/$(SUITE))
	override BUILD := win64/$(BUILD)

else
    $(error Unsupported OS: $(UNAME_S))
endif

ifdef PREFIX
INCLUDE_INSTALL_PATH := $(PREFIX)/include
LIB_INSTALL_PATH := $(PREFIX)/lib
BIN_INSTALL_PATH := $(PREFIX)/bin
PC_INSTALL_PATH := $(PREFIX)/share/pkgconfig
ifeq ($(OS_NAME), Windows)
PC_INCLUDE_DIR = $(shell cygpath -m $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH))
PC_LIB_DIR = $(shell cygpath -m $(LIB_INSTALL_PATH)/$(SUITE))
else
PC_INCLUDE_DIR := $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
PC_LIB_DIR := $(LIB_INSTALL_PATH)/$(SUITE)
endif
LDCONF_INSTALL_PATH :=
endif

PKG_CONFIG_LOOKUP_PATH := $(if $(PKG_CONFIG_PATH_ENV),$(PKG_CONFIG_PATH_ENV):)$(PC_INSTALL_PATH)

# AD-17 and AD-26: a 32-bit x86 host computes a double in SSE, not in the x87
# stack, whose 80-bit registers round a sum twice. A cross build for i686 gets
# the same flags from xarch_fp_cflags in suite/tools/xarch/targets.sh.
ifneq ($(filter i386 i486 i586 i686,$(shell uname -m)),)
ARCH_FP_FLAGS := -msse2 -mfpmath=sse
else
ARCH_FP_FLAGS :=
endif

# -ffp-contract=off is named, not inherited (CONVENTIONS section 6): a fused
# multiply-add rounds once where the reference rounds twice. GCC contracts by
# default only in the GNU modes and clang's default is "on". Every set below
# that names a -std carries it, and tools/check-fp-contract.sh fails when one
# does not, the sanitizer sets included. A fuzz build added later needs its
# own FUZZ_CFLAGS and FUZZ_CXXFLAGS naming it, which the gate will then read.
CXX := g++
CXXFLAGS := -pedantic-errors -Wall -Wextra -Werror -Wno-error=unused-function -Wfatal-errors -std=c++20 -O1 -g -ffp-contract=off $(ARCH_FP_FLAGS) $(EXTRA_CXXFLAGS)
CC := cc
# -Wstrict-aliasing=1 and -fstrict-aliasing, named rather than inherited.
# -Wall sets the aliasing warning to level 3, which is silent on the probe
# check-aliasing compiles. An explicit level beats -Wall from either side.
# -fstrict-aliasing is off below -O2 unless named, so a debug or coverage
# tree would otherwise have the warning armed and the assumption off.
# The probe is a pointer parameter stored through a second variable: that
# shape is reported at level 1 and silent at 0, 2, and 3. Do not simplify it
# to `*(int *)&local`, which fires at every level from 1 up and certifies
# nothing. check-aliasing is the measurement.
CFLAGS := -pedantic-errors -Wall -Wextra -Werror -Wfloat-conversion -fstrict-aliasing -Wstrict-aliasing=1 -Wno-error=unused-function -Wfatal-errors -std=c17 $(OPT_CFLAGS) -ffp-contract=off -fno-math-errno $(ARCH_FP_FLAGS) -g $(EXTRA_CFLAGS)
ifeq ($(OS_NAME), Windows)
CFLAGS += -DGMATH_STATIC
CXXFLAGS += -DGMATH_STATIC
endif
LIB_CFLAGS := $(CFLAGS) -fvisibility=hidden -DGMATH_BUILD $(EXTRA_CFLAGS)
LDFLAGS := -L /usr/lib -lstdc++ -lm $(EXTRA_LDFLAGS)
ifdef PREFIX
LDFLAGS += -Wl,-rpath,$(LIB_INSTALL_PATH)/$(SUITE)
ifeq ($(OS_NAME), Windows)
export PATH := $(BIN_INSTALL_PATH):$(PATH)
endif
endif

BUILD_DIR := ./build/$(BUILD)
OBJ_DIR := $(BUILD_DIR)/objects
FLAGS_STAMP := $(OBJ_DIR)/.flags
GEN_DIR := $(BUILD_DIR)/generated
APP_DIR := $(BUILD_DIR)/apps

ifeq ($(UNAME_S), Linux)
	LIB_CFLAGS += -fPIC
endif

INCLUDE := -I include/ -I $(GEN_DIR)/

# libver-gen is here so that suite/tools/xarch/shape.sh can write the generated
# header for a cross build without any dependency installed.
DEPLESS_GOALS := docs docs-pdf clean fuzz-clean cloc help libver-gen
ifeq ($(filter-out $(DEPLESS_GOALS),$(or $(MAKECMDGOALS),all)),)
SKIP_DEP_CHECK := 1
endif

# The names carry $(BRANCH). ghoti.io-cutil never matches the installed file.
DEP_PCS := $(foreach d,$(DEPS),ghoti.io-$(d)$(BRANCH))
$(foreach pc,$(DEP_PCS),$(if $(shell PKG_CONFIG_PATH=$(PKG_CONFIG_LOOKUP_PATH) pkg-config --exists $(pc) 2>/dev/null && echo yes),,$(if $(SKIP_DEP_CHECK),,$(error $(pc) was not found by pkg-config. Build and install it into a prefix (install.sh in the suite repository, github.com/Ghoti-io/suite, builds every library in order) and pass the same PREFIX here - or point PKG_CONFIG_PATH at the directory holding its .pc file. There is deliberately no sibling-checkout fallback.))))
DEP_CFLAGS := $(shell PKG_CONFIG_PATH=$(PKG_CONFIG_LOOKUP_PATH) pkg-config --cflags $(DEP_PCS) 2>/dev/null)
DEP_LIBS := $(shell PKG_CONFIG_PATH=$(PKG_CONFIG_LOOKUP_PATH) pkg-config --libs $(DEP_PCS) 2>/dev/null)
INCLUDE += $(DEP_CFLAGS)

SOURCES := $(shell find src -type f -name '*.c')
LIBOBJECTS := $(patsubst src/%.c,$(OBJ_DIR)/%.o,$(SOURCES))

TESTFLAGS := `PKG_CONFIG_PATH=$(PKG_CONFIG_LOOKUP_PATH) pkg-config --libs --cflags gtest`

# coverage clears this: --coverage links the gcov runtime, whose mangle_path
# check-symbols is right to reject in a shipping library.
TEST_GATES ?= check-symbols check-aliasing check-stamps check-fp-contract check-edges check-libm check-no-x87 check-gates check-corpus-hash check-planted check-oracle-fresh check-remainder-corpus check-extrema-corpus check-logbase-oracle check-exp2-oracle run-examples

VALGRIND_FLAGS := --leak-check=full --show-leak-kinds=definite,indirect,possible --track-origins=yes --error-exitcode=1 --suppressions=tests/valgrind.supp

TEST_HELPER_SRC := $(wildcard tests/test_helpers.cpp)
TEST_HELPER_OBJ := $(patsubst tests/%.cpp,$(OBJ_DIR)/tests/%.o,$(TEST_HELPER_SRC))

# The archive, not the shared library: a static link resolves hidden symbols.
# --whole-archive because a constructor-registered object would otherwise be
# dropped. The archive is a normal prerequisite of every test, so a clean
# tree builds it; the .so is order-only because check-symbols wants it and
# the tests do not link it.
SELF_LIBRARY := -Wl,--whole-archive $(APP_DIR)/$(STATIC_TARGET) -Wl,--no-whole-archive $(DEP_LIBS)

ifeq ($(OS_NAME), Windows)
TEST_LDFLAGS := -Wl,--wrap=__mingw_fprintf
else
TEST_LDFLAGS :=
endif

TEST_PAIRS := $(shell find tests -type f -name 'test_*.cpp' 2>/dev/null | sort | grep -v test_helpers | while read f; do \
	echo "$$f|$$(basename "$$f" .cpp | sed 's/test_/test/; s/^test\([a-z]\)/test\U\1/')"; done)
TEST_SOURCES := $(foreach pair,$(TEST_PAIRS),$(word 1,$(subst |, ,$(pair))))
TEST_NAMES := $(foreach pair,$(TEST_PAIRS),$(word 2,$(subst |, ,$(pair))))
TEST_EXECUTABLES := $(addprefix $(APP_DIR)/,$(addsuffix $(EXE_EXTENSION),$(TEST_NAMES)))

EXAMPLE_SOURCES := $(shell find examples -type f -name '*.c' 2>/dev/null)
EXAMPLES := $(patsubst examples/%.c,$(APP_DIR)/examples/%$(EXE_EXTENSION),$(EXAMPLE_SOURCES))

all: $(APP_DIR)/$(TARGET) $(APP_DIR)/$(STATIC_TARGET) ## Build shared + static libraries

TEST_DEPFILES := $(foreach pair,$(TEST_PAIRS),$(OBJ_DIR)/tests/$(basename $(notdir $(word 1,$(subst |, ,$(pair))))).d)
DEPFILES := $(LIBOBJECTS:.o=.d) $(TEST_HELPER_OBJ:.o=.d) $(TEST_DEPFILES)
-include $(DEPFILES)

LIBVER_GEN := $(GEN_DIR)/ghoti.io/$(PROJECT)/libver_gen.h

.PHONY: force-libver
force-libver:

$(LIBVER_GEN): force-libver
	@if [ -z "$(LIBVER_SYMBOL)" ]; then \
		printf "### LIBVER_SYMBOL is empty ###\n" >&2; \
		printf "Every exported symbol would lose its version namespace.\n" >&2; \
		exit 1; \
	fi
	@mkdir -p $(@D)
	@printf '%s\n' \
		'// Generated by the Makefile. Do not edit.' \
		'#ifndef GHOTI_IO_GMATH_LIBVER_GEN_H' \
		'#define GHOTI_IO_GMATH_LIBVER_GEN_H' \
		'' \
		'/** The symbol namespace for this build, from the Makefile'"'"'s BRANCH. */' \
		'#define GHOTIIO_MATH_NAME $(LIBVER_SYMBOL)' \
		'' \
		'/** Human-readable version of this build. */' \
		'#define GHOTIIO_MATH_VERSION "$(VERSION_STRING)"' \
		'' \
		'/** The same version as three integers. */' \
		'#define GHOTIIO_MATH_VERSION_MAJOR $(MAJOR_VERSION)' \
		'#define GHOTIIO_MATH_VERSION_MINOR $(VERSION_MINOR_ONLY)' \
		'#define GHOTIIO_MATH_VERSION_PATCH $(VERSION_PATCH_ONLY)' \
		'' \
		'#endif // GHOTI_IO_GMATH_LIBVER_GEN_H' > $@.tmp
	@if cmp -s $@.tmp $@; then rm -f $@.tmp; else mv $@.tmp $@; fi

libver-gen: $(LIBVER_GEN) ## Write the generated version header (needs no dependency)

$(OBJ_DIR)/%.o: src/%.c $(FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(LIB_CFLAGS) $(INCLUDE) -c $< -MMD -MP -MF $(@:.o=.d) -o $@

$(APP_DIR)/$(TARGET): $(LIBOBJECTS)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -shared -o $@ $^ $(LDFLAGS) $(AS_NEEDED) $(DEP_LIBS) $(OS_SPECIFIC_LIBRARY_NAME_FLAG)
ifeq ($(OS_NAME), Linux)
	@ln -f -s $(TARGET) $(APP_DIR)/$(SO_NAME)
	@ln -f -s $(SO_NAME) $(APP_DIR)/$(BASE_NAME)
endif

$(APP_DIR)/$(STATIC_TARGET): $(LIBOBJECTS)
	@mkdir -p $(@D)
	@rm -f $@
	ar rcs $@ $^

ifneq ($(TEST_HELPER_SRC),)
$(TEST_HELPER_OBJ): $(TEST_HELPER_SRC) $(FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(INCLUDE) -c $< -MMD -MP -MF $(@:.o=.d) -o $@
endif

$(OBJ_DIR)/tests/%.o: tests/%.cpp $(FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(INCLUDE) -Itests -c $< -MMD -MP -MF $(@:.o=.d) -o $@

$(OBJ_DIR)/tests/%.o: tests/unit/%.cpp $(FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(INCLUDE) -Itests -c $< -MMD -MP -MF $(@:.o=.d) -o $@

define test-executable-rule
TEST_OBJ_$1 := $(OBJ_DIR)/tests/$(basename $(notdir $1)).o

$(APP_DIR)/$2$(EXE_EXTENSION): $$(TEST_OBJ_$1) $(TEST_HELPER_OBJ) \
		$(APP_DIR)/$(STATIC_TARGET) | $(APP_DIR)/$(TARGET)
	@mkdir -p $$(@D)
	$(CXX) $(CXXFLAGS) -o $$@ $$(TEST_OBJ_$1) $(TEST_HELPER_OBJ) $(LDFLAGS) $(TEST_LDFLAGS) $(SELF_LIBRARY) $(DEP_LIBS) $(TESTFLAGS)
endef

$(foreach pair,$(TEST_PAIRS),\
	$(eval $(call test-executable-rule,$(word 1,$(subst |, ,$(pair))),$(word 2,$(subst |, ,$(pair))))))

$(APP_DIR)/examples/%$(EXE_EXTENSION): examples/%.c $(APP_DIR)/$(STATIC_TARGET) \
		$(FLAGS_STAMP) | $(APP_DIR)/$(TARGET) $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) $(DEP_LIBS)

.PHONY: clean cloc docs docs-pdf examples coverage check-symbols check-stamps check-aliasing
.PHONY: run-examples
.PHONY: check-fp-contract check-edges check-libm check-no-x87 check-gates libver-gen
.PHONY: oracle-selfcheck bench check-corpus-hash check-planted check-planted-exact check-planted-decimal check-oracle-fresh oracle-build oracle-version oracle-fit oracle-corpus oracle-fresh corpus-hash-update
.PHONY: check-planted-remainder check-remainder-corpus
.PHONY: check-planted-extrema check-extrema-corpus
.PHONY: check-planted-logbase check-logbase-oracle oracle-logbase oracle-fit-logbase
.PHONY: check-planted-exp2 check-exp2-oracle oracle-exp2
.PHONY: all install test test-quiet test-asan test-valgrind test-valgrind-quiet test-watch uninstall watch
.PHONY: all-debug install-debug test-debug test-valgrind-debug test-watch-debug uninstall-debug watch-debug
.PHONY: fuzz fuzz-clean

watch: ## Watch sources and rebuild
	@while true; do \
		make --no-print-directory all; \
		inotifywait -qr -e modify -e create -e delete -e move src include tests Makefile; \
		done

test-watch: ## Watch sources and rerun the tests
	@while true; do \
		make --no-print-directory test; \
		inotifywait -qr -e modify -e create -e delete -e move src include tests Makefile; \
		done

examples: $(APP_DIR)/$(TARGET) $(EXAMPLES) ## Build the examples

# Every example is run, not only compiled (story 16): one that is only compiled rots unseen, its calls still linking
# while what it claims stops being true. Each example checks what it shows and exits non-zero when that does not
# hold; tools/run-examples.sh first shows itself failing on planted examples, then runs these. A target that runs a
# built program sets LD_LIBRARY_PATH (CONVENTIONS section 6).
run-examples: $(EXAMPLES) ## Build and run every example; fail on one that exits non-zero
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" sh tools/run-examples.sh $(BUILD_DIR)/examples-out $(EXAMPLES)

# The dependencies' library directories, from the -L words pkg-config gave, so
# a test run finds them when they are installed in a prefix of their own.
EMPTY :=
SPACE := $(EMPTY) $(EMPTY)
DEP_LIB_DIRS := $(subst $(SPACE),:,$(strip $(patsubst -L%,%,$(filter -L%,$(DEP_LIBS)))))
TEST_LD_PATH := $(APP_DIR):$(LIB_INSTALL_PATH)/$(SUITE)$(if $(DEP_LIB_DIRS),:$(DEP_LIB_DIRS))

check-aliasing: ## Fail if -Wstrict-aliasing is not armed at level 1
	@mkdir -p $(BUILD_DIR)
	@printf 'int gmath_alias_probe(float * f);\nint gmath_alias_probe(float * f) { int * i = (int *)f; *i = 7; return *i; }\n' > $(BUILD_DIR)/alias_probe.c
	@printf 'int gmath_alias_clean(int * i);\nint gmath_alias_clean(int * i) { *i = 7; return *i; }\n' > $(BUILD_DIR)/alias_clean.c
	@probe=$$($(CC) $(CFLAGS) -Wno-error -c $(BUILD_DIR)/alias_probe.c -o $(BUILD_DIR)/alias_probe.o 2>&1); \
	ctl=$$($(CC) $(CFLAGS) -Wno-error -c $(BUILD_DIR)/alias_clean.c -o $(BUILD_DIR)/alias_clean.o 2>&1); ctlrc=$$?; \
	if [ $$ctlrc -ne 0 ]; then \
		printf 'check-aliasing: the control file did not compile, so this gate is measuring nothing:\n%s\n' "$$ctl" >&2; \
		exit 1; \
	fi; \
	if printf '%s' "$$ctl" | grep -q 'strict-aliasing'; then \
		printf 'check-aliasing: the control file drew a strict-aliasing diagnostic, so the probe proves nothing:\n%s\n' "$$ctl" >&2; \
		exit 1; \
	fi; \
	if printf '%s' "$$probe" | grep -q 'strict-aliasing'; then \
		printf 'check-aliasing: the planted violation is reported\n'; \
		exit 0; \
	fi; \
	qout=$$($(CC) -Q --help=warnings $(CFLAGS) 2>/dev/null); qrc=$$?; \
	level=$$(printf '%s' "$$qout" | awk '/-Wstrict-aliasing=</{print $$2}'); \
	if [ $$qrc -ne 0 ] || [ -z "$$level" ]; then \
		printf 'check-aliasing: no diagnostic, and %s reports no -Wstrict-aliasing level. That is a compiler which accepts the option and implements nothing.\n' "$(CC)" >&2; \
	elif [ "$$level" = 1 ]; then \
		printf 'check-aliasing: level 1 is set and the planted store still drew no diagnostic.\n' >&2; \
	else \
		printf 'check-aliasing: CFLAGS resolves to -Wstrict-aliasing=%s; only level 1 reports this probe.\n' "$$level" >&2; \
	fi; \
	exit 1

check-stamps: ## Fail if a compile rule names no flags stamp, or a stamp omits a variable
	@python3 tools/check-stamps.py

####################################################################
# The shape family's gates (AD-2, AD-17, AD-22). tools/check-gates.sh
# plants a violation for each and requires the gate to fail on it.
####################################################################

check-fp-contract: ## Fail if a compile-flag set lacks -ffp-contract=off (a fused multiply-add changes bits)
	@tools/check-fp-contract.sh

check-edges: $(APP_DIR)/$(TARGET) ## Fail on an #include or NEEDED edge outside EDGES_ALLOWED (AD-2)
	@tools/check-edges.sh --allowed '$(EDGES_ALLOWED)' --self $(PROJECT) --includes .
	@tools/check-edges.sh --allowed '$(EDGES_ALLOWED)' --self $(PROJECT) --links $(APP_DIR)

check-libm: $(APP_DIR)/$(TARGET) $(APP_DIR)/$(STATIC_TARGET) ## Fail if any libm function is referenced or defined (AD-22)
	@tools/check-libm.sh $(APP_DIR)/$(TARGET) $(APP_DIR)/$(STATIC_TARGET)

check-no-x87: $(APP_DIR)/$(STATIC_TARGET) ## Fail if an x86 object holds an x87 instruction (AD-17)
	@tools/check-no-x87.sh $(APP_DIR)/$(STATIC_TARGET)

check-gates: ## Prove each gate fails on its planted violation and passes its control
	@CC='$(CC)' GATE_PROJECT='$(PROJECT)' GATE_ALLOWED='$(EDGES_ALLOWED)' GATE_LIBM_EXEMPT='$(LIBM_EXEMPT)' tools/check-gates.sh

####################################################################
# sin, cos and tan against the multiple-precision oracle (CAP-1, AD-22)
####################################################################
#
# tests/corpus holds the oracle's committed answers (MPFR, in the pinned image
# tools/oracle/containers/mpfr); testTrig checks every result against them and
# needs no container. The container is needed to regenerate the corpus, to fit
# the kernel coefficients, and for the fresh sample below.
#
#   check-corpus-hash  the hash of the library's results over the corpus is the
#                      committed one (tests/corpus/trig.hash). The same program
#                      is built for every other target by suite/tools/xarch and
#                      xwin, which is what makes the hash a cross-target check.
#   check-planted      a perturbed coefficient, a skipped reduction branch and
#                      the other defects in tools/check-planted.py are each
#                      built into a copy of the library and must fail testTrig;
#                      the unplanted copy must pass.
#   check-oracle-fresh a sample drawn now, in the container, checked by testTrig.
#                      Without the container it prints SKIPPED and passes;
#                      GHOTI_ORACLE_REQUIRED=1 makes that a failure.

CORPUS_DIR := tests/corpus
HASH_PROBE := $(APP_DIR)/tools/corpus-hash$(EXE_EXTENSION)
ORACLE := python3 tools/oracle/oracle.py
ORACLE_SEED := 20261017
BENCH_REPEATS ?= 20
PLANT_JOBS ?= 4
# TESTFLAGS is a backtick expression for the shell; the planted-defect script
# splits its flags itself and needs them expanded.
GTEST_FLAGS := $(shell PKG_CONFIG_PATH=$(PKG_CONFIG_LOOKUP_PATH) pkg-config --libs --cflags gtest 2>/dev/null)

$(HASH_PROBE): tools/corpus-hash.c tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) \
		$(FLAGS_STAMP) | $(APP_DIR)/$(TARGET) $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY)

BENCH_PROBE := $(APP_DIR)/tools/bench-trig$(EXE_EXTENSION)
BENCH_PROBE_ELEM := $(APP_DIR)/tools/bench-elementary$(EXE_EXTENSION)
BENCH_PROBE_REMAINDER := $(APP_DIR)/tools/bench-remainder$(EXE_EXTENSION)
BENCH_PROBE_EXTREMA := $(APP_DIR)/tools/bench-extrema$(EXE_EXTENSION)
BENCH_PROBE_LOGBASE := $(APP_DIR)/tools/bench-logbase$(EXE_EXTENSION)
BENCH_PROBE_EXP2 := $(APP_DIR)/tools/bench-exp2$(EXE_EXTENSION)

$(BENCH_PROBE_EXP2): tools/bench-exp2.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE_LOGBASE): tools/bench-logbase.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE_EXTREMA): tools/bench-extrema.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE_REMAINDER): tools/bench-remainder.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE): tools/bench-trig.c $(APP_DIR)/$(STATIC_TARGET) \
		$(FLAGS_STAMP) | $(APP_DIR)/$(TARGET) $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE_ELEM): tools/bench-elementary.c $(APP_DIR)/$(STATIC_TARGET) \
		$(FLAGS_STAMP) | $(APP_DIR)/$(TARGET) $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

bench: $(BENCH_PROBE) $(BENCH_PROBE_ELEM) $(BENCH_PROBE_REMAINDER) $(BENCH_PROBE_EXTREMA) $(BENCH_PROBE_LOGBASE) $(BENCH_PROBE_EXP2) ## Time math functions against host libm, per argument range (a measurement, not a test)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_ELEM) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_REMAINDER) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_EXTREMA) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_LOGBASE) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_EXP2) $(BENCH_REPEATS)

check-corpus-hash: $(HASH_PROBE) ## Fail if the hash over the trig corpus is not the committed one (AD-17)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" tools/check-corpus-hash.sh $(HASH_PROBE) $(CORPUS_DIR) $(CORPUS_DIR)/trig.hash

corpus-hash-update: $(HASH_PROBE) ## Rewrite tests/corpus/trig.hash from this build (after a deliberate change)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(HASH_PROBE) $(CORPUS_DIR) | awk 'BEGIN{print "# FNV-1a 64 over the little-endian bytes of every result, sin cos tan atan2 exp log pow hypot sqrt floor ceil trunc round rint fabs copysign scalbn frexp ilogb, in corpus order."; print "# `hash` and `count` are over all nineteen; each `fn` line is one function alone; sqrt_portable, sqrt_hardware and ldexp are variants, outside the total, that must equal sqrt and scalbn; decimal_parse (bits, flags, bytes consumed) and decimal_shortest (sign, digits, exponent) are outside the total too."; print "# Written by `make corpus-hash-update`; checked by check-corpus-hash, testTrig, testElementary and the cross-target scripts."} $$1=="math.trig.hash"{print "hash " $$2} $$1=="math.trig.count"{print "count " $$2} $$1 ~ /^math\.[a-z0-9_]+\.hash$$/ && $$1!="math.trig.hash"{split($$1,a,"."); h[a[2]]=$$2; o[++n]=a[2]} $$1 ~ /^math\.[a-z0-9_]+\.count$$/ && $$1!="math.trig.count"{split($$1,a,"."); c[a[2]]=$$2} END{for(i=1;i<=n;i++) print "fn " o[i] " " h[o[i]] " " c[o[i]]}' > $(CORPUS_DIR)/trig.hash
	@cat $(CORPUS_DIR)/trig.hash

check-planted: check-planted-exact check-planted-decimal check-planted-remainder check-planted-extrema check-planted-logbase check-planted-exp2 $(OBJ_DIR)/tests/test_trig.o $(OBJ_DIR)/tests/test_elementary.o $(HASH_PROBE) $(LIBOBJECTS) ## Fail unless each planted defect fails its tests and the control passes
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_trig.o' PLANT_PROBE_CFLAGS='$(CFLAGS) $(INCLUDE)' \
	 PLANT_CXX_INCLUDE='$(INCLUDE) -Itests' \
	 PLANT_PROBE='$(HASH_PROBE)' PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_DECIMAL_OBJS='$(filter $(OBJ_DIR)/decimal/%.o,$(LIBOBJECTS))' PLANT_WORK='$(BUILD_DIR)/planted' \
	 PLANT_OTHER_OBJS='$(filter-out $(OBJ_DIR)/elementary/trig.o,$(filter $(OBJ_DIR)/elementary/%.o,$(LIBOBJECTS)))' \
	 python3 tools/check-planted.py
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_elementary.o' PLANT_PROBE_CFLAGS='$(CFLAGS) $(INCLUDE)' \
	 PLANT_CXX_INCLUDE='$(INCLUDE) -Itests' \
	 PLANT_PROBE='$(HASH_PROBE)' PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_DECIMAL_OBJS='$(filter $(OBJ_DIR)/decimal/%.o,$(LIBOBJECTS))' PLANT_WORK='$(BUILD_DIR)/planted-elem' \
	 PLANT_TRIG_OBJ='$(OBJ_DIR)/elementary/trig.o' PLANT_OBJ_DIR='$(OBJ_DIR)/elementary' PLANT_JOBS='$(PLANT_JOBS)' \
	 python3 tools/check-planted-elem.py

check-planted-decimal: $(OBJ_DIR)/tests/test_decimal.o $(LIBOBJECTS) ## Fail unless each planted defect in the decimal conversions fails testDecimal (and the corpus hash) and the control passes
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(DEP_LIBS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_decimal.o' PLANT_PROBE_CFLAGS='$(CFLAGS) $(INCLUDE)' \
	 PLANT_OTHER_OBJS='$(filter-out $(OBJ_DIR)/decimal/%.o,$(LIBOBJECTS))' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-decimal' \
	 python3 tools/check-planted-decimal.py

check-planted-exact: $(OBJ_DIR)/tests/test_basic.o $(HASH_PROBE) $(LIBOBJECTS) ## Fail unless each planted defect in sqrt, the rounding and the exponent functions fails testBasic or the corpus hash
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_basic.o' PLANT_PROBE_CFLAGS='$(CFLAGS) $(INCLUDE)' \
	 PLANT_CXX_INCLUDE='$(INCLUDE) -Itests' \
	 PLANT_PROBE='$(HASH_PROBE)' PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_DECIMAL_OBJS='$(filter $(OBJ_DIR)/decimal/%.o,$(LIBOBJECTS))' PLANT_WORK='$(BUILD_DIR)/planted-exact' \
	 PLANT_TRIG_OBJ='$(OBJ_DIR)/elementary/trig.o' PLANT_OBJ_DIR='$(OBJ_DIR)/elementary' PLANT_JOBS='$(PLANT_JOBS)' \
	 python3 tools/check-planted-exact.py

check-planted-remainder: $(OBJ_DIR)/tests/test_remainder.o $(LIBOBJECTS) $(HASH_PROBE) ## Require each remainder mutation to fail and its control to pass
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_remainder.o' \
	 PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-remainder' \
	 python3 tools/check-planted-remainder.py

check-planted-extrema: $(OBJ_DIR)/tests/test_extrema.o $(LIBOBJECTS) $(HASH_PROBE) ## Require each extrema mutation and supplemental hash corruption to fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_extrema.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-extrema' \
	 python3 tools/check-planted-extrema.py

check-planted-logbase: $(OBJ_DIR)/tests/test_logbase.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove log-base implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_logbase.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-logbase' \
	 python3 tools/check-planted-logbase.py

oracle-fit-logbase: ## Regenerate the split base-logarithm reciprocals in the pinned image
	@$(ORACLE) fit-logbase > src/elementary/logbase_constants.h.new && mv src/elementary/logbase_constants.h.new src/elementary/logbase_constants.h

oracle-logbase: ## Regenerate committed base-logarithm corpora in the pinned image
	@$(ORACLE) logbase --out $(CORPUS_DIR) --seed 20261026 --count 3000

check-planted-exp2: $(OBJ_DIR)/tests/test_exp2.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove exp2 implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_exp2.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-exp2' \
	 python3 tools/check-planted-exp2.py

oracle-exp2: ## Regenerate committed binary exponential references in the pinned image
	@$(ORACLE) exp2 --out $(CORPUS_DIR) --seed 20261026 --count 3000

check-exp2-oracle: $(APP_DIR)/testExp2$(EXE_EXTENSION) ## Check committed and fresh exp2 references (skip fresh loudly without the pinned image)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testExp2$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-exp2-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-exp2 --out $(BUILD_DIR)/oracle-exp2 --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) exp2 --out $(BUILD_DIR)/exp2-committed --seed 20261026 --count 3000 && \
	   cmp tests/corpus/exp2.corpus $(BUILD_DIR)/exp2-committed/exp2.corpus && \
	   GMATH_EXP2_CORPUS_DIR=$(BUILD_DIR)/oracle-exp2 LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testExp2$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-exp2-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-exp2-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

check-logbase-oracle: $(APP_DIR)/testLogbase$(EXE_EXTENSION) ## Check constants and a fresh logarithm sample (skip loudly without the pinned image)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testLogbase$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-logbase-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-logbase --out $(BUILD_DIR)/oracle-logbase --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) logbase --out $(BUILD_DIR)/logbase-committed --seed 20261026 --count 3000 && \
	   cmp tests/corpus/log2.corpus $(BUILD_DIR)/logbase-committed/log2.corpus && \
	   cmp tests/corpus/log10.corpus $(BUILD_DIR)/logbase-committed/log10.corpus && \
	   cmp tests/corpus/log2f.corpus $(BUILD_DIR)/logbase-committed/log2f.corpus && \
	   $(ORACLE) fit-logbase > $(BUILD_DIR)/logbase_constants.h && \
	   cmp src/elementary/logbase_constants.h $(BUILD_DIR)/logbase_constants.h && \
	   GMATH_LOGBASE_CORPUS_DIR=$(BUILD_DIR)/oracle-logbase LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testLogbase$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-logbase-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-logbase-oracle: SKIPPED fresh reference and constant regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

check-extrema-corpus: $(APP_DIR)/testExtrema$(EXE_EXTENSION) ## Reproduce exact extrema corpus and check a fresh sample in all rounding modes
	@python3 tools/oracle/gen_corpus_extrema.py --out $(BUILD_DIR)/extrema-committed --seed 20261026 --count 3000
	@for n in fmin fmax fminf fmaxf; do \
	 cmp tests/corpus/$$n.corpus $(BUILD_DIR)/extrema-committed/$$n.corpus || exit 1; done
	@seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 printf 'check-extrema-corpus: fresh seed %s\n' "$$seed"; \
	 python3 tools/oracle/gen_corpus_extrema.py --out $(BUILD_DIR)/oracle-extrema --seed $$seed --count 3000 && \
	 GMATH_EXTREMA_CORPUS_DIR=$(BUILD_DIR)/oracle-extrema \
	 LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testExtrema$(EXE_EXTENSION) --gtest_brief=1 \
	 || { printf 'check-extrema-corpus: FAIL with seed %s\n' "$$seed" >&2; exit 1; }

check-remainder-corpus: $(APP_DIR)/testRemainder$(EXE_EXTENSION) ## Reproduce the exact rational corpus and check a fresh sample without a container
	@python3 tools/oracle/gen_corpus_remainder.py --out $(BUILD_DIR)/remainder-committed --seed 20261026 --count 3000
	@cmp tests/corpus/fmod.corpus $(BUILD_DIR)/remainder-committed/fmod.corpus
	@cmp tests/corpus/fmodf.corpus $(BUILD_DIR)/remainder-committed/fmodf.corpus
	@seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 printf 'check-remainder-corpus: fresh seed %s\n' "$$seed"; \
	 python3 tools/oracle/gen_corpus_remainder.py --out $(BUILD_DIR)/oracle-remainder --seed $$seed --count 3000 && \
	 GMATH_REMAINDER_CORPUS_DIR=$(BUILD_DIR)/oracle-remainder \
	 LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testRemainder$(EXE_EXTENSION) --gtest_brief=1 \
	 || { printf 'check-remainder-corpus: FAIL with seed %s\n' "$$seed" >&2; exit 1; }

check-oracle-fresh: $(APP_DIR)/testTrig$(EXE_EXTENSION) $(APP_DIR)/testElementary$(EXE_EXTENSION) $(APP_DIR)/testBasic$(EXE_EXTENSION) $(APP_DIR)/testDecimal$(EXE_EXTENSION) ## Check a sample drawn now against the oracle (skips loudly without the container)
	@mkdir -p $(BUILD_DIR); rm -rf $(BUILD_DIR)/oracle-fresh; \
	seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	$(ORACLE) fresh --out $(BUILD_DIR)/oracle-fresh --seed $$seed || rc=$$?; \
	if [ $$rc -eq 0 ]; then \
		printf 'check-oracle-fresh: seed %s\n' "$$seed"; \
		GMATH_TRIG_CORPUS_DIR=$(BUILD_DIR)/oracle-fresh GMATH_TRIG_MIN_ENTRIES=2000 \
			LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testTrig$(EXE_EXTENSION) --gtest_brief=1 --gtest_filter=Trig.CorpusIsWithinOneUlp \
			|| { printf 'check-oracle-fresh: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
		GMATH_TRIG_CORPUS_DIR=$(BUILD_DIR)/oracle-fresh GMATH_TRIG_MIN_ENTRIES=2000 \
			LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testElementary$(EXE_EXTENSION) --gtest_brief=1 --gtest_filter=Elementary.CorpusIsWithinOneUlp \
			|| { printf 'check-oracle-fresh: FAIL (testElementary) with seed %s\n' "$$seed" >&2; exit 1; }; \
		GMATH_TRIG_CORPUS_DIR=$(BUILD_DIR)/oracle-fresh GMATH_TRIG_MIN_ENTRIES=1000 \
			LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testBasic$(EXE_EXTENSION) --gtest_brief=1 --gtest_filter=Basic.CorpusIsExact \
			|| { printf 'check-oracle-fresh: FAIL (testBasic) with seed %s\n' "$$seed" >&2; exit 1; }; \
		GMATH_TRIG_CORPUS_DIR=$(BUILD_DIR)/oracle-fresh GMATH_TRIG_MIN_ENTRIES=1000 \
			LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testDecimal$(EXE_EXTENSION) --gtest_brief=1 --gtest_filter='DecimalCorpus.*' \
			|| { printf 'check-oracle-fresh: FAIL (testDecimal) with seed %s\n' "$$seed" >&2; exit 1; }; \
	elif [ $$rc -eq 3 ]; then \
		printf 'check-oracle-fresh: SKIPPED (no oracle container here); the committed corpus was checked by testTrig, testElementary, testBasic and testDecimal\n'; \
	else exit $$rc; fi

oracle-build: ## Build the oracle image from its pinned Containerfile
	podman build -t ghoti-math-oracle-mpfr:2.3.2 \
		-f tools/oracle/containers/mpfr/Containerfile tools/oracle/containers/mpfr

oracle-version: ## Fail unless the oracle image is present and matches its pin
	@GHOTI_ORACLE_REQUIRED=1 $(ORACLE) version

oracle-fit: ## Regenerate src/elementary/trig_tables.h (reduction constants), trig_kernel_table.h (kernel table and tails), explog_tables.h, atan2_table.h and hypot_table.h (changes every result)
	@$(ORACLE) fit > src/elementary/trig_tables.h.new && mv src/elementary/trig_tables.h.new src/elementary/trig_tables.h
	@$(ORACLE) fit-kernel > src/elementary/trig_kernel_table.h.new && mv src/elementary/trig_kernel_table.h.new src/elementary/trig_kernel_table.h
	@$(ORACLE) fit-explog > src/elementary/explog_tables.h.new && mv src/elementary/explog_tables.h.new src/elementary/explog_tables.h
	@$(ORACLE) fit-logbase > src/elementary/logbase_constants.h.new && mv src/elementary/logbase_constants.h.new src/elementary/logbase_constants.h
	@$(ORACLE) fit-atan2 > src/elementary/atan2_table.h.new && mv src/elementary/atan2_table.h.new src/elementary/atan2_table.h
	@$(ORACLE) fit-hypot > src/elementary/hypot_table.h.new && mv src/elementary/hypot_table.h.new src/elementary/hypot_table.h

oracle-selfcheck: ## Show that the generator of the exact functions' corpora fails on a planted defect in either statement of an answer (host; needs the oracle image)
	@tools/oracle/check-generator-plants.sh

oracle-corpus: ## Regenerate tests/corpus from the oracle (then make corpus-hash-update)
	@$(ORACLE) corpus --out $(CORPUS_DIR) --seed $(ORACLE_SEED)

####################################################################
# Symbols
####################################################################

check-symbols: $(APP_DIR)/$(TARGET) ## Fail if any exported symbol lacks the version namespace
ifeq ($(OS_NAME), Linux)
	@leaked=$$(nm -D --defined-only $(APP_DIR)/$(TARGET) \
		| awk '$$2 ~ /^[TDBR]$$/ {print $$3}' \
		| grep -v '^$(LIBVER_SYMBOL)_' | grep -v '^_' || true); \
	if [ -n "$$leaked" ]; then \
		printf '### Exported symbols missing the $(LIBVER_SYMBOL)_ namespace ###\n%s\n' "$$leaked" >&2; \
		exit 1; \
	fi
	@unexported=$$(find include -name '*.h' -exec awk '/^#if DOXYGEN/{d=1} d==0 && /^[a-z_][A-Za-z0-9_ ]*\**[[:space:]]*gmath_[a-z0-9_]+[[:space:]]*\(/{print FILENAME": "$$0} /^#endif/{d=0}' {} + \
		| grep -vE 'typedef|static inline' || true); \
	if [ -n "$$unexported" ]; then \
		printf '### Public declarations without GMATH_API ###\n%s\n' "$$unexported" >&2; \
		exit 1; \
	fi
	@split=$$(nm -D --undefined-only $(APP_DIR)/$(TARGET) \
		| awk '{print $$2}' | grep '^$(LIBVER_SYMBOL)_' || true); \
	if [ -n "$$split" ]; then \
		printf '### Renamed but undefined - a split symbol ###\n%s\n' "$$split" >&2; \
		exit 1; \
	fi
	@nomacros=$$(find include src -name '*.h' \
		! -name 'libver.h' ! -name 'libver_gen.h' ! -name 'namespace.h' ! -name 'macros.h' \
		-exec grep -L '#include <ghoti.io/$(PROJECT)/macros.h>' {} + || true); \
	if [ -n "$$nomacros" ]; then \
		printf '### Headers that do not include macros.h ###\n%s\n' "$$nomacros" >&2; \
		exit 1; \
	fi
	@badguards=$$(find include src -name '*.h' -exec awk 'FNR==1{d=0} !d && /^#ifndef/{print $$2; d=1}' {} + \
		| awk '$$1 !~ /^GHOTI_IO_GMATH_/ {print $$1}' || true); \
	if [ -n "$$badguards" ]; then \
		printf '### Include guards with the wrong prefix ###\n%s\n' "$$badguards" >&2; \
		exit 1; \
	fi
	@dupguards=$$(find include src -name '*.h' -exec awk 'FNR==1{d=0} !d && /^#ifndef/{print $$2; d=1}' {} + \
		| sort | uniq -d || true); \
	if [ -n "$$dupguards" ]; then \
		printf '### Headers sharing an include guard ###\n%s\n' "$$dupguards" >&2; \
		exit 1; \
	fi
	@printf 'Every exported symbol carries the %s_ namespace.\n' "$(LIBVER_SYMBOL)"
else
	@printf 'check-symbols: skipped (Linux only)\n'
endif

test: $(APP_DIR)/$(TARGET) $(TEST_EXECUTABLES) $(TEST_GATES) ## Build and run the tests
	@for test_exe in $(TEST_EXECUTABLES); do \
		test_name=$$(basename $$test_exe $(EXE_EXTENSION)); \
		printf '\n### Running %s ###\n\n' "$$test_name"; \
		LD_LIBRARY_PATH="$(TEST_LD_PATH)" $$test_exe --gtest_brief=1 || exit 1; \
	done

test-quiet: $(APP_DIR)/$(TARGET) $(TEST_EXECUTABLES) ## Run tests, one line per suite
	@total_tests=0; total_passed=0; total_failed=0; total_time=0; failed_suites=""; any_failed=0; \
	printf '\n%-30s %8s %10s %s\n' "Test Suite" "Tests" "Time" "Status"; \
	for test_exe in $(TEST_EXECUTABLES); do \
		test_name=$$(basename $$test_exe $(EXE_EXTENSION)); \
		output=$$(LD_LIBRARY_PATH="$(TEST_LD_PATH)" $$test_exe --gtest_brief=1 2>&1); \
		exit_code=$$?; \
		num_tests=$$(echo "$$output" | grep -oP '\[\s*=+\s*\]\s*\K\d+(?=\s+tests?)' | head -1); \
		time_ms=$$(echo "$$output" | grep -oP '\(\K\d+(?=\s*ms\s*total\))' | head -1); \
		[ -z "$$num_tests" ] && num_tests=0; \
		[ -z "$$time_ms" ] && time_ms=0; \
		total_tests=$$((total_tests + num_tests)); \
		total_time=$$((total_time + time_ms)); \
		if [ $$exit_code -eq 0 ]; then \
			total_passed=$$((total_passed + num_tests)); \
			printf '%-30s %8d %8dms PASS\n' "$$test_name" "$$num_tests" "$$time_ms"; \
		else \
			any_failed=1; \
			failures=$$(echo "$$output" | grep -oP '\[\s*FAILED\s*\]\s*\K\d+' | head -1); \
			[ -z "$$failures" ] && failures=$$num_tests; \
			[ "$$failures" -eq 0 ] && failures=1; \
			total_failed=$$((total_failed + failures)); \
			total_passed=$$((total_passed + num_tests - failures)); \
			printf '%-30s %8d %8dms FAIL (exit %d)\n' "$$test_name" "$$num_tests" "$$time_ms" "$$exit_code"; \
			failed_suites="$$failed_suites\n=== $$test_name FAILURES ===\n$$output\n"; \
		fi; \
	done; \
	if [ $$any_failed -eq 0 ]; then \
		printf '%-30s %8d %6dms PASS\n\n' "TOTAL" "$$total_tests" "$$total_time"; \
	else \
		printf '%-30s %8d %6dms FAIL (%d failed)\n' "TOTAL" "$$total_tests" "$$total_time" "$$total_failed"; \
		printf '%s\n' "$$failed_suites"; \
		exit 1; \
	fi

test-valgrind: $(APP_DIR)/$(TARGET) $(TEST_EXECUTABLES) ## Run the tests under Valgrind
ifeq ($(OS_NAME), Linux)
	@for test_exe in $(TEST_EXECUTABLES); do \
		printf '\n### Valgrind %s ###\n\n' "$$(basename $$test_exe)"; \
		LD_LIBRARY_PATH="$(TEST_LD_PATH)" valgrind $(VALGRIND_FLAGS) $$test_exe --gtest_brief=1 || exit 1; \
	done
else
	@printf 'Valgrind is only available on Linux\n' >&2; exit 1
endif

test-valgrind-quiet: $(APP_DIR)/$(TARGET) $(TEST_EXECUTABLES) ## Valgrind, one line per suite
ifeq ($(OS_NAME), Linux)
	@total_tests=0; total_failed=0; total_time=0; failed_suites=""; \
	printf '\n%-30s %8s %10s %s\n' "Test Suite (Valgrind)" "Tests" "Time" "Status"; \
	for test_exe in $(TEST_EXECUTABLES); do \
		test_name=$$(basename $$test_exe $(EXE_EXTENSION)); \
		output=$$(LD_LIBRARY_PATH="$(TEST_LD_PATH)" valgrind $(VALGRIND_FLAGS) $$test_exe --gtest_brief=1 2>&1); \
		exit_code=$$?; \
		num_tests=$$(echo "$$output" | grep -oP '\[\s*=+\s*\]\s*\K\d+(?=\s+tests?)' | head -1); \
		time_ms=$$(echo "$$output" | grep -oP '\(\K\d+(?=\s*ms\s*total\))' | head -1); \
		[ -z "$$num_tests" ] && num_tests=0; \
		[ -z "$$time_ms" ] && time_ms=0; \
		total_tests=$$((total_tests + num_tests)); \
		total_time=$$((total_time + time_ms)); \
		has_leak=$$(echo "$$output" | grep -c "are definitely lost\|are indirectly lost\|are possibly lost" || true); \
		if [ $$exit_code -eq 0 ] && [ $$has_leak -eq 0 ]; then \
			printf '%-30s %8d %8dms PASS\n' "$$test_name" "$$num_tests" "$$time_ms"; \
		else \
			total_failed=$$((total_failed + 1)); \
			printf '%-30s %8d %8dms FAIL\n' "$$test_name" "$$num_tests" "$$time_ms"; \
			failed_suites="$$failed_suites\n=== $$test_name ===\n$$output\n"; \
		fi; \
	done; \
	if [ $$total_failed -eq 0 ]; then \
		printf '%-30s %8d %6dms PASS\n\n' "TOTAL" "$$total_tests" "$$total_time"; \
	else \
		printf '%-30s %8d %6dms FAIL (%d suites)\n' "TOTAL" "$$total_tests" "$$total_time" "$$total_failed"; \
		printf '%s\n' "$$failed_suites"; \
		exit 1; \
	fi
else
	@printf 'Valgrind is only available on Linux\n' >&2; exit 1
endif

####################################################################
# ASan + UBSan, in their own tree
####################################################################

UBSAN_CHECKS := undefined,float-cast-overflow
ASAN_UBSAN_FLAGS := -fsanitize=address,$(UBSAN_CHECKS) -fno-sanitize-recover=$(UBSAN_CHECKS) -fno-omit-frame-pointer -g -O1
COV_BUILD_DIR := ./build/$(BUILD)-cov
ASAN_BUILD_DIR := ./build/$(BUILD)-asan
ASAN_OBJ_DIR := $(ASAN_BUILD_DIR)/objects
ASAN_FLAGS_STAMP := $(ASAN_OBJ_DIR)/.flags
ASAN_APP_DIR := $(ASAN_BUILD_DIR)/apps
ASAN_LIBOBJECTS := $(patsubst src/%.c,$(ASAN_OBJ_DIR)/%.o,$(SOURCES))
ASAN_DEPFILES := $(ASAN_LIBOBJECTS:.o=.d) \
	$(foreach pair,$(TEST_PAIRS),$(ASAN_OBJ_DIR)/tests/$(basename $(notdir $(word 1,$(subst |, ,$(pair))))).d)
-include $(ASAN_DEPFILES)
ASAN_ARCHIVE := $(ASAN_APP_DIR)/$(STATIC_TARGET)
ASAN_SELF_LIBRARY := -Wl,--whole-archive $(ASAN_ARCHIVE) -Wl,--no-whole-archive $(DEP_LIBS)
ASAN_CFLAGS := $(CFLAGS) $(ASAN_UBSAN_FLAGS) -DGMATH_BUILD
ASAN_CXXFLAGS := $(CXXFLAGS) $(ASAN_UBSAN_FLAGS)
ASAN_LDFLAGS := $(LDFLAGS) $(ASAN_UBSAN_FLAGS)
ifeq ($(UNAME_S), Linux)
	ASAN_CFLAGS += -fPIC
endif

$(ASAN_OBJ_DIR)/%.o: src/%.c $(ASAN_FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(ASAN_CFLAGS) $(INCLUDE) -c $< -MMD -MP -MF $(@:.o=.d) -o $@

$(ASAN_ARCHIVE): $(ASAN_LIBOBJECTS)
	@mkdir -p $(@D)
	@rm -f $@
	ar rcs $@ $^

$(ASAN_OBJ_DIR)/tests/%.o: tests/%.cpp $(ASAN_FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CXX) $(ASAN_CXXFLAGS) $(INCLUDE) -Itests -c $< -MMD -MP -MF $(@:.o=.d) -o $@

$(ASAN_OBJ_DIR)/tests/%.o: tests/unit/%.cpp $(ASAN_FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CXX) $(ASAN_CXXFLAGS) $(INCLUDE) -Itests -c $< -MMD -MP -MF $(@:.o=.d) -o $@

define asan-test-executable-rule
ASAN_TEST_OBJ_$1 := $(ASAN_OBJ_DIR)/tests/$(basename $(notdir $1)).o

$(ASAN_APP_DIR)/$2$(EXE_EXTENSION): $$(ASAN_TEST_OBJ_$1) $(ASAN_ARCHIVE)
	@mkdir -p $$(@D)
	$(CXX) $(ASAN_CXXFLAGS) -o $$@ $$(ASAN_TEST_OBJ_$1) $(ASAN_LDFLAGS) $(ASAN_SELF_LIBRARY) $(DEP_LIBS) $(TESTFLAGS)
endef

$(foreach pair,$(TEST_PAIRS),\
	$(eval $(call asan-test-executable-rule,$(word 1,$(subst |, ,$(pair))),$(word 2,$(subst |, ,$(pair))))))

ASAN_TEST_EXECUTABLES := $(addprefix $(ASAN_APP_DIR)/,$(addsuffix $(EXE_EXTENSION),$(TEST_NAMES)))
ASAN_RUNTIME := $(shell $(CC) -print-file-name=libasan.so 2>/dev/null)

test-asan: $(ASAN_TEST_EXECUTABLES) ## Build with ASan+UBSan and run the tests
	@for test_exe in $(ASAN_TEST_EXECUTABLES); do \
		printf '\n### ASan+UBSan %s ###\n\n' "$$(basename $$test_exe)"; \
		LD_PRELOAD="$(ASAN_RUNTIME)$${LD_PRELOAD:+:$$LD_PRELOAD}" \
		LD_LIBRARY_PATH="$(ASAN_APP_DIR):$(LIB_INSTALL_PATH)/$(SUITE)$(if $(DEP_LIB_DIRS),:$(DEP_LIB_DIRS))" \
			$$test_exe --gtest_brief=1 || exit 1; \
	done
	@printf '\nASan+UBSan suite clean.\n'

####################################################################
# Fuzzing: nothing here parses untrusted input yet
####################################################################

fuzz: ## Build and run every fuzzer
	@printf 'fuzz: no fuzzers in tests/fuzz, because nothing here parses untrusted\n'
	@printf '      input. A fuzz build added later must name -ffp-contract=off in its\n'
	@printf '      own FUZZ_CFLAGS and FUZZ_CXXFLAGS, which check-fp-contract then reads.\n'

fuzz-clean: ## Remove the fuzz build
	-@rm -rf $(BUILD_DIR)/fuzz

####################################################################
# Install
####################################################################

LDCONF_INSTALL_PATH ?= /etc/ld.so.conf.d
PC_REQUIRES := $(DEP_PCS)
PKGCONFIG_INSTALL_PATH ?= $(PC_INSTALL_PATH)

install: all ## Install the library
	@mkdir -p $(LIB_INSTALL_PATH)/$(SUITE)
ifeq ($(OS_NAME), Linux)
	@cp $(APP_DIR)/$(TARGET) $(LIB_INSTALL_PATH)/$(SUITE)/
	@ln -f -s $(TARGET) $(LIB_INSTALL_PATH)/$(SUITE)/$(SO_NAME)
	@ln -f -s $(SO_NAME) $(LIB_INSTALL_PATH)/$(SUITE)/$(BASE_NAME)
	@if [ -n "$(LDCONF_INSTALL_PATH)" ]; then mkdir -p $(LDCONF_INSTALL_PATH); fi
	@if [ -n "$(LDCONF_INSTALL_PATH)" ]; then echo "$(LIB_INSTALL_PATH)/$(SUITE)" > $(LDCONF_INSTALL_PATH)/$(SUITE)-$(PROJECT)$(BRANCH).conf; fi
endif
ifeq ($(OS_NAME), Windows)
	@mkdir -p $(BIN_INSTALL_PATH) $(LIB_INSTALL_PATH)/$(SUITE)
	@cp $(APP_DIR)/$(TARGET).a $(LIB_INSTALL_PATH)/$(SUITE)/
	@cp $(APP_DIR)/$(TARGET) $(BIN_INSTALL_PATH)/
endif
	@rm -rf $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
	@mkdir -p $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
	@if [ -d include/ghoti.io ]; then \
		cp -r include/ghoti.io $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)/ ; \
	fi
	@if [ -d $(GEN_DIR)/ghoti.io ]; then \
		cp -r $(GEN_DIR)/ghoti.io $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)/ ; \
	fi
	@mkdir -p $(PKGCONFIG_INSTALL_PATH)
	@cat pkgconfig/$(SUITE)-$(PROJECT).pc | sed 's/(SUITE)/$(SUITE)/g; s/(PROJECT)/$(PROJECT)/g; s/(BRANCH)/$(BRANCH)/g; s/(VERSION)/$(VERSION)/g; s|(PC_LIB_DIR)|$(PC_LIB_DIR)|g; s|(PC_INCLUDE_DIR)|$(PC_INCLUDE_DIR)|g; s|(REQUIRES)|$(PC_REQUIRES)|g' > $(PKGCONFIG_INSTALL_PATH)/$(SUITE)-$(PROJECT)$(BRANCH).pc
ifeq ($(OS_NAME), Linux)
	@if [ -n "$(LDCONF_INSTALL_PATH)" ]; then ldconfig >> /dev/null 2>&1; fi
endif
	@echo "Ghoti.io $(PROJECT)$(BRANCH) installed"

uninstall: ## Delete the installed files
ifeq ($(OS_NAME), Linux)
	@rm -f $(LIB_INSTALL_PATH)/$(SUITE)/$(BASE_NAME)*
	@rm -f $(LDCONF_INSTALL_PATH)/$(SUITE)-$(PROJECT)$(BRANCH).conf
endif
ifeq ($(OS_NAME), Windows)
	@rm -f $(LIB_INSTALL_PATH)/$(SUITE)/$(TARGET).a
	@rm -f $(BIN_INSTALL_PATH)/$(TARGET)
endif
	@rm -rf $(INCLUDE_INSTALL_PATH)/$(SUITE)/$(PROJECT)$(BRANCH)
	@rm -f $(PKGCONFIG_INSTALL_PATH)/$(SUITE)-$(PROJECT)$(BRANCH).pc
ifeq ($(OS_NAME), Linux)
	@if [ -n "$(LDCONF_INSTALL_PATH)" ]; then ldconfig >> /dev/null 2>&1; fi
endif
	@echo "Ghoti.io $(PROJECT)$(BRANCH) has been uninstalled"

debug: ## Build in DEBUG mode
	make all BUILD=debug

install-debug: ## Install the DEBUG library
	make install BUILD=debug

uninstall-debug: ## Uninstall the DEBUG library
	make uninstall BUILD=debug

test-debug: ## Run the tests in DEBUG mode
	make test BUILD=debug

test-valgrind-debug: ## Valgrind in DEBUG mode
	make test-valgrind BUILD=debug

watch-debug: ## Watch and rebuild in DEBUG mode
	make watch BUILD=debug

test-watch-debug: ## Watch and test in DEBUG mode
	make test-watch BUILD=debug

docs: ## Generate documentation under docs/
	doxygen

docs-pdf: docs ## Generate the PDF manual
	cd ./docs/latex/ && make
	mv -f ./docs/latex/refman.pdf ./docs/$(SUITE)-$(PROJECT)$(BRANCH)-docs.pdf

cloc: ## Count the lines of code used in the project
	cloc src include tests Makefile

coverage: ## Build instrumented, run the tests, and report line coverage
	@rm -rf $(COV_BUILD_DIR)/objects/*.gcda \
		$(COV_BUILD_DIR)/objects/*/*.gcda 2> /dev/null || true
	@status=0; \
	$(MAKE) --no-print-directory test TEST_GATES= \
		BUILD_DIR=$(COV_BUILD_DIR) \
		EXTRA_CFLAGS="--coverage -O0 -fprofile-update=atomic" \
		EXTRA_LDFLAGS="--coverage" > /dev/null || status=$$?; \
	if [ $$status -eq 0 ]; then \
		tools/coverage.sh $(COV_BUILD_DIR)/objects || status=$$?; \
	else \
		printf 'coverage: the instrumented test run failed; no report\n' >&2; \
	fi; \
	exit $$status

clean: ## Remove the build directories
	-@rm -rf ./build

help: ## Display this help
	@grep -E '^[ a-zA-Z_-]+:.*?## .*$$' Makefile | sort | sed 's/\([^:]*\):.*## \(.*\)/\1:\2/' | awk -F: '{printf "%-22s %s\n", $$1, $$2}'

####################################################################
# Flag stamps. At the end so they are not the default goal, and so the
# directories they name have already been assigned.
####################################################################

.PHONY: force-flags

$(FLAGS_STAMP): force-flags
	@mkdir -p $(@D)
	@printf '%s\n' '$(CC) $(CXX) $(LIB_CFLAGS) $(CFLAGS) $(CXXFLAGS) $(LDFLAGS) $(INCLUDE) $(SELF_LIBRARY) $(DEP_LIBS) $(AS_NEEDED) $(TESTFLAGS) $(TEST_LDFLAGS) $(OS_SPECIFIC_LIBRARY_NAME_FLAG)' > $@.new
	@cmp -s $@.new $@ 2>/dev/null && rm -f $@.new || mv -f $@.new $@

$(ASAN_FLAGS_STAMP): force-flags
	@mkdir -p $(@D)
	@printf '%s\n' '$(CC) $(CXX) $(ASAN_CFLAGS) $(ASAN_CXXFLAGS) $(ASAN_LDFLAGS) $(INCLUDE) $(ASAN_SELF_LIBRARY) $(DEP_LIBS) $(TESTFLAGS)' > $@.new
	@cmp -s $@.new $@ 2>/dev/null && rm -f $@.new || mv -f $@.new $@
