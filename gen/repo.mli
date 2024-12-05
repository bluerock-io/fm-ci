type t = {
  name : string;
  bhv_path : string;
  main_branch : string;
  deps : string list;
  vendored : bool;
}

val repos_from_config : string -> t list

val all_downstream_from : repos:t list -> string list -> t list
