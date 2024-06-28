(** Information on where a triggered job originated from. This data is used to
    make sure that the triggering repository is checked out to the commit hash
    from the triggering pipeline. The commit branch is only available when the
    triggering job is from branch pipeline: it can be used to test whether the
    trigger comes from a merge to the main branch. *)
type trigger_info = {
  project_title : string;
  commit_sha : string;
  commit_branch : string option;
}

(** Information on the MR that initiated the pipeline (either a trigger to the
    fm-ci repository, or directly a pipeline from fm-ci). *)
type mr_info = {
  mr_iid : string;
  mr_labels : string list;
  mr_project_id : string;
  mr_source_branch_name : string;
  pipeline_url : string;
}

(** Information on the pipeline. *)
type t = {
  trigger : trigger_info option;
  mr      : mr_info option;
}

(** [from_env ()] constructs pipeline information form the environment. *)
val from_env : unit -> t
