(*
 * Copyright (C) 2021 BlueRock Security, Inc.
 *
 * This software is distributed under the terms of the BedRock Open-Source
 * License. See the LICENSE-BedRock file in the repository root for details.
 *)

type ('a, 'b) koutfmt = ('a, Format.formatter, unit, unit, unit, 'b) format6

let panic : ('a, 'b) koutfmt -> 'a = fun fmt ->
  Format.kfprintf (fun _ -> exit 1) Format.err_formatter
    ("\027[31m[Panic] " ^^ fmt ^^ "\027[0m\n%!")

let failwith : ?fail:(string -> 'b) -> ('a, 'b) koutfmt -> 'a =
    fun ?(fail=Stdlib.failwith) fmt ->
  let buf = Buffer.create 1024 in
  let ff = Format.formatter_of_buffer buf in
  let k _ =
    Format.pp_print_flush ff ();
    fail (Buffer.contents buf)
  in
  Format.kfprintf k ff fmt

module In_channel = struct
  include Stdlib.In_channel

  let input_lines : t -> string list = fun ic ->
    let rec input_lines rev_lines =
      match input_line ic with
      | None       -> List.rev rev_lines
      | Some(line) -> input_lines (line :: rev_lines)
    in
    input_lines []
end

module Thunk = struct
  type 'a t = unit -> 'a

  let make f = f

  let run f = f ()

  let run_all fs = List.iter run fs
end

let process_out ~cmd run =
  let ic = Unix.open_process_in cmd in
  Thunk.make @@ fun _ ->
  let lines = In_channel.input_lines ic in
  match Unix.close_process_in ic with
  | Unix.WEXITED(s) -> run lines s
  | _               -> panic "Process %S stopped or killed." cmd
