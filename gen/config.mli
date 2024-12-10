(** Configuration for versions. *)
type versions = {
  image : string;
  (** CI image version (format "YYYY-MM-DD"). *)
  main_llvm : int;
  (** Main LLVM major version (used, e.g., in the main build job). *)
  main_swipl : string;
  (** Main SWI-Prolog version (used, e.g., in the main build job). *)
}

(** Configuration for a repository. *)
type repo = {
  name : string;
  (** Name of the repository (used as key). *)
  gitlab : string;
  (** BlueRock GitLab project path for the repository. *)
  bhv_path : string;
  (** Relative path of the clone in bhv. *)
  main_branch : string;
  (** Name of the main branch. *)
  deps : string list;
  (** Names of immediate dependencies. *)
  vendored : bool;
  (** Is the repository vendored? *)
}

(** Configuration obtained from the configuration file. *)
type config = {
  versions : versions;
  (** Versions configuration. *)
  repos : repo list;
  (** List of configured repositories. *)
}

(** [read_config file] reads a configuration in the TOML file [file]. If there
    is an error, then the whole program is aborted. *)
val read_config : string -> config

(** [repo_from_project_name ~config proj_name] gives the repository config for
    the repo whose GitLab project name matches [proj_name]. If no such repo is
    contained in [config], then the program is aborted with an error. *)
val repo_from_project_name : config:config -> string -> repo

(** [all_downstream_from ~config repos] gives a list of all repositories (from
    [config]) that depend on repositories from [repos]. *)
val all_downstream_from : config:config -> repo list -> repo list
