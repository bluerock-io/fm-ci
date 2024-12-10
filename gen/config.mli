(** Configuration for versions. *)
type versions = {
  (** CI image version (format "YYYY-MM-DD"). *)
  image : string;
  (** Main LLVM major version (used, e.g., in the main build job). *)
  main_llvm : int;
  (** Main SWI-Prolog version (used, e.g., in the main build job). *)
  main_swipl : string;
}

(** Configuration for a repository. *)
type repo = {
  (** Name of the repository (used as key). *)
  name : string;
  (** BlueRock GitLab project path for the repository. *)
  gitlab : string;
  (** Relative path of the clone in bhv. *)
  bhv_path : string;
  (** Name of the main branch. *)
  main_branch : string;
  (** Names of immediate dependencies. *)
  deps : string list;
  (** Is the repository vendored? *)
  vendored : bool;
}

(** Configuration obtained from the configuration file. *)
type config = {
  (** Versions configuration. *)
  versions : versions;
  (** List of configured repositories. *)
  repos : repo list;
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
