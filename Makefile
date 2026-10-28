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
# C++ callers must see the library query backend selected through C flags.
override CXXFLAGS += $(filter -DGMATH_NEARBY_FENV_QUERY%,$(LIB_CFLAGS))
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
TEST_GATES ?= check-currentint-bench-controls check-currentint-link check-currentint-controls check-currentint check-planted-currentint check-currentint-oracle check-currentint-oracle-controls check-nearby-mode-plants check-nearby-link check-nearby check-planted-nearby check-nearby-controls check-nearby-oracle check-nearby-oracle-controls check-ieee-remainder-prior-driver check-ieee-remainder-portable check-ieee-remainder check-planted-ieee-remainder check-ieee-remainder-reference-controls check-ieee-remainder-oracle check-cbrtf-fast-budget check-cbrtf-compat-driver check-cbrtf check-planted-cbrtf check-cbrtf-oracle check-long-scale check-planted-long-scale check-long-scale-oracle check-exponent-domain-driver check-exponent-value check-planted-exponent-value check-exponent-value-oracle check-fraction-split-oracle check-fraction-split check-planted-fraction-split check-symbols check-aliasing check-stamps check-fp-contract check-edges check-libm check-no-x87 check-gates check-corpus-hash check-planted check-oracle-fresh check-remainder-corpus check-extrema-corpus check-logbase-oracle check-exp2-oracle check-exp2f-oracle check-exp2f-special check-expf-oracle check-expf-special check-logf-oracle check-logf-special check-log10f-oracle check-log10f-special check-hypotf-oracle check-hypotf-special check-atan2f-oracle check-atan2f-special check-budget-optimization check-adjacent-oracle check-adjacent-special check-planted-adjacent check-adjacent-compat-driver check-floatscale-oracle check-floatscale-special check-planted-floatscale check-intround-oracle check-intround-special check-planted-intround check-planted-atanf check-atanf-special check-atanf-compat check-atanf-oracle check-cbrt-oracle check-floatbasic-oracle check-floatbasic-special check-floattrig-oracle check-floattrig-special check-floattrig-wide run-examples

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
.PHONY: check-planted-exp2f check-exp2f-oracle oracle-exp2f
.PHONY: check-planted-expf check-expf-oracle oracle-expf
.PHONY: check-planted-logf check-logf-oracle oracle-logf
.PHONY: check-planted-log10f check-log10f-oracle oracle-log10f
.PHONY: check-planted-hypotf check-hypotf-oracle oracle-hypotf
.PHONY: check-planted-atan2f check-atan2f-oracle oracle-atan2f
.PHONY: check-planted-cbrt check-cbrt-oracle oracle-cbrt oracle-fit-cbrt
.PHONY: check-planted-floattrig check-floattrig-oracle oracle-floattrig check-floattrig-special
.PHONY: check-planted-floatbasic check-floatbasic-oracle oracle-floatbasic check-floatbasic-special
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
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

BENCH_PROBE := $(APP_DIR)/tools/bench-trig$(EXE_EXTENSION)
BENCH_PROBE_ELEM := $(APP_DIR)/tools/bench-elementary$(EXE_EXTENSION)
BENCH_PROBE_REMAINDER := $(APP_DIR)/tools/bench-remainder$(EXE_EXTENSION)
BENCH_PROBE_EXTREMA := $(APP_DIR)/tools/bench-extrema$(EXE_EXTENSION)
BENCH_PROBE_LOGBASE := $(APP_DIR)/tools/bench-logbase$(EXE_EXTENSION)
BENCH_PROBE_EXP2 := $(APP_DIR)/tools/bench-exp2$(EXE_EXTENSION)
BENCH_PROBE_CBRT := $(APP_DIR)/tools/bench-cbrt$(EXE_EXTENSION)
BENCH_PROBE_FLOATBASIC := $(APP_DIR)/tools/bench-floatbasic$(EXE_EXTENSION)
BENCH_PROBE_FLOATTRIG := $(APP_DIR)/tools/bench-floattrig$(EXE_EXTENSION)
FLOATTRIG_SPECIAL_PROBE := $(APP_DIR)/tools/probe-floattrig-special$(EXE_EXTENSION)

$(BENCH_PROBE_FLOATTRIG): tools/bench-floattrig.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(FLOATTRIG_SPECIAL_PROBE): tools/probe-floattrig-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

check-floattrig-special: $(FLOATTRIG_SPECIAL_PROBE) ## Check raw binary32 trig special values and floating state
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(FLOATTRIG_SPECIAL_PROBE)

BENCH_PROBE_EXP2F := $(APP_DIR)/tools/bench-exp2f$(EXE_EXTENSION)
EXP2F_SPECIAL_PROBE := $(APP_DIR)/tools/probe-exp2f-special$(EXE_EXTENSION)
$(BENCH_PROBE_EXP2F): tools/bench-exp2f.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(EXP2F_SPECIAL_PROBE): tools/probe-exp2f-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-exp2f-special
check-exp2f-special: $(EXP2F_SPECIAL_PROBE) tests/corpus/exp2f-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(EXP2F_SPECIAL_PROBE) > $(BUILD_DIR)/exp2f-special.actual && \
	 cmp tests/corpus/exp2f-special.hash $(BUILD_DIR)/exp2f-special.actual && \
	 cat $(BUILD_DIR)/exp2f-special.actual

BENCH_PROBE_EXPF := $(APP_DIR)/tools/bench-expf$(EXE_EXTENSION)
EXPF_SPECIAL_PROBE := $(APP_DIR)/tools/probe-expf-special$(EXE_EXTENSION)
$(BENCH_PROBE_EXPF): tools/bench-expf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(EXPF_SPECIAL_PROBE): tools/probe-expf-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-expf-special
check-expf-special: $(EXPF_SPECIAL_PROBE) tests/corpus/expf-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(EXPF_SPECIAL_PROBE) > $(BUILD_DIR)/expf-special.actual && \
	 cmp tests/corpus/expf-special.hash $(BUILD_DIR)/expf-special.actual && \
	 cat $(BUILD_DIR)/expf-special.actual

BENCH_PROBE_LOGF := $(APP_DIR)/tools/bench-logf$(EXE_EXTENSION)
LOGF_SPECIAL_PROBE := $(APP_DIR)/tools/probe-logf-special$(EXE_EXTENSION)
$(BENCH_PROBE_LOGF): tools/bench-logf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(LOGF_SPECIAL_PROBE): tools/probe-logf-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-logf-special
check-logf-special: $(LOGF_SPECIAL_PROBE) tests/corpus/logf-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(LOGF_SPECIAL_PROBE) > $(BUILD_DIR)/logf-special.actual && \
	 cmp tests/corpus/logf-special.hash $(BUILD_DIR)/logf-special.actual && \
	 cat $(BUILD_DIR)/logf-special.actual

BENCH_PROBE_LOG10F := $(APP_DIR)/tools/bench-log10f$(EXE_EXTENSION)
LOG10F_SPECIAL_PROBE := $(APP_DIR)/tools/probe-log10f-special$(EXE_EXTENSION)
$(BENCH_PROBE_LOG10F): tools/bench-log10f.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(LOG10F_SPECIAL_PROBE): tools/probe-log10f-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-log10f-special
check-log10f-special: $(LOG10F_SPECIAL_PROBE) tests/corpus/log10f-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(LOG10F_SPECIAL_PROBE) > $(BUILD_DIR)/log10f-special.actual && \
	 cmp tests/corpus/log10f-special.hash $(BUILD_DIR)/log10f-special.actual && \
	 cat $(BUILD_DIR)/log10f-special.actual

BENCH_PROBE_HYPOTF := $(APP_DIR)/tools/bench-hypotf$(EXE_EXTENSION)
HYPOTF_SPECIAL_PROBE := $(APP_DIR)/tools/probe-hypotf-special$(EXE_EXTENSION)
$(BENCH_PROBE_HYPOTF): tools/bench-hypotf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(HYPOTF_SPECIAL_PROBE): tools/probe-hypotf-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-hypotf-special
check-hypotf-special: $(HYPOTF_SPECIAL_PROBE) tests/corpus/hypotf-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(HYPOTF_SPECIAL_PROBE) > $(BUILD_DIR)/hypotf-special.actual && \
	 cmp tests/corpus/hypotf-special.hash $(BUILD_DIR)/hypotf-special.actual && \
	 cat $(BUILD_DIR)/hypotf-special.actual

# Actual-prior tools are explicit: ordinary source builds need no Git history.
ADJACENT_REFERENCE_OBJECT ?=
ADJACENT_REFERENCE_METADATA ?= $(if $(strip $(ADJACENT_REFERENCE_OBJECT)),$(ADJACENT_REFERENCE_OBJECT).json)
.PHONY: adjacent-reference-force
adjacent-reference-force:
ADJACENT_COMPARE := $(APP_DIR)/tools/compare-adjacent$(EXE_EXTENSION)
ADJACENT_REFERENCE_PROBE := $(APP_DIR)/tools/probe-adjacent-prior$(EXE_EXTENSION)
ADJACENT_REFERENCE_BENCH := $(APP_DIR)/tools/bench-adjacent-prior$(EXE_EXTENSION)
$(ADJACENT_COMPARE): tools/compare-adjacent.c $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(FLAGS_STAMP) adjacent-reference-force $(ADJACENT_REFERENCE_METADATA) tools/adjacent_baseline.py
	@test -n "$(ADJACENT_REFERENCE_OBJECT)" || { echo 'compare-adjacent requires ADJACENT_REFERENCE_OBJECT from an actual prior build' >&2; exit 1; }
	@mkdir -p $(@D)
	@python3 tools/adjacent_baseline.py "$(ADJACENT_REFERENCE_OBJECT)" "$(ADJACENT_REFERENCE_METADATA)" --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_NEXTAFTER_REFERENCE=gmath_adjacent_prior_nextafter -DGMATH_NEXTAFTERF_REFERENCE=gmath_adjacent_prior_nextafterf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(ADJACENT_REFERENCE_PROBE): tools/probe-adjacent.c tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(FLAGS_STAMP) adjacent-reference-force $(ADJACENT_REFERENCE_METADATA) tools/adjacent_baseline.py
	@test -n "$(ADJACENT_REFERENCE_OBJECT)" || { echo 'probe-adjacent-prior requires ADJACENT_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(@D)
	@python3 tools/adjacent_baseline.py "$(ADJACENT_REFERENCE_OBJECT)" "$(ADJACENT_REFERENCE_METADATA)" --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_NEXTAFTER_REFERENCE=gmath_adjacent_prior_nextafter -DGMATH_NEXTAFTERF_REFERENCE=gmath_adjacent_prior_nextafterf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(ADJACENT_REFERENCE_BENCH): tools/bench-adjacent.c $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(FLAGS_STAMP) adjacent-reference-force $(ADJACENT_REFERENCE_METADATA) tools/adjacent_baseline.py
	@test -n "$(ADJACENT_REFERENCE_OBJECT)" || { echo 'bench-adjacent-prior requires ADJACENT_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(@D)
	@python3 tools/adjacent_baseline.py "$(ADJACENT_REFERENCE_OBJECT)" "$(ADJACENT_REFERENCE_METADATA)" --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_NEXTAFTER_BASELINE=gmath_adjacent_prior_nextafter -DGMATH_NEXTAFTERF_BASELINE=gmath_adjacent_prior_nextafterf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
.PHONY: check-adjacent-compat-driver check-adjacent-compat bench-adjacent-prior check-adjacent-native-controls
check-adjacent-compat-driver:
	@python3 tools/check-adjacent-compat.py --calibrate
check-adjacent-native-controls: $(APP_DIR)/$(STATIC_TARGET) $(ADJACENT_REFERENCE_OBJECT) $(ADJACENT_REFERENCE_METADATA)
	@test -n "$(ADJACENT_REFERENCE_OBJECT)" || { echo 'native controls require ADJACENT_REFERENCE_OBJECT' >&2; exit 1; }
	@NATIVE_CC='$(CC)' NATIVE_CFLAGS='$(CFLAGS) $(INCLUDE)' NATIVE_LIB_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 NATIVE_LDFLAGS='$(LDFLAGS)' NATIVE_LIBRARY='$(APP_DIR)/$(STATIC_TARGET)' \
	 NATIVE_REFERENCE='$(ADJACENT_REFERENCE_OBJECT)' NATIVE_METADATA='$(ADJACENT_REFERENCE_METADATA)' \
	 NATIVE_WORK='$(BUILD_DIR)/adjacent-native-controls' python3 tools/check-adjacent-native-controls.py
check-adjacent-compat: $(ADJACENT_COMPARE) $(ADJACENT_REFERENCE_PROBE)
	@python3 tools/check-adjacent-compat.py $(ADJACENT_COMPARE) --baseline-metadata "$(ADJACENT_REFERENCE_METADATA)"
	@$(ADJACENT_REFERENCE_PROBE) > $(BUILD_DIR)/adjacent-prior.actual && python3 tools/check-adjacent-output.py $(BUILD_DIR)/adjacent-prior.actual
bench-adjacent-prior: $(ADJACENT_REFERENCE_BENCH)
	@$(ADJACENT_REFERENCE_BENCH)

ADJACENT_PROBE := $(APP_DIR)/tools/probe-adjacent$(EXE_EXTENSION)
$(ADJACENT_PROBE): tools/probe-adjacent.c tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-adjacent-special
check-adjacent-special: $(ADJACENT_PROBE)
	@$(ADJACENT_PROBE) > $(BUILD_DIR)/adjacent-special.actual && \
	 python3 tools/check-adjacent-output.py $(BUILD_DIR)/adjacent-special.actual

FLOATSCALE_PROBE := $(APP_DIR)/tools/probe-float-scale$(EXE_EXTENSION)
$(FLOATSCALE_PROBE): tools/probe-float-scale.c tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)
.PHONY: check-floatscale-special
check-floatscale-special: $(FLOATSCALE_PROBE)
	@$(FLOATSCALE_PROBE) > $(BUILD_DIR)/floatscale-special.actual && \
	 python3 tools/check-floatscale-output.py $(BUILD_DIR)/floatscale-special.actual

BENCH_PROBE_INTROUND := $(APP_DIR)/tools/bench-intround$(EXE_EXTENSION)
$(BENCH_PROBE_INTROUND): tools/bench-intround.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)

INTROUND_PROBE := $(APP_DIR)/tools/probe-intround$(EXE_EXTENSION)
$(INTROUND_PROBE): tools/probe-intround.c tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)
.PHONY: check-intround-special
check-intround-special: $(INTROUND_PROBE)
	@$(INTROUND_PROBE) > $(BUILD_DIR)/intround-special.actual && \
	 python3 tools/check-intround-output.py $(BUILD_DIR)/intround-special.actual

ATANF_COMPAT_PROBE := $(APP_DIR)/tools/compare-atanf$(EXE_EXTENSION)
$(ATANF_COMPAT_PROBE): tools/compare-atanf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)
.PHONY: check-atanf-compat
check-atanf-compat: $(ATANF_COMPAT_PROBE)
	@python3 tools/check-atanf-compat.py $(ATANF_COMPAT_PROBE)

ATANF_SPECIAL_PROBE := $(APP_DIR)/tools/probe-atanf-special$(EXE_EXTENSION)
$(ATANF_SPECIAL_PROBE): tools/probe-atanf-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)
.PHONY: check-atanf-special
check-atanf-special: $(ATANF_SPECIAL_PROBE) tests/corpus/atanf-special.hash
	@$(ATANF_SPECIAL_PROBE) > $(BUILD_DIR)/atanf-special.actual && \
	 cmp tests/corpus/atanf-special.hash $(BUILD_DIR)/atanf-special.actual && \
	 cat $(BUILD_DIR)/atanf-special.actual

BENCH_PROBE_ADJACENT := $(APP_DIR)/tools/bench-adjacent$(EXE_EXTENSION)
$(BENCH_PROBE_ADJACENT): tools/bench-adjacent.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-adjacent
bench-adjacent: $(BENCH_PROBE_ADJACENT)
	@$(BENCH_PROBE_ADJACENT)

BENCH_PROBE_FLOATSCALE := $(APP_DIR)/tools/bench-floatscale$(EXE_EXTENSION)
$(BENCH_PROBE_FLOATSCALE): tools/bench-floatscale.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-floatscale
bench-floatscale: $(BENCH_PROBE_FLOATSCALE)
	@$(BENCH_PROBE_FLOATSCALE)

BENCH_PROBE_ATANF := $(APP_DIR)/tools/bench-atanf$(EXE_EXTENSION)
$(BENCH_PROBE_ATANF): tools/bench-atanf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS)

BENCH_PROBE_ATAN2F := $(APP_DIR)/tools/bench-atan2f$(EXE_EXTENSION)
ATAN2F_SPECIAL_PROBE := $(APP_DIR)/tools/probe-atan2f-special$(EXE_EXTENSION)
$(BENCH_PROBE_ATAN2F): tools/bench-atan2f.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(ATAN2F_SPECIAL_PROBE): tools/probe-atan2f-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-atan2f-special
check-atan2f-special: $(ATAN2F_SPECIAL_PROBE) tests/corpus/atan2f-special.hash
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(ATAN2F_SPECIAL_PROBE) > $(BUILD_DIR)/atan2f-special.actual && \
	 cmp tests/corpus/atan2f-special.hash $(BUILD_DIR)/atan2f-special.actual && \
	 cat $(BUILD_DIR)/atan2f-special.actual

FLOATTRIG_WIDE_PROBE := $(APP_DIR)/tools/probe-floattrig-wide$(EXE_EXTENSION)
$(FLOATTRIG_WIDE_PROBE): tools/probe-floattrig-wide.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP) | $(APP_DIR)/$(TARGET) $(LIBVER_GEN)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

.PHONY: check-floattrig-wide
check-floattrig-wide: $(FLOATTRIG_WIDE_PROBE) ## Compare wide float trig results and state with the double baseline
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(FLOATTRIG_WIDE_PROBE)

FLOATBASIC_SPECIAL_PROBE := $(APP_DIR)/tools/probe-floatbasic-special$(EXE_EXTENSION)

$(FLOATBASIC_SPECIAL_PROBE): tools/probe-floatbasic-special.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

check-floatbasic-special: $(FLOATBASIC_SPECIAL_PROBE) ## Check raw binary32 NaN, sign and exception contracts (also usable under emulation)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(FLOATBASIC_SPECIAL_PROBE)

$(BENCH_PROBE_FLOATBASIC): tools/bench-floatbasic.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

$(BENCH_PROBE_CBRT): tools/bench-cbrt.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(LDFLAGS) $(SELF_LIBRARY) -lm

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

bench: $(BENCH_PROBE) $(BENCH_PROBE_ELEM) $(BENCH_PROBE_REMAINDER) $(BENCH_PROBE_EXTREMA) $(BENCH_PROBE_LOGBASE) $(BENCH_PROBE_EXP2) $(BENCH_PROBE_CBRT) $(BENCH_PROBE_FLOATBASIC) $(BENCH_PROBE_FLOATTRIG) ## Time math functions against host libm, per argument range (a measurement, not a test)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_ELEM) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_REMAINDER) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_EXTREMA) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_LOGBASE) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_EXP2) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_CBRT) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_FLOATBASIC) $(BENCH_REPEATS)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(BENCH_PROBE_FLOATTRIG) $(BENCH_REPEATS)

check-corpus-hash: $(HASH_PROBE) ## Fail if the hash over the trig corpus is not the committed one (AD-17)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" tools/check-corpus-hash.sh $(HASH_PROBE) $(CORPUS_DIR) $(CORPUS_DIR)/trig.hash

corpus-hash-update: $(HASH_PROBE) ## Rewrite tests/corpus/trig.hash from this build (after a deliberate change)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(HASH_PROBE) $(CORPUS_DIR) | awk 'BEGIN{print "# FNV-1a 64 over the little-endian bytes of every result, sin cos tan atan2 exp log pow hypot sqrt floor ceil trunc round rint fabs copysign scalbn frexp ilogb, in corpus order."; print "# `hash` and `count` are over all nineteen; each `fn` line is one function alone; sqrt_portable, sqrt_hardware and ldexp are variants, outside the total, that must equal sqrt and scalbn; decimal_parse (bits, flags, bytes consumed) and decimal_shortest (sign, digits, exponent) are outside the total too."; print "# Written by `make corpus-hash-update`; checked by check-corpus-hash, testTrig, testElementary and the cross-target scripts."} $$1=="math.trig.hash"{print "hash " $$2} $$1=="math.trig.count"{print "count " $$2} $$1 ~ /^math\.[a-z0-9_]+\.hash$$/ && $$1!="math.trig.hash"{split($$1,a,"."); h[a[2]]=$$2; o[++n]=a[2]} $$1 ~ /^math\.[a-z0-9_]+\.count$$/ && $$1!="math.trig.count"{split($$1,a,"."); c[a[2]]=$$2} END{for(i=1;i<=n;i++) print "fn " o[i] " " h[o[i]] " " c[o[i]]}' > $(CORPUS_DIR)/trig.hash
	@cat $(CORPUS_DIR)/trig.hash

check-planted: check-planted-exact check-planted-decimal check-planted-remainder check-planted-extrema check-planted-logbase check-planted-exp2 check-planted-exp2f check-planted-expf check-planted-logf check-planted-log10f check-planted-hypotf check-planted-atan2f check-planted-cbrt check-planted-floatbasic check-planted-floattrig $(OBJ_DIR)/tests/test_trig.o $(OBJ_DIR)/tests/test_elementary.o $(HASH_PROBE) $(LIBOBJECTS) ## Fail unless each planted defect fails its tests and the control passes
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

check-planted-exp2f: $(OBJ_DIR)/tests/test_exp2f.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove exp2f implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_exp2f.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-exp2f' \
	 python3 tools/check-planted-exp2f.py
check-planted-expf: $(OBJ_DIR)/tests/test_expf.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove expf implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_expf.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-expf' \
	 python3 tools/check-planted-expf.py
check-planted-logf: $(OBJ_DIR)/tests/test_logf.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove logf implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_logf.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-logf' \
	 python3 tools/check-planted-logf.py

check-planted-log10f: $(OBJ_DIR)/tests/test_log10f.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove log10f implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_log10f.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-log10f' \
	 python3 tools/check-planted-log10f.py

check-planted-hypotf: $(OBJ_DIR)/tests/test_hypotf.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove hypotf implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_hypotf.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-hypotf' \
	 python3 tools/check-planted-hypotf.py

check-planted-atan2f: $(OBJ_DIR)/tests/test_atan2f.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove atan2f implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_atan2f.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-atan2f' \
	 python3 tools/check-planted-atan2f.py

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

oracle-exp2f: ## Regenerate committed binary exponential references in the pinned image
	@$(ORACLE) exp2f --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-exp2f-oracle: $(APP_DIR)/testExp2f$(EXE_EXTENSION) ## Check committed and fresh exp2f references (skip fresh loudly without the pinned image)
	@python3 tools/check-exp2f-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testExp2f$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-exp2f-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-exp2f --out $(BUILD_DIR)/oracle-exp2f --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) exp2f --out $(BUILD_DIR)/exp2f-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/exp2f.corpus $(BUILD_DIR)/exp2f-committed/exp2f.corpus && \
	   GMATH_EXP2F_CORPUS_DIR=$(BUILD_DIR)/oracle-exp2f LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testExp2f$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-exp2f-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-exp2f-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

oracle-expf: ## Regenerate committed binary32 natural-exponential references in the pinned image
	@$(ORACLE) expf --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-expf-oracle: $(APP_DIR)/testExpf$(EXE_EXTENSION) ## Check committed and fresh expf references (skip fresh loudly without the pinned image)
	@python3 tools/check-expf-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testExpf$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-expf-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-expf --out $(BUILD_DIR)/oracle-expf --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) expf --out $(BUILD_DIR)/expf-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/expf.corpus $(BUILD_DIR)/expf-committed/expf.corpus && \
	   GMATH_EXPF_CORPUS_DIR=$(BUILD_DIR)/oracle-expf LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testExpf$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-expf-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-expf-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

oracle-logf: ## Regenerate committed binary32 natural-logarithm references in the pinned image
	@$(ORACLE) logf --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-logf-oracle: $(APP_DIR)/testLogf$(EXE_EXTENSION) ## Check committed and fresh logf references (skip fresh loudly without the pinned image)
	@python3 tools/check-logf-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testLogf$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-logf-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-logf --out $(BUILD_DIR)/oracle-logf --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) logf --out $(BUILD_DIR)/logf-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/logf.corpus $(BUILD_DIR)/logf-committed/logf.corpus && \
	   GMATH_LOGF_CORPUS_DIR=$(BUILD_DIR)/oracle-logf LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testLogf$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-logf-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-logf-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

oracle-log10f: ## Regenerate committed binary32 base-ten-logarithm references in the pinned image
	@$(ORACLE) log10f --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-log10f-oracle: $(APP_DIR)/testLog10f$(EXE_EXTENSION) ## Check committed and fresh log10f references (skip fresh loudly without the pinned image)
	@python3 tools/check-log10f-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testLog10f$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-log10f-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-log10f --out $(BUILD_DIR)/oracle-log10f --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) budget-log10f && \
	   $(ORACLE) log10f --out $(BUILD_DIR)/log10f-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/log10f.corpus $(BUILD_DIR)/log10f-committed/log10f.corpus && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-log10f.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testLog10f$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-log10f)" \
	     "$$seed" 3000 "$(abspath $(BUILD_DIR)/log10f-fresh-selection)" \
	   || { printf 'check-log10f-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-log10f-oracle: SKIPPED fresh reference, committed regeneration and pinned budget; committed corpus still checked\n'; \
	 else exit $$rc; fi

oracle-hypotf: ## Regenerate committed binary32 hypotenuse references in the pinned image
	@$(ORACLE) hypotf --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-hypotf-oracle: $(APP_DIR)/testHypotf$(EXE_EXTENSION) ## Check committed and fresh hypotf references (skip fresh loudly without the pinned image)
	@python3 tools/check-hypotf-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testHypotf$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-hypotf-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-hypotf --out $(BUILD_DIR)/oracle-hypotf --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) budget-hypotf && \
	   $(ORACLE) hypotf --out $(BUILD_DIR)/hypotf-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/hypotf.corpus $(BUILD_DIR)/hypotf-committed/hypotf.corpus && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-hypotf.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testHypotf$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-hypotf)" \
	     "$$seed" 3000 "$(abspath $(BUILD_DIR)/hypotf-fresh-selection)" \
	   || { printf 'check-hypotf-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-hypotf-oracle: SKIPPED fresh reference, committed regeneration and pinned budget; committed corpus still checked\n'; \
	 else exit $$rc; fi

.PHONY: check-budget-optimization
check-budget-optimization: ## Reject optimized certificates and check normal pinned controls
	@python3 tools/check-budget-optimization.py

.PHONY: oracle-adjacent check-adjacent-oracle check-planted-adjacent
oracle-adjacent: ## Regenerate exact adjacent-value references
	@$(ORACLE) adjacent --out $(CORPUS_DIR) --seed 20261027 --count 2000

check-adjacent-oracle: $(APP_DIR)/testAdjacent$(EXE_EXTENSION) $(ADJACENT_PROBE)
	@python3 tools/check-adjacent-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testAdjacent$(EXE_EXTENSION) --gtest_brief=1
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 $(ORACLE) fresh-adjacent --out $(BUILD_DIR)/oracle-adjacent --seed $$seed --count 2000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) adjacent --out $(BUILD_DIR)/adjacent-committed --seed 20261027 --count 2000 && \
	   for f in nextafter-special.corpus nextafterf-special.corpus nextafter.corpus nextafterf.corpus adjacent-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/adjacent-committed/$$f || exit 1; \
	   done && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-adjacent.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testAdjacent$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-adjacent)" "$$seed" 2000 \
	   || exit 1; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-adjacent-oracle: SKIPPED fresh references and pinned regeneration; committed corpus checked\n'; \
	 else exit $$rc; fi

check-planted-adjacent: $(OBJ_DIR)/tests/test_adjacent.o $(LIBOBJECTS) $(ADJACENT_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_adjacent.o' PLANT_RAW_PROBE='$(ADJACENT_PROBE)' PLANT_WORK='$(BUILD_DIR)/planted-adjacent' \
	 python3 tools/check-planted-adjacent.py

.PHONY: oracle-floatscale check-floatscale-oracle check-planted-floatscale
oracle-floatscale: ## Regenerate exact Float decomposition/scaling references
	@$(ORACLE) float_scale --out $(CORPUS_DIR) --seed 20261027 --count 1000

check-floatscale-oracle: $(APP_DIR)/testFloat_scale$(EXE_EXTENSION) $(FLOATSCALE_PROBE)
	@python3 tools/check-floatscale-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testFloat_scale$(EXE_EXTENSION) --gtest_brief=1
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 $(ORACLE) fresh-float_scale --out $(BUILD_DIR)/oracle-floatscale --seed $$seed --count 1000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) float_scale --out $(BUILD_DIR)/floatscale-committed --seed 20261027 --count 1000 && \
	   for f in float_scale.corpus scalbnf.corpus frexpf.corpus ilogbf.corpus float_scale-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/floatscale-committed/$$f || exit 1; \
	   done && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-floatscale.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testFloat_scale$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-floatscale)" "$$seed" 1000 \
	   || exit 1; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-floatscale-oracle: SKIPPED fresh references and pinned regeneration; committed corpus checked\n'; \
	 else exit $$rc; fi

check-planted-floatscale: $(OBJ_DIR)/tests/test_float_scale.o $(LIBOBJECTS) $(FLOATSCALE_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_float_scale.o' PLANT_RAW_PROBE='$(FLOATSCALE_PROBE)' PLANT_WORK='$(BUILD_DIR)/planted-floatscale' \
	 python3 tools/check-planted-floatscale.py

.PHONY: oracle-intround check-intround-oracle check-planted-intround
oracle-intround: ## Regenerate exact integer-return rounding references
	@$(ORACLE) intround --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-intround-oracle: $(APP_DIR)/testIntround$(EXE_EXTENSION)
	@python3 tools/check-intround-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testIntround$(EXE_EXTENSION) --gtest_brief=1
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 $(ORACLE) fresh-intround --out $(BUILD_DIR)/oracle-intround --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) intround --out $(BUILD_DIR)/intround-committed --seed 20261027 --count 3000 && \
	   for f in intround32.corpus intround64.corpus lround.corpus lroundf.corpus intround-long32.hash intround-long64.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/intround-committed/$$f || exit 1; \
	   done && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-intround.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testIntround$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-intround)" "$$seed" 3000 \
	   || exit 1; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-intround-oracle: SKIPPED fresh references and pinned regeneration; committed corpus checked\n'; \
	 else exit $$rc; fi

check-planted-intround: $(OBJ_DIR)/tests/test_intround.o $(LIBOBJECTS) $(INTROUND_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_intround.o' PLANT_RAW_PROBE='$(INTROUND_PROBE)' PLANT_WORK='$(BUILD_DIR)/planted-intround' \
	 python3 tools/check-planted-intround.py

.PHONY: check-atanf-oracle oracle-atanf check-planted-atanf
check-planted-atanf: $(OBJ_DIR)/tests/test_atanf.o $(LIBOBJECTS)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_atanf.o' PLANT_WORK='$(BUILD_DIR)/planted-atanf' \
	 python3 tools/check-planted-atanf.py

oracle-atanf: ## Regenerate the independent unary binary32 arctangent corpus
	@$(ORACLE) atanf --out $(CORPUS_DIR) --seed 20261027 --count 5000

check-atanf-oracle: $(APP_DIR)/testAtanf$(EXE_EXTENSION) ## Check committed and optional fresh unary arctangent references
	@python3 tools/check-atanf-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testAtanf$(EXE_EXTENSION) --gtest_brief=1
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; \
	 $(ORACLE) fresh-atanf --out $(BUILD_DIR)/oracle-atanf --seed $$seed --count 5000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) atanf --out $(BUILD_DIR)/atanf-committed --seed 20261027 --count 5000 && \
	   cmp tests/corpus/atanf.corpus $(BUILD_DIR)/atanf-committed/atanf.corpus && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-atanf.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testAtanf$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-atanf)" "$$seed" 5000 \
	   || exit 1; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-atanf-oracle: SKIPPED fresh reference and pinned regeneration; committed corpus checked\n'; \
	 else exit $$rc; fi

oracle-atan2f: ## Regenerate committed binary32 two-argument-arctangent references in the pinned image
	@$(ORACLE) atan2f --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-atan2f-oracle: $(APP_DIR)/testAtan2f$(EXE_EXTENSION) ## Check committed and fresh atan2f references (skip fresh loudly without the pinned image)
	@python3 tools/check-atan2f-reference.py
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testAtan2f$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-atan2f-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-atan2f --out $(BUILD_DIR)/oracle-atan2f --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) budget-atan2f && \
	   $(ORACLE) atan2f --out $(BUILD_DIR)/atan2f-committed --seed 20261027 --count 3000 && \
	   cmp tests/corpus/atan2f.corpus $(BUILD_DIR)/atan2f-committed/atan2f.corpus && \
	   LD_LIBRARY_PATH="$(TEST_LD_PATH)" python3 tools/check-planted-atan2f.py --verify-fresh \
	     "$(abspath $(APP_DIR)/testAtan2f$(EXE_EXTENSION))" "$(abspath $(BUILD_DIR)/oracle-atan2f)" \
	     "$$seed" 3000 "$(abspath $(BUILD_DIR)/atan2f-fresh-selection)" \
	   || { printf 'check-atan2f-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-atan2f-oracle: SKIPPED fresh reference, committed regeneration and pinned budget; committed corpus still checked\n'; \
	 else exit $$rc; fi

check-planted-floattrig: $(OBJ_DIR)/tests/test_floattrig.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove floattrig implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_floattrig.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_CXX_INCLUDE='$(INCLUDE) -Itests' \
	 PLANT_TRIG_OBJ='$(OBJ_DIR)/elementary/trig.o' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-floattrig' \
	 python3 tools/check-planted-floattrig.py

oracle-floattrig: ## Regenerate committed binary32 trig references in the pinned image
	@$(ORACLE) floattrig --out $(CORPUS_DIR) --seed 20261027 --count 3000

check-floattrig-oracle: $(APP_DIR)/testFloattrig$(EXE_EXTENSION) ## Check committed and fresh floattrig references (skip fresh loudly without the pinned image)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testFloattrig$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-floattrig-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-floattrig --out $(BUILD_DIR)/oracle-floattrig --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) fit-floattrig-reduce --out $(BUILD_DIR)/floattrig_reduce_table.h && \
	   cmp src/elementary/floattrig_reduce_table.h $(BUILD_DIR)/floattrig_reduce_table.h && \
	   $(ORACLE) floattrig --out $(BUILD_DIR)/floattrig-committed --seed 20261027 --count 3000 && \
	   for fn in sinf cosf tanf; do \
	     cmp tests/corpus/$$fn.corpus $(BUILD_DIR)/floattrig-committed/$$fn.corpus || exit 1; \
	   done && \
	   GMATH_FLOATTRIG_CORPUS_DIR=$(BUILD_DIR)/oracle-floattrig LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testFloattrig$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-floattrig-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-floattrig-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

check-planted-floatbasic: $(OBJ_DIR)/tests/test_floatbasic.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove floatbasic implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_floatbasic.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-floatbasic' \
	 python3 tools/check-planted-floatbasic.py

oracle-floatbasic: ## Regenerate committed binary32 basic references in the pinned image
	@$(ORACLE) floatbasic --out $(CORPUS_DIR) --seed 20261026 --count 3000

check-floatbasic-oracle: $(APP_DIR)/testFloatbasic$(EXE_EXTENSION) ## Check committed and fresh floatbasic references (skip fresh loudly without the pinned image)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testFloatbasic$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-floatbasic-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-floatbasic --out $(BUILD_DIR)/oracle-floatbasic --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) floatbasic --out $(BUILD_DIR)/floatbasic-committed --seed 20261026 --count 3000 && \
	   for fn in floorf ceilf truncf roundf rintf fabsf copysignf sqrtf; do \
	     cmp tests/corpus/$$fn.corpus $(BUILD_DIR)/floatbasic-committed/$$fn.corpus || exit 1; \
	   done && \
	   GMATH_FLOATBASIC_CORPUS_DIR=$(BUILD_DIR)/oracle-floatbasic LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testFloatbasic$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-floatbasic-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-floatbasic-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
	 else exit $$rc; fi

check-planted-cbrt: $(OBJ_DIR)/tests/test_cbrt.o $(LIBOBJECTS) $(HASH_PROBE) ## Prove cbrt implementation, oracle and hash defects fail
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_cbrt.o' PLANT_PROBE='$(HASH_PROBE)' \
	 PLANT_LD_PATH='$(TEST_LD_PATH)' PLANT_WORK='$(BUILD_DIR)/planted-cbrt' \
	 python3 tools/check-planted-cbrt.py

oracle-fit-cbrt: ## Regenerate the cube-root seed table in the pinned image
	@$(ORACLE) fit-cbrt > src/elementary/cbrt_table.h.tmp && mv src/elementary/cbrt_table.h.tmp src/elementary/cbrt_table.h

oracle-cbrt: ## Regenerate committed real cube-root references in the pinned image
	@$(ORACLE) cbrt --out $(CORPUS_DIR) --seed 20261026 --count 3000

check-cbrt-oracle: $(APP_DIR)/testCbrt$(EXE_EXTENSION) ## Check committed and fresh cbrt references (skip fresh loudly without the pinned image)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testCbrt$(EXE_EXTENSION) --gtest_brief=1
	@mkdir -p $(BUILD_DIR); \
	 seed=$${GMATH_ORACLE_SEED:-$$(date +%s)}; rc=0; \
	 printf 'check-cbrt-oracle: fresh seed %s\n' "$$seed"; \
	 $(ORACLE) fresh-cbrt --out $(BUILD_DIR)/oracle-cbrt --seed $$seed --count 3000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) cbrt --out $(BUILD_DIR)/cbrt-committed --seed 20261026 --count 3000 && \
	   cmp tests/corpus/cbrt.corpus $(BUILD_DIR)/cbrt-committed/cbrt.corpus && \
	   $(ORACLE) fit-cbrt > $(BUILD_DIR)/cbrt-committed/cbrt_table.h && \
	   cmp src/elementary/cbrt_table.h $(BUILD_DIR)/cbrt-committed/cbrt_table.h && \
	   GMATH_CBRT_CORPUS_DIR=$(BUILD_DIR)/oracle-cbrt LD_LIBRARY_PATH="$(TEST_LD_PATH)" \
	   $(APP_DIR)/testCbrt$(EXE_EXTENSION) --gtest_brief=1 \
	   || { printf 'check-cbrt-oracle: FAIL with seed %s\n' "$$seed" >&2; exit 1; }; \
	 elif [ $$rc -eq 3 ]; then \
	   printf 'check-cbrt-oracle: SKIPPED fresh reference and committed regeneration; committed corpus still checked\n'; \
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

# Exact integral/fractional split; default checks do not require an oracle image.
FRACTION_SPLIT_PROBE := $(APP_DIR)/tools/probe-fraction-split$(EXE_EXTENSION)
$(FRACTION_SPLIT_PROBE): tools/probe-fraction-split.c tests/fraction_split_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-fraction-split check-planted-fraction-split oracle-fraction-split
check-fraction-split: $(FRACTION_SPLIT_PROBE)
	@python3 tools/check-fraction-split.py $(CORPUS_DIR)
	@python3 tools/check-split-controls.py $(FRACTION_SPLIT_PROBE) --corpus $(CORPUS_DIR)
check-planted-fraction-split: $(OBJ_DIR)/tests/test_fraction_split.o $(LIBOBJECTS) $(FRACTION_SPLIT_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' PLANT_CXX='$(CXX)' \
	 PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_fraction_split.o' PLANT_WORK='$(BUILD_DIR)/planted-fraction-split' \
	 python3 tools/check-planted-fraction-split.py
oracle-fraction-split:
	@$(ORACLE) fraction_split --out $(CORPUS_DIR) --seed 20261027 --count 2000
FRACTION_SPLIT_BENCH := $(APP_DIR)/tools/bench-fraction-split$(EXE_EXTENSION)
$(FRACTION_SPLIT_BENCH): tools/bench-fraction-split.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-fraction-split
bench-fraction-split: $(FRACTION_SPLIT_BENCH)
	@$(FRACTION_SPLIT_BENCH)

.PHONY: check-fraction-split-oracle
check-fraction-split-oracle: $(FRACTION_SPLIT_PROBE)
	@rc=0; seed=$$(python3 -c 'import secrets;print(secrets.randbits(63))'); \
	 $(ORACLE) fresh-fraction_split --out $(BUILD_DIR)/oracle-fraction-split --seed $$seed --count 2000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) fraction_split --out $(BUILD_DIR)/split-committed --seed 20261027 --count 2000 && \
	   for f in modf-special.corpus modff-special.corpus modf_fraction.corpus modf_integral.corpus modff_fraction.corpus modff_integral.corpus fraction_split-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/split-committed/$$f || exit 1; \
	   done && python3 tools/check-split-controls.py $(FRACTION_SPLIT_PROBE) --fresh $(BUILD_DIR)/oracle-fraction-split --seed $$seed --count 2000; \
	 elif [ $$rc -eq 3 ]; then echo 'split oracle: SKIPPED optional pinned regeneration/fresh'; else exit $$rc; fi

# Exact floating exponent values; raw state validation is standalone C17.
EXPONENT_VALUE_PROBE := $(APP_DIR)/tools/probe-exponent-value$(EXE_EXTENSION)
$(EXPONENT_VALUE_PROBE): tools/probe-exponent-value.c tests/exponent_value_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-exponent-value oracle-exponent-value
check-exponent-value: $(EXPONENT_VALUE_PROBE)
	@python3 tools/check-exponent-value.py $(CORPUS_DIR)
	@python3 tools/check-exponent-controls.py $(EXPONENT_VALUE_PROBE) --corpus $(CORPUS_DIR)
oracle-exponent-value:
	@$(ORACLE) exponent_value --out $(CORPUS_DIR) --seed 20261027 --count 2000
.PHONY: check-planted-exponent-value check-exponent-value-oracle
check-planted-exponent-value: $(OBJ_DIR)/tests/test_exponent_value.o $(LIBOBJECTS) $(EXPONENT_VALUE_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_exponent_value.o' PLANT_WORK='$(BUILD_DIR)/planted-exponent-value' \
	 python3 tools/check-planted-exponent-value.py
check-exponent-value-oracle: $(EXPONENT_VALUE_PROBE) $(HASH_PROBE)
	@rc=0; seed=$$(python3 -c 'import secrets;print(secrets.randbits(63))'); \
	 $(ORACLE) fresh-exponent_value --out $(BUILD_DIR)/oracle-exponent-value --seed $$seed --count 2000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) exponent_value --out $(BUILD_DIR)/exponent-committed --seed 20261027 --count 2000 && \
	   for f in logb-special.corpus logbf-special.corpus logb.corpus logbf.corpus exponent_value-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/exponent-committed/$$f || exit 1; \
	   done && python3 tools/check-exponent-controls.py $(EXPONENT_VALUE_PROBE) --fresh $(BUILD_DIR)/oracle-exponent-value --seed $$seed --count 2000 --numeric-probe $(HASH_PROBE); \
	 elif [ $$rc -eq 3 ]; then echo 'exponent oracle: SKIPPED optional pinned regeneration/fresh'; else exit $$rc; fi
EXPONENT_VALUE_BENCH := $(APP_DIR)/tools/bench-exponent-value$(EXE_EXTENSION)
$(EXPONENT_VALUE_BENCH): tools/bench-exponent-value.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-exponent-value
bench-exponent-value: $(EXPONENT_VALUE_BENCH)
	@$(EXPONENT_VALUE_BENCH)

# Optional actual-prior object-backed exponent comparisons; ordinary gates do
# not need Git or a prior object. Force relinking for configuration changes.
EXPONENT_REFERENCE_OBJECT ?=
EXPONENT_REFERENCE_METADATA ?= $(if $(strip $(EXPONENT_REFERENCE_OBJECT)),$(EXPONENT_REFERENCE_OBJECT).json)
.PHONY: exponent-reference-force
exponent-reference-force:
EXPONENT_DOMAIN_COMPARE := $(APP_DIR)/tools/compare-exponent-domain$(EXE_EXTENSION)
EXPONENT_REFERENCE_PROBE := $(APP_DIR)/tools/probe-exponent-prior$(EXE_EXTENSION)
EXPONENT_REFERENCE_BENCH := $(APP_DIR)/tools/bench-exponent-prior$(EXE_EXTENSION)
$(EXPONENT_DOMAIN_COMPARE): tools/compare-exponent-domain.c tests/exponent_value_domain.h tests/exponent_value_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(EXPONENT_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) exponent-reference-force
	@test -n "$(EXPONENT_REFERENCE_OBJECT)" || { echo 'exponent comparison requires an actual EXPONENT_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(EXPONENT_REFERENCE_OBJECT)" "$(EXPONENT_REFERENCE_METADATA)" --family exponent --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_LOGB_REFERENCE=gmath_exponent_prior_logb -DGMATH_LOGBF_REFERENCE=gmath_exponent_prior_logbf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(EXPONENT_REFERENCE_PROBE): tools/probe-exponent-value.c tests/exponent_value_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(EXPONENT_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) exponent-reference-force
	@test -n "$(EXPONENT_REFERENCE_OBJECT)" || { echo 'exponent probe requires EXPONENT_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(EXPONENT_REFERENCE_OBJECT)" "$(EXPONENT_REFERENCE_METADATA)" --family exponent --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_LOGB_REFERENCE=gmath_exponent_prior_logb -DGMATH_LOGBF_REFERENCE=gmath_exponent_prior_logbf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(EXPONENT_REFERENCE_BENCH): tools/bench-exponent-value.c $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(EXPONENT_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) exponent-reference-force
	@test -n "$(EXPONENT_REFERENCE_OBJECT)" || { echo 'exponent benchmark requires EXPONENT_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(EXPONENT_REFERENCE_OBJECT)" "$(EXPONENT_REFERENCE_METADATA)" --family exponent --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_LOGB_BASELINE=gmath_exponent_prior_logb -DGMATH_LOGBF_BASELINE=gmath_exponent_prior_logbf -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(LDFLAGS) -lm
.PHONY: check-exponent-prior bench-exponent-prior
check-exponent-prior: $(EXPONENT_DOMAIN_COMPARE) $(EXPONENT_REFERENCE_PROBE)
	@python3 tools/check-exponent-domain.py $(EXPONENT_DOMAIN_COMPARE) --baseline-metadata "$(EXPONENT_REFERENCE_METADATA)"
	@$(EXPONENT_REFERENCE_PROBE) "$(CORPUS_DIR)" > $(BUILD_DIR)/exponent-prior.actual
	@sed 's/ from .*//' $(BUILD_DIR)/exponent-prior.actual > $(BUILD_DIR)/exponent-prior.normalized
	@cmp $(CORPUS_DIR)/exponent_value-special.hash $(BUILD_DIR)/exponent-prior.normalized
bench-exponent-prior: $(EXPONENT_REFERENCE_BENCH)
	@$(EXPONENT_REFERENCE_BENCH)

.PHONY: check-exponent-domain-driver
check-exponent-domain-driver:
	@python3 tools/check-exponent-domain.py --calibrate
.PHONY: check-exponent-native-controls
check-exponent-native-controls: $(APP_DIR)/$(STATIC_TARGET) $(EXPONENT_REFERENCE_OBJECT) $(EXPONENT_REFERENCE_METADATA)
	@NATIVE_CC='$(CC)' NATIVE_CFLAGS='$(CFLAGS) $(INCLUDE)' NATIVE_LIB_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 NATIVE_LDFLAGS='$(LDFLAGS)' NATIVE_LIBRARY='$(APP_DIR)/$(STATIC_TARGET)' \
	 NATIVE_REFERENCE='$(EXPONENT_REFERENCE_OBJECT)' NATIVE_METADATA='$(EXPONENT_REFERENCE_METADATA)' \
	 NATIVE_CORPUS='$(CORPUS_DIR)' NATIVE_WORK='$(BUILD_DIR)/exponent-native-controls' python3 tools/check-exponent-native-controls.py

# Native-long exponent scaling, independent raw width/state references.
LONG_SCALE_PROBE := $(APP_DIR)/tools/probe-long-scale$(EXE_EXTENSION)
$(LONG_SCALE_PROBE): tools/probe-long-scale.c tests/long_scale_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-long-scale check-planted-long-scale oracle-long-scale check-long-scale-oracle
check-long-scale: $(LONG_SCALE_PROBE)
	@python3 tools/check-long-scale.py $(CORPUS_DIR)
	@longbits=$$($(CC) $(CFLAGS) -dM -E -x c /dev/null | awk '$$2=="__SIZEOF_LONG__"{print $$3*8}'); \
	 python3 tools/check-long-scale-output.py $(LONG_SCALE_PROBE) --corpus $(CORPUS_DIR) --long-bits "$$longbits"
oracle-long-scale:
	@$(ORACLE) long_scale --out $(CORPUS_DIR) --seed 20261028 --count 1000
check-long-scale-oracle: $(LONG_SCALE_PROBE) $(HASH_PROBE)
	@rc=0; seed=$$(python3 -c 'import secrets;print(secrets.randbits(63))'); \
	 $(ORACLE) fresh-long_scale --out $(BUILD_DIR)/oracle-long-scale --seed $$seed --count 1000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) long_scale --out $(BUILD_DIR)/longscale-committed --seed 20261028 --count 1000 && \
	   for f in scalbln-special.corpus scalblnf-special.corpus scalbln.corpus scalblnf.corpus long_scale-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/longscale-committed/$$f || exit 1; \
	   done && longbits=$$($(CC) $(CFLAGS) -dM -E -x c /dev/null | awk '$$2=="__SIZEOF_LONG__"{print $$3*8}') && \
	   python3 tools/check-long-scale-output.py $(LONG_SCALE_PROBE) --fresh $(BUILD_DIR)/oracle-long-scale --seed $$seed --count 1000 --long-bits "$$longbits" --numeric-probe $(HASH_PROBE); \
	 elif [ $$rc -eq 3 ]; then echo 'long scale oracle: SKIPPED optional pinned regeneration/fresh'; else exit $$rc; fi
	@longbits=$$($(CC) $(CFLAGS) -dM -E -x c /dev/null | awk '$$2=="__SIZEOF_LONG__"{print $$3*8}'); \
	 python3 tools/check-long-scale-oracle.py --work $(BUILD_DIR)/longscale-oracle-controls --probe $(LONG_SCALE_PROBE) --numeric-probe $(HASH_PROBE) --long-bits "$$longbits"
check-planted-long-scale: $(OBJ_DIR)/tests/test_long_scale.o $(LIBOBJECTS) $(LONG_SCALE_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_RAW_LDFLAGS='$(LDFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_long_scale.o' PLANT_WORK='$(BUILD_DIR)/planted-long-scale' \
	 python3 tools/check-planted-long-scale.py
LONG_SCALE_BENCH := $(APP_DIR)/tools/bench-long-scale$(EXE_EXTENSION)
$(LONG_SCALE_BENCH): tools/bench-long-scale.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-long-scale
bench-long-scale: $(LONG_SCALE_BENCH)
	@$(LONG_SCALE_BENCH)

# Float cube-root wrapper and independently cube-certified references.
CBRTF_PROBE := $(APP_DIR)/tools/probe-cbrtf$(EXE_EXTENSION)
$(CBRTF_PROBE): tools/probe-cbrtf.c tests/cbrtf_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-cbrtf check-cbrtf-oracle check-planted-cbrtf
check-cbrtf: $(CBRTF_PROBE)
	@python3 tools/check-cbrtf.py --probe $(CBRTF_PROBE) --corpus $(CORPUS_DIR) --controls
check-cbrtf-oracle: check-cbrtf $(CBRTF_PROBE) $(APP_DIR)/testCbrtf$(EXE_EXTENSION)
	@LD_LIBRARY_PATH="$(TEST_LD_PATH)" $(APP_DIR)/testCbrtf$(EXE_EXTENSION) --gtest_brief=1
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(python3 -c 'import secrets;print(secrets.randbits(63))')}; \
	 echo "cbrtf fresh seed $$seed count 1000"; \
	 $(ORACLE) fresh-cbrtf --out $(BUILD_DIR)/oracle-cbrtf --seed $$seed --count 1000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) cbrtf --out $(BUILD_DIR)/cbrtf-committed --seed 20261028 --count 1000 && \
	   cmp tests/corpus/cbrtf.corpus $(BUILD_DIR)/cbrtf-committed/cbrtf.corpus && \
	   cmp tests/corpus/cbrtf-special.corpus $(BUILD_DIR)/cbrtf-committed/cbrtf-special.corpus && \
	   python3 tools/check-cbrtf.py --fresh --seed $$seed --count 1000 --probe $(CBRTF_PROBE) --corpus $(BUILD_DIR)/oracle-cbrtf --unit $(APP_DIR)/testCbrtf$(EXE_EXTENSION); \
	 elif [ $$rc -eq 3 ]; then echo 'cbrtf oracle: SKIPPED optional pinned generation'; else exit $$rc; fi
	@python3 tools/check-cbrtf-oracle.py --work $(BUILD_DIR)/cbrtf-oracle-controls --probe $(CBRTF_PROBE)
check-planted-cbrtf: $(APP_DIR)/$(STATIC_TARGET) $(OBJ_DIR)/tests/test_cbrtf.o $(CBRTF_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_RAW_LDFLAGS='$(LDFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_cbrtf.o' \
	 PLANT_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' PLANT_WORK='$(BUILD_DIR)/planted-cbrtf' \
	 python3 tools/check-planted-cbrtf.py
CBRTF_BENCH := $(APP_DIR)/tools/bench-cbrtf$(EXE_EXTENSION)
$(CBRTF_BENCH): tools/bench-cbrtf.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-cbrtf
bench-cbrtf: $(CBRTF_BENCH)
	@$(CBRTF_BENCH)

# Source-linked all-mode bound and compatibility controller accounting.
.PHONY: check-cbrtf-fast-budget check-cbrtf-compat-driver
check-cbrtf-fast-budget:
	@python3 tools/oracle/check_cbrtf_fast_budget.py
	@python3 tools/check-cbrtf-fast-budget.py
check-cbrtf-compat-driver:
	@python3 tools/check-cbrtf-compat.py --calibrate

# Actual-prior comparisons are optional; default gates need no Git/prior object.
CBRTF_REFERENCE_OBJECT ?=
CBRTF_REFERENCE_METADATA ?= $(if $(strip $(CBRTF_REFERENCE_OBJECT)),$(CBRTF_REFERENCE_OBJECT).json)
.PHONY: cbrtf-reference-force
cbrtf-reference-force:
CBRTF_COMPARE := $(APP_DIR)/tools/compare-cbrtf$(EXE_EXTENSION)
CBRTF_REFERENCE_PROBE := $(APP_DIR)/tools/probe-cbrtf-prior$(EXE_EXTENSION)
CBRTF_REFERENCE_BENCH := $(APP_DIR)/tools/bench-cbrtf-prior$(EXE_EXTENSION)
$(CBRTF_COMPARE): tools/compare-cbrtf.c $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(CBRTF_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) cbrtf-reference-force
	@test -n "$(CBRTF_REFERENCE_OBJECT)" || { echo 'cbrtf comparison requires an actual CBRTF_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(CBRTF_REFERENCE_OBJECT)" "$(CBRTF_REFERENCE_METADATA)" --family cbrtf --expected-revision 412417c7a0edc5b0066296e578400dd21d4685e4 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_CBRTF_REFERENCE=gmath_cbrtf_prior -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(CBRTF_REFERENCE_PROBE): tools/probe-cbrtf.c tests/cbrtf_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(CBRTF_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) cbrtf-reference-force
	@test -n "$(CBRTF_REFERENCE_OBJECT)" || { echo 'cbrtf probe requires CBRTF_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(CBRTF_REFERENCE_OBJECT)" "$(CBRTF_REFERENCE_METADATA)" --family cbrtf --expected-revision 412417c7a0edc5b0066296e578400dd21d4685e4 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_CBRTF_REFERENCE=gmath_cbrtf_prior -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(CBRTF_REFERENCE_BENCH): tools/bench-cbrtf.c $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(CBRTF_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) cbrtf-reference-force
	@test -n "$(CBRTF_REFERENCE_OBJECT)" || { echo 'cbrtf benchmark requires CBRTF_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(CBRTF_REFERENCE_OBJECT)" "$(CBRTF_REFERENCE_METADATA)" --family cbrtf --expected-revision 412417c7a0edc5b0066296e578400dd21d4685e4 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_CBRTF_BASELINE=gmath_cbrtf_prior -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(LDFLAGS) -lm
.PHONY: check-cbrtf-prior bench-cbrtf-prior
check-cbrtf-prior: $(CBRTF_COMPARE) $(CBRTF_REFERENCE_PROBE)
	@python3 tools/check-cbrtf-compat.py $(CBRTF_COMPARE) --baseline-metadata "$(CBRTF_REFERENCE_METADATA)"
	@$(CBRTF_REFERENCE_PROBE) $(CORPUS_DIR)
bench-cbrtf-prior: $(CBRTF_REFERENCE_BENCH)
	@$(CBRTF_REFERENCE_BENCH)

.PHONY: check-cbrtf-native-controls
check-cbrtf-native-controls: $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(CBRTF_REFERENCE_METADATA)
	@test -n "$(CBRTF_REFERENCE_OBJECT)" || { echo 'native controls require CBRTF_REFERENCE_OBJECT' >&2; exit 1; }
	@NATIVE_CC='$(CC)' NATIVE_CXX='$(CXX) $(CXXFLAGS)' NATIVE_CFLAGS='$(CFLAGS) $(INCLUDE)' \
	 NATIVE_LIB_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' NATIVE_INCLUDE='$(INCLUDE)' NATIVE_LDFLAGS='$(LDFLAGS)' \
	 NATIVE_LIBRARY='$(APP_DIR)/$(STATIC_TARGET)' NATIVE_REFERENCE='$(CBRTF_REFERENCE_OBJECT)' NATIVE_METADATA='$(CBRTF_REFERENCE_METADATA)' \
	 NATIVE_CORPUS='$(CORPUS_DIR)' NATIVE_WORK='$(BUILD_DIR)/cbrtf-native-controls' python3 tools/check-cbrtf-native-controls.py

NM ?= nm
OBJCOPY ?= objcopy
CBRTF_BASELINE_DIR ?= $(BUILD_DIR)/cbrtf-baseline
.PHONY: build-cbrtf-baseline
build-cbrtf-baseline: $(FLAGS_STAMP) | $(LIBVER_GEN)
	@python3 tools/build-cbrtf-baseline.py --out "$(CBRTF_BASELINE_DIR)" --cc='$(CC)' --flags='$(LIB_CFLAGS) $(INCLUDE)' --nm='$(NM)' --objcopy='$(OBJCOPY)'

CBRTF_BOUNDARY_PROBE := $(APP_DIR)/tools/probe-cbrtf-boundaries$(EXE_EXTENSION)
$(CBRTF_BOUNDARY_PROBE): tools/probe-cbrtf-boundaries.c tests/cbrtf_probe.h src/elementary/float_cbrt.c src/elementary/cbrt_table.h src/elementary/elem_common.h $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(CBRTF_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) cbrtf-reference-force
	@test -n "$(CBRTF_REFERENCE_OBJECT)" || { echo 'boundary probe requires CBRTF_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(CBRTF_REFERENCE_OBJECT)" "$(CBRTF_REFERENCE_METADATA)" --family cbrtf --expected-revision 412417c7a0edc5b0066296e578400dd21d4685e4 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_CBRTF_REFERENCE=gmath_cbrtf_prior -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(CBRTF_REFERENCE_OBJECT) $(LDFLAGS) -lm
.PHONY: check-cbrtf-boundaries
check-cbrtf-boundaries: $(CBRTF_BOUNDARY_PROBE)
	@$(CBRTF_BOUNDARY_PROBE)

# Exact IEEE remainder and signed seven-bit quotient fragments.
IEEE_REMAINDER_PROBE := $(APP_DIR)/tools/probe-ieee-remainder$(EXE_EXTENSION)
$(IEEE_REMAINDER_PROBE): tools/probe-ieee-remainder.c tests/ieee_remainder_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-ieee-remainder check-planted-ieee-remainder
check-ieee-remainder: $(IEEE_REMAINDER_PROBE) $(APP_DIR)/testIeee_remainder$(EXE_EXTENSION) $(HASH_PROBE)
	@python3 tools/check-ieee-remainder.py --probe $(IEEE_REMAINDER_PROBE) --corpus $(CORPUS_DIR) --unit $(APP_DIR)/testIeee_remainder$(EXE_EXTENSION) --controls
	@python3 tools/check-ieee-remainder-numeric.py --probe $(HASH_PROBE) --corpus $(CORPUS_DIR) --controls
check-planted-ieee-remainder: $(APP_DIR)/$(STATIC_TARGET) $(OBJ_DIR)/tests/test_ieee_remainder.o $(IEEE_REMAINDER_PROBE)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_RAW_LDFLAGS='$(LDFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_ieee_remainder.o' \
	 PLANT_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' PLANT_WORK='$(BUILD_DIR)/planted-ieee-remainder' \
	 python3 tools/check-planted-ieee-remainder.py
.PHONY: check-ieee-remainder-reference-controls
check-ieee-remainder-reference-controls:
	@python3 tools/check-ieee-remainder-reference-controls.py
.PHONY: oracle-ieee-remainder check-ieee-remainder-oracle
oracle-ieee-remainder:
	@$(ORACLE) ieee_remainder --out $(CORPUS_DIR) --seed 20261028 --count 1000
check-ieee-remainder-oracle: $(IEEE_REMAINDER_PROBE) $(APP_DIR)/testIeee_remainder$(EXE_EXTENSION) $(HASH_PROBE)
	@rc=0; seed=$${GMATH_ORACLE_SEED:-$$(python3 -c 'import secrets;print(secrets.randbits(63))')}; \
	 echo "IEEE remainder fresh seed $$seed count 1000"; \
	 $(ORACLE) fresh-ieee_remainder --out $(BUILD_DIR)/oracle-ieee-remainder --seed $$seed --count 1000 || rc=$$?; \
	 if [ $$rc -eq 0 ]; then \
	   $(ORACLE) ieee_remainder --out $(BUILD_DIR)/ieee-remainder-committed --seed 20261028 --count 1000 && \
	   for f in remainder-special.corpus remainderf-special.corpus remainder.corpus remainderf.corpus remainder_quotient.corpus remainderf_quotient.corpus ieee_remainder-special.hash; do \
	     cmp tests/corpus/$$f $(BUILD_DIR)/ieee-remainder-committed/$$f || exit 1; \
	   done && python3 tools/check-ieee-remainder.py --fresh --seed $$seed --count 1000 --probe $(IEEE_REMAINDER_PROBE) --corpus $(BUILD_DIR)/oracle-ieee-remainder --unit $(APP_DIR)/testIeee_remainder$(EXE_EXTENSION) && python3 tools/check-ieee-remainder-numeric.py --probe $(HASH_PROBE) --corpus $(BUILD_DIR)/oracle-ieee-remainder; \
	 elif [ $$rc -eq 3 ]; then echo 'IEEE remainder oracle: SKIPPED optional pinned generation'; else exit $$rc; fi
	@python3 tools/check-ieee-remainder-oracle.py --work $(BUILD_DIR)/ieee-remainder-oracle-controls --probe $(IEEE_REMAINDER_PROBE)
IEEE_REMAINDER_BENCH := $(APP_DIR)/tools/bench-ieee-remainder$(EXE_EXTENSION)
$(IEEE_REMAINDER_BENCH): tools/bench-ieee-remainder.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-ieee-remainder
bench-ieee-remainder: $(IEEE_REMAINDER_BENCH)
	@$(IEEE_REMAINDER_BENCH)
IEEE_REMAINDER_PORTABLE_PROBE := $(APP_DIR)/tools/probe-ieee-remainder-portable$(EXE_EXTENSION)
$(IEEE_REMAINDER_PORTABLE_PROBE): tools/probe-ieee-remainder.c tests/ieee_remainder_probe.h tests/corpus_hash.h src/elementary/ieee_remainder.c src/elementary/elem_common.h Makefile $(FLAGS_STAMP) | $(LIBVER_GEN)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -DGMATH_BUILD -DGMATH_IEEE_REMAINDER_PORTABLE_BITS -o $@ tools/probe-ieee-remainder.c src/elementary/ieee_remainder.c $(LDFLAGS) -lm
.PHONY: check-ieee-remainder-portable check-planted-ieee-remainder-portable
check-ieee-remainder-portable: $(IEEE_REMAINDER_PORTABLE_PROBE) check-planted-ieee-remainder-portable
	@python3 tools/check-ieee-remainder.py --probe $(IEEE_REMAINDER_PORTABLE_PROBE) --corpus $(CORPUS_DIR)
check-planted-ieee-remainder-portable: $(APP_DIR)/$(STATIC_TARGET) $(OBJ_DIR)/tests/test_ieee_remainder.o
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE) -DGMATH_IEEE_REMAINDER_PORTABLE_BITS' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' \
	 PLANT_RAW_LDFLAGS='$(LDFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_ieee_remainder.o' \
	 PLANT_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' PLANT_WORK='$(BUILD_DIR)/planted-ieee-remainder-portable' PLANT_EXPECT_PORTABLE='1' \
	 python3 tools/check-planted-ieee-remainder.py

# Actual prior IEEE remainder builds are optional, with caller-declared identity.
IEEE_REMAINDER_REFERENCE_OBJECT ?=
IEEE_REMAINDER_REFERENCE_METADATA ?= $(if $(strip $(IEEE_REMAINDER_REFERENCE_OBJECT)),$(IEEE_REMAINDER_REFERENCE_OBJECT).json)
IEEE_REMAINDER_BASELINE_DIR ?= $(BUILD_DIR)/ieee-remainder-baseline
.PHONY: build-ieee-remainder-baseline ieee-remainder-reference-force
ieee-remainder-reference-force:
build-ieee-remainder-baseline: $(FLAGS_STAMP) | $(LIBVER_GEN)
	@python3 tools/build-ieee-remainder-baseline.py --out "$(IEEE_REMAINDER_BASELINE_DIR)" --cc='$(CC)' --flags='$(LIB_CFLAGS) $(INCLUDE)' --nm='$(NM)' --objcopy='$(OBJCOPY)'
IEEE_REMAINDER_PRIOR_PROBE := $(APP_DIR)/tools/probe-ieee-remainder-prior$(EXE_EXTENSION)
IEEE_REMAINDER_PRIOR_BENCH := $(APP_DIR)/tools/bench-ieee-remainder-prior$(EXE_EXTENSION)
$(IEEE_REMAINDER_PRIOR_PROBE): tools/probe-ieee-remainder.c tests/ieee_remainder_initial.h tests/ieee_remainder_probe.h tests/ieee_remainder_prior.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(IEEE_REMAINDER_REFERENCE_OBJECT) $(IEEE_REMAINDER_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) ieee-remainder-reference-force
	@test -n "$(IEEE_REMAINDER_REFERENCE_OBJECT)" || { echo 'IEEE remainder probe requires IEEE_REMAINDER_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(IEEE_REMAINDER_REFERENCE_OBJECT)" "$(IEEE_REMAINDER_REFERENCE_METADATA)" --family ieee_remainder --expected-revision a54cfbacafa735c0bc7fd1a56af869b8877fa501 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_IEEE_REMAINDER_PRIOR -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(IEEE_REMAINDER_REFERENCE_OBJECT) $(LDFLAGS) -lm
$(IEEE_REMAINDER_PRIOR_BENCH): tools/bench-ieee-remainder.c tests/ieee_remainder_probe.h tests/corpus_hash.h tests/ieee_remainder_prior.h $(APP_DIR)/$(STATIC_TARGET) $(IEEE_REMAINDER_REFERENCE_OBJECT) $(IEEE_REMAINDER_REFERENCE_METADATA) tools/adjacent_baseline.py $(FLAGS_STAMP) ieee-remainder-reference-force
	@test -n "$(IEEE_REMAINDER_REFERENCE_OBJECT)" || { echo 'IEEE remainder benchmark requires IEEE_REMAINDER_REFERENCE_OBJECT' >&2; exit 1; }
	@mkdir -p $(dir $@)
	@python3 tools/adjacent_baseline.py "$(IEEE_REMAINDER_REFERENCE_OBJECT)" "$(IEEE_REMAINDER_REFERENCE_METADATA)" --family ieee_remainder --expected-revision a54cfbacafa735c0bc7fd1a56af869b8877fa501 --flags='$(LIB_CFLAGS) $(INCLUDE)' --cc='$(CC)' --header "$@.identity.h"
	$(CC) $(CFLAGS) $(INCLUDE) -include "$@.identity.h" -DGMATH_IEEE_REMAINDER_PRIOR -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(IEEE_REMAINDER_REFERENCE_OBJECT) $(LDFLAGS) -lm
.PHONY: check-ieee-remainder-prior bench-ieee-remainder-prior
check-ieee-remainder-prior: $(IEEE_REMAINDER_PRIOR_PROBE)
	@python3 tools/check-ieee-remainder-prior.py $(IEEE_REMAINDER_PRIOR_PROBE) --metadata "$(IEEE_REMAINDER_REFERENCE_METADATA)" --corpus $(CORPUS_DIR)
bench-ieee-remainder-prior: $(IEEE_REMAINDER_PRIOR_BENCH)
	@$(IEEE_REMAINDER_PRIOR_BENCH)

.PHONY: check-ieee-remainder-prior-driver
check-ieee-remainder-prior-driver:
	@python3 tools/check-ieee-remainder-prior.py --calibrate

.PHONY: check-ieee-remainder-prior-controls
check-ieee-remainder-prior-controls: $(APP_DIR)/$(STATIC_TARGET) $(IEEE_REMAINDER_REFERENCE_OBJECT) $(IEEE_REMAINDER_REFERENCE_METADATA)
	@test -n "$(IEEE_REMAINDER_REFERENCE_OBJECT)" || { echo 'IEEE native controls require IEEE_REMAINDER_REFERENCE_OBJECT' >&2; exit 1; }
	@NATIVE_CC='$(CC)' NATIVE_CFLAGS='$(CFLAGS) $(INCLUDE)' NATIVE_LIB_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 NATIVE_LDFLAGS='$(LDFLAGS)' NATIVE_LIBRARY='$(APP_DIR)/$(STATIC_TARGET)' NATIVE_REFERENCE='$(IEEE_REMAINDER_REFERENCE_OBJECT)' \
	 NATIVE_NM='$(NM)' NATIVE_OBJCOPY='$(OBJCOPY)' NATIVE_METADATA='$(IEEE_REMAINDER_REFERENCE_METADATA)' NATIVE_CORPUS='$(CORPUS_DIR)' NATIVE_WORK='$(BUILD_DIR)/ieee-remainder-prior-controls' \
	 python3 tools/check-ieee-remainder-prior-controls.py

NEARBY_PROBE := $(APP_DIR)/tools/probe-nearby$(EXE_EXTENSION)
$(NEARBY_PROBE): tools/probe-nearby.c tests/nearby_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-nearby oracle-nearby
check-nearby: $(NEARBY_PROBE)
	@python3 tools/check-nearby.py --probe $(NEARBY_PROBE)
oracle-nearby:
	@$(ORACLE) nearby --out $(CORPUS_DIR) --seed 20261028 --count 2000
.PHONY: check-planted-nearby
check-planted-nearby: $(OBJ_DIR)/tests/test_nearby.o $(APP_DIR)/$(STATIC_TARGET)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_nearby.o' \
	 PLANT_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' PLANT_LDFLAGS='$(LDFLAGS)' \
	 PLANT_UNIT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' PLANT_WORK='$(BUILD_DIR)/planted-nearby' \
	 python3 tools/check-planted-nearby.py
.PHONY: check-nearby-controls check-nearby-oracle
check-nearby-controls: $(NEARBY_PROBE) $(APP_DIR)/testNearby$(EXE_EXTENSION) $(HASH_PROBE)
	@python3 tools/check-nearby-controls.py --probe $(NEARBY_PROBE)
check-nearby-oracle: check-nearby $(NEARBY_PROBE) $(APP_DIR)/testNearby$(EXE_EXTENSION) $(HASH_PROBE)
	@seed=$$(od -An -N4 -tu4 /dev/urandom | tr -d ' '); rc=0; \
	 $(ORACLE) fresh-nearby --out $(BUILD_DIR)/oracle-nearby --seed $$seed --count 2000 || rc=$$?; \
	 if [ $$rc -eq 3 ]; then echo 'nearby pinned fresh: SKIPPED optional engine'; \
	 elif [ $$rc -ne 0 ]; then exit $$rc; \
	 else $(ORACLE) nearby --out $(BUILD_DIR)/nearby-committed --seed 20261028 --count 2000 && \
	   for f in nearbyint-special.corpus nearbyintf-special.corpus nearbyint.corpus nearbyintf.corpus nearby-special.hash; do \
	     cmp $(CORPUS_DIR)/$$f $(BUILD_DIR)/nearby-committed/$$f || exit 1; \
	   done && python3 tools/check-nearby-controls.py --probe $(NEARBY_PROBE) --unit $(APP_DIR)/testNearby$(EXE_EXTENSION) \
	     --numeric-probe $(HASH_PROBE) --fresh $(BUILD_DIR)/oracle-nearby --seed $$seed --count 2000; \
	 fi
.PHONY: check-nearby-oracle-controls
check-nearby-oracle-controls:
	@python3 tools/check-nearby-oracle.py --work $(BUILD_DIR)/nearby-oracle-controls
NEARBY_BENCH := $(APP_DIR)/tools/bench-nearby$(EXE_EXTENSION)
$(NEARBY_BENCH): tools/bench-nearby.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-nearby
bench-nearby: $(NEARBY_BENCH)
	@$(NEARBY_BENCH)
NEARBY_LINK_PROBE := $(APP_DIR)/tools/probe-nearby-link$(EXE_EXTENSION)
$(NEARBY_LINK_PROBE): tools/probe-nearby-link.c src/elementary/nearby_mode.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(LIB_CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET)
.PHONY: check-nearby-link
check-nearby-link: $(NEARBY_LINK_PROBE)
NEARBY_PLATFORM_PROBE := $(APP_DIR)/tools/probe-nearby-platform$(EXE_EXTENSION)
$(NEARBY_PLATFORM_PROBE): tools/probe-nearby-link.c src/elementary/nearby_mode.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(LIB_CFLAGS) $(INCLUDE) -DGMATH_NEARBY_LINK_ALLOW_FENV -o $@ $< $(APP_DIR)/$(STATIC_TARGET) -lm
check-nearby-link: $(NEARBY_PLATFORM_PROBE)
	@$(NEARBY_LINK_PROBE)
	@$(NEARBY_PLATFORM_PROBE)
.PHONY: check-nearby-mode-plants
check-nearby-mode-plants:
	@MODE_CC='$(CC)' MODE_FLAGS='$(LIB_CFLAGS) $(INCLUDE)' MODE_WORK='$(BUILD_DIR)/nearby-mode-plants' python3 tools/check-nearby-mode-plants.py

CURRENTINT_PROBE := $(APP_DIR)/tools/probe-currentint$(EXE_EXTENSION)
$(CURRENTINT_PROBE): tools/probe-currentint.c tests/current_ir_probe.h tests/corpus_hash.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: check-currentint check-currentint-oracle oracle-currentint
check-currentint: $(CURRENTINT_PROBE)
	@python3 tools/check-currentint.py --probe $(CURRENTINT_PROBE)
oracle-currentint:
	@$(ORACLE) currentint --out $(CORPUS_DIR) --seed 20261028 --count 2000
check-currentint-oracle: check-currentint $(APP_DIR)/testCurrentint$(EXE_EXTENSION) $(HASH_PROBE)
	@seed=$$(od -An -N4 -tu4 /dev/urandom | tr -d ' '); rc=0; \
	 $(ORACLE) fresh-currentint --out $(BUILD_DIR)/oracle-currentint --seed $$seed --count 2000 || rc=$$?; \
	 if [ $$rc -eq 3 ]; then echo 'currentint fresh: SKIPPED optional engine'; \
	 elif [ $$rc -ne 0 ]; then exit $$rc; \
	 else $(ORACLE) currentint --out $(BUILD_DIR)/currentint-committed --seed 20261028 --count 2000 && \
	   for f in currentint64-special.corpus currentint32-special.corpus currentint-special.hash lrint.corpus lrintf.corpus llrint.corpus llrintf.corpus; do \
	     cmp $(CORPUS_DIR)/$$f $(BUILD_DIR)/currentint-committed/$$f || exit 1; \
	   done && python3 tools/check-currentint.py --probe $(CURRENTINT_PROBE) --unit $(APP_DIR)/testCurrentint$(EXE_EXTENSION) \
	     --numeric $(HASH_PROBE) --fresh --directory $(BUILD_DIR)/oracle-currentint --seed $$seed --count 2000; \
	 fi
.PHONY: check-planted-currentint
check-planted-currentint: $(OBJ_DIR)/tests/test_currentint.o $(APP_DIR)/$(STATIC_TARGET)
	@PLANT_CC='$(CC)' PLANT_CFLAGS='$(LIB_CFLAGS) $(INCLUDE)' \
	 PLANT_CXX='$(CXX) $(CXXFLAGS)' PLANT_TEST_OBJ='$(OBJ_DIR)/tests/test_currentint.o' \
	 PLANT_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' PLANT_LDFLAGS='$(LDFLAGS)' \
	 PLANT_UNIT_LDFLAGS='$(LDFLAGS) $(GTEST_FLAGS)' PLANT_WORK='$(BUILD_DIR)/planted-currentint' \
	 python3 tools/check-planted-currentint.py
.PHONY: check-currentint-controls check-currentint-link
check-currentint-controls: $(CURRENTINT_PROBE)
	@python3 tools/check-currentint-controls.py --probe $(CURRENTINT_PROBE)
CURRENTINT_LINK := $(APP_DIR)/tools/probe-currentint-link$(EXE_EXTENSION)
$(CURRENTINT_LINK): tools/probe-currentint-link.c src/elementary/nearby_mode.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(LIB_CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET)
CURRENTINT_PLATFORM_LINK := $(APP_DIR)/tools/probe-currentint-platform$(EXE_EXTENSION)
$(CURRENTINT_PLATFORM_LINK): tools/probe-currentint-link.c src/elementary/nearby_mode.h $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(LIB_CFLAGS) $(INCLUDE) -DGMATH_CURRENTINT_LINK_ALLOW_FENV -o $@ $< $(APP_DIR)/$(STATIC_TARGET) -lm
check-currentint-link: $(CURRENTINT_LINK) $(CURRENTINT_PLATFORM_LINK)
	@$(CURRENTINT_LINK)
	@$(CURRENTINT_PLATFORM_LINK)
.PHONY: check-currentint-oracle-controls
check-currentint-oracle-controls:
	@python3 tools/check-currentint-oracle.py --work $(BUILD_DIR)/currentint-oracle-controls
CURRENTINT_BENCH := $(APP_DIR)/tools/bench-currentint$(EXE_EXTENSION)
$(CURRENTINT_BENCH): tools/bench-currentint.c $(APP_DIR)/$(STATIC_TARGET) $(FLAGS_STAMP)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $< $(APP_DIR)/$(STATIC_TARGET) $(LDFLAGS) -lm
.PHONY: bench-currentint
bench-currentint: $(CURRENTINT_BENCH)
	@$(CURRENTINT_BENCH)
.PHONY: check-currentint-bench-controls
check-currentint-bench-controls: $(APP_DIR)/$(STATIC_TARGET)
	@BENCH_CC='$(CC)' BENCH_CFLAGS='$(CFLAGS) $(INCLUDE)' BENCH_ARCHIVE='$(APP_DIR)/$(STATIC_TARGET)' \
	 BENCH_LDFLAGS='$(LDFLAGS)' BENCH_WORK='$(BUILD_DIR)/currentint-bench-controls' python3 tools/check-currentint-bench.py
