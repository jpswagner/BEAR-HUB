"""Bactopia main pipeline — guided wizard (FOFN → cleaning → assembly → typing → extras → run)."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.components import wizard as wz
from bearhub.components import help as helpmod
from bearhub.data import catalog
from bearhub.state import BactopiaState as S

# "Typing & extras" was split into two steps: "Typing" and "Extras".
STEPS = ["Input & FOFN", "Read cleaning", "Assembler", "Typing", "Extras", "Run"]
GENOME_OPTS = ["(Select or Custom)"] + catalog.GENOME_SIZES + ["Custom"]
MLST_OPTS = catalog.MLST_DISPLAY


# ── small bound-field helpers (state: S.bopts / S.bflags) ──────────────────────
def opt_in(label, key, *, typ="text", width="160px", placeholder=""):
    return wz.labeled(
        label,
        rx.input(
            value=S.bopts[key],
            type=typ,
            size="2",
            width=width,
            placeholder=placeholder,
            on_change=lambda v: S.set_bopt(key, v),
        ),
    )


def opt_sel(label, key, options, width="200px"):
    return wz.labeled(
        label,
        rx.select(
            options,
            value=S.bopts[key],
            size="2",
            width=width,
            on_change=lambda v: S.set_bopt(key, v),
        ),
    )


def flag_cb(label, key):
    return rx.checkbox(
        label,
        checked=S.bflags[key],
        color_scheme="teal",
        size="3",
        on_change=lambda v: S.set_bflag(key, v),
    )


def _fastp_card(title, key, checks, inputs):
    body = [helpmod.section(title, key, size="2")]
    if checks:
        body.append(rx.flex(*checks, wrap="wrap", spacing="5", align="center"))
    if inputs:
        body.append(rx.flex(*inputs, wrap="wrap", spacing="3", align="end"))
    return rx.card(
        rx.vstack(*body, spacing="3", align="start", width="100%"),
        width="100%",
    )


def _qc_thresholds_card() -> rx.Component:
    """Collapsible card for Bactopia's Gather/QC gate thresholds.

    These define when a sample fails QC and is skipped. Leave blank to use
    Bactopia's defaults. Useful for low-yield or unusual-size isolates.
    """
    return rx.accordion.root(
        rx.accordion.item(
            header=rx.hstack(
                helpmod.section("QC thresholds (Gather)", "qc_thresholds", size="3"),
                rx.text(
                    "Leave blank to use Bactopia defaults",
                    size="1", color="var(--gray-9)", margin_left="8px",
                ),
                align="center",
            ),
            content=rx.vstack(
                rx.text(
                    "Samples that don't meet these minimums are skipped by Bactopia's "
                    "Gather module. Relax them for low-yield isolates.",
                    size="1", color="var(--gray-10)",
                ),
                rx.flex(
                    opt_in("--min_coverage",    "min_coverage",    typ="number", width="140px"),
                    opt_in("--min_basepairs",   "min_basepairs",   typ="number", width="150px"),
                    opt_in("--min_reads",       "min_reads",       typ="number", width="140px"),
                    opt_in("--min_genome_size", "min_genome_size", typ="number", width="150px"),
                    opt_in("--max_genome_size", "max_genome_size", typ="number", width="150px"),
                    wrap="wrap", spacing="3", align="end",
                ),
                rx.text(
                    "Bactopia defaults: coverage=10 · basepairs=2 241 820 · "
                    "reads=7 472 · min_genome=100 000 · max_genome=18 040 666",
                    size="1", color="var(--gray-9)",
                ),
                spacing="3", align="start", width="100%",
            ),
        ),
        collapsible=True,
        width="100%",
        variant="ghost",
    )


def _mode_is(*modes):
    cond = S.bopts["assembly_mode"] == modes[0]
    for m in modes[1:]:
        cond = cond | (S.bopts["assembly_mode"] == m)
    return cond


# ── Step 1: input & FOFN ───────────────────────────────────────────────────────
def _step_input():
    return rx.vstack(
        wz.labeled("Output directory (--outdir)", wz.dir_input(S, "outdir"), width="100%"),
        rx.card(
            helpmod.section("Generate FOFN", "fofn", size="3"),
            rx.text(
                "Scan a folder for FASTQ/FASTA; runtype (paired-end, single-end, ont, hybrid, "
                "assembly) is inferred per sample.",
                size="1",
                color="var(--gray-10)",
            ),
            wz.labeled(
                "Base folder with reads/assemblies",
                wz.dir_input(S, "base_dir", value=S.base_dir, with_rescan=False),
                width="100%",
            ),
            rx.flex(
                opt_in("species", "species", width="200px"),
                rx.vstack(
                    helpmod.field_label("genome_size", "genome_size"),
                    rx.select(
                        GENOME_OPTS,
                        value=S.bopts["genome_size"],
                        size="2",
                        width="200px",
                        on_change=lambda v: S.set_bopt("genome_size", v),
                    ),
                    spacing="1",
                    align="start",
                ),
                wrap="wrap",
                spacing="4",
                align="end",
            ),
            rx.flex(
                flag_cb("Include subfolders", "recursive"),
                flag_cb("Include assemblies (FASTA)", "include_assemblies"),
                flag_cb("Treat SE as ONT", "treat_se_as_ont"),
                flag_cb("Infer ONT by name", "infer_ont_by_name"),
                flag_cb("Merge multi-files (commas)", "merge_multi"),
                wrap="wrap",
                spacing="5",
                align="center",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("search", size=16),
                    "Scan & build FOFN",
                    on_click=S.scan_fofn,
                    color_scheme="teal",
                    size="2",
                ),
                rx.cond(
                    S.fofn_built,
                    rx.badge(S.fofn_summary, color_scheme="green", size="2"),
                    rx.cond(
                        S.fofn_summary != "",
                        rx.badge(S.fofn_summary, color_scheme="red", size="2"),
                    ),
                ),
                spacing="3",
                align="center",
                wrap="wrap",
            ),
            rx.cond(
                S.fofn_path != "",
                rx.text(S.fofn_path, font_family="monospace", size="1", color="var(--gray-9)"),
            ),
            rx.cond(
                S.fofn_issues.length() > 0,
                rx.vstack(
                    rx.text("Issues:", size="1", weight="bold", color="var(--amber-11)"),
                    rx.foreach(
                        S.fofn_issues,
                        lambda m: rx.text(f"• {m}", size="1", color="var(--amber-11)"),
                    ),
                    spacing="0",
                    align="start",
                ),
            ),
            width="100%",
            spacing="3",
        ),
        wz.dir_picker(S),
        _qc_thresholds_card(),
        wz.nav_buttons(S.prev_step, S.next_step, first=True),
        spacing="6",
        width="100%",
        align="start",
    )


# ── Step 2: read cleaning (fastp) ──────────────────────────────────────────────
def _fastp_simple():
    return rx.vstack(
        _fastp_card(
            "Sliding window / cutting",
            "fastp_window",
            [
                flag_cb("Cut tail (-3)", "fastp_dash3"),
                flag_cb("Cut front (-5)", "fastp_5prime"),
                flag_cb("Cut right (-r)", "fastp_cut_right"),
            ],
            [
                opt_in("Mean quality (-M)", "fastp_M", typ="number", width="150px"),
                opt_in("Window size (-W)", "fastp_W", typ="number", width="150px"),
            ],
        ),
        _fastp_card(
            "Quality & length filters",
            "fastp_filters",
            [
                flag_cb("Enable -q", "fastp_q_enable"),
                flag_cb("Enable -l", "fastp_l_enable"),
            ],
            [
                opt_in("-q value", "fastp_q", typ="number", width="130px"),
                opt_in("-l value", "fastp_l", typ="number", width="130px"),
                opt_in("Max N (-n)", "fastp_n", typ="number", width="130px"),
                opt_in("Max % unqual (-u)", "fastp_u", typ="number", width="150px"),
            ],
        ),
        _fastp_card(
            "Adapters",
            "fastp_adapters",
            [flag_cb("Detect adapters (PE)", "fastp_detect_adapter_pe")],
            [
                opt_in("Adapter R1 (-a)", "fastp_adapter_r1", width="240px"),
                opt_in("Adapter R2", "fastp_adapter_r2", width="240px"),
            ],
        ),
        _fastp_card(
            "Additional processing",
            "fastp_processing",
            [
                flag_cb("Dedup (-D)", "fastp_dedup"),
                flag_cb("Correction (-c)", "fastp_correction"),
                flag_cb("Trim polyG (-g)", "fastp_poly_g"),
                flag_cb("Trim polyX (-x)", "fastp_poly_x"),
                flag_cb("Overrep (-p)", "fastp_overrep"),
                flag_cb("UMI (-U)", "fastp_umi"),
            ],
            None,
        ),
        rx.cond(
            S.bflags["fastp_umi"],
            rx.card(
                rx.flex(
                    opt_sel(
                        "UMI location",
                        "fastp_umi_loc",
                        ["index1", "index2", "read1", "read2", "per_index", "per_read"],
                        width="170px",
                    ),
                    opt_in("UMI length", "fastp_umi_len", typ="number", width="130px"),
                    wrap="wrap",
                    spacing="4",
                    align="end",
                ),
                width="100%",
            ),
        ),
        wz.labeled(
            "Advanced extra (append)",
            rx.input(
                value=S.bopts["fastp_extra"],
                size="2",
                width="100%",
                on_change=lambda v: S.set_bopt("fastp_extra", v),
            ),
            width="100%",
        ),
        spacing="6",
        width="100%",
        align="start",
    )


def _step_cleaning():
    return rx.vstack(
        rx.hstack(
            helpmod.section("Read cleaning (fastp)", "fastp_window", size="4"),
            rx.spacer(),
            opt_sel("Mode", "fastp_mode", ["Simple", "Advanced"], width="150px"),
            width="100%",
            align="center",
        ),
        rx.text(
            "Builds the --fastp_opts string. Default: -3 -M 20 -W 5.",
            size="2",
            color="var(--gray-10)",
        ),
        rx.cond(
            S.bopts["fastp_mode"] == "Simple",
            _fastp_simple(),
            wz.labeled(
                "Full fastp line (advanced)",
                rx.input(
                    value=S.bopts["fastp_raw"],
                    size="3",
                    width="100%",
                    on_change=lambda v: S.set_bopt("fastp_raw", v),
                ),
                width="100%",
            ),
        ),
        wz.nav_buttons(S.prev_step, S.next_step),
        spacing="6",
        width="100%",
        align="start",
    )


# ── Step 3: assembler ──────────────────────────────────────────────────────────
def _step_assembler():
    return rx.vstack(
        rx.hstack(
            helpmod.field_label("Assembly mode", "assembly_mode"),
            rx.select(
                [
                    "Illumina PE (Shovill)",
                    "Illumina PE (Unicycler)",
                    "Illumina SE (Shovill-SE)",
                    "ONT (Dragonflye)",
                    "Hybrid (Unicycler --hybrid)",
                    "Hybrid (Dragonflye --short_polish)",
                ],
                value=S.bopts["assembly_mode"],
                width="340px",
                size="2",
                on_change=lambda v: S.set_bopt("assembly_mode", v),
            ),
            spacing="2",
            align="end",
        ),
        rx.cond(
            _mode_is("Illumina PE (Shovill)", "Illumina SE (Shovill-SE)"),
            rx.card(
                helpmod.section("Shovill", "shovill", size="3"),
                rx.flex(
                    opt_sel("Assembler", "shovill_assembler",
                            ["skesa", "spades", "velvet", "megahit"], width="150px"),
                    opt_in("--shovill_opts", "shovill_opts", width="200px"),
                    opt_in("--shovill_kmers", "shovill_kmers", width="160px", placeholder="21,33,55"),
                    flag_cb("--trim", "trim"),
                    flag_cb("--no_stitch", "no_stitch"),
                    flag_cb("--no_corr", "no_corr"),
                    wrap="wrap", spacing="3", align="end",
                ),
                width="100%", style={"borderColor": "var(--teal-6)"},
            ),
        ),
        rx.cond(
            _mode_is("ONT (Dragonflye)", "Hybrid (Dragonflye --short_polish)"),
            rx.card(
                helpmod.section("Dragonflye", "dragonflye", size="3"),
                rx.flex(
                    opt_sel("Assembler", "dragonflye_assembler",
                            ["flye", "miniasm", "raven"], width="150px"),
                    opt_in("--dragonflye_opts", "dragonflye_opts", width="200px"),
                    flag_cb("--nanohq", "nanohq"),
                    flag_cb("--no_miniasm", "no_miniasm"),
                    wrap="wrap", spacing="3", align="end",
                ),
                width="100%", style={"borderColor": "var(--teal-6)"},
            ),
        ),
        rx.cond(
            _mode_is("Illumina PE (Unicycler)", "Hybrid (Unicycler --hybrid)"),
            rx.card(
                helpmod.section("Unicycler", "unicycler", size="3"),
                rx.flex(
                    opt_sel("Mode", "unicycler_mode",
                            ["conservative", "normal", "bold"], width="150px"),
                    opt_in("min_fasta_length", "unicycler_min_len", typ="number", width="150px"),
                    opt_in("Extra (append)", "unicycler_extra", width="200px"),
                    wrap="wrap", spacing="3", align="end",
                ),
                width="100%", style={"borderColor": "var(--teal-6)"},
            ),
        ),
        rx.card(
            rx.vstack(
                helpmod.section("General assembly", "general_assembly", size="3"),
                rx.flex(
                    flag_cb("--reassemble", "reassemble"),
                    flag_cb("--no_rotate", "no_rotate"),
                    flag_cb("--skip_qc_plot", "skip_qc_plot"),
                    wrap="wrap", spacing="5", align="center",
                ),
                rx.flex(
                    opt_in("Min contig len", "min_contig_len", typ="number", width="150px"),
                    opt_in("Min contig cov", "min_contig_cov", typ="number", width="150px"),
                    wrap="wrap", spacing="4", align="end",
                ),
                spacing="3", align="start", width="100%",
            ),
            width="100%",
        ),
        helpmod.section("Polishing", "polishing", size="3"),
        flag_cb("--no_polish (skip all polishing)", "no_polish"),
        rx.cond(
            _mode_is("Hybrid (Unicycler --hybrid)", "Hybrid (Dragonflye --short_polish)"),
            rx.flex(
                opt_in("Polypolish rounds", "polypolish_rounds", typ="number", width="150px"),
                opt_in("Pilon rounds", "pilon_rounds", typ="number", width="130px"),
                wrap="wrap", spacing="3", align="end",
            ),
        ),
        rx.cond(
            _mode_is("ONT (Dragonflye)"),
            rx.flex(
                opt_in("Racon rounds", "racon_rounds", typ="number", width="130px"),
                opt_in("Medaka rounds", "medaka_rounds", typ="number", width="130px"),
                opt_in("Medaka model", "medaka_model", width="160px"),
                wrap="wrap", spacing="3", align="end",
            ),
        ),
        wz.nav_buttons(S.prev_step, S.next_step),
        spacing="6",
        width="100%",
        align="start",
    )


# ── Step 4: typing & annotation (main-pipeline prefixed params) ────────────────
def _annotation_card():
    return rx.card(
        rx.vstack(
            rx.hstack(
                helpmod.field_label("Annotator", "annotator"),
                rx.select(
                    ["Prokka", "Bakta"],
                    value=S.bopts["annotator"],
                    size="2", width="150px",
                    on_change=lambda v: S.set_bopt("annotator", v),
                ),
                spacing="2", align="end",
            ),
            # Prokka fields
            rx.cond(
                S.bopts["annotator"] == "Prokka",
                rx.flex(
                    opt_in("--prokka_proteins (FASTA)", "prokka_proteins", width="240px"),
                    opt_in("--prokka_opts", "prokka_opts", width="200px"),
                    flag_cb("--prokka_compliant", "prokka_compliant"),
                    wrap="wrap", spacing="3", align="end",
                ),
            ),
            # Bakta fields (requires DB)
            rx.cond(
                S.bopts["annotator"] == "Bakta",
                rx.vstack(
                    rx.callout(
                        "Bakta requires a database. Set --bakta_db to the path of a "
                        "downloaded Bakta DB, or it will be skipped.",
                        icon="triangle_alert", color_scheme="amber", size="1",
                    ),
                    rx.flex(
                        opt_in("--bakta_db (required)", "bakta_db", width="280px"),
                        opt_in("--bakta_opts", "bakta_opts", width="200px"),
                        wrap="wrap", spacing="3", align="end",
                    ),
                    spacing="2", align="start", width="100%",
                ),
            ),
            spacing="3", align="start", width="100%",
        ),
        width="100%",
    )


def _step_typing():
    return rx.vstack(
        rx.text(
            "Annotation & typing run as part of the main pipeline. Leave fields "
            "blank to use Bactopia's defaults.",
            size="2", color="var(--gray-10)",
        ),
        # Annotation
        helpmod.section("Annotation", "annotator", size="4"),
        _annotation_card(),
        # AMRFinderPlus
        rx.card(
            rx.vstack(
                helpmod.section("AMRFinderPlus", "amrfinder", size="3"),
                rx.flex(
                    opt_in("--organism", "amrfinderplus_organism", width="220px",
                           placeholder="e.g. Streptococcus_pyogenes"),
                    flag_cb("--noplus", "amrfinderplus_noplus"),
                    wrap="wrap", spacing="3", align="end",
                ),
                rx.text(
                    "ident_min / coverage_min run with Bactopia defaults here "
                    "(configurable on the Bactopia Tools page).",
                    size="1", color="var(--gray-9)",
                ),
                spacing="3", align="start", width="100%",
            ),
            width="100%",
        ),
        # MLST
        rx.card(
            rx.vstack(
                helpmod.section("MLST", "mlst", size="3"),
                rx.flex(
                    opt_sel("Scheme", "mlst_scheme", MLST_OPTS, width="220px"),
                    opt_in("--minid", "mlst_minid", typ="number", width="120px"),
                    opt_in("--mincov", "mlst_mincov", typ="number", width="120px"),
                    opt_in("--minscore", "mlst_minscore", typ="number", width="120px"),
                    flag_cb("--nopath", "mlst_nopath"),
                    wrap="wrap", spacing="3", align="end",
                ),
                spacing="3", align="start", width="100%",
            ),
            width="100%",
        ),
        # Datasets
        opt_in("datasets/ (optional path)", "datasets", width="100%"),
        wz.nav_buttons(S.prev_step, S.next_step),
        spacing="6",
        width="100%",
        align="start",
    )


# ── Step 5: extras (execution params, Nextflow reports, raw extras) ────────────
def _step_extras():
    return rx.vstack(
        rx.text(
            "Execution resources, Nextflow reports, and extra parameters.",
            size="2", color="var(--gray-10)",
        ),
        wz.general_params(S),
        rx.flex(
            flag_cb("-with-report", "with_report"),
            flag_cb("-with-timeline", "with_timeline"),
            flag_cb("-with-trace", "with_trace"),
            wrap="wrap", spacing="5", align="center",
        ),
        opt_in("Extra parameters (raw line)", "extra_params", width="100%"),
        wz.nav_buttons(S.prev_step, S.next_step, next_label="Review & run"),
        spacing="6",
        width="100%",
        align="start",
    )


# ── Step 6: run ────────────────────────────────────────────────────────────────
def _step_run():
    return rx.vstack(
        rx.heading("Command preview", size="3"),
        rx.code_block(S.preview, language="bash", width="100%", wrap_long_lines=True),
        rx.cond(
            ~S.fofn_built,
            rx.callout(
                "Generate the FOFN in step 1 before running.",
                icon="triangle_alert", color_scheme="amber", size="1",
            ),
        ),
        wz.run_panel(S),
        wz.merged_panel(S),
        wz.nav_buttons(S.prev_step, S.next_step, next_label="Back", next_handler=S.prev_step),
        spacing="6",
        width="100%",
        align="start",
    )


def bactopia_page():
    return shell(
        wz.hero("dna", "Bactopia",
                "Main pipeline: QC, assembly, annotation and typing from raw reads."),
        wz.step_indicator(STEPS, S.step, S.goto),
        rx.divider(),
        rx.match(
            S.step,
            (0, _step_input()),
            (1, _step_cleaning()),
            (2, _step_assembler()),
            (3, _step_typing()),
            (4, _step_extras()),
            (5, _step_run()),
            _step_input(),
        ),
        active="/bactopia",
    )
