open Extra

type t = {
  name : string;
  bhv_path : string;
  main_branch : string;
  deps : string list;
}

let repos_from_config : string -> t list = fun file ->
  let exception Syntax_error of int * string in
  try
    let ic = In_channel.open_text file in
    let rec loop i acc =
      let syntax_error msg = raise (Syntax_error(i, msg)) in
      match In_channel.input_line ic with
      | None -> In_channel.close_noerr ic; List.rev acc
      | Some("") -> loop (i+1) acc
      | Some(line) when line.[0] = '#' -> loop (i+1) acc
      | Some(line) ->
      match String.split_on_char ' ' line with
      | name :: bhv_path :: main_branch :: deps ->
          let deps = String.concat "" deps in
          let len = String.length deps in
          if deps = "" || deps.[0] <> '[' || deps.[len - 1] <> ']' then
            syntax_error "bad dependency specification";
          let deps = String.sub deps 1 (len - 2) in
          let deps =
            if deps = "" then [] else String.split_on_char ',' deps
          in
          loop (i+1) ({name; bhv_path; main_branch; deps} :: acc)
      | _ ->
          syntax_error "missing component"
    in
    loop 1 []
  with
  | Sys_error(msg) -> panic "File system error while reading %s.\n%s" file msg
  | Syntax_error(i,msg) -> panic "File %s, line %i: %s." file i msg

let transitive_deps : repos:t list -> t -> string list = fun ~repos root ->
  let module S = Set.Make(String) in
  let rec transitive_deps deps roots =
    match roots with
    | []            -> S.elements deps
    | root :: roots ->
    if S.mem root deps then transitive_deps deps roots else
    match List.find_opt (fun r -> r.name = root) repos with
    | None            ->
        panic "Bad dependency in config: no repo named %s." root
    | Some(root_repo) ->
    transitive_deps (S.add root deps) (root_repo.deps @ roots)
  in
  transitive_deps S.empty [root.name]

let all_downstream_from : repos:t list -> string list -> t list =
    fun ~repos roots ->
  let downstream_from_root repo =
    let deps = transitive_deps ~repos repo in
    List.exists (fun root -> List.mem root deps) roots
  in
  List.filter downstream_from_root repos
