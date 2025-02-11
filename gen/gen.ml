open Extra

let perr fmt = Printf.eprintf (fmt ^^ "\n%!")

let _ =
  match Array.length Sys.argv with 4 -> () | _ ->
  perr "Usage: %s <TOKEN> <CONFIG_FILE> <OUTPUT_YAML_FILE>\n%!" Sys.argv.(0);
  exit 1

(** Reading the configuration file. *)
let config = Config.read_config Sys.argv.(2)

(** CI image version. *)
let image_version = config.Config.versions.Config.image

(** Main version of SWI-Prolog (usable with all supported LLVM versions). *)
let main_swipl_version = config.Config.versions.Config.main_swipl

(** Main version of LLVM (usable with all supported SWI-Prolog versions). *)
let main_llvm_version = config.Config.versions.Config.main_llvm

(** GitLab token. *)
let token : string = Sys.argv.(1)

(** Configuration for the repos. *)
let repos : Config.repo list = config.Config.repos

(** Output YAML file. *)
let yaml_file : string = Sys.argv.(3)

(** Directory where the repositories are cloned. *)
let repos_destdir = "repos"

(** Project name for fm-ci (the current repository). *)
let fm_ci_project_name = "formal-methods/fm-ci"

(** Information about the originating repository (trigger). *)
let trigger = Info.get_trigger ~main_swipl_version

let _ =
  (* Output info: originating repository / trigger. *)
  perr "#### Originating repository ####";
  let Info.{project_title; project_path; project_name; _} = trigger in
  let Info.{commit_sha; commit_branch; _} = trigger in
  let Info.{pipeline_source; trigger_kind; _} = trigger in
  let Info.{trim_dune_cache; only_full_build; default_swipl; _} = trigger in
  perr "Pipeline triggered from repository %s:" project_title;
  perr " - Project title  : %s" project_title;
  perr " - Project path   : %s" project_path;
  perr " - Project name   : %s" project_name;
  perr " - Commit sha     : %s" commit_sha;
  perr " - Pipeline source: %s" pipeline_source;
  perr " - Trigger kind   : %s" trigger_kind;
  perr " - Trim dune cache: %b" trim_dune_cache;
  perr " - Only full build: %b" only_full_build;
  perr " - Default swipl  : %s" default_swipl;
  Option.iter (perr " - Commit branch  : %s (branch pipeline)") commit_branch

(** Is the trigger comming from fm-ci (the current repository). *)
let trigger_is_fm_ci : bool =
  trigger.Info.project_name = fm_ci_project_name

(** Check that the trigger comes from a known project. *)
let _ =
  match trigger_is_fm_ci with true -> () | false ->
  let project_name = trigger.Info.project_name in
  if List.for_all (fun repo -> repo.Config.gitlab <> project_name) repos then
    panic "Repository %s not specified in the config." project_name

(** Information about the originating MR, if any. *)
let mr = Info.get_mr ()

let _ =
  (* Output info: MR information. *)
  perr "#### MR information ####";
  match mr with
  | None     -> perr "Pipeline without an associated MR."
  | Some(mr) ->
  let Info.{mr_iid; mr_labels; mr_project_id; pipeline_url; _} = mr in
  let Info.{mr_source_branch_name; mr_target_branch_name; _} = mr in
  perr "Pipeline with an associated MR:";
  perr " - IID       : %s" mr_iid;
  perr " - labels    : [%s]" (String.concat ", " mr_labels);
  perr " - project ID: %s" mr_project_id;
  perr " - branch    : %s" mr_source_branch_name;
  perr " - target    : %s" mr_target_branch_name;
  perr " - pipeline  : %s" pipeline_url

(** CI image for a given version of LLVM (only 16 to 18 exist). *)
let ci_image : swipl:string -> llvm:int -> string = fun ~swipl ~llvm ->
  Printf.sprintf "fm-%s-swipl-%s-llvm-%i" image_version swipl llvm

(** CI image with the default version of SWI-Prolog. *)
let ci_image_default_swipl : llvm:int -> string = fun ~llvm ->
  ci_image ~swipl:trigger.default_swipl ~llvm

(** Main CI image, with latest supported LLVM. *)
let main_image = ci_image_default_swipl ~llvm:main_llvm_version

(** [main_branch project] gives the name of the main branch of [project]. This
    relies on the configuration file, and the code panics if no project with a
    corresponding name exists. *)
let main_branch : string -> string = fun project ->
  let repo =
    try List.find (fun repo -> repo.Config.gitlab = project) repos
    with Not_found -> panic "No repo data for %s." project
  in
  repo.Config.main_branch

(** [lightweight_clone repo] spawns a git process to clone the given [repo]. A
    thunk is returned, and it should be run to wait for the process. The clone
    that is created is put in [repos_destdir]. *)
let lightweight_clone : Config.repo -> unit Thunk.t = fun repo ->
  let name = repo.Config.gitlab in
  let url =
    Printf.sprintf
      "https://gitlab-ci-token:%s@gitlab.com/bedrocksystems/%s.git"
      token name
  in
  let cmd =
    Printf.sprintf
      "git clone --no-checkout --filter=tree:0 --quiet %s %s/%s"
      url repos_destdir name
  in
  perr "Cloning %s in %s/%s." name repos_destdir name;
  process_out ~cmd @@ fun _ i ->
  if i <> 0 then panic "Command %S gave return code %i." cmd i;
  perr "Cloned %s in %s/%s." name repos_destdir name

let _ =
  (* Cloning all the repositories. *)
  perr "#### Cloning all repositories ####";
  (try Sys.mkdir repos_destdir 0o755 with Sys_error _ -> ());
  Thunk.run_all (List.map lightweight_clone repos)

(** [rev_parse repo branch] gives the commit hash of [branch] in [repo], if it
    exists. A [None] value is returned otherwise. This function assumes that a
    clone of the repo is available under [repos_destdir]. *)
let rev_parse : Config.repo -> string -> string option = fun repo branch ->
  let cmd =
    Printf.sprintf
      "git -C %s/%s rev-parse --verify --quiet refs/remotes/origin/%s"
      repos_destdir repo.Config.gitlab branch
  in
  Thunk.run @@ process_out ~cmd @@ fun lines i ->
  match (i, lines) with
  | (0, [hash]) -> Some(hash)
  | (0, _     ) -> panic "Unexpected output for command %S." cmd
  | (_, _     ) -> None

(** [merge_base repo hash1 hash2] yields the commit hash of the git merge base
    of the given hashes, [hash1] and [hash2], in repository [repo]. Note that,
    as with [rev_parse], a clone of the repo is assumed to be available (under
    the [repos_destdir] directory). *)
let merge_base : Config.repo -> string -> string -> string =
    fun repo hash1 hash2 ->
  let cmd =
    Printf.sprintf
      "git -C %s/%s merge-base %s %s"
      repos_destdir repo.Config.gitlab hash1 hash2
  in
  Thunk.run @@ process_out ~cmd @@ fun lines i ->
  match (i, lines) with
  | (0, [hash]) -> hash
  | (_, _     ) -> panic "Unexpected output form command %S." cmd

(** Type gathering commit hashes of interest for a repo. *)
type hashes = {
  target_branch : string;
  mr_branch : string option;
  merge_base : string option;
}

(** Indicates the name of the MR branch when the pipeline is triggered from an
    MR with ["CI::same-branch"] enabled. *)
let same_branch : string option =
  match mr with None -> None | Some(mr) ->
  let same_branch = List.mem "CI::same-branch" mr.Info.mr_labels in
  if same_branch then Some(mr.Info.mr_source_branch_name) else None

(** Gives the name of the MR target branch when the pipeline is triggered from
    an MR, and its target branch is not the main branch (as configured). *)
let target_branch : string option =
  match mr with None -> None | Some(mr) ->
  let main_branch = main_branch trigger.Info.project_name in
  let target_branch = mr.Info.mr_target_branch_name in
  if main_branch = target_branch then None else Some(target_branch)

(** [repo_hashes repo] returns a pair [(target_branch_name, hashes)], in which
    [target_branch_name] is the name for the target branch for [repo], and the
    [hashes] record gives relevant commit hashes, where [hashes.target_branch]
    is the commit hash of [target_branch_name]. *)
let repo_hashes : Config.repo -> string * hashes = fun repo ->
  let Config.{gitlab; name; main_branch; vendored; _} = repo in
  (* If triggered from [repo], commit hash from the initial trigger. *)
  let trigger_commit_hash =
    if trigger_is_fm_ci then None else
    if gitlab <> trigger.Info.project_name then None else
    Some(trigger.Info.commit_sha)
  in
  let branch_hash branch =
    match rev_parse repo branch with Some(hash) -> hash | _ ->
    panic "Cannot find the hash of branch %s for %s." branch name
  in
  let fallback_to_main () =
    let target_branch = branch_hash main_branch in
    (main_branch, {target_branch; mr_branch = None; merge_base = None})
  in
  match (mr, same_branch, trigger_commit_hash) with
  | (None   , _           , Some(hash)) ->
      (* Push pipeline (to main) and triggering repo: use trigger hash. *)
      (main_branch, {target_branch=hash; mr_branch=None; merge_base=None})
  | (None   , _           , None      ) ->
      (* Push pipeline (to main) and not triggering repo: use main hash. *)
      fallback_to_main ()
  | (Some(_), _           , Some(hash)) ->
      (* MR pipeline and triggering repo: use trigger hash for MR branch. *)
      let target_branch_name =
        match target_branch with
        | None         -> main_branch
        | Some(branch) -> branch
      in
      let target_branch = branch_hash target_branch_name in
      let mr_branch = Some(hash) in
      let merge_base =
        if vendored then None else
        let merge_base hash = merge_base repo target_branch hash in
        Option.map merge_base mr_branch
      in
      (target_branch_name, {target_branch; mr_branch; merge_base})
  | (Some(_), None        , None      ) ->
      (* MR pipeline, not triggering repo, no CI::same-branch. *)
      fallback_to_main ()
  | (Some(_), Some(branch), None      ) ->
      (* MR pipeline, not triggering repo, CI::same-branch. *)
      match rev_parse repo branch with
      | None                      -> fallback_to_main () (* No branch. *)
      | Some(branch) as mr_branch ->
      (* The MR branch exists on the repo, compute the target branch. *)
      let (target_branch_name, target_branch) =
        match target_branch with
        | None         ->
            (* No special target branch, use main. *)
            (main_branch, branch_hash main_branch)
        | Some(target) ->
            (* Use the special target branch if it exists. *)
            match rev_parse repo target with
            | Some(hash) -> (target, hash)
            | None       -> (main_branch, branch_hash main_branch)
      in
      let merge_base =
        if vendored then None else
        Some(merge_base repo target_branch branch)
      in
      (target_branch_name, {target_branch; mr_branch; merge_base})

(** Extended version of [repos] with the target branch name and hashes. *)
let repos_with_hashes : (Config.repo * (string * hashes)) list =
  List.map (fun repo -> (repo, repo_hashes repo)) repos

let _ =
  (* Output info: computed data for all the repos. *)
  perr "#### Data for all repositories ####";
  let pp_repo (repo, (target_branch_name, hashes)) =
    let deps = String.concat ", " repo.Config.deps in
    perr "%s:" repo.Config.name;
    perr " - gitlab       : %s" repo.Config.gitlab;
    perr " - bhv path     : %s" repo.Config.bhv_path;
    perr " - main branch  : %s" repo.Config.main_branch;
    perr " - deps         : [%s]" deps;
    perr " - vendored     : %b" repo.Config.vendored;
    perr " - target branch: %s" target_branch_name;
    perr " - target hash  : %s" hashes.target_branch;
    Option.iter (perr " - branch hash  : %s") hashes.mr_branch;
    Option.iter (perr " - merge base   : %s") hashes.merge_base
  in
  List.iter pp_repo repos_with_hashes

(** Commit hashes for the main build step. *)
let main_build : (Config.repo * string) list =
  let with_main_build_hash (repo, (_, hashes)) =
    match hashes.mr_branch with
    | Some(hash) -> (repo, hash)
    | None       -> (repo, hashes.target_branch)
  in
  List.map with_main_build_hash repos_with_hashes

let _ =
  (* Output info: commit hashes for the main build. *)
  perr "#### Information for the generated config ####";
  perr "Commit hashes for the main build:";
  let print_info (repo, hash) = perr " - %s: %s" repo.Config.name hash in
  List.iter print_info main_build

(** Commit hashes for the reference build step if necessary. *)
let ref_build : (Config.repo * string) list option =
  match mr with
  | None     -> None
  | Some(mr) ->
  if not (List.mem "FM-CI-Compare" mr.Info.mr_labels) then None else
  let with_ref_build_hash (repo, (_, hashes)) =
    match hashes.merge_base with
    | Some(hash) -> (repo, hash)
    | None       -> (repo, hashes.target_branch)
  in
  Some(List.map with_ref_build_hash repos_with_hashes)

let _ =
  (* Output info: commit hashes for the reference build (if any). *)
  match ref_build with
  | None            -> perr "No reference build."
  | Some(ref_build) ->
  perr "Commit hashes for the reference build:";
  let print_info (repo, hash) = perr " - %s: %s" repo.Config.name hash in
  List.iter print_info ref_build

(** Repositories that need to be fully built. *)
let repos_needing_full_build : Config.repo list =
  (* Job comes from fm-ci: everything needs a full build. *)
  if trigger_is_fm_ci then repos else
  let Info.{project_name=origin; _} = trigger in
  (* No MR: everything downstream of [origin] needs a full build. *)
  match mr with
  | None    ->
      let origin = Config.repo_from_project_name ~config origin in
      Config.all_downstream_from ~config [origin]
  | Some(_) ->
  (* MR: everything downstream of a repo with a branch needs a full build. *)
  let has_branch (repo, (_, hashes)) =
    match hashes.mr_branch with
    | None                                    -> None
    | Some(br) when br = hashes.target_branch -> None
    | Some(_ )                                -> Some(repo)
  in
  let with_branch = List.filter_map has_branch repos_with_hashes in
  Config.all_downstream_from ~config with_branch

let needs_full_build : string -> bool = fun name ->
  List.exists (fun repo -> repo.Config.name = name) repos_needing_full_build

let _ =
  (* Output info: repositories needing a full build. *)
  perr "Repositories needing a full build:";
  let print_info repo = perr " - %s" repo.Config.name in
  List.iter print_info repos_needing_full_build

(** Full timing mode for BHV. *)
let full_timing : [`No | `Partial | `Full] =
  match mr with
  | Some(mr) when List.mem "FM-CI-timing-full" mr.Info.mr_labels -> `Full
  | Some(mr) when List.mem "FM-CI-timing"      mr.Info.mr_labels -> `Partial
  | Some(_ )                                                     -> `No
  | None                                                         ->
  match Sys.getenv_opt "FULL_TIMING" with
  | None      -> `No
  | Some("" ) -> `No
  | Some("0") -> `No
  | Some("1") -> `Partial
  | Some("2") -> `Full
  | Some(v  ) ->
      panic "Invalid value for FULL_TIMING: %S (expected 0, 1 or 2)." v

let _ =
  (* Output info: full timing mode. *)
  match full_timing with
  | `No      -> perr "Full timing for bhv: no."
  | `Partial -> perr "Full timing for bhv: partial."
  | `Full    -> perr "Full timing for bhv: full."

(** Location of the bhv checkout in CI builds. *)
let build_dir = "/tmp/build-dir"

let output_static : Out_channel.t -> unit = fun oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "# Dynamically generated CI configuration.";
  line "";
  line "workflow:";
  line "  rules:";
  line "    - if: $CI_PIPELINE_SOURCE == 'parent_pipeline'";
  line ""

let common_ci_image oc tag =
  let registry = "registry.gitlab.com/bedrocksystems/formal-methods/fm-ci" in
  Printf.fprintf oc "%s:%s" registry tag

let gitlab_url = "https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.com"

let repo_url oc name =
  Printf.fprintf oc "%s/bedrocksystems/%s.git" gitlab_url name

let checkout_commands oc config =
  let cmd fmt = Printf.fprintf oc ("    - " ^^ fmt ^^ "\n") in
  let checkout (repo, hash) =
    let bhv_path = repo.Config.bhv_path in
    cmd "git -C %s fetch --quiet origin %s" bhv_path hash;
    cmd "git -C %s -c advice.detachedHead=false checkout %s" bhv_path hash
  in
  List.iter checkout config

let artifacts_url =
  let base = "https://bedrocksystems.gitlab.io/-/formal-methods/fm-ci/-" in
  Printf.sprintf "%s/jobs/${CI_JOB_ID}/artifacts" base

let common : image:string -> dune_cache:bool -> Out_channel.t -> unit =
    fun ~image ~dune_cache oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "  image: %a" common_ci_image image;
  line "  tags:";
  line "    - fm.nfs";
  line "  variables:";
  line "    CLICOLOR: 1";
  line "    GNUMAKEFLAGS: --no-print-directory";
  line "    OCAMLRUNPARAM: \"a=2,o=120,s=256M\"";
  line "    DUNE_CACHE: %sabled" (if dune_cache then "en" else "dis");
  line "    DUNE_CACHE_STORAGE_MODE: copy";
  line "    DUNE_CONFIG__BACKGROUND_DIGESTS: disabled";
  line "    DUNE_PROFILE: release";
  line "    LLVM: '1'";
  line "    CHANGES_PATH : '**/*'";
  line "    GET_SOURCES_ATTEMPTS: 3";
  line "    # Only used to build Zydis (we only do caching via dune).";
  line "    BUILD_CACHING: 0";
  line "    # Speed up [make init]";
  line "    BRASS_aarch64: 'off'";
  line "    BRASS_x86_64: 'off'";
  line "    GITLAB_URL: %s/bedrocksystems/" gitlab_url;
  line "  retry:";
  line "    max: 1";
  line "    when:";
  line "      - runner_system_failure";
  line "      - api_failure";
  line "      - unmet_prerequisites";
  line "      - scheduler_failure";
  line "      - stale_schedule"

let bhv_cloning : Out_channel.t -> string -> unit = fun oc destdir ->
  let cmd fmt = Printf.fprintf oc ("    - " ^^ fmt ^^ "\n") in
  let (_, hash) =
    try List.find (fun (r, _) -> r.Config.name = "bhv") main_build
    with Not_found -> panic "No repo data for bhv."
  in
  cmd "git clone --depth 1 %a %s" repo_url "bhv" destdir;
  cmd "git -C %s fetch --quiet origin %s" destdir hash;
  cmd "git -C %s -c advice.detachedHead=false checkout %s" destdir hash


let main_job : Out_channel.t -> unit = fun oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  let sect =
    let fresh_name =
      let counter = ref 0 in
      fun () -> incr counter; Printf.sprintf "section_%i" (!counter)
    in
    fun spaces header ?(collapsed=true) cmd ->
    let name = fresh_name () in
    (* magic strings taken from
       https://docs.gitlab.com/ee/ci/yaml/script.html#custom-collapsible-sections
       on 2024/08/06 *)
    if collapsed then
      line {|%s- echo -e "\e[0Ksection_start:`date +%%s`:%s[collapsed=true]\r\e[0K%s"|}
        spaces name header
    else
      line {|%s- echo -e "\e[0Ksection_start:`date +%%s`:%s\r\e[0K%s"|}
        spaces name header;
    cmd ();
    line {|%s- echo -e "\e[0Ksection_end:`date +%%s`:%s\r\e[0K"|}
      spaces name
  in
  line "full-build%s:" (if ref_build = None then "" else "-compare");
  common ~image:main_image ~dune_cache:(full_timing = `No) oc;
  line "  script:";
  line "    # Print environment for debug.";
  sect "    " "Environment" (fun () ->
  line "    - env");
  line "    # Initialize a bhv checkout.";
  bhv_cloning oc build_dir;
  line "    - cd %s" build_dir;
  sect "    " "Initialize bhv" (fun () ->
  line "    - time make -j ${NJOBS} init");
  line "    - make dump_repos_info";
  line "    # Create Directory structure for dune";
  line "    - mkdir -p ~/.cache/ ~/.config/dune/";
  line "    - cp support/fm/dune_config ~/.config/dune/config";
  line "    - rm -rf _build";
  (* Trim the dune cache if necessary. *)
  if trigger.trim_dune_cache then begin
  line "    # Trimming the dune cache.";
  line "    - dune cache trim --size=64GB";
  end;
  line "    # Increase the stack size for large files.";
  line "    - ulimit -S -s 32768";
  line "    # Install the python deps.";
  sect "    " "Install dependencies" (fun () ->
  line "    - pip3 install -r python_requirements.txt");
  (* Checkout the commit hashes for the main build, and build. *)
  line "    #### MAIN BUILD ####";
  sect "    " "Check out main branches" (fun () ->
  checkout_commands oc main_build);
  line "    - make statusm | tee $CI_PROJECT_DIR/statusm.txt";
  line "    # ASTs";
  let failure_file = "/tmp/main_build_failure" in
  line "    - rm -rf %s" failure_file;
  sect "    " "Build ASTs" (fun () ->
  line "    - (./fm-build.py -b -j${NJOBS} @ast || (\
                touch %s; echo \"MAIN BUILD FAILED AT THE AST STAGE\"))"
                failure_file);
  line "    - checksum_asts() { \
                find _build/default -name '*_[ch]pp.v' -o \
                  -name '*_[ch]pp_names.v' | \
                grep -v 'zeta/apps/msc/src/.*build_id_cpp.v' | \
                sort | xargs md5sum > ast_md5sums.txt; }";
  line "    - checksum_asts";
  line "    - cp ast_md5sums.txt $CI_PROJECT_DIR/ast_md5sums.txt";
  if full_timing = `Full then begin
  line "    # FM-3547: check AST generation is reproducible.";
  line "    - mv ast_md5sums.txt ast_md5sums_v1.txt";
  line "    - dune clean";
  sect "    " "Build ASTs" (fun () ->
  line "    - (dune build @ast -j ${NJOBS} || (touch %s; \
                echo \"MAIN BUILD FAILED AT THE SECOND AST STAGE\"))"
                failure_file);
  line "    - checksum_asts";
  line "    - diff -su ast_md5sums_v1.txt ast_md5sums.txt"
  end;
  line "    # Actual build.";
  line "    - dune build _build/install/default/bin/filter-dune-output";
  if full_timing = `Full then begin
  line "    - ((dune build -j ${NJOBS} @default @runtest 2>&1 | \
                  _build/install/default/bin/filter-dune-output; \
                make dune_check -j${NJOBS}) || (\
                touch %s; echo \"MAIN BUILD FAILED AT THE BUILD STAGE\"))"
                failure_file;
  end else begin
  line "    - ((dune build -j${NJOBS} \
                @proof @fmdeps/default @NOVA/default @runtest 2>&1 | \
                  _build/install/default/bin/filter-dune-output && ./fmdeps/fm-docs/ci-build.sh) \
                || (\
                touch %s; echo \"MAIN BUILD FAILED AT THE BUILD STAGE\"))"
                failure_file;
  end;
  line "    # Print information on the size of the _build directory.";
  line "    - du -hs _build";
  line "    - du -hc $(find _build -type f -name \"*.v\") | tail -n 1";
  line "    - du -hc $(find _build -type f -name \"*.vo\") | tail -n 1";
  line "    - du -hc $(find _build -type f -name \"*.glob\") | tail -n 1";
  line "    # Compute FM stats.";
  line "    - mkdir -p $CI_PROJECT_DIR/fm-stats/_build/default/apps/vswitch";
  sect "    " "stash.sh (all)" (fun () ->
  line "    - ./support/fm/stats.sh _build/default /dev/null";
  line "    - ./support/fm/stats2json.py -g . -i \
                /tmp/_tmp_build-dir_full_spec_names.stats \
                -o /tmp/spec_list.json";
  line "    - ./support/fm/stats.sh -v _build/default /dev/null \
                > _build_default.stats";
  line "    - cp /tmp/*.stats $CI_PROJECT_DIR/fm-stats/_build/default";
  line "    - cp /tmp/*.json $CI_PROJECT_DIR/fm-stats/_build/default";
  line "    - rm /tmp/*.stats /tmp/*.json");
  sect "    " "stash.sh (vswitch)" (fun () ->
  line "    - ./support/fm/stats.sh _build/default/apps/vswitch \
                _build/default/zeta";
  line "    - ./support/fm/stats.sh -v _build/default/apps/vswitch \
                _build/default/zeta > _build_default_apps_vswitch.stats";
  line "    - cp /tmp/*.stats \
                $CI_PROJECT_DIR/fm-stats/_build/default/apps/vswitch";
  line "    - cp *.stats $CI_PROJECT_DIR/fm-stats");
  line "    # Extract data.";
  line "    - find _build/ -name '*.vo'| sort | xargs md5sum \
                > $CI_PROJECT_DIR/md5sums.txt";
  line "    - dune exec -- globfs.extract-all ${NJOBS} _build/default";
  sect "    " "Generate code quality report" (fun () ->
  line "    - (cd _build/default; dune exec -- coqc-perf.report .) | \
                tee -a coq_codeq.log";
  line "    - cat coq_codeq.log | dune exec -- coqc-perf.code-quality-report \
                > $CI_PROJECT_DIR/gl-code-quality-report.json");
  line "    - dune exec -- coqc-perf.extract-all _build/default perf-data";
  line "    - dune exec -- hint-data.extract-all ${NJOBS} perf-data";
  line "    - du -hs _build";
  line "    - du -hs perf-data";
  if ref_build = None then begin
  (* Minimal data gathering when no reference build. *)
  line "    - cp perf-data/perf_summary.csv \
                $CI_PROJECT_DIR/perf_summary.csv";
  line "    - find perf-data -type f -name \"*.hints.csv\" | \
                dune exec -- coqc-perf.gather-hint-data \
                > $CI_PROJECT_DIR/hint-data.csv"
  end else begin
  (* Data collection happens after the reference build, put data aside. *)
  line "    - mv perf-data $CI_PROJECT_DIR/perf-data";
  end;
  (* Copy ".v.d" files and skip empty folders (--exclude="*" is used to skip
     files by default, see https://stackoverflow.com/a/11111793/53974). *)
  line "    - rsync -a --prune-empty-dirs --include=\"*/\" --include=\"*.d\" \
                --exclude=\"*\" _build/ $CI_PROJECT_DIR/build_vd";
  begin match ref_build with None -> () | Some(ref_build) ->
  (* Checkout the commit hashes for the reference build, and build. *)
  line "    #### REF BUILD ####";
  line "    - make -sj ${NJOBS} gitclean > /dev/null";
  sect "    " "Check out reference branches" (fun () ->
  checkout_commands oc ref_build);
  line "    - make statusm | tee $CI_PROJECT_DIR/statusm_ref.txt";
  line "    # clean thoroughly in case the main branch introduced new vendored repos";
  line "    - git clean -ffxd";
  line "    - make -sj ${NJOBS} gitclean > /dev/null";
  line "    # ASTs";
  sect "    " "Build reference ASTs" (fun () ->
  line "    - ./fm-build.py -b -j${NJOBS} @ast");
  line "    - checksum_asts";
  line "    - cp ast_md5sums.txt $CI_PROJECT_DIR/ast_md5sums_ref.txt";
  if full_timing = `Full then begin
  line "    # FM-3547: check AST generation is reproducible.";
  line "    - mv ast_md5sums.txt ast_md5sums_v1.txt";
  line "    - dune clean";
  sect "    " "Build ASTs (reference)" (fun () ->
  line "    - dune build @ast -j ${NJOBS}");
  line "    - checksum_asts";
  line "    - diff -su ast_md5sums_v1.txt ast_md5sums.txt"
  end;
  line "    # Actual build.";
  line "    - dune build _build/install/default/bin/filter-dune-output";
  if full_timing = `Full then begin
  line "    - (dune build -j ${NJOBS} @default @runtest 2>&1 | \
                _build/install/default/bin/filter-dune-output; \
                make dune_check -j${NJOBS})"
  end else begin
  line "    - (dune build -j${NJOBS} \
                @proof @fmdeps/default @NOVA/default @runtest 2>&1 | \
                  _build/install/default/bin/filter-dune-output)"
  end;
  line "    # Print information on the size of the _build directory.";
  line "    - du -hs _build";
  line "    - du -hc $(find _build -type f -name \"*.v\") | tail -n 1";
  line "    - du -hc $(find _build -type f -name \"*.vo\") | tail -n 1";
  line "    - du -hc $(find _build -type f -name \"*.glob\") | tail -n 1";
  line "    # Extract data.";
  line "    - find _build/ -name '*.vo'| sort | xargs md5sum \
                > $CI_PROJECT_DIR/md5sums_ref.txt";
  line "    - dune exec -- globfs.extract-all ${NJOBS} _build/default";
  line "    - dune exec -- coqc-perf.extract-all _build/default perf-data";
  line "    - dune exec -- hint-data.extract-all ${NJOBS} perf-data";
  line "    - du -hs _build";
  line "    - du -hs perf-data";
  line "    - mv perf-data $CI_PROJECT_DIR/perf-data_ref";
  (* Checkout the commit hashes for the main build again, and compare perf. *)
  line "    #### PERF ANALYSIS ####";
  line "    - make -sj ${NJOBS} gitclean > /dev/null";
  sect "    " "Check out main branches (again)" (fun () ->
  checkout_commands oc main_build);
  sect "    " "Initialize bhv" (fun () ->
  line "    - time make -j ${NJOBS} init");
  line "    - make statusm";
  line "    - make -C fmdeps/cpp2v ast-prepare";
  line "    - dune build fmdeps/cpp2v-core/rocq-tools";
  line "    - mv $CI_PROJECT_DIR/perf-data perf-data";
  line "    - mv $CI_PROJECT_DIR/perf-data_ref perf-data_ref";
  line "    - cp perf-data/perf_summary.csv \
                $CI_PROJECT_DIR/perf_summary.csv";
  line "    - cp perf-data_ref/perf_summary.csv \
                $CI_PROJECT_DIR/perf_summary_ref.csv";
  line "    - dune exec -- coqc-perf.summary-diff \
                --assume-missing-unchanged --no-colors --instr-threshold 1 \
                perf-data_ref/perf_summary.csv perf-data/perf_summary.csv \
                > $CI_PROJECT_DIR/perf_analysis.md";
  line "    - dune exec -- coqc-perf.summary-diff \
                --assume-missing-unchanged --no-colors --instr-threshold 1 \
                --csv perf-data_ref/perf_summary.csv \
                perf-data/perf_summary.csv \
                > $CI_PROJECT_DIR/perf_analysis.csv";
  line "    - dune exec -- coqc-perf.summary-diff \
                --assume-missing-unchanged --no-colors --instr-threshold 1 \
                --gitlab --diff-base-url \"%s/perf-report\" \
                perf-data_ref/perf_summary.csv \
                perf-data/perf_summary.csv \
                > $CI_PROJECT_DIR/perf_analysis_gitlab.md" artifacts_url;
  line "    - dune exec -- coqc-perf.summary-diff --assume-missing-unchanged \
                --instr-threshold 1 --gitlab \
                perf-data_ref/perf_summary.csv \
                perf-data/perf_summary.csv";
  line "    - dune exec -- coqc-perf.html-diff-all perf-data_ref perf-data \
                $CI_PROJECT_DIR/perf-report";
  line "    # Adding hint data diff";
  line "    - find perf-data_ref -type f -name \"*.hints.csv\" | \
                dune exec -- coqc-perf.gather-hint-data \
                > $CI_PROJECT_DIR/hint-data_ref.csv";
  line "    - find perf-data -type f -name \"*.hints.csv\" | \
                dune exec -- coqc-perf.gather-hint-data \
                > $CI_PROJECT_DIR/hint-data.csv";
  line "    - dune exec -- coqc-perf.hint-data-diff \
                $CI_PROJECT_DIR/hint-data_ref.csv \
                $CI_PROJECT_DIR/hint-data.csv \
                > hint_data_diff.md";
  line "    - dune exec -- coqc-perf.hint-data-diff --html \
                $CI_PROJECT_DIR/hint-data_ref.csv \
                $CI_PROJECT_DIR/hint-data.csv \
                > $CI_PROJECT_DIR/hint_data_diff.html";
  line "    - head -n 202 hint_data_diff.md > hint_data_diff_truncated.md";
  line "    - echo -e \"\\n<details><summary>[Hint data diff]\
                (%s/hint_data_diff.html)</summary>\\n\" \
                >> $CI_PROJECT_DIR/perf_analysis_gitlab.md" artifacts_url;
  line "    - cat hint_data_diff_truncated.md \
                >> $CI_PROJECT_DIR/perf_analysis_gitlab.md";
  line "    - >";
  line "      if ! cmp -s hint_data_diff.md hint_data_diff_truncated.md; then";
  line "        echo \"| ... | ... | ... | ... |\" \
                  >> $CI_PROJECT_DIR/perf_analysis.gitlab.md";
  line "      fi";
  line "    - echo -e '\\n</details>\\n' \
                >> $CI_PROJECT_DIR/perf_analysis_gitlab.md";
  let mr = match mr with None -> assert false | Some(mr) -> mr in
  let Info.{mr_iid; mr_project_id; pipeline_url; _} = mr in
  line "    - python3 support/fm-perf/post_fm_perf.py \
                --access-token ${PROOF_PERF_TOKEN} --project-id %s \
                --mr-id %s -f $CI_PROJECT_DIR/perf_analysis_gitlab.md \
                --pipe-url %S" mr_project_id mr_iid pipeline_url;
  end;
  line "    - if [[ -f %s ]]; then \
                echo \"Main build failure.\"; false; fi" failure_file;
  line "  artifacts:";
  line "    when: always";
  line "    expose_as: \"build artifact\"";
  line "    name: main_artifacts";
  line "    paths: ";
  line "      - statusm.txt";
  line "      - ast_md5sums.txt";
  line "      - md5sums.txt";
  line "      - fm-stats";
  line "      - hint-data.csv";
  line "      - perf_summary.csv";
  if ref_build <> None then begin
  line "      - statusm_ref.txt";
  line "      - ast_md5sums_ref.txt";
  line "      - md5sums_ref.txt";
  line "      - perf-report";
  line "      - perf_analysis.md";
  line "      - perf_analysis.csv";
  line "      - perf_analysis_gitlab.md";
  line "      - hint_data_diff.html";
  line "      - hint-data_ref.csv ";
  line "      - perf_summary_ref.csv";
  end;
  line "    reports:";
  line "      codequality: gl-code-quality-report.json"

let nova_job : Out_channel.t -> unit = fun oc ->
  let (nova, (_, hashes)) =
    try
      List.find (fun (repo, _) -> repo.Config.name = "NOVA") repos_with_hashes
    with Not_found -> panic "No config found for NOVA."
  in
  let nova_branch =
    match hashes.mr_branch with
    | None    -> nova.Config.main_branch
    | Some(_) ->
    let mr = match mr with None -> assert false | Some(mr) -> mr in
    mr.Info.mr_source_branch_name
  in
  let gen_name =
    let master_merge =
      match mr with Some(_) -> false | None ->
      let Info.{project_name; commit_branch; _} = trigger in
      match commit_branch with
      | None                -> false
      | Some(commit_branch) -> main_branch project_name = commit_branch
    in
    "gen-installed-artifact" ^ (if master_merge then "" else "-mr")
  in
  let image = main_image in
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "";
  line "%s:" gen_name;
  common ~image ~dune_cache:true oc;
  line "  script:";
  line "    # Print environment for debug.";
  line "    - env";
  line "    # Save job ID since the current job creates the artifact.";
  line "    - echo \"ARTIFACT_CI_JOB_ID=$CI_JOB_ID\" \
                > $CI_PROJECT_DIR/build.env";
  (* We only want fmdeps, so clone everything in a temporary directory. *)
  line "    # Initialize a bhv checkout.";
  let clone_dir = "/tmp/clone-dir" in
  bhv_cloning oc clone_dir;
  line "    - cd %s" clone_dir;
  line "    - time make -j ${NJOBS} init";
  line "    - make dump_repos_info";
  checkout_commands oc main_build;
  line "    - make statusm | tee $CI_PROJECT_DIR/statusm.txt";
  line "    - grep \"^fmdeps/\" $CI_PROJECT_DIR/statusm.txt \
                > $CI_PROJECT_DIR/gitshas.txt";
  (* Prepare the dune file structure for the cache. *)
  line "    # Create Directory structure for dune";
  line "    - mkdir -p ~/.cache/ ~/.config/dune/";
  line "    - cp support/fm/dune_config ~/.config/dune/config";
  (* Prepare and move to the build directory. *)
  line "    # Build directory preparation.";
  line "    - mkdir %s" build_dir;
  line "    - mv fmdeps dune-workspace %s/" build_dir;
  line "    - cd %s" build_dir;
  (* Build and create installed artifact. *)
  line "    # Build.";
  line "    - make -C fmdeps/cpp2v ast-prepare";
  line "    - dune build _build/install/default/bin/filter-dune-output";
  line "    - dune build -j ${NJOBS} @install 2>&1 | \
                _build/install/default/bin/filter-dune-output";
  line "    # Prepare installed artifact.";
  line "    - rm -rf $CI_PROJECT_DIR/fm-install";
  line "    - mkdir $CI_PROJECT_DIR/fm-install";
  line "    - dune install --prefix=$CI_PROJECT_DIR/fm-install \
                --display=quiet";
  line "    - find $CI_PROJECT_DIR/fm-install -name '*.v' -o -name '*.ml' | while read i; do > $i; done";
  line "  artifacts:";
  line "    when: always";
  line "    expose_as: \"installed fmdeps\"";
  line "    name: cpp2v";
  line "    paths:";
  line "      - fm-install";
  line "      - gitshas.txt";
  line "    reports:";
  line "      dotenv: build.env";
  line "";
  line "NOVA-trigger:";
  line "  needs:";
  line "    - %s" gen_name;
  line "  variables:";
  line "    UPSTREAM_IMAGE: \"%s\"" image;
  line "    UPSTREAM_CI_JOB_ID: $ARTIFACT_CI_JOB_ID";
  line "  trigger:";
  line "    project: bedrocksystems/NOVA";
  line "    branch: %s" nova_branch;
  line "    strategy: depend"

let cpp2v_core_llvm_job : Out_channel.t -> int -> unit = fun oc llvm ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "";
  line "cpp2v-llvm-%i:" llvm;
  common ~image:(ci_image_default_swipl ~llvm) ~dune_cache:true oc;
  line "  script:";
  line "    # Print environment for debug.";
  line "    - env";
  bhv_cloning oc build_dir;
  line "    - cd %s" build_dir;
  line "    - time make -j ${NJOBS} init";
  line "    - make dump_repos_info";
  checkout_commands oc main_build;
  line "    - make statusm";
  (* Prepare the dune file structure for the cache. *)
  line "    # Create Directory structure for dune";
  line "    - mkdir -p ~/.cache/ ~/.config/dune/";
  line "    - cp support/fm/dune_config ~/.config/dune/config";
  (* Build cpp2v-core including tests. *)
  line "    # Build.";
  line "    - make -C fmdeps/cpp2v ast-prepare";
  line "    - dune build _build/install/default/bin/filter-dune-output";
  line "    - dune build -j ${NJOBS} \
                fmdeps/cpp2v-core @fmdeps/cpp2v-core/runtest 2>&1 | \
                _build/install/default/bin/filter-dune-output"

let cpp2v_core_public_job : Out_channel.t -> int -> unit = fun oc llvm ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "";
  line "cpp2v-public-llvm-%i:" llvm;
  common ~image:(ci_image_default_swipl ~llvm) ~dune_cache:true oc;
  line "  script:";
  line "    # Print environment for debug.";
  line "    - env";
  bhv_cloning oc build_dir;
  line "    - cd %s" build_dir;
  line "    - time make -j ${NJOBS} init";
  line "    - make dump_repos_info";
  checkout_commands oc main_build;
  line "    - make statusm";
  (* Prepare the dune file structure for the cache. *)
  line "    # Create Directory structure for dune";
  line "    - mkdir -p ~/.cache/ ~/.config/dune/";
  line "    - cp support/fm/dune_config ~/.config/dune/config";
  (* Pin the packages. *)
  line "    # Pin the packages and install.";
  line "    - opam pin add -n -y coq-upoly.dev ./fmdeps/cpp2v-core/coq-upoly";
  line "    - opam pin add -n -y coq-cpp2v.dev ./fmdeps/cpp2v-core";
  line "    - opam pin add -n -y coq-cpp2v-bin.dev ./fmdeps/cpp2v-core";
  line "    - opam pin add -n -y coq-lens.dev ./fmdeps/cpp2v-core/coq-lens";
  line "    - opam pin add -n -y coq-lens-elpi.dev \
                ./fmdeps/cpp2v-core/coq-lens";
  line "    - opam install --assume-depexts -y \
                coq-upoly coq-cpp2v coq-cpp2v-bin coq-lens coq-lens-elpi"
[@@warning "-32"]

let cpp2v_core_pages_publish : Out_channel.t -> unit = fun oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "";
  line "cpp2v-docs-publish:";
  line "  image: ruby:2.5";
  line "  needs:";
  line "    - cpp2v-docs-gen";
  line "  tags:";
  line "    - fm.nfs";
  line "  script:";
  line "    - git config --global user.email \"${BRICK_BOT_EMAIL}\"";
  line "    - git config --global user.name \"${BRICK_BOT_USERNAME}\"";
  line "    - git clone \
                https://${BRICK_BOT_USERNAME}:${BRICK_BOT_TOKEN}@\
                gitlab.com/bedrocksystems/cpp2v-core.git";
  line "    - cd cpp2v-core";
  line "    - git checkout gh-pages";
  line "    - git rm -r docs";
  line "    - mv ../html docs";
  line "    - touch docs/.nojekyll";
  line "    - git add -f docs";
  line "    - >";
  line "      if git diff-index --quiet HEAD; then";
  line "        echo \" No changes to the documentation.\"";
  line "        exit 0";
  line "      fi";
  line "    - git commit -m \"[github pages] BRiCk documentation created \
                from $CI_COMMIT_SHORT_SHA\"";
  line "    - git push origin gh-pages"


let cpp2v_core_pages_job : Out_channel.t -> unit = fun oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "";
  line "cpp2v-docs-gen:";
  common ~image:main_image ~dune_cache:true oc;
  line "  script:";
  line "    # Print environment for debug.";
  line "    - env";
  bhv_cloning oc build_dir;
  line "    - cd %s" build_dir;
  line "    - time make -j ${NJOBS} init";
  line "    - make dump_repos_info";
  checkout_commands oc main_build;
  line "    - make statusm";
  (* Prepare the dune file structure for the cache. *)
  line "    # Create Directory structure for dune";
  line "    - mkdir -p ~/.cache/ ~/.config/dune/";
  line "    - cp support/fm/dune_config ~/.config/dune/config";
  (* Build the pages. *)
  line "    # Build the pages.";
  line "    - make -C fmdeps/cpp2v ast-prepare";
  line "    - cd fmdeps/cpp2v-core";
  line "    - git submodule update --init";
  line "    - make -j ${NJOBS} doc";
  line "    - mv doc/sphinx/_build/html $CI_PROJECT_DIR/html";
  line "  artifacts:";
  line "    paths:";
  line "      - html";
  (* Only publish the pages on master branch pipelines from cpp2v-core. *)
  let publish =
    let Info.{project_name; commit_branch; _} = trigger in
    match commit_branch with None -> false | Some(commit_branch) ->
    project_name = "cpp2v-core" && main_branch "cpp2v-core" = commit_branch
  in
  if publish then cpp2v_core_pages_publish oc

(* TODO (FM-4443): generalize to:
   1) run on all [.v] artifacts
   2) produce a code quality report that is consumeable by gitlab. *)
let proof_tidy : Out_channel.t -> unit = fun oc ->
  let line fmt = Printf.fprintf oc (fmt ^^ "\n") in
  line "proof-tidy:";
  common ~image:main_image ~dune_cache:true oc;
  line "  script:";
  line "    # Print environment for debug.";
  line "    - env";
  bhv_cloning oc build_dir;
  line "    - cd %s" build_dir;
  line "    - time make -j ${NJOBS} init";
  line "    - make dump_repos_info";
  checkout_commands oc main_build;
  line "    - make statusm";
  line "    # Apply structured linting policies to portions of the vSwitch";
  line "    - python3 ./fmdeps/fm-ci/fm-linter/coq_lint.py \
                --use-ci-output-format \
                --proof-dirs apps/vswitch/lib/forwarding/proof/ \
                apps/vswitch/lib/port/proof/ \
                # apps/vswitch/lib/vswitch/proof/";
  line "    # Apply a generic linting policy to all child [.v] files, \
                enforcing avoidance of imports/exports written using [From]";
  line "    - python3 ./fmdeps/fm-ci/fm-linter/coq_lint.py \
                --use-ci-output-format apps/vswitch";
  line "    - python3 ./fmdeps/fm-ci/fm-linter/coq_lint.py
                --use-ci-output-format apps/vmm/"

let output_config : Out_channel.t -> unit = fun oc ->
  (* Static header, with workflow config. *)
  output_static oc;
  (* Main bhv build with performance comparison support. *)
  main_job oc;
  (* Stop here if we only want the full job. *)
  match trigger.only_full_build with true -> () | false ->
  (* Proof tidy job. *)
  proof_tidy oc;
  (* Triggered NOVA build. *)
  if needs_full_build "NOVA" then nova_job oc;
  (* Extra cpp2v-core builds. *)
  if needs_full_build "cpp2v-core" then begin
    cpp2v_core_llvm_job oc 16;
    cpp2v_core_llvm_job oc 17;
    cpp2v_core_llvm_job oc 19;
    (*cpp2v_core_public_job oc "16";*)
    cpp2v_core_pages_job oc;
  end

let _ =
  (* Generate the configuration. *)
  perr "#### Generating the configuration file ####";
  perr "Target file: %S." yaml_file;
  Out_channel.with_open_text yaml_file output_config
