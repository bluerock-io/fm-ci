type repo = {
  name : string;
  gitlab : string;
  bhv_path : string;
  main_branch : string;
  deps : string list;
  vendored : bool;
}

type config = {
  repos : repo list;
  main_llvm_version : int;
  main_swipl_version : string;
}

val read_config : string -> config

val repo_from_project_name : config:config -> string -> repo

val all_downstream_from : config:config -> repo list -> repo list
