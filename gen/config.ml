open Extra

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

let read_config : string -> config = fun file ->
  let table =
    let open Toml.Parser in
    match from_filename file with
    | `Ok(table)               -> table
    | `Error(msg, loc)         ->
        panic "File %s, line %i, column %i: %s." file loc.line loc.column msg
    | exception Sys_error(msg) ->
        panic "File system error while reading %s.\n%s" file msg
  in
  let versions = ref None in
  let repos = ref [] in
  let handle_section key value =
    let open Toml.Types in
    match Table.Key.to_string key with
    | "config" ->
        let main_llvm_version = ref None in
        let main_swipl_version = ref None in
        let handle_config key value =
          let key = Table.Key.to_string key in
          match (key, value) with
          | ("main_llvm_version" , TInt(i)   ) ->
              main_llvm_version := Some(i)
          | ("main_llvm_version" , _         ) ->
              panic "File %s: expected integer in field [config.%s]." file key
          | ("main_swipl_version", TString(s)) ->
              main_swipl_version := Some(s)
          | ("main_swipl_version", _         ) ->
              panic "File %s: expected string in field [config.%s]." file key
          | (_                   , _         ) ->
              panic "File %s: unknown field key [config.%s]." file key
        in
        let table =
          match value with TTable(table) -> table | _ ->
          panic "File %s: entry [config] is not a table." file
        in
        Toml.Types.Table.iter handle_config table;
        let main_llvm_version =
          try Option.get !main_llvm_version with Invalid_argument(_) ->
          panic "File %s: [config.main_llvm_version] is mandatory." file
        in
        let main_swipl_version =
          try Option.get !main_swipl_version with Invalid_argument(_) ->
          panic "File %s: [config.main_swipl_version] is mandatory." file
        in
        versions := Some(main_llvm_version, main_swipl_version)
    | "repo"   ->
        let table =
          match value with TTable(table) -> table | _ ->
          panic "File %s: entry [repo] is not a table." file
        in
        let handle_repo key value =
          let name = Table.Key.to_string key in
          let repo = Format.sprintf "repo.%s" name in
          let table =
            match value with TTable(table) -> table | _ ->
            panic "File %s: entry [repo.%s] is not a table." file name
          in
          let gitlab = ref None in
          let bhv_path = ref None in
          let main_branch = ref None in
          let deps = ref None in
          let vendored = ref None in
          let handle_config key value =
            let key = Table.Key.to_string key in
            match (key, value) with
            | ("gitlab"  , TString(s)           ) -> gitlab := Some(s)
            | ("gitlab"  , _                    ) ->
                panic "File %s: expected string in field [%s.%s]." file repo key
            | ("branch"  , TString(s)           ) -> main_branch := Some(s)
            | ("branch"  , _                    ) ->
                panic "File %s: expected string in field [%s.%s]." file repo key
            | ("path"    , TString(s)           ) -> bhv_path := Some(s)
            | ("path"    , _                    ) ->
                panic "File %s: expected string in field [%s.%s]." file repo key
            | ("deps"    , TArray(NodeString(l))) -> deps := Some(l)
            | ("deps"    , TArray(NodeEmpty)    ) -> deps := Some([])
            | ("deps"    , _                    ) ->
                panic "File %s: expected string list in [%s.%s]." file repo key
            | ("vendored", TBool(b)             ) -> vendored := Some(b)
            | ("vendored", _                    ) ->
                panic "File %s: expected bool in field [%s.%s]." file repo key
            | (_         , _                    ) ->
                panic "File %s: unknown field key [%s.%s]." file repo key
          in
          Toml.Types.Table.iter handle_config table;
          let gitlab =
            match !gitlab with
            | Some(gitlab) -> gitlab
            | None         -> Format.sprintf "formal-methods/%s" name
          in
          let bhv_path =
            match !bhv_path with
            | Some(path) -> path
            | None       -> Format.sprintf "./fmdeps/%s" name
          in
          let main_branch = Option.value !main_branch ~default:"main" in
          let deps = Option.value !deps ~default:[] in
          let vendored = Option.value !vendored ~default:false in
          let repo = {name; gitlab; bhv_path; main_branch; deps; vendored} in
          repos := repo :: !repos
        in
        Toml.Types.Table.iter handle_repo table
    | key      ->
        panic "File %s: unknown field key [%s]." file key
  in
  Toml.Types.Table.iter handle_section table;
  let (main_llvm_version, main_swipl_version) =
    match !versions with
    | Some(llvm, swipl) -> (llvm, swipl)
    | None              ->
    panic "File %s should include a [config] section." file
  in
  let repos = List.rev !repos in
  {repos; main_llvm_version; main_swipl_version}

let repo_from_project_name : config:config -> string -> repo =
    fun ~config project_name ->
  try List.find (fun repo -> repo.gitlab = project_name) config.repos
  with Not_found ->
    panic "No repository configured with project name %s." project_name

let transitive_deps : config:config -> repo -> string list =
    fun ~config root ->
  let module S = Set.Make(String) in
  let rec transitive_deps deps roots =
    match roots with
    | []            -> S.elements deps
    | root :: roots ->
    if S.mem root deps then transitive_deps deps roots else
    match List.find_opt (fun r -> r.name = root) config.repos with
    | None            ->
        panic "Bad dependency in config: no repo named %s." root
    | Some(root_repo) ->
    transitive_deps (S.add root deps) (root_repo.deps @ roots)
  in
  transitive_deps S.empty [root.name]

let all_downstream_from : config:config -> repo list -> repo list =
    fun ~config roots ->
  let downstream_from_root repo =
    let deps = transitive_deps ~config repo in
    List.exists (fun root -> List.mem root.name deps) roots
  in
  List.filter downstream_from_root config.repos
