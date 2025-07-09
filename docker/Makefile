REGISTRY ?= registry.gitlab.com
BR_REGISTRY ?= $(REGISTRY)/bedrocksystems/formal-methods/fm-ci
BR_FMDEPS_VERSION ?= 2025-06-05
RELEASE_TAG ?= fm-release
# Bump the following number when pushing new images with the same version
# numbers. This is necessary to properly invalidate the NOVA cache.
BR_IMAGE_VERSION ?= 1
LLVM_VERSIONS ?= 18 19 20
LLVM_MAIN_VERSION ?= 19
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

files/_dune-project: ../fm-deps/dune-project
	$(Q)cp ../fm-deps/dune-project $@

files/_br-fm-deps.opam: ../fm-deps/dune-project
	$(Q)dune b --no-print-directory --display=quiet ../fm-deps/br-fm-deps.opam
	$(Q)cp ../fm-deps/br-fm-deps.opam $@

DOCKER_BUILD_TARGETS =
DOCKER_RUN_TARGETS =
DOCKER_PUSH_TARGETS =

define image-target
fm-$$(BR_FMDEPS_VERSION)-llvm-$1: Dockerfile-fm-ci files/_br-fm-deps.opam files/_dune-project files/fmdocs_python_deps.txt
	@echo "[DOCKER] Building $$@"
	$$(Q)docker buildx build --pull \
		--platform linux/amd64 \
		-t $$(BR_REGISTRY):$$@ \
		--build-arg BR_FMDEPS_VERSION=$$(BR_FMDEPS_VERSION) \
		--build-arg BR_IMAGE_VERSION=$$(BR_IMAGE_VERSION) \
		--build-arg BR_LLVM_MAJ_VER=$1 \
		-f $$< .
.PHONY: fm-$$(BR_FMDEPS_VERSION)-llvm-$1
DOCKER_BUILD_TARGETS += fm-$$(BR_FMDEPS_VERSION)-llvm-$1

run-fm-$$(BR_FMDEPS_VERSION)-llvm-$1: fm-$$(BR_FMDEPS_VERSION)-llvm-$1
	@echo "[DOCKER] Running $$<"
	$$(Q)docker run -i -t $$(BR_REGISTRY):$$<
.PHONY: run-fm-$$(BR_FMDEPS_VERSION)-llvm-$1
DOCKER_RUN_TARGETS += run-fm-$$(BR_FMDEPS_VERSION)-llvm-$1

push-fm-$$(BR_FMDEPS_VERSION)-llvm-$1: fm-$$(BR_FMDEPS_VERSION)-llvm-$1
	@echo "[DOCKER] Pushing $$<"
ifeq ($(I_KNOW_WHAT_I_AM_DOING),yes)
	@echo "(Let's hope you did not mess anything up...)"
	$$(Q)docker push $$(BR_REGISTRY):$$<
else
	@echo "The command that would run would be:"
	@echo "  docker push $$(BR_REGISTRY):$$<"
	@echo -e $(call color,$(CYAN),Use I_KNOW_WHAT_I_AM_DOING=yes to actually run it)
endif
.PHONY: push-fm-$$(BR_FMDEPS_VERSION)-llvm-$1
DOCKER_PUSH_TARGETS += push-fm-$$(BR_FMDEPS_VERSION)-llvm-$1
endef

$(foreach llvm,$(LLVM_VERSIONS),\
	$(eval $(call image-target,$(llvm))))

build: $(DOCKER_BUILD_TARGETS)
.PHONY: build

push: build $(DOCKER_PUSH_TARGETS)
.PHONY: push

list-targets:
	@echo "$(DOCKER_BUILD_TARGETS)" | tr ' ' '\n' | sort -V
	@echo "$(DOCKER_RUN_TARGETS)" | tr ' ' '\n' | sort -V
	@echo "$(DOCKER_PUSH_TARGETS)" | tr ' ' '\n' | sort -V
.PHONY: list-targets

DEFAULT_TAG := fm-$(BR_FMDEPS_VERSION)-llvm-$(LLVM_MAIN_VERSION)

tag-default: $(DEFAULT_TAG)
	@echo "[DOCKER] Tagging $< as fm-default"
	@docker image tag $(BR_REGISTRY):$< $(BR_REGISTRY):fm-default
.PHONY: tag-default

run-default: tag-default
	@echo "[DOCKER] Running fm-default"
	$(Q)docker run -i -t $(BR_REGISTRY):fm-default
.PHONY: run-default

push-default: tag-default
	@echo "[DOCKER] Pushing tag fm-default"
ifeq ($(I_KNOW_WHAT_I_AM_DOING),yes)
	@echo "(Let's hope you did not mess anything up...)"
	$(Q)docker push $(BR_REGISTRY):fm-default
else
	@echo "The command that would run would be:"
	@echo "  docker push $(BR_REGISTRY):fm-default"
	@echo -e $(call color,$(CYAN),Use I_KNOW_WHAT_I_AM_DOING=yes to actually run it)
endif

.PHONY: push-default

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

ARTIFACT_JOB := https://gitlab.com/api/v4/projects/59374913/jobs/artifacts
ARTIFACT_URL := $(ARTIFACT_JOB)/trigger-default/download?job=gen-installed-artifact
ifndef CI_JOB_TOKEN
HEADER_DEPS := gitlab-token
HEADER := "PRIVATE-TOKEN: $$(cat gitlab-token)"
else
HEADER_DEPS :=
HEADER := "JOB-TOKEN: $(CI_JOB_TOKEN)"
endif

files/fm-artifact.zip: $(HEADER_DEPS)
	@echo -e $(call color,$(CYAN),Downloading the artifact...)
	@curl --show-error --location --output $@ --header $(HEADER) $(ARTIFACT_URL)

files/fmdocs_python_deps.txt: ../../fm-docs/python_requirements.txt
	cp $< $@

bhv_parent=../../../..
docker_build_folder=docker-opam-release

$(bhv_parent)/$(docker_build_folder)/files/bhv.tar:
	cd $(bhv_parent); mkdir -p $(docker_build_folder)/files; time tar cf $(docker_build_folder)/files/bhv.tar bhv/

prepare-opam-release: $(bhv_parent)/$(docker_build_folder)/files/bhv.tar
	cp -t $(bhv_parent)/$(docker_build_folder)/files files/dune-config files/LICENSE files/opam-clean
	cp -t $(bhv_parent)/$(docker_build_folder) Dockerfile-opam-release

build-opam-release: prepare-opam-release
	cd $(bhv_parent)/$(docker_build_folder); \
	docker buildx build \
		-f Dockerfile-opam-release \
		--build-arg BASE_IMAGE=$(BR_REGISTRY):$(DEFAULT_TAG) \
		-t $(BR_REGISTRY):fm-opam-release \
		.

build-release: $(RELEASE_TAG)
.PHONY: build-release

$(RELEASE_TAG): files/fm-artifact.zip
	@echo "[DOCKER] Building $(RELEASE_TAG)"
	$(Q)docker buildx build --pull -t $(BR_REGISTRY):$(RELEASE_TAG) \
		--platform linux/amd64 \
		--build-arg BASE_IMAGE=$(BR_REGISTRY):$(DEFAULT_TAG) \
		-f Dockerfile-artifact-release .
.PHONY: $(RELEASE_TAG)

tag-release: $(RELEASE_TAG)
	@echo "[DOCKER] Tagging $< as fm-release"
	@docker image tag $(BR_REGISTRY):$< $(BR_REGISTRY):fm-release
.PHONY: tag-release

run-release: build-release
	@echo "[DOCKER] Running fm-release"
	$(Q)docker run -i -t $(BR_REGISTRY):$(RELEASE_TAG)
.PHONY: run-release

push-release: build-release
	@echo "[DOCKER] Pushing fm-release"
ifeq ($(I_KNOW_WHAT_I_AM_DOING),yes)
	@echo "(Let's hope you did not mess anything up...)"
	$(Q)docker push $(BR_REGISTRY):$(RELEASE_TAG)
else
	@echo "The command that would run would be:"
	@echo "  docker push $(BR_REGISTRY):$(RELEASE_TAG)"
	@echo -e $(call color,$(CYAN),Use I_KNOW_WHAT_I_AM_DOING=yes to actually run it)
endif

.PHONY: push-release

pull-release:
	$(Q)docker pull $(BR_REGISTRY):$(RELEASE_TAG)

.PHONY: pull-release

PV = $(if $(shell which pv),pv,cat)

# We keep $(BR_IMAGE_VERSION) purely internal.
# FM_RELEASE_FULL_VERSION = $(BR_FMDEPS_VERSION)-$(BR_IMAGE_VERSION)
FM_RELEASE_FULL_VERSION = $(BR_FMDEPS_VERSION)
FM_RELEASE_TARBALL_NAME = bluerock-fm-release-$(FM_RELEASE_FULL_VERSION)

ver-release:
	@echo $(FM_RELEASE_FULL_VERSION)
name-release:
	@echo $(FM_RELEASE_TARBALL_NAME)

$(FM_RELEASE_TARBALL_NAME).tar.gz:
	docker save $(BR_REGISTRY):fm-release | $(PV) | gzip > "$@"

pack-release: $(FM_RELEASE_TARBALL_NAME).tar.gz
.PHONY: pack-release

unpack-release:
	$(PV) $(FM_RELEASE_TARBALL_NAME).tar.gz | docker load
.PHONY: unpack-release

clean:
	@rm -f files/_br-fm-deps.opam files/_dune-project files/fm-artifact.zip
.PHONY: clean

clean-all: clean
	@rm -f gitlab-token gitlab-login
.PHONY: clean-token

system-prune:
	@docker system prune
.PHONY: system-prune
