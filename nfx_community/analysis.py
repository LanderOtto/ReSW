import re
from pathlib import Path

from .api import contents_list


def analyze_via_api(full_name):
    info = {
        "has_modules_json": False,
        "has_nfcore_dir": False,
        "has_local_dir": False,
        "has_gitmodules": False,
        "has_nextflow_config": False,
        "has_main_nf": False,
        "entrypoint": None,
        "modules_dir_contents": [],
        "nfcore_modules": [],
        "local_modules": [],
    }
    root = contents_list(full_name, "")
    if root is None or not isinstance(root, list):
        return info
    names = {i["name"] for i in root}
    info["has_nextflow_config"] = "nextflow.config" in names
    info["has_main_nf"] = "main.nf" in names
    if info["has_main_nf"]:
        info["entrypoint"] = "main.nf"
    info["has_modules_json"] = "modules.json" in names
    info["has_gitmodules"] = ".gitmodules" in names
    if "modules" not in names:
        return info
    mod = contents_list(full_name, "modules")
    if mod is None or not isinstance(mod, list):
        return info
    info["modules_dir_contents"] = sorted(i["name"] for i in mod if i["type"] == "dir")
    mn = set(info["modules_dir_contents"])
    info["has_nfcore_dir"] = "nf-core" in mn
    info["has_local_dir"] = "local" in mn
    if info["has_nfcore_dir"]:
        nf = contents_list(full_name, "modules/nf-core")
        if nf and isinstance(nf, list):
            info["nfcore_modules"] = sorted(i["name"] for i in nf if i["type"] == "dir")
    if info["has_local_dir"]:
        loc = contents_list(full_name, "modules/local")
        if loc and isinstance(loc, list):
            info["local_modules"] = sorted(i["name"] for i in loc if i["type"] == "dir")
    return info


def analyze_via_clone(clone_dir):
    info = {
        "has_modules_json": False,
        "has_nfcore_dir": False,
        "has_local_dir": False,
        "has_gitmodules": False,
        "has_nextflow_config": False,
        "has_main_nf": False,
        "entrypoint": None,
        "modules_dir_contents": [],
        "nfcore_modules": [],
        "local_modules": [],
    }

    info["has_nextflow_config"] = (clone_dir / "nextflow.config").is_file()
    info["has_main_nf"] = (clone_dir / "main.nf").is_file()

    if info["has_nextflow_config"]:
        text = (clone_dir / "nextflow.config").read_text()
        m = re.search(r"mainScript\s*=\s*['\"]([^'\"]+)['\"]", text)
        if m:
            info["entrypoint"] = m.group(1)
        elif info["has_main_nf"]:
            info["entrypoint"] = "main.nf"

    info["has_modules_json"] = (clone_dir / "modules.json").is_file()
    gm = clone_dir / ".gitmodules"
    if gm.is_file():
        info["has_gitmodules"] = "nf-core/modules" in gm.read_text()
    mod = clone_dir / "modules"
    if not mod.is_dir():
        return info
    info["modules_dir_contents"] = sorted(d.name for d in mod.iterdir() if d.is_dir())
    nfcore = mod / "nf-core"
    local = mod / "local"
    info["has_nfcore_dir"] = nfcore.is_dir()
    info["has_local_dir"] = local.is_dir()
    if info["has_nfcore_dir"]:
        info["nfcore_modules"] = sorted(d.name for d in nfcore.iterdir() if d.is_dir())
    if info["has_local_dir"]:
        info["local_modules"] = sorted(d.name for d in local.iterdir() if d.is_dir())
    return info


def classify_module_style(mod_info):
    has_nf = mod_info.get("has_nfcore_dir")
    has_lo = mod_info.get("has_local_dir")
    has_ot = any(
        d not in ("nf-core", "local") for d in mod_info.get("modules_dir_contents", [])
    )
    if has_nf and has_lo and has_ot:
        return "nf-core+local+other"
    elif has_nf and has_lo:
        return "nf-core+local"
    elif has_nf and has_ot:
        return "nf-core+other"
    elif has_lo and has_ot:
        return "local+other"
    elif has_nf:
        return "nf-core"
    elif has_lo:
        return "local"
    elif mod_info.get("modules_dir_contents"):
        return "custom"
    else:
        return "no_modules"


def classify_module_subtype(mod_info, fn, clone_base):
    sub = "unknown"
    has_mod_inc = False
    has_nfcore_inc = False

    if mod_info.get("has_modules_json"):
        sub = "nfcore_declared"
    elif mod_info.get("has_nfcore_dir"):
        sub = "nfcore_direct"
    elif mod_info.get("cloned"):
        cd = clone_base / fn.replace("/", "__")
        gm = cd / ".gitmodules"
        gm_nfcore = False
        if gm.exists():
            try:
                txt = gm.read_text().lower()
                if "nf-core" in txt or "github.com/nf-core" in txt:
                    gm_nfcore = True
            except:
                pass
        nf_files = list(cd.rglob("*.nf"))
        for nf in nf_files[:50]:
            try:
                text = nf.read_text()
            except:
                continue
            for line in text.splitlines():
                s = line.strip()
                if not s.startswith("include"):
                    continue
                if "nf-core" in s:
                    has_nfcore_inc = True
                elif "/module" in s.lower() or "'./mod" in s or '"./mod' in s:
                    has_mod_inc = True
        if has_nfcore_inc:
            sub = "nfcore_include"
        elif gm_nfcore:
            sub = "nfcore_submodule"

    if sub == "unknown":
        style = mod_info.get("module_style")
        if style == "no_modules":
            if mod_info.get("cloned"):
                cd = clone_base / fn.replace("/", "__")
                mod_dir = cd / "modules"
                if mod_dir.is_dir():
                    contents = list(mod_dir.iterdir())
                    files = [p for p in contents if p.is_file()]
                    subdirs = [p for p in contents if p.is_dir()]
                    if files and not subdirs:
                        sub = "flat_modules_dir"
                    elif subdirs:
                        sub = "has_module_subdirs"
                if sub == "unknown" and has_mod_inc:
                    sub = "has_include_modules"
            if sub == "unknown":
                gm = (clone_base / fn.replace("/", "__")) / ".gitmodules"
                if gm.exists():
                    sub = "has_submodules"
            if sub == "unknown":
                if mod_info.get("has_nextflow_config"):
                    sub = "config_only"
                elif mod_info.get("entrypoint"):
                    sub = "entrypoint_only"
                else:
                    sub = "truly_empty"
        elif style in ("local", "local+other"):
            sub = "local_only"
        elif style == "custom":
            sub = "custom_only"
        else:
            sub = "nfcore_only"

    if sub == "unknown":
        sub = "truly_empty"
    return sub


def detect_reimplementations(mod_info, nfcore_modules, nfcore_subworkflows=None):
    reimp = set()
    nf_sw_set = set(s.lower() for s in (nfcore_subworkflows or []))
    style = mod_info.get("module_style")
    if style in ("local", "nf-core+local", "nf-core+local+other", "local+other"):
        for name in mod_info.get("local_modules", []):
            for nf in nfcore_modules:
                if name == nf or name in nf or nf in name:
                    reimp.add(nf)
            if nf_sw_set and name.lower() in nf_sw_set:
                reimp.add(f"subworkflow:{name}")
    if style in ("custom", "nf-core+other", "local+other", "nf-core+local+other"):
        for name in mod_info.get("modules_dir_contents", []):
            for nf in nfcore_modules:
                if name == nf or nf.startswith(name + "/") or name == nf.split("/")[0]:
                    reimp.add(nf)
            if nf_sw_set and name.lower() in nf_sw_set:
                reimp.add(f"subworkflow:{name}")
    return reimp
