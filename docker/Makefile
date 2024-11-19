REGISTRY ?= registry.gitlab.com
BR_REGISTRY ?= $(REGISTRY)/bedrocksystems/docker-image
BR_FMDEPS_VERSION ?= 2024-11-01
LLVM_VERSIONS ?= 16 17 18 19
LLVM_MAIN_VERSION ?= 18
SWIPL_VERSIONS ?= 9.0.4 9.1.8 9.2.7 9.3.8
SWIPL_MAIN_VERSION ?= 9.2.7
I_KNOW_WHAT_I_AM_DOING ?= no
QUIET ?= true

# Checking the value of I_KNOW_WHAT_I_AM_DOING.
ifneq ($(I_KNOW_WHAT_I_AM_DOING),yes)
ifneq ($(I_KNOW_WHAT_I_AM_DOING),no)
$(error I_KNOW_WHAT_I_AM_DOING should be either "yes" or "no")
endif
endif

# Support for quiet build.
ifeq ($(QUIET),true)
Q := @
else
ifeq ($(QUIET),false)
Q :=
else
$(error QUIET should be either "true" or "false")
endif
endif

# Support for colors.
CYAN = 36
define color
	"\033[0;$1m$2\033[0m"
endef

all:
	@echo -e $(call color,$(CYAN),See README.md for documentation.)
.PHONY: all

files/br-fm-deps.opam: ../fm-deps/dune-project
	$(Q)dune b --no-print-directory --display=quiet ../fm-deps/br-fm-deps.opam
	$(Q)cp ../fm-deps/br-fm-deps.opam files/br-fm-deps.opam

DOCKER_BUILD_TARGETS =
DOCKER_RUN_TARGETS =
DOCKER_PUSH_TARGETS =

define image-target
build-swipl.$1-llvm.$2: Dockerfile-fm-ci files/br-fm-deps.opam
	@echo "[DOCKER] Building fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2"
	$$(Q)docker buildx build --pull \
		-t $$(BR_REGISTRY):fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2 \
		--build-arg BR_FMDEPS_VERSION=$$(BR_FMDEPS_VERSION) \
		--build-arg BR_SWIPL_VERSION=$1 \
		--build-arg BR_LLVM_MAJ_VER=$2 \
		-f $$< .
.PHONY: build-swipl.$1-llvm.$2
DOCKER_BUILD_TARGETS += build-swipl.$1-llvm.$2

run-swipl.$1-llvm.$2: build-swipl.$1-llvm.$2
	@echo "[DOCKER] Running fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2"
	$$(Q)docker run -i \
		-t $$(BR_REGISTRY):fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2
.PHONY: run-swipl.$1-llvm.$2
DOCKER_RUN_TARGETS += run-swipl.$1-llvm.$2

push-swipl.$1-llvm.$2: build-swipl.$1-llvm.$2
	@echo "[DOCKER] Pusing fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2"
ifeq ($(I_KNOW_WHAT_I_AM_DOING),no)
	@echo "The command that would run would be:"
	@echo "  docker push $$(BR_REGISTRY):fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2"
	@echo -e $(call color,$(CYAN),Use I_KNOW_WHAT_I_AM_DOING=yes to actually run it)
endif
ifeq ($(I_KNOW_WHAT_I_AM_DOING),yes)
	@echo "(Let's hope you did not mess anything up...)"
	$$(Q)docker push $$(BR_REGISTRY):fm-$$(BR_FMDEPS_VERSION)-swipl-$1-llvm-$2
endif
.PHONY: push-swipl.$1-llvm.$2
DOCKER_PUSH_TARGETS += push-swipl.$1-llvm.$2
endef

$(foreach llvm,$(LLVM_VERSIONS),\
	$(eval $(call image-target,$(SWIPL_MAIN_VERSION),$(llvm))))
$(foreach swipl,$(filter-out $(SWIPL_MAIN_VERSION),$(SWIPL_VERSIONS)),\
	$(eval $(call image-target,$(swipl),$(LLVM_MAIN_VERSION))))

build: $(DOCKER_BUILD_TARGETS)
.PHONY: build

push: build $(DOCKER_PUSH_TARGETS)
.PHONY: push

list-targets:
	@echo "$(DOCKER_BUILD_TARGETS)" | tr ' ' '\n' | sort -V
	@echo "$(DOCKER_RUN_TARGETS)" | tr ' ' '\n' | sort -V
	@echo "$(DOCKER_PUSH_TARGETS)" | tr ' ' '\n' | sort -V
.PHONY: list-targets

gitlab-login:
	@echo -n "Enter your GitLab login: "
	@read -r LOGIN; echo $$LOGIN > $@

gitlab-token:
	@echo -e $(call color,$(CYAN),You need a GitLab API token.)
	@echo "See https://gitlab.com/-/user_settings/personal_access_tokens."
	@echo -n "Enter your GitLab API token: "
	@read -r TOKEN; echo $$TOKEN > $@

login: gitlab-login gitlab-token
	$(Q)docker login -u $$(cat $<) --password-stdin $(REGISTRY) < gitlab-token
.PHONY: login

logout:
	$(Q)docker logout $(REGISTRY)
.PHONY: logout

clean:
	@rm -f files/br-fm-deps.opam
.PHONY: clean

clean-all: clean
	@rm -f gitlab-token gitlab-login
.PHONY: clean-token

system-prune:
	@docker system prune
.PHONY: system-prune
