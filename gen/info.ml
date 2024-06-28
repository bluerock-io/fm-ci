open Extra

type trigger_info = {
  project_title : string;
  commit_sha : string;
  commit_branch : string option;
}

type mr_info = {
  mr_iid : string;
  mr_labels : string list;
  mr_project_id : string;
  mr_source_branch_name : string;
  pipeline_url : string;
}

type t = {
  trigger : trigger_info option;
  mr      : mr_info option;
}

let from_env : unit -> t = fun _ ->
  let getenv ?(allow_empty=false) var =
    let o = Option.map String.trim (Sys.getenv_opt var) in
    if o <> Some("") || allow_empty then o else
    panic "Variable %s is defined but empty." var
  in
  let trigger =
    let project_title_var = "ORIGIN_CI_PROJECT_TITLE" in
    let commit_sha_var = "ORIGIN_CI_COMMIT_SHA" in
    let commit_branch_var = "ORIGIN_CI_COMMIT_BRANCH" in
    let project_title = getenv project_title_var in
    let commit_sha = getenv commit_sha_var in
    let commit_branch = getenv ~allow_empty:true commit_branch_var in
    match (project_title, commit_sha, commit_branch) with
    | (Some(project_title), Some(commit_sha), Some(""           )) ->
        Some({project_title; commit_sha; commit_branch = None})
    | (Some(project_title), Some(commit_sha), Some(commit_branch)) ->
        Some({project_title; commit_sha; commit_branch = Some(commit_branch)})
    | (None               , None            , None               ) ->
        None
    | (_                  , _               , _                  ) ->
        panic "Either all of none of %s, %s and %s should be defined."
          project_title_var commit_sha_var commit_branch_var
  in
  let mr =
    let build use_origin mr_iid =
      let mr_getenv ?(allow_empty=false) ?(allow_undef=false) var =
        let var = if use_origin then "ORIGIN_" ^ var else var in
        match getenv ~allow_empty var with
        | None    ->
            if allow_undef && allow_empty then "" else
              panic "Variable %s is not defined, and cannot be empty." var
        | Some(v) ->
            if v <> "" || allow_empty then v else
              panic "Variable %s is defined but empty." var;
      in
      let mr_labels =
        mr_getenv ~allow_empty:true ~allow_undef:true
          "CI_MERGE_REQUEST_LABELS"
      in
      let mr_project_id =
        mr_getenv "CI_MERGE_REQUEST_PROJECT_ID"
      in
      let mr_source_branch_name =
        mr_getenv "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"
      in
      let pipeline_url =
        mr_getenv "CI_PIPELINE_URL"
      in
      let mr_labels = String.split_on_char ',' mr_labels in
      {mr_iid; mr_labels; mr_project_id; mr_source_branch_name; pipeline_url}
    in
    let mr_iid = "CI_MERGE_REQUEST_IID" in
    let origin_mr_iid = "ORIGIN_CI_MERGE_REQUEST_IID" in
    (* ORIGIN_CI_MERGE_REQUEST_IID is always defined on triggered jobs, so the
       empty case means "undefined". *)
    match (getenv mr_iid, getenv ~allow_empty:true origin_mr_iid) with
    | (None        , None        )
    | (None        , Some(""    )) -> None
    | (None        , Some(mr_iid)) -> Some(build true  mr_iid)
    | (Some(mr_iid), None        )
    | (Some(mr_iid), Some(""    )) -> Some(build false mr_iid)
    | (Some(_     ), Some(_     )) ->
        panic "Both %s and %s are defined and non-empty." mr_iid origin_mr_iid
  in
  {trigger; mr}
