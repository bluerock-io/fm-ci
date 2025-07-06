#!/bin/sh

usage() {
  cat << EOF

Run this script to test gen.ml.

Screen output is saved in test_output.txt; YAML output is saved in test_out.yaml.

Takes no arguments.

EOF
}

[ -n "$1" ] && { usage; exit 1; }

cd $(dirname "$0")

config=test_config.toml

rm -rf repos/

[ -z "${CI_JOB_TOKEN}" ] && CI_JOB_TOKEN=FAKE_TOKEN

ORIGIN_CI_PROJECT_TITLE=BHV \
  ORIGIN_CI_PROJECT_PATH=bedrocksystems/bhv \
  ORIGIN_CI_COMMIT_SHA=`git rev-parse HEAD` \
  ORIGIN_CI_COMMIT_BRANCH=main \
  ORIGIN_CI_PIPELINE_SOURCE=default \
  FM_CI_TRIGGER_KIND=default \
  ORIGIN_CI_MERGE_REQUEST_IID='' \
  dune exec --profile dev ./gen.exe "${CI_JOB_TOKEN}" ${config} test_out.yaml 2>&1 |
  tee test_output.txt
