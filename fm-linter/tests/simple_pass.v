(*
 * Copyright (c) 2023 BlueRock Security, Inc.
 * This software is distributed under the terms of the BedRock Open-Source License.
 * See the LICENSE-BedRock file in the repository root for details.
 *)

From foo Require Import bar.baz.

Theorem zob_spec_ok : qux_spec |-- zob_spec.
Proof.
  by go.
Qed.
