(*
 * Copyright (c) 2023 BedRock Systems, Inc.
 * This software is distributed under the terms of the BedRock Open-Source License.
 * See the LICENSE-BedRock file in the repository root for details.
 *)

From foo Require Import bar.baz.

#[local] Open Scope N_scope.
Set Nested Proofs Allowed.

#[local] Hint Resolve foo : br_opacity.
#[local] Remove Hints bar : br_opacity.

Lemma helper : True.
Proof using.
Admitted.
