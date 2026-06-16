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

# GitHub repo backing the in-app "update available" check (owner/name).
GITHUB_REPO = "jpswagner/BEAR-HUB"


# ── Static data (MLST schemes + genome-size presets) ──────────────────────────
# Lives in-package (bearhub/data/static.py). Falls back to the legacy root-level
# utils/data.py by path if the in-package module is ever missing.
def _load_static():
    try:
        from bearhub.data import static as _s  # noqa: PLC0415
        return _s
    except Exception:
        pass
    try:
        data_py = _REPO_ROOT / "utils" / "data.py"
        spec = importlib.util.spec_from_file_location("_bactopia_data", data_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        return None


_DATA = _load_static()
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
        {"key": "amrfinderplus.plus", "kind": "bool", "label": "--amrfinderplus_noplus off (use --plus DB)", "default": True},
        {"key": "amrfinderplus.report_common", "kind": "bool", "label": "--amrfinderplus_report_common", "default": False},
        {"key": "amrfinderplus.report_all_equal_best", "kind": "bool", "label": "--amrfinderplus_report_all_equal", "default": False},
        {"key": "amrfinderplus.ident_min", "kind": "float", "label": "--amrfinderplus_ident_min", "default": "", "help": "Bactopia default: -1 (organism-specific / 0.9)"},
        {"key": "amrfinderplus.coverage_min", "kind": "float", "label": "--amrfinderplus_coverage_min", "default": "", "help": "Bactopia default: 0.5"},
        {"key": "amrfinderplus.organism", "kind": "text", "label": "--amrfinderplus_organism", "default": "", "help": "e.g. Escherichia (enables point mutations)"},
        {"key": "amrfinderplus.extra", "kind": "text", "label": "--amrfinderplus_opts (raw)", "default": "", "help": "e.g. --allow_overlap"},
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
        {"key": "mlst.db", "kind": "path", "label": "--mlst_db (REQUIRED)", "default": "",
         "help": "Path to a PubMLST database dir or .tar.gz — the mlst tool needs it"},
        {"key": "mlst.scheme", "kind": "select", "label": "--mlst_scheme", "default": "(auto/none)", "options": MLST_DISPLAY},
        {"key": "mlst.minid", "kind": "int", "label": "--mlst_minid", "default": "", "help": "Bactopia default: 95"},
        {"key": "mlst.mincov", "kind": "int", "label": "--mlst_mincov", "default": "", "help": "Bactopia default: 10"},
        {"key": "mlst.minscore", "kind": "int", "label": "--mlst_minscore", "default": "", "help": "Bactopia default: 50"},
        {"key": "mlst.nopath", "kind": "bool", "label": "--mlst_nopath", "default": False},
    ],
    "plasmidfinder": [
        {"key": "plasmidfinder.mincov", "kind": "float", "label": "--plasmidfinder_mincov (0–1)", "default": "", "help": "Bactopia default: 0.6"},
        {"key": "plasmidfinder.threshold", "kind": "float", "label": "--plasmidfinder_threshold (0–1)", "default": "", "help": "Bactopia default: 0.9"},
    ],
    "mashtree": [
        {"key": "mashtree.trunclength", "kind": "int", "label": "--mashtree_trunclength", "default": "", "help": "Bactopia default: 250"},
        {"key": "mashtree.sortorder", "kind": "text", "label": "--mashtree_sortorder", "default": "", "help": "ABC | random | tree"},
        {"key": "mashtree.genomesize", "kind": "int", "label": "--mashtree_genomesize", "default": "", "help": "Bactopia default: 5000000"},
        {"key": "mashtree.mindepth", "kind": "int", "label": "--mashtree_mindepth", "default": "", "help": "Bactopia default: 5"},
        {"key": "mashtree.kmerlength", "kind": "int", "label": "--mashtree_kmerlength", "default": "", "help": "Bactopia default: 21"},
        {"key": "mashtree.sketchsize", "kind": "int", "label": "--mashtree_sketchsize", "default": "", "help": "Bactopia default: 10000"},
        {"key": "mashtree.save_sketches", "kind": "bool", "label": "--mashtree_save_sketches", "default": False},
    ],
    "pangenome": [
        {"key": "pangenome.engine", "kind": "select", "label": "Engine", "default": "Panaroo",
         "options": ["Panaroo", "PIRATE", "Roary"]},
        {"key": "pangenome.species", "kind": "text", "label": "--species", "default": "", "help": "e.g. Escherichia coli"},
        {"key": "pangenome.accessions", "kind": "text", "label": "--accessions", "default": ""},
        {"key": "pangenome.skip_recombination", "kind": "bool", "label": "--skip_recombination", "default": False},
        # IQ-TREE
        {"key": "pangenome.iqtree_model", "kind": "text", "label": "--iqtree_model", "default": ""},
        {"key": "pangenome.bb", "kind": "int", "label": "--iqtree_bb (ufboot)", "default": "", "help": "Bactopia default: 1000"},
        {"key": "pangenome.alrt", "kind": "int", "label": "--iqtree_alrt", "default": "", "help": "Bactopia default: 1000"},
        {"key": "pangenome.asr", "kind": "bool", "label": "--iqtree_asr", "default": False},
        {"key": "pangenome.iqtree_opts", "kind": "text", "label": "--iqtree_opts", "default": ""},
        # Panaroo (used when engine = Panaroo)
        {"key": "pangenome.panaroo_mode", "kind": "text", "label": "--panaroo_mode", "default": "", "help": "strict | moderate | sensitive"},
        {"key": "pangenome.panaroo_threshold", "kind": "float", "label": "--panaroo_threshold", "default": "", "help": "Bactopia default: 0.98"},
        {"key": "pangenome.panaroo_core_threshold", "kind": "float", "label": "--panaroo_core_threshold", "default": "", "help": "Bactopia default: 0.95"},
        {"key": "pangenome.merge_paralogs", "kind": "bool", "label": "--panaroo_merge_paralogs", "default": False},
        {"key": "pangenome.panaroo_opts", "kind": "text", "label": "--panaroo_opts", "default": ""},
        # PIRATE (used when engine = PIRATE)
        {"key": "pangenome.pirate_steps", "kind": "text", "label": "--pirate_steps", "default": "", "help": "e.g. 50,60,70,80,90,95,98"},
        {"key": "pangenome.para_off", "kind": "bool", "label": "--pirate_para_off", "default": False},
        # Roary (used when engine = Roary)
        {"key": "pangenome.roary_i", "kind": "int", "label": "--roary_i (identity %)", "default": "", "help": "Bactopia default: 95"},
        {"key": "pangenome.roary_cd", "kind": "int", "label": "--roary_cd (core %)", "default": "", "help": "Bactopia default: 99"},
        {"key": "pangenome.use_prank", "kind": "bool", "label": "--roary_use_prank", "default": False},
        # Prokka (reference re-annotation)
        {"key": "pangenome.prokka_proteins", "kind": "text", "label": "--prokka_proteins (FASTA)", "default": ""},
        {"key": "pangenome.prokka_opts", "kind": "text", "label": "--prokka_opts", "default": ""},
        # Scoary & SNP-dists
        {"key": "pangenome.traits", "kind": "text", "label": "--scoary_traits (CSV)", "default": ""},
        {"key": "pangenome.p_value_cutoff", "kind": "float", "label": "--scoary_p_value_cutoff", "default": "", "help": "Bactopia default: 0.05"},
        {"key": "pangenome.correction", "kind": "text", "label": "--scoary_correction", "default": "", "help": "e.g. BH, bonferroni"},
        {"key": "pangenome.permute", "kind": "int", "label": "--scoary_permute", "default": "", "help": "permutations (Bactopia default: 0)"},
        {"key": "pangenome.snpdists_csv", "kind": "bool", "label": "--snpdists_csv", "default": False},
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


# Bactopia 4.0 tools declare some inputs as static-typed `Path?` (e.g.
# `amrfinderplus_db : Path?`) while their schema default is an empty string "".
# On Nextflow 26 the empty string is coerced to a Path at param-resolution time
# and aborts the whole run with "Path string cannot be empty" — before any
# process starts. Passing the param as JSON `null` via the -params-file sets it
# to null (a valid `Path?` value) and lets the tool run. We null every such
# param the user did NOT explicitly provide. Map verified against each tool's
# main.nf (typed `params{}` block) + nextflow_schema.json defaults.
TOOL_NULL_PATHS: dict[str, tuple[str, ...]] = {
    "amrfinderplus": ("amrfinderplus_db",),
    "bakta": ("bakta_db", "bakta_proteins", "bakta_prodigal_tf", "replicons"),
    "blastn": ("blastn_query",), "blastp": ("blastp_query",), "blastx": ("blastx_query",),
    "bracken": ("kraken2_db",), "checkm2": ("checkm2_db",), "eggnog": ("eggnog_db",),
    "emmtyper": ("emmtyper_blastdb",),
    "fastani": ("fastani_reference", "accessions"), "gamma": ("gamma_db",), "gtdb": ("gtdb",),
    "hicap": ("hicap_database_dir", "hicap_model_fp"),
    "ismapper": ("reference", "insertions"), "kraken2": ("kraken2_db",),
    "mashdist": ("mash_sketch",), "mashtree": ("accessions",),
    "merlin": ("emmtyper_blastdb", "hicap_database_dir", "hicap_model_fp",
               "spatyper_repeats", "spatyper_repeat_order"),
    "midas": ("midas_db",), "mlst": ("mlst_db",),
    "pangenome": ("accessions", "prokka_proteins", "prokka_prodigal_tf", "scoary_traits"),
    "prokka": ("prokka_proteins", "prokka_prodigal_tf"), "scrubber": ("nohuman_db",),
    "snippy": ("reference", "snippy_core_mask"),
    "spatyper": ("spatyper_repeats", "spatyper_repeat_order"),
    "staphtyper": ("spatyper_repeats", "spatyper_repeat_order"), "sylph": ("sylph_db",),
    "tblastn": ("tblastn_query",), "tblastx": ("tblastx_query",),
}


# UI opt key → Bactopia `number`-typed param name. These are routed to a
# `-params-file` JSON (nf-schema rejects floats from the CLI: "string but
# should be number"). Verified against each tool's nextflow_schema.json.
FLOAT_TOOL_PARAMS: dict[str, str] = {
    "amrfinderplus.ident_min":         "amrfinderplus_ident_min",
    "amrfinderplus.coverage_min":      "amrfinderplus_coverage_min",
    "plasmidfinder.mincov":            "plasmidfinder_mincov",
    "plasmidfinder.threshold":         "plasmidfinder_threshold",
    "pangenome.panaroo_threshold":     "panaroo_threshold",
    "pangenome.panaroo_core_threshold":"panaroo_core_threshold",
    "pangenome.p_value_cutoff":        "scoary_p_value_cutoff",
}


def build_tool_args(tool_id: str, opts: dict, flags: dict) -> tuple[list[str], dict]:
    """Translate per-tool options/flags into Bactopia `--wf` args.

    Returns ``(cli_args, json_params)``. All param names are the schema's
    prefixed names (e.g. ``--mlst_minid``, not ``--minid``). ``number``-typed
    params go into ``json_params`` for a ``-params-file`` (see FLOAT_TOOL_PARAMS);
    empty-default ``Path?`` params are added as JSON ``null`` (see TOOL_NULL_PATHS)
    so the run doesn't abort on Nextflow 26; everything else is a CLI flag/value.
    Empty fields are omitted so Bactopia keeps its own programmed defaults.
    """
    e: list[str] = []
    jp: dict = {}

    def num(key: str):
        """Route a number-typed opt to the params-file if the user set it."""
        v = _o(opts, key)
        if v == "":
            return
        try:
            jp[FLOAT_TOOL_PARAMS[key]] = float(v)
        except ValueError:
            pass

    def val(key: str, flag: str):
        """Emit `flag value` for a non-empty string/int opt."""
        v = _o(opts, key)
        if v != "":
            e.extend([flag, v])

    if tool_id == "amrfinderplus":
        if not flags.get("amrfinderplus.plus", True):
            e.append("--amrfinderplus_noplus")
        num("amrfinderplus.ident_min")
        num("amrfinderplus.coverage_min")
        val("amrfinderplus.organism", "--amrfinderplus_organism")
        if flags.get("amrfinderplus.report_common"):
            e.append("--amrfinderplus_report_common")
        if flags.get("amrfinderplus.report_all_equal_best"):
            e.append("--amrfinderplus_report_all_equal")
        if _o(opts, "amrfinderplus.extra"):
            e += ["--amrfinderplus_opts", _o(opts, "amrfinderplus.extra")]

    elif tool_id == "rgi":
        if flags.get("rgi.use_diamond"):
            e.append("--rgi_use_diamond")
        if flags.get("rgi.include_loose"):
            e.append("--rgi_include_loose")
        if flags.get("rgi.exclude_nudge"):
            e.append("--rgi_exclude_nudge")
        for k, flag in [("frequency", "--rgi_frequency"), ("category", "--rgi_category"),
                        ("cluster", "--rgi_cluster"), ("display", "--rgi_display")]:
            val(f"rgi.{k}", flag)
        if _o(opts, "rgi.extra"):
            e += _o(opts, "rgi.extra").split()

    elif tool_id == "mlst":
        val("mlst.db", "--mlst_db")
        disp = opts.get("mlst.scheme", "(auto/none)")
        if disp and disp != "(auto/none)":
            code = MLST_SCHEMES.get(disp)
            if code:
                e += ["--mlst_scheme", code]
        val("mlst.minid", "--mlst_minid")
        val("mlst.mincov", "--mlst_mincov")
        val("mlst.minscore", "--mlst_minscore")
        if flags.get("mlst.nopath"):
            e.append("--mlst_nopath")

    elif tool_id == "plasmidfinder":
        num("plasmidfinder.mincov")
        num("plasmidfinder.threshold")

    elif tool_id == "mashtree":
        val("mashtree.trunclength", "--mashtree_trunclength")
        val("mashtree.sortorder", "--mashtree_sortorder")
        val("mashtree.genomesize", "--mashtree_genomesize")
        val("mashtree.mindepth", "--mashtree_mindepth")
        val("mashtree.kmerlength", "--mashtree_kmerlength")
        val("mashtree.sketchsize", "--mashtree_sketchsize")
        if flags.get("mashtree.save_sketches"):
            e.append("--mashtree_save_sketches")

    elif tool_id == "pangenome":
        engine = opts.get("pangenome.engine", "Panaroo")
        if engine == "PIRATE":
            e.append("--use_pirate")
        elif engine == "Roary":
            e.append("--use_roary")
        val("pangenome.species", "--species")
        val("pangenome.accessions", "--accessions")
        if flags.get("pangenome.skip_recombination"):
            e.append("--skip_recombination")
        # IQ-TREE
        val("pangenome.iqtree_model", "--iqtree_model")
        val("pangenome.bb", "--iqtree_bb")
        val("pangenome.alrt", "--iqtree_alrt")
        if flags.get("pangenome.asr"):
            e.append("--iqtree_asr")
        val("pangenome.iqtree_opts", "--iqtree_opts")
        # Engine-specific
        if engine == "Panaroo":
            val("pangenome.panaroo_mode", "--panaroo_mode")
            num("pangenome.panaroo_threshold")
            num("pangenome.panaroo_core_threshold")
            if flags.get("pangenome.merge_paralogs"):
                e.append("--panaroo_merge_paralogs")
            val("pangenome.panaroo_opts", "--panaroo_opts")
        elif engine == "PIRATE":
            val("pangenome.pirate_steps", "--pirate_steps")
            if flags.get("pangenome.para_off"):
                e.append("--pirate_para_off")
        elif engine == "Roary":
            val("pangenome.roary_i", "--roary_i")
            val("pangenome.roary_cd", "--roary_cd")
            if flags.get("pangenome.use_prank"):
                e.append("--roary_use_prank")
        # Prokka
        val("pangenome.prokka_proteins", "--prokka_proteins")
        val("pangenome.prokka_opts", "--prokka_opts")
        # Scoary & SNP-dists
        val("pangenome.traits", "--scoary_traits")
        num("pangenome.p_value_cutoff")
        val("pangenome.correction", "--scoary_correction")
        val("pangenome.permute", "--scoary_permute")
        if flags.get("pangenome.snpdists_csv"):
            e.append("--snpdists_csv")

    # Null empty-default Path? params the user didn't provide on the CLI, so the
    # run doesn't abort with "Path string cannot be empty" on Nextflow 26.
    for p in TOOL_NULL_PATHS.get(tool_id, ()):
        if f"--{p}" not in e:
            jp[p] = None

    return e, jp
