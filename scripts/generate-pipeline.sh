#!/usr/bin/env bash

cat <<EOF
include: '/templates/.gitlab-ci.yml'

stages:
  - test
  - install
  - release

EOF

for f in $(find charts/* -maxdepth 0 -type d)
do
  CHART_VERSION=$(grep "^version:" ${f}/Chart.yaml | cut -d' ' -f2-)
  CHART_RELEASE="${f##*/}-${CHART_VERSION}"
  cat <<EOF
'${f##*/}:lint':
  stage: test
  extends: .lint
  variables:
    HELM_NAME: "${f##*/}"
  rules:
    - if: '\$CI_COMMIT_TAG =~ "/^$/"'
      changes:
        - ${f}/**/*

'${f##*/}:dev_push':
  stage: release
  extends: .dev_push
  variables:
    HELM_NAME: "${f##*/}"
  rules:
    - if: '\$CI_COMMIT_TAG =~ "/^$/"'
      changes:
        - ${f}/**/*

'${f##*/}:release':
  stage: release
  extends: .release
  variables:
    HELM_NAME: "${f##*/}"
  rules:
    - if: '\$CI_COMMIT_TAG =~ "/^$/"'
      changes:
        - ${f}/Chart.yaml

#'${f##*/}:release_tag':
#  stage: release
#  extends: .release_tag
#  needs:
#    - '${f##*/}:release'
#  variables:
#    HELM_NAME: "${f##*/}"
#    CHART_RELEASE: "${CHART_RELEASE}"
#    CHART_VERSION: "${CHART_VERSION}"
#  rules:
#    - if: '\$CI_COMMIT_TAG =~ "/^$/"'
#      changes:
#        - ${f}/Chart.yaml
#      allow_failure: true

EOF

done
