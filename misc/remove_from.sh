#!/bin/bash

for i in $(seq 1 40); do
  find $1 -name "*.v" | \
    xargs sed -i 's/^From \(.*\) Require Import  *\([^ ][^ ]*\)  *\([^ ].*\)\.$/Require Import \1.\2.\nFrom \1 Require Import \3./g'
  find $1 -name "*.v" | \
    xargs sed -i 's/^From \(.*\) Require Export  *\([^ ][^ ]*\)  *\([^ ].*\)\.$/Require Export \1.\2.\nFrom \1 Require Export \3./g'
done

find $1 -name "*.v" | \
  xargs sed -i 's/^From \(.*\) Require Import  *\([^ ][^ ]*\)\.$/Require Import \1.\2./g'
find $1 -name "*.v" | \
  xargs sed -i 's/^From \(.*\) Require Export  *\([^ ][^ ]*\)\.$/Require Export \1.\2./g'

for i in $(seq 1 40); do
  find $1 -name "*.v" | \
    xargs sed -i 's/^From \(.*\) Require  *\([^ ][^ ]*\)  *\([^ ].*\)\.$/Require \1.\2.\nFrom \1 Require \3./g'
done

find $1 -name "*.v" | \
  xargs sed -i 's/^From \(.*\) Require  *\([^ ][^ ]*\)\.$/Require \1.\2./g'
