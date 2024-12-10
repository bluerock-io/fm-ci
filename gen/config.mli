type versions = {
  image : string;
  main_llvm : int;
  main_swipl : string;
}

type repo = {
  name : string;
  gitlab : string;
  bhv_path : string;
  main_branch : string;
  deps : string list;
  vendored : bool;
}

type config = {
  versions : versions;
  repos : repo list;
}

val read_config : string -> config

val repo_from_project_name : config:config -> string -> repo

val all_downstream_from : config:config -> repo list -> repo list
