open Extra

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
  let panic fmt = panic ("File %s: " ^^ fmt ^^ ".") file in
  let versions = ref None in
  let repos = ref [] in
  let handle_section key value =
    let open Toml.Types in
    match Table.Key.to_string key with
    | "versions" ->
        let image = ref None in
        let main_llvm = ref None in
        let main_swipl = ref None in
        let handle_version key value =
          let key = Table.Key.to_string key in
          match (key, value) with
          | ("image"     , TString(s)) -> image := Some(s)
          | ("image"     , _         ) ->
              panic "expected string in field [versions.%s]" key
          | ("main_llvm" , TInt(i)   ) -> main_llvm := Some(i)
          | ("main_llvm" , _         ) ->
              panic "expected integer in field [versions.%s]" key
          | ("main_swipl", TString(s)) -> main_swipl := Some(s)
          | ("main_swipl", _         ) ->
              panic "expected string in field [versions.%s]" key
          | (_                   , _         ) ->
              panic "unknown field key [versions.%s]" key
        in
        let table =
          match value with TTable(table) -> table | _ ->
          panic "entry [versions] is not a table"
        in
        Toml.Types.Table.iter handle_version table;
        let image =
          try Option.get !image with Invalid_argument(_) ->
          panic "[versions.image] is mandatory" file
        in
        let main_llvm =
          try Option.get !main_llvm with Invalid_argument(_) ->
          panic "[versions.main_llvm] is mandatory" file
        in
        let main_swipl =
          try Option.get !main_swipl with Invalid_argument(_) ->
          panic "[versions.main_swipl] is mandatory" file
        in
        versions := Some({image; main_llvm; main_swipl})
    | "repo"   ->
        let table =
          match value with TTable(table) -> table | _ ->
          panic "entry [repo] is not a table"
        in
        let handle_repo key value =
          let name = Table.Key.to_string key in
          let repo = Format.sprintf "repo.%s" name in
          let table =
            match value with TTable(table) -> table | _ ->
            panic "entry [repo.%s] is not a table" name
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
                panic "expected string in field [%s.%s]" repo key
            | ("branch"  , TString(s)           ) -> main_branch := Some(s)
            | ("branch"  , _                    ) ->
                panic "expected string in field [%s.%s]" repo key
            | ("path"    , TString(s)           ) -> bhv_path := Some(s)
            | ("path"    , _                    ) ->
                panic "expected string in field [%s.%s]" repo key
            | ("deps"    , TArray(NodeString(l))) -> deps := Some(l)
            | ("deps"    , TArray(NodeEmpty)    ) -> deps := Some([])
            | ("deps"    , _                    ) ->
                panic "expected string list in [%s.%s]" repo key
            | ("vendored", TBool(b)             ) -> vendored := Some(b)
            | ("vendored", _                    ) ->
                panic "expected bool in field [%s.%s]" repo key
            | (_         , _                    ) ->
                panic "unknown field key [%s.%s]" repo key
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
        panic "unknown field key [%s]" key
  in
  Toml.Types.Table.iter handle_section table;
  let versions =
    try Option.get !versions with Invalid_argument(_) ->
    panic "no [versions] section included"
  in
  let repos = List.rev !repos in
  {versions; repos}

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
