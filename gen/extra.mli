(*
 * Copyright (C) BedRock Systems Inc. 2023
 *
 * This software is distributed under the terms of the BedRock Open-Source
 * License. See the LICENSE-BedRock file in the repository root for details.
 *)

(** Short name for a standard formatter with continuation. *)
type ('a, 'b) koutfmt = ('a, Format.formatter, unit, unit, unit, 'b) format6

(** [panic fmt ...] aborts the program with the given message, specified using
    a format string and arguments similar to [Format.fprintf]. A newline and a
    flush instructions are automatically added to the message. *)
val panic : ('a, 'b) koutfmt -> 'a

(** [failwith ~fail fmt] is equivalent to calling [fail msg] (or, if [fail] is
    not given, [Stdlib.failwith msg]), where [msg] is an error message that is
    specified using a format string and arguments similar to [Format.fprintf].
    Warning: [fail] is only called once the function is fully applied. *)
val failwith : ?fail:(string -> 'b) -> ('a, 'b) koutfmt -> 'a

(** Extension of [Stdlib.In_channel]. *)
module In_channel : sig
  include module type of Stdlib.In_channel

  (** [input_lines ic] is an iterated version of [input_line ic]. *)
  val input_lines : t -> string list
end

(** Thunk, i.e., suspended computation. *)
module Thunk : sig
  (** Type of a thunk. *)
  type 'a t

  (** [make f] creates a thunk from function [f]. *)
  val make : (unit -> 'a) -> 'a t

  (** [run t] runs the thunk [t] and returns its result. *)
  val run : 'a t -> 'a

  (** [run_all ts] runs the thunks of [ts] in order. *)
  val run_all : unit t list -> unit
end

(** [process_out ~cmd run] runs command [cmd] with [Unix.open_process_in], and
    returns a thunk to be run to collect the result of the command using [run]
    (a function receiving as input the lines output by the program, as well as
    its return code). The whole program panics if [cmd] is stopped (or killed)
    by a signal, or if there are any other system errors. *)
val process_out : cmd:string -> (string list -> int -> 'a) -> 'a Thunk.t
