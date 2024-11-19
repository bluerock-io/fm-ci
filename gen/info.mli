(** Information on where a triggered job originated from. This data is used to
    make sure that the triggering repository is checked out to the commit hash
    from the triggering pipeline. The commit branch is only available when the
    triggering job is from branch pipeline: it can be used to test whether the
    trigger comes from a merge to the main branch. *)
type trigger = {
  project_title : string;
  project_path : string;
  project_name : string;
  commit_sha : string;
  commit_branch : string option;
  pipeline_source : string;
  trigger_kind : string;
  trim_dune_cache : bool;
  only_full_build : bool;
  default_swipl : string;
}

(** [get_trigger ~main_swipl_version] constructs triggern information from the
    environemnt. The [main_swipl_version] parameter indicates the main version
    of SWI-Prolog used in CI. *)
val get_trigger : main_swipl_version:string -> trigger

(** Information on the MR that initiated the pipeline (either a trigger to the
    fm-ci repository, or directly a pipeline from fm-ci). *)
type mr = {
  mr_iid : string;
  mr_labels : string list;
  mr_project_id : string;
  mr_source_branch_name : string;
  mr_target_branch_name : string;
  pipeline_url : string;
}

(** [get_mr ()] constructs MR information from the environment, or returns the
    value [None] if there is no MR. *)
val get_mr : unit -> mr option
