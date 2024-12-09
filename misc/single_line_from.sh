#!/bin/bash

for i in $(seq 1 40); do
  find $1 -name "*.v" | \
    xargs sed -i '/^From .* Require$/{N;s/\n//;}'
done

for i in $(seq 1 40); do
  find $1 -name "*.v" | \
    xargs sed -i '/^From .* Require .*[^.]$/{N;s/\n//;}'
done
