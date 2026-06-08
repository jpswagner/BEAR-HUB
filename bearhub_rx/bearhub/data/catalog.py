"""
BEAR-HUB data catalog — driven by Bactopia's official catalog.json (v4.0.0).

`bactopia_catalog.json` is shipped verbatim from bactopia/bactopia@v4.0.0, so the
tool list here is exactly the set of `--wf` Bactopia Tools the pipeline exposes.
We layer on a curated category map, nice labels, and detailed parameter specs for
the high-value tools (the rest run with the shared general options + raw extras).
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]  # bearhub_rx/bearhub/data/ -> repo root (BEAR-HUB)

BACTOPIA_VERSION = "4.0.0"
PROFILES = ["docker", "singularity", "standard"]


# ── Static data (load utils/data.py by path; it only imports `re`) ─────────────
def _load_data_module():
    data_py = _REPO_ROOT / "utils" / "data.py"
    try:
        spec = importlib.util.spec_from_file_location("_bactopia_data", data_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        return None


_DATA = _load_data_module()
MLST_SCHEMES = dict(getattr(_DATA, "MLST_SCHEMES", {}))
MLST_DISPLAY = ["(auto/none)"] + sorted(MLST_SCHEMES.keys())
GENOME_SIZES = list(getattr(_DATA, "GENOME_SIZES", []))


# ── Curated categories + nice labels for the 67 Bactopia Tools ─────────────────
CATEGORY_ORDER = [
    "Antimicrobial Resistance",
    "Typing & Serotyping",
    "Plasmids & Mobile Elements",
    "Taxonomy & Metagenomics",
    "Quality Control",
    "Annotation",
    "Sequence Search (BLAST)",
    "Phylogenetics & Pangenome",
    "Other",
]

_CATEGORY = {
    # AMR
    "amrfinderplus": "Antimicrobial Resistance", "rgi": "Antimicrobial Resistance",
    "abricate": "Antimicrobial Resistance", "abritamr": "Antimicrobial Resistance",
    "ariba": "Antimicrobial Resistance", "gamma": "Antimicrobial Resistance",
    "mykrobe": "Antimicrobial Resistance", "mcroni": "Antimicrobial Resistance",
    "tbprofiler": "Antimicrobial Resistance",
    # Typing & serotyping
    "mlst": "Typing & Serotyping", "gigatyper": "Typing & Serotyping",
    "sccmec": "Typing & Serotyping", "spatyper": "Typing & Serotyping",
    "agrvate": "Typing & Serotyping", "staphtyper": "Typing & Serotyping",
    "ectyper": "Typing & Serotyping", "stecfinder": "Typing & Serotyping",
    "shigatyper": "Typing & Serotyping", "shigeifinder": "Typing & Serotyping",
    "shigapass": "Typing & Serotyping", "clermontyping": "Typing & Serotyping",
    "kleborate": "Typing & Serotyping", "lissero": "Typing & Serotyping",
    "legsta": "Typing & Serotyping", "seqsero2": "Typing & Serotyping",
    "sistr": "Typing & Serotyping", "genotyphi": "Typing & Serotyping",
    "meningotype": "Typing & Serotyping", "ngmaster": "Typing & Serotyping",
    "emmtyper": "Typing & Serotyping", "pbptyper": "Typing & Serotyping",
    "seroba": "Typing & Serotyping", "pneumocat": "Typing & Serotyping",
    "pasty": "Typing & Serotyping", "hicap": "Typing & Serotyping",
    "hpsuissero": "Typing & Serotyping", "ssuissero": "Typing & Serotyping",
    "btyper3": "Typing & Serotyping",
    # Plasmids & MGE
    "mobsuite": "Plasmids & Mobile Elements", "plasmidfinder": "Plasmids & Mobile Elements",
    "ismapper": "Plasmids & Mobile Elements", "phispy": "Plasmids & Mobile Elements",
    "defensefinder": "Plasmids & Mobile Elements",
    # Taxonomy & metagenomics
    "kraken2": "Taxonomy & Metagenomics", "bracken": "Taxonomy & Metagenomics",
    "sylph": "Taxonomy & Metagenomics", "midas": "Taxonomy & Metagenomics",
    "gtdb": "Taxonomy & Metagenomics", "fastani": "Taxonomy & Metagenomics",
    "mashdist": "Taxonomy & Metagenomics", "scrubber": "Taxonomy & Metagenomics",
    # QC
    "checkm": "Quality Control", "checkm2": "Quality Control",
    "busco": "Quality Control", "quast": "Quality Control",
    # Annotation
    "bakta": "Annotation", "prokka": "Annotation", "eggnog": "Annotation",
    # BLAST
    "blastn": "Sequence Search (BLAST)", "blastp": "Sequence Search (BLAST)",
    "blastx": "Sequence Search (BLAST)", "tblastn": "Sequence Search (BLAST)",
    "tblastx": "Sequence Search (BLAST)",
    # Phylogenetics & pangenome
    "pangenome": "Phylogenetics & Pangenome", "mashtree": "Phylogenetics & Pangenome",
    "snippy": "Phylogenetics & Pangenome",
}

_LABELS = {
    "amrfinderplus": "AMRFinderPlus", "rgi": "RGI (CARD)", "abricate": "ABRicate",
    "abritamr": "abriTAMR", "mlst": "MLST", "mobsuite": "MOB-suite",
    "plasmidfinder": "PlasmidFinder", "tbprofiler": "TB-Profiler",
    "seqsero2": "SeqSero2", "sistr": "SISTR", "ectyper": "ECTyper",
    "shigatyper": "ShigaTyper", "shigeifinder": "ShigEiFinder", "shigapass": "ShigaPass",
    "stecfinder": "STECFinder", "clermontyping": "ClermonTyping", "kleborate": "Kleborate",
    "lissero": "LisSero", "legsta": "legsta", "genotyphi": "genotyphi",
    "meningotype": "meningotype", "ngmaster": "ngmaster", "emmtyper": "emmtyper",
    "pbptyper": "pbptyper", "seroba": "SeroBA", "pneumocat": "PneumoCaT",
    "pasty": "pasty", "hicap": "hicap", "hpsuissero": "HpsuisSero",
    "ssuissero": "SsuisSero", "btyper3": "BTyper3", "sccmec": "SCCmec",
    "spatyper": "spaTyper", "agrvate": "AgrVATE", "staphtyper": "StaphTyper",
    "kraken2": "Kraken2", "bracken": "Bracken", "sylph": "Sylph", "midas": "MIDAS",
    "gtdb": "GTDB-Tk", "fastani": "FastANI", "mashdist": "Mash dist",
    "checkm": "CheckM", "checkm2": "CheckM2", "busco": "BUSCO", "quast": "QUAST",
    "bakta": "Bakta", "prokka": "Prokka", "eggnog": "eggNOG-mapper",
    "mashtree": "Mashtree", "snippy": "Snippy", "pangenome": "Pangenome",
    "defensefinder": "DefenseFinder", "phispy": "PhiSpy", "ismapper": "ISMapper",
    "gamma": "GAMMA", "mykrobe": "Mykrobe", "mcroni": "mcroni", "ariba": "ARIBA",
    "gigatyper": "GigaTyper", "scrubber": "SRA Scrubber",
}

# Tools with bespoke parameter panels (everything else uses general opts + extras).
DETAILED = {"amrfinderplus", "rgi", "mlst", "plasmidfinder", "mashtree", "pangenome"}


def _label_for(tool_id: str) -> str:
    return _LABELS.get(tool_id, tool_id.replace("_", " ").replace("-", " ").title())


def _load_tools() -> list[dict]:
    raw = json.loads((_HERE / "bactopia_catalog.json").read_text(encoding="utf-8"))
    out: list[dict] = []
    for name, meta in raw.get("workflows", {}).items():
        if meta.get("type") != "tool":
            continue
        if name == "merlin":  # MERLIN has its own dedicated page
            continue
        desc = meta.get("description", "")
        if desc.startswith("Bactopia Tool:"):  # placeholder descriptions in catalog
            desc = {
                "amrfinderplus": "Detect AMR & virulence genes/mutations (NCBI AMRFinderPlus).",
                "plasmidfinder": "Detect plasmid replicons in assemblies.",
            }.get(name, desc)
        out.append({
            "id": name,
            "label": _label_for(name),
            "desc": desc,
            "category": _CATEGORY.get(name, "Other"),
            "detailed": name in DETAILED,
        })
    out.sort(key=lambda t: (CATEGORY_ORDER.index(t["category"]), t["label"].lower()))
    return out


TOOLS: list[dict] = _load_tools()
TOOLS_BY_ID: dict[str, dict] = {t["id"]: t for t in TOOLS}


def tools_in_category(cat: str) -> list[dict]:
    return [t for t in TOOLS if t["category"] == cat]


# ── MERLIN species-specific tools (bactopia v4.0.0 subworkflows/merlin) ────────
MERLIN_SPECIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Escherichia / Shigella", [
        ("ClermonTyping", "clermontyping"), ("ECTyper", "ectyper"),
        ("ShigaPass", "shigapass"), ("ShigaTyper", "shigatyper"),
        ("ShigEiFinder", "shigeifinder"), ("STECFinder", "stecfinder"),
    ]),
    ("Haemophilus", [("hicap", "hicap"), ("HpsuisSero", "hpsuissero")]),
    ("Klebsiella", [("Kleborate", "kleborate")]),
    ("Legionella", [("legsta", "legsta")]),
    ("Listeria", [("LisSero", "lissero")]),
    ("Mycobacterium", [("TB-Profiler", "tbprofiler")]),
    ("Neisseria", [("ngmaster", "ngmaster")]),
    ("Pseudomonas", [("pasty", "pasty")]),
    ("Salmonella", [("genotyphi", "genotyphi"), ("SeqSero2", "seqsero2"), ("SISTR", "sistr")]),
    ("Staphylococcus", [("StaphTyper", "staphtyper")]),
    ("Streptococcus", [
        ("emmtyper", "emmtyper"), ("pbptyper", "pbptyper"),
        ("SeroBA", "seroba"), ("SsuisSero", "ssuissero"),
    ]),
]
MERLIN_WF_IDS = [wf for _, lst in MERLIN_SPECIES for _, wf in lst]


# ── Detailed parameter field specs ─────────────────────────────────────────────
# Each field: (key, kind, flag, label, default, help). kind in
# {bool,text,int,float,select}. `key` is namespaced "<tool>.<name>"; defaults
# below seed DEFAULT_OPTS / DEFAULT_FLAGS. Custom CLI assembly lives in
# build_tool_args() so quirks (inverted flags, grouped opts) stay correct.

FIELD_SPECS: dict[str, list[dict]] = {
    "amrfinderplus": [
        {"key": "amrfinderplus.plus", "kind": "bool", "label": "--plus", "default": True},
        {"key": "amrfinderplus.report_common", "kind": "bool", "label": "--report_common", "default": False},
        {"key": "amrfinderplus.report_all_equal_best", "kind": "bool", "label": "--report_all_equal", "default": False},
        {"key": "amrfinderplus.allow_overlap", "kind": "bool", "label": "--allow_overlap", "default": False},
        {"key": "amrfinderplus.exclude_quick", "kind": "bool", "label": "--exclude_quick_need_prediction", "default": False},
        {"key": "amrfinderplus.ident_min", "kind": "float", "label": "--ident_min", "default": "0.9"},
        {"key": "amrfinderplus.coverage_min", "kind": "float", "label": "--coverage_min", "default": "0.6"},
        {"key": "amrfinderplus.organism", "kind": "text", "label": "--organism", "default": "", "help": "e.g. Enterobacteriaceae"},
        {"key": "amrfinderplus.extra", "kind": "text", "label": "Extra (raw)", "default": ""},
    ],
    "rgi": [
        {"key": "rgi.use_diamond", "kind": "bool", "label": "--use_diamond", "default": True},
        {"key": "rgi.include_loose", "kind": "bool", "label": "--include_loose", "default": False},
        {"key": "rgi.exclude_nudge", "kind": "bool", "label": "--exclude_nudge", "default": False},
        {"key": "rgi.frequency", "kind": "text", "label": "--frequency", "default": "", "help": "e.g. perfect,strict"},
        {"key": "rgi.category", "kind": "text", "label": "--category", "default": ""},
        {"key": "rgi.cluster", "kind": "text", "label": "--cluster", "default": ""},
        {"key": "rgi.display", "kind": "text", "label": "--display", "default": ""},
        {"key": "rgi.extra", "kind": "text", "label": "Extra (raw)", "default": ""},
    ],
    "mlst": [
        {"key": "mlst.scheme", "kind": "select", "label": "--scheme", "default": "(auto/none)", "options": MLST_DISPLAY},
        {"key": "mlst.minid", "kind": "float", "label": "--minid", "default": "95"},
        {"key": "mlst.mincov", "kind": "float", "label": "--mincov", "default": "50"},
        {"key": "mlst.minscore", "kind": "float", "label": "--minscore", "default": "0"},
        {"key": "mlst.nopath", "kind": "bool", "label": "--nopath", "default": False},
    ],
    "plasmidfinder": [
        {"key": "plasmidfinder.mincov", "kind": "float", "label": "--pf_mincov (0–1)", "default": "0.6"},
        {"key": "plasmidfinder.threshold", "kind": "float", "label": "--pf_threshold (0–1)", "default": "0.9"},
        {"key": "plasmidfinder.extra", "kind": "text", "label": "Extra (raw)", "default": ""},
    ],
    "mashtree": [
        {"key": "mashtree.trunclength", "kind": "int", "label": "--trunclength", "default": "0"},
        {"key": "mashtree.sortorder", "kind": "text", "label": "--sortorder", "default": "", "help": "e.g. avg"},
        {"key": "mashtree.genomesize", "kind": "int", "label": "--genomesize", "default": "0"},
        {"key": "mashtree.mindepth", "kind": "int", "label": "--mindepth", "default": "0"},
        {"key": "mashtree.kmerlength", "kind": "int", "label": "--kmerlength", "default": "21"},
        {"key": "mashtree.sketchsize", "kind": "int", "label": "--sketchsize", "default": "10000"},
        {"key": "mashtree.save_sketches", "kind": "bool", "label": "--save_sketches", "default": False},
    ],
    "pangenome": [
        {"key": "pangenome.engine", "kind": "select", "label": "Engine", "default": "Panaroo",
         "options": ["Panaroo", "PIRATE", "Roary"]},
        {"key": "pangenome.species", "kind": "text", "label": "--species", "default": "", "help": "e.g. Escherichia coli"},
        {"key": "pangenome.accessions", "kind": "text", "label": "--accessions", "default": ""},
        {"key": "pangenome.skip_recombination", "kind": "bool", "label": "--skip_recombination", "default": False},
        # IQ-TREE
        {"key": "pangenome.iqtree_model", "kind": "text", "label": "--iqtree_model", "default": ""},
        {"key": "pangenome.bb", "kind": "int", "label": "--bb (ufboot)", "default": "0"},
        {"key": "pangenome.alrt", "kind": "int", "label": "--alrt", "default": "0"},
        {"key": "pangenome.asr", "kind": "bool", "label": "--asr", "default": False},
        {"key": "pangenome.iqtree_opts", "kind": "text", "label": "iqtree_opts", "default": ""},
        # Panaroo (used when engine = Panaroo)
        {"key": "pangenome.panaroo_mode", "kind": "text", "label": "--panaroo_mode", "default": "", "help": "strict | moderate | sensitive"},
        {"key": "pangenome.panaroo_threshold", "kind": "text", "label": "--panaroo_threshold", "default": ""},
        {"key": "pangenome.panaroo_core_threshold", "kind": "text", "label": "--panaroo_core_threshold", "default": ""},
        {"key": "pangenome.merge_paralogs", "kind": "bool", "label": "--merge_paralogs", "default": False},
        {"key": "pangenome.panaroo_opts", "kind": "text", "label": "panaroo_opts", "default": ""},
        # PIRATE (used when engine = PIRATE)
        {"key": "pangenome.pirate_steps", "kind": "text", "label": "--steps (PIRATE)", "default": "", "help": "e.g. 50,60,70,80,90,95,98"},
        {"key": "pangenome.para_off", "kind": "bool", "label": "--para_off (PIRATE)", "default": False},
        # Roary (used when engine = Roary)
        {"key": "pangenome.roary_i", "kind": "text", "label": "--i (Roary identity %)", "default": ""},
        {"key": "pangenome.roary_cd", "kind": "text", "label": "--cd (Roary core %)", "default": ""},
        {"key": "pangenome.use_prank", "kind": "bool", "label": "--use_prank (Roary)", "default": False},
        # Prokka (reference re-annotation)
        {"key": "pangenome.prokka_proteins", "kind": "text", "label": "--proteins (Prokka FASTA)", "default": ""},
        {"key": "pangenome.prokka_opts", "kind": "text", "label": "prokka_opts", "default": ""},
        # Scoary & SNP-dists
        {"key": "pangenome.traits", "kind": "text", "label": "Scoary --traits", "default": ""},
        {"key": "pangenome.p_value_cutoff", "kind": "text", "label": "Scoary --p_value_cutoff", "default": ""},
        {"key": "pangenome.correction", "kind": "text", "label": "Scoary --correction", "default": ""},
        {"key": "pangenome.permute", "kind": "bool", "label": "Scoary --permute", "default": False},
        {"key": "pangenome.snpdists_csv", "kind": "bool", "label": "SNP-dists --csv", "default": False},
    ],
}


def _seed_defaults() -> tuple[dict[str, str], dict[str, bool]]:
    opts: dict[str, str] = {}
    flags: dict[str, bool] = {}
    for fields in FIELD_SPECS.values():
        for f in fields:
            if f["kind"] == "bool":
                flags[f["key"]] = bool(f["default"])
            else:
                opts[f["key"]] = str(f["default"])
    return opts, flags


DEFAULT_OPTS, DEFAULT_FLAGS = _seed_defaults()


def _o(opts: dict, key: str) -> str:
    return str(opts.get(key, "")).strip()


def _num(v: str) -> bool:
    try:
        return float(v) != 0
    except (TypeError, ValueError):
        return bool(str(v).strip())


def build_tool_args(tool_id: str, opts: dict, flags: dict) -> list[str]:
    """Translate the per-tool options/flags into Bactopia `--wf` CLI args."""
    e: list[str] = []

    if tool_id == "amrfinderplus":
        if not flags.get("amrfinderplus.plus", True):
            e.append("--amrfinder_noplus")
        if _num(_o(opts, "amrfinderplus.ident_min")):
            e += ["--ident_min", _o(opts, "amrfinderplus.ident_min")]
        if _num(_o(opts, "amrfinderplus.coverage_min")):
            e += ["--coverage_min", _o(opts, "amrfinderplus.coverage_min")]
        if _o(opts, "amrfinderplus.organism"):
            e += ["--organism", _o(opts, "amrfinderplus.organism")]
        if flags.get("amrfinderplus.report_common"):
            e.append("--report_common")
        if flags.get("amrfinderplus.report_all_equal_best"):
            e.append("--report_all_equal")
        amr_opts = []
        if flags.get("amrfinderplus.allow_overlap"):
            amr_opts.append("--allow_overlap")
        if flags.get("amrfinderplus.exclude_quick"):
            amr_opts.append("--exclude_quick_need_prediction")
        if amr_opts:
            e += ["--amrfinder_opts", " ".join(amr_opts)]
        if _o(opts, "amrfinderplus.extra"):
            e += _o(opts, "amrfinderplus.extra").split()

    elif tool_id == "rgi":
        if flags.get("rgi.use_diamond"):
            e.append("--rgi_use_diamond")
        if flags.get("rgi.include_loose"):
            e.append("--rgi_include_loose")
        if flags.get("rgi.exclude_nudge"):
            e.append("--rgi_exclude_nudge")
        for k, flag in [("frequency", "--rgi_frequency"), ("category", "--rgi_category"),
                        ("cluster", "--rgi_cluster"), ("display", "--rgi_display")]:
            if _o(opts, f"rgi.{k}"):
                e += [flag, _o(opts, f"rgi.{k}")]
        if _o(opts, "rgi.extra"):
            e += _o(opts, "rgi.extra").split()

    elif tool_id == "mlst":
        disp = opts.get("mlst.scheme", "(auto/none)")
        if disp and disp != "(auto/none)":
            code = MLST_SCHEMES.get(disp)
            if code:
                e += ["--scheme", code]
        for k, flag in [("minid", "--minid"), ("mincov", "--mincov"), ("minscore", "--minscore")]:
            v = _o(opts, f"mlst.{k}")
            if v != "":
                e += [flag, v]
        if flags.get("mlst.nopath"):
            e.append("--nopath")

    elif tool_id == "plasmidfinder":
        if _num(_o(opts, "plasmidfinder.mincov")):
            e += ["--pf_mincov", _o(opts, "plasmidfinder.mincov")]
        if _num(_o(opts, "plasmidfinder.threshold")):
            e += ["--pf_threshold", _o(opts, "plasmidfinder.threshold")]
        if _o(opts, "plasmidfinder.extra"):
            e += _o(opts, "plasmidfinder.extra").split()

    elif tool_id == "mashtree":
        for k, flag in [("trunclength", "--trunclength"), ("sortorder", "--sortorder"),
                        ("genomesize", "--genomesize"), ("mindepth", "--mindepth"),
                        ("kmerlength", "--kmerlength"), ("sketchsize", "--sketchsize")]:
            v = _o(opts, f"mashtree.{k}")
            if _num(v):
                e += [flag, v]
        if flags.get("mashtree.save_sketches"):
            e.append("--save_sketches")

    elif tool_id == "pangenome":
        engine = opts.get("pangenome.engine", "Panaroo")
        if engine == "PIRATE":
            e.append("--use_pirate")
        elif engine == "Roary":
            e.append("--use_roary")
        if _o(opts, "pangenome.species"):
            e += ["--species", _o(opts, "pangenome.species")]
        if _o(opts, "pangenome.accessions"):
            e += ["--accessions", _o(opts, "pangenome.accessions")]
        if flags.get("pangenome.skip_recombination"):
            e.append("--skip_recombination")
        # IQ-TREE
        if _o(opts, "pangenome.iqtree_model"):
            e += ["--iqtree_model", _o(opts, "pangenome.iqtree_model")]
        if _num(_o(opts, "pangenome.bb")):
            e += ["--bb", _o(opts, "pangenome.bb")]
        if _num(_o(opts, "pangenome.alrt")):
            e += ["--alrt", _o(opts, "pangenome.alrt")]
        if flags.get("pangenome.asr"):
            e.append("--asr")
        if _o(opts, "pangenome.iqtree_opts"):
            e += ["--iqtree_opts", _o(opts, "pangenome.iqtree_opts")]
        # Engine-specific
        if engine == "Panaroo":
            for k, flag in [("panaroo_mode", "--panaroo_mode"),
                            ("panaroo_threshold", "--panaroo_threshold"),
                            ("panaroo_core_threshold", "--panaroo_core_threshold")]:
                if _o(opts, f"pangenome.{k}"):
                    e += [flag, _o(opts, f"pangenome.{k}")]
            if flags.get("pangenome.merge_paralogs"):
                e.append("--merge_paralogs")
            if _o(opts, "pangenome.panaroo_opts"):
                e += ["--panaroo_opts", _o(opts, "pangenome.panaroo_opts")]
        elif engine == "PIRATE":
            if _o(opts, "pangenome.pirate_steps"):
                e += ["--steps", _o(opts, "pangenome.pirate_steps")]
            if flags.get("pangenome.para_off"):
                e.append("--para_off")
        elif engine == "Roary":
            if _o(opts, "pangenome.roary_i"):
                e += ["--i", _o(opts, "pangenome.roary_i")]
            if _o(opts, "pangenome.roary_cd"):
                e += ["--cd", _o(opts, "pangenome.roary_cd")]
            if flags.get("pangenome.use_prank"):
                e.append("--use_prank")
        # Prokka
        if _o(opts, "pangenome.prokka_proteins"):
            e += ["--proteins", _o(opts, "pangenome.prokka_proteins")]
        if _o(opts, "pangenome.prokka_opts"):
            e += ["--prokka_opts", _o(opts, "pangenome.prokka_opts")]
        # Scoary & SNP-dists
        if _o(opts, "pangenome.traits"):
            e += ["--traits", _o(opts, "pangenome.traits")]
        if _o(opts, "pangenome.p_value_cutoff"):
            e += ["--p_value_cutoff", _o(opts, "pangenome.p_value_cutoff")]
        if _o(opts, "pangenome.correction"):
            e += ["--correction", _o(opts, "pangenome.correction")]
        if flags.get("pangenome.permute"):
            e.append("--permute")
        if flags.get("pangenome.snpdists_csv"):
            e.append("--csv")

    return e
