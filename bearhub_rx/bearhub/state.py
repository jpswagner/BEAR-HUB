"""
Reflex state for BEAR-HUB.

A shared `WizardMixin` carries the bits every guided page needs (step nav,
output directory + directory-picker, sample selection, general Nextflow params,
and the live runner log/status). Concrete page states add their tool selection
and a background `run` event that builds the command and streams output.
"""
from __future__ import annotations

import os
import pathlib
import shlex
from shlex import quote as _q, split as _split

import reflex as rx

from bearhub.core import bactopia, runner, system
from bearhub.data import catalog
from bearhub.core import fofn as _fofn

_pathlib = pathlib


def _to_int(v) -> int:
    try:
        return int(float(str(v))) if v else 0
    except (TypeError, ValueError):
        return 0


# ── WizardMixin ────────────────────────────────────────────────────────────────

class WizardMixin(rx.State, mixin=True):
    step: int = 0
    outdir: str = ""
    samples: list[str] = []
    selected: list[str] = []
    profile: str = "docker"
    threads: int = 0
    memory: int = 0
    resume: bool = True
    extra: str = ""
    picker_open: bool = False
    picker_cur: str = ""
    picker_dirs: list[str] = []
    picker_target: str = "outdir"
    log: list[str] = []
    status: str = "idle"
    running: bool = False
    merged: list[str] = []
    merged_dir: str = ""

    def next_step(self):
        self.step += 1

    def prev_step(self):
        if self.step > 0:
            self.step -= 1

    def goto(self, i: int):
        self.step = i

    def init_outdir(self):
        # on_load handler: always start the wizard at step 1 so reloading or
        # re-entering the page from the sidebar gives a clean, predictable start.
        self.step = 0
        if not self.outdir:
            self.outdir = bactopia.guess_root_default()
        self.scan()

    def scan(self):
        d = bactopia.safe_dir(self.outdir)
        self.outdir = d
        self.samples = bactopia.discover_samples(d)
        self.selected = list(self.samples)

    def toggle_sample(self, name: str):
        if name in self.selected:
            self.selected = [s for s in self.selected if s != name]
        else:
            self.selected = self.selected + [name]

    def select_all_samples(self):
        self.selected = list(self.samples)

    def clear_samples(self):
        self.selected = []

    def set_profile(self, v: str):
        self.profile = v

    def set_threads(self, v):
        if isinstance(v, (list, tuple)):
            v = v[0] if v else 0
        self.threads = _to_int(v)

    def set_memory(self, v):
        if isinstance(v, (list, tuple)):
            v = v[0] if v else 0
        self.memory = _to_int(v)

    def set_resume(self, v):
        self.resume = bool(v)

    def set_extra(self, v: str):
        self.extra = v

    def open_picker_for(self, target: str):
        self.picker_target = target
        if not getattr(self, target, ""):
            self.picker_cur = bactopia.safe_dir(self.outdir)
        else:
            self.picker_cur = bactopia.safe_dir(getattr(self, target))
        self.picker_dirs = bactopia.list_subdirs(self.picker_cur)
        self.picker_open = True

    def open_picker(self):
        self.open_picker_for("outdir")

    def set_picker_open(self, v):
        self.picker_open = bool(v)

    def picker_enter(self, name: str):
        self.picker_cur = bactopia.safe_dir(os.path.join(self.picker_cur, name))
        self.picker_dirs = bactopia.list_subdirs(self.picker_cur)

    def picker_up(self):
        self.picker_cur = bactopia.safe_dir(os.path.dirname(self.picker_cur))
        self.picker_dirs = bactopia.list_subdirs(self.picker_cur)

    def picker_home(self):
        self.picker_cur = bactopia.safe_dir(os.path.expanduser("~"))
        self.picker_dirs = bactopia.list_subdirs(self.picker_cur)

    def picker_select(self):
        setattr(self, self.picker_target, self.picker_cur)
        self.picker_open = False
        if self.picker_target == "outdir":
            self.samples = bactopia.discover_samples(self.outdir)
            self.selected = list(self.samples)

    def refresh_merged(self):
        self.merged = []
        self.merged_dir = ""
        out = bactopia.safe_dir(self.outdir)
        runs = _pathlib.Path(out) / "bactopia-runs"
        if not runs.is_dir():
            return
        subs = sorted([p for p in runs.glob("*") if p.is_dir()])
        if not subs:
            return
        mr = subs[-1] / "merged-results"
        if mr.is_dir():
            self.merged_dir = str(mr)
            self.merged = [f.name for f in sorted(mr.glob("*.tsv"))]

    @rx.var
    def n_selected(self) -> int:
        return len(self.selected)

    @rx.var
    def n_samples(self) -> int:
        return len(self.samples)

    @rx.var
    def has_samples(self) -> bool:
        return len(self.samples) > 0

    @rx.var
    def status_label(self) -> str:
        return {"running": "Running…", "success": "Finished successfully",
                "failed": "Run failed — check the log", "stopped": "Stopped by user",
                "idle": ""}.get(self.status, self.status)

    @rx.var
    def status_color(self) -> str:
        return {"running": "blue", "success": "green", "failed": "red",
                "stopped": "amber", "idle": "gray"}.get(self.status, "gray")

    @rx.var
    def log_text(self) -> str:
        return "\n".join(self.log)


# ── ToolsState ─────────────────────────────────────────────────────────────────

class ToolsState(WizardMixin, rx.State):
    picks: dict[str, bool] = {}
    opts: dict[str, str] = dict(catalog.DEFAULT_OPTS)
    flags: dict[str, bool] = dict(catalog.DEFAULT_FLAGS)

    def toggle(self, tid: str):
        self.picks[tid] = not self.picks.get(tid, False)

    def set_opt(self, key: str, value: str):
        self.opts[key] = str(value)

    def set_flag(self, key: str, value: bool):
        self.flags[key] = bool(value)

    @rx.var
    def picked_ids(self) -> list[str]:
        return [t for t, on in self.picks.items() if on]

    @rx.var
    def n_picked(self) -> int:
        return len(self.picked_ids)

    @rx.var
    def picked_detailed(self) -> list[str]:
        return [t for t in self.picked_ids if t in catalog.DETAILED]

    @rx.var
    def preview(self) -> str:
        lines = []
        for tid in self.picked_ids:
            args = catalog.build_tool_args(tid, self.opts, self.flags)
            lines.append(runner.nextflow_wf_cmd(
                tid, "<outdir>", "<include-file>",
                self.profile, int(self.threads or 0), int(self.memory or 0),
                bool(self.resume), args, self.extra,
            ))
        return "\n\n".join(lines) if lines else "# select at least one tool"

    def _build(self):
        if not system.nextflow_available():
            return ("", "Nextflow not found (PATH / BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN).")
        outdir = bactopia.safe_dir(self.outdir)
        samples = list(self.selected) or list(self.samples)
        if not samples:
            return ("", "Select at least one sample.")
        picked = self.picked_ids
        if not picked:
            return ("", "Select at least one tool.")
        inc = _fofn.write_include_file(outdir, samples)
        labelled = []
        for tid in picked:
            args = catalog.build_tool_args(tid, self.opts, self.flags)
            cmd = runner.nextflow_wf_cmd(
                tid, outdir, inc, self.profile,
                int(self.threads or 0), int(self.memory or 0),
                bool(self.resume), args, self.extra,
            )
            labelled.append((f"[Bactopia Tool] {tid}", cmd))
        return (runner.join_subcommands(labelled), "")

    @rx.event(background=True)
    async def run(self):
        async with self:
            cmd, err = self._build()
        if err:
            yield rx.toast.error(err)
            return
        async for _ in runner.stream(
            self, cmd, "tools",
            work_dir=bactopia.safe_dir(self.outdir),
            page="Bactopia Tools",
            n_samples=self.n_selected,
        ):
            yield _
        async with self:
            self.refresh_merged()

    @rx.event(background=True)
    async def stop_run(self):
        await runner.stop("tools")
        async with self:
            self.status = "stopped"
            self.running = False


# ── MerlinState ────────────────────────────────────────────────────────────────

class MerlinState(WizardMixin, rx.State):
    picks: dict[str, bool] = {wf: False for wf in catalog.MERLIN_WF_IDS}

    def toggle(self, wf: str):
        self.picks[wf] = not self.picks.get(wf, False)

    @rx.var
    def picked_ids(self) -> list[str]:
        return [w for w, on in self.picks.items() if on]

    @rx.var
    def n_picked(self) -> int:
        return len(self.picked_ids)

    @rx.var
    def preview(self) -> str:
        lines = []
        for wf in self.picked_ids:
            lines.append(runner.nextflow_wf_cmd(
                wf, "<outdir>", "<include-file>",
                self.profile, int(self.threads or 0), int(self.memory or 0),
                bool(self.resume), [], self.extra,
            ))
        return "\n\n".join(lines) if lines else "# select at least one species tool"

    def _build(self):
        if not system.nextflow_available():
            return ("", "Nextflow not found (PATH / BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN).")
        outdir = bactopia.safe_dir(self.outdir)
        samples = list(self.selected) or list(self.samples)
        if not samples:
            return ("", "Select at least one sample.")
        picked = self.picked_ids
        if not picked:
            return ("", "Select at least one species-specific tool.")
        inc = _fofn.write_include_file(outdir, samples)
        labelled = []
        for wf in picked:
            cmd = runner.nextflow_wf_cmd(
                wf, outdir, inc, self.profile,
                int(self.threads or 0), int(self.memory or 0),
                bool(self.resume), [], self.extra,
            )
            labelled.append((f"[Bactopia Species] {wf}", cmd))
        return (runner.join_subcommands(labelled), "")

    @rx.event(background=True)
    async def run(self):
        async with self:
            cmd, err = self._build()
        if err:
            yield rx.toast.error(err)
            return
        async for _ in runner.stream(
            self, cmd, "merlin",
            work_dir=bactopia.safe_dir(self.outdir),
            page="MERLIN",
            n_samples=self.n_selected,
        ):
            yield _
        async with self:
            self.refresh_merged()

    @rx.event(background=True)
    async def stop_run(self):
        await runner.stop("merlin")
        async with self:
            self.status = "stopped"
            self.running = False


# ── BactopiaState defaults ─────────────────────────────────────────────────────
# BEAR-HUB intentionally overrides some Bactopia defaults. Keep in sync with
# docs/bactopia/PARAM_AUDIT.md §"Preserve the programmed defaults".

_ASSEMBLY_MODES = [
    "Illumina PE (Shovill)",
    "Illumina PE (Unicycler)",
    "Illumina SE (Shovill-SE)",
    "ONT (Dragonflye)",
    "Hybrid (Unicycler --hybrid)",
    "Hybrid (Dragonflye --short_polish)",
]
_MODE_IMPLIED = {
    "Illumina PE (Shovill)":              (False, None),
    "Illumina PE (Unicycler)":            (True,  None),
    "Illumina SE (Shovill-SE)":           (False, None),
    "ONT (Dragonflye)":                   (False, None),
    # Hybrid Unicycler: use_unicycler=True so Bactopia picks Unicycler as assembler
    "Hybrid (Unicycler --hybrid)":        (True,  None),
    "Hybrid (Dragonflye --short_polish)": (False, None),
}

DEFAULT_BOPTS: dict[str, str] = {
    # FOFN
    "species":        "UNKNOWN_SPECIES",
    "genome_size":    "(Select or Custom)",
    "datasets":       "",
    # QC gate thresholds (Gather/QC module) — Bactopia native defaults.
    # These define when a sample fails QC and is skipped. Users with low-yield
    # isolates frequently need to relax them. Empty string = use Bactopia default.
    "min_coverage":    "",
    "min_basepairs":   "",
    "min_reads":       "",
    "min_genome_size": "",
    "max_genome_size": "",
    # fastp
    "fastp_mode":     "Simple",
    "fastp_M":        "20",
    "fastp_W":        "5",
    "fastp_q":        "20",
    "fastp_l":        "15",
    "fastp_n":        "0",
    "fastp_u":        "0",
    "fastp_adapter_r1": "",
    "fastp_adapter_r2": "",
    "fastp_umi_loc":  "index1",
    "fastp_umi_len":  "0",
    "fastp_extra":    "",
    "fastp_raw":      "-3 -M 20 -W 5",
    # assembler
    "assembly_mode":        "Illumina PE (Unicycler)",
    "shovill_assembler":    "skesa",
    "shovill_opts":         "",
    "shovill_kmers":        "",
    "dragonflye_assembler": "flye",
    "dragonflye_opts":      "",
    # unicycler — mode passed as --unicycler_mode (valid Bactopia param)
    "unicycler_mode":       "normal",
    # min_contig_len = 1000 (BEAR-HUB default; Bactopia default is 500).
    # This also drives Unicycler --min_fasta_length via Bactopia's assembler subworkflow.
    "min_contig_len":       "1000",
    "min_contig_cov":       "10",
    # polishing
    "polypolish_rounds":    "1",
    "pilon_rounds":         "0",
    "racon_rounds":         "1",
    "medaka_rounds":        "0",
    "medaka_model":         "",
    # Typing — main-pipeline params use the *prefixed* names (amrfinderplus_*, mlst_*).
    # Blank = use Bactopia defaults; only emitted when the user sets a value.
    # NOTE: AMRFinder ident_min/coverage_min are FLOAT params; nf-schema rejects
    # floats passed from the CLI ("string but should be number"). Tune those via
    # --amrfinderplus_opts or the Bactopia Tools page instead.
    "amrfinderplus_organism":     "",
    "mlst_scheme":                "(auto/none)",
    "mlst_minid":                 "",
    "mlst_mincov":                "",
    "mlst_minscore":              "",
    # Annotation — Prokka (default, no DB) or Bakta (requires bakta_db)
    "annotator":                  "Prokka",
    "prokka_proteins":            "",
    "prokka_opts":                "",
    "bakta_db":                   "",
    "bakta_opts":                 "",
    # extras
    "extra_params":         "",
}

DEFAULT_BFLAGS: dict[str, bool] = {
    # FOFN
    "recursive":              True,
    "include_assemblies":     True,
    "treat_se_as_ont":        False,
    "infer_ont_by_name":      True,
    "merge_multi":            True,
    # fastp
    "fastp_dash3":            True,
    "fastp_5prime":           False,
    "fastp_cut_right":        False,
    "fastp_q_enable":         False,
    "fastp_l_enable":         False,
    "fastp_dedup":            False,
    "fastp_correction":       False,
    "fastp_poly_g":           False,
    "fastp_poly_x":           False,
    "fastp_overrep":          False,
    "fastp_umi":              False,
    "fastp_detect_adapter_pe": False,
    # assembly
    "trim":        False,
    "no_stitch":   False,
    "no_corr":     False,
    "nanohq":      False,
    "no_miniasm":  False,
    "reassemble":  False,
    "no_rotate":   False,
    # skip_qc_plot is the UI key; the correct Bactopia param is --skip_qc_plots (plural).
    # _assembler_flags emits --skip_qc_plots when this is True.
    "skip_qc_plot": True,
    "no_polish":   False,
    # Typing / annotation
    "amrfinderplus_noplus":  False,   # --amrfinderplus_noplus (disable --plus)
    "mlst_nopath":           False,   # --mlst_nopath
    "prokka_compliant":      False,   # --prokka_compliant
    # Nextflow reports
    "with_report":   True,
    "with_timeline": True,
    "with_trace":    True,
}


# ── Command builders (pure functions — no rx state) ────────────────────────────

def _numt(v: str) -> bool:
    """True if v parses as a non-zero number."""
    try:
        return float(v) != 0
    except (TypeError, ValueError):
        return bool(str(v).strip())


def _fastp_opts(o: dict, f: dict) -> str:
    """Build the --fastp_opts string from bopts/bflags."""
    mode = o.get("fastp_mode", "Simple")
    if mode.startswith("Advanced"):
        return o.get("fastp_raw", "").strip()
    p: list[str] = []
    if f.get("fastp_dash3"):    p.append("-3")
    if f.get("fastp_5prime"):   p.append("-5")
    if f.get("fastp_cut_right"): p.append("-r")
    p += ["-M", o.get("fastp_M", "20")]
    p += ["-W", o.get("fastp_W", "5")]
    if f.get("fastp_q_enable"):
        p += ["-q", o.get("fastp_q", "20")]
    if f.get("fastp_l_enable"):
        p += ["-l", o.get("fastp_l", "15")]
    if _numt(o.get("fastp_n", "0")):
        p += ["-n", o["fastp_n"]]
    if _numt(o.get("fastp_u", "0")):
        p += ["-u", o["fastp_u"]]
    if f.get("fastp_dedup"):       p.append("-D")
    if f.get("fastp_correction"):  p.append("-c")
    if f.get("fastp_poly_g"):      p.append("-g")
    if f.get("fastp_poly_x"):      p.append("-x")
    if f.get("fastp_detect_adapter_pe"):
        p.append("--detect_adapter_for_pe")
    r1 = o.get("fastp_adapter_r1", "").strip()
    r2 = o.get("fastp_adapter_r2", "").strip()
    if r1: p.append(f"-a {_q(r1)}")
    if r2: p.append(f"--adapter_sequence_r2 {_q(r2)}")
    if f.get("fastp_overrep"): p.append("-p")
    if f.get("fastp_umi"):
        p.append("-U")
        loc = o.get("fastp_umi_loc", "")
        if loc: p.append(f"--umi_loc={loc}")
        ulen = o.get("fastp_umi_len", "0")
        if _numt(ulen): p.append(f"--umi_len={ulen}")
    extra = o.get("fastp_extra", "").strip()
    if extra: p.append(extra)
    return " ".join(p)


def _assembler_flags(o: dict, f: dict) -> list[str]:
    """
    Build the per-assembler CLI flags for the main Bactopia pipeline.

    PARAMETER AUDIT:
    - unicycler_opts  → INVALID (undeclared in Bactopia). Removed.
      Use --unicycler_mode (declared) for the bridging mode.
    - skip_qc_plot    → INVALID. Correct param is --skip_qc_plots (plural).
    - --min_contig_len → always emitted at BEAR-HUB's 1000 default (Bactopia
      default is 500); also drives Unicycler --min_fasta_length internally.
    - --short_polish  → NOT a CLI param. Set via FOFN `runtype` column instead
      (build_fofn receives `hybrid_strategy` and writes the correct runtype per row).
    - --hybrid        → only valid for single-sample (--sample/--r1/--r2/--se).
      With FOFN (--samples) the assembly mode is per-row in `runtype`; emitting
      --hybrid as a global flag is redundant and confusing. Removed.
    Both are now handled exclusively in core/fofn.py build_fofn().
    """
    import importlib
    cat = importlib.import_module("bearhub.data.catalog")
    af: list[str] = []
    mode = o.get("assembly_mode", "Illumina PE (Unicycler)")
    use_uni, _hyb = _MODE_IMPLIED.get(mode, (False, None))
    if use_uni:
        af.append("--use_unicycler")
    # --unicycler_mode (valid Bactopia param; default 'normal')
    if mode in ("Illumina PE (Unicycler)", "Hybrid (Unicycler --hybrid)"):
        uni_mode = o.get("unicycler_mode", "normal")
        if uni_mode:
            af += ["--unicycler_mode", uni_mode]
    # --hybrid / --short_polish intentionally omitted: handled via FOFN runtype
    # Shovill
    sa = o.get("shovill_assembler", "skesa")
    if sa and sa != "skesa":
        af += ["--shovill_assembler", sa]
    da = o.get("dragonflye_assembler", "flye")
    if da and da != "flye":
        af += ["--dragonflye_assembler", da]
    for key, flag in [("shovill_opts", "--shovill_opts"),
                      ("shovill_kmers", "--shovill_kmers"),
                      ("dragonflye_opts", "--dragonflye_opts")]:
        v = o.get(key, "").strip()
        if v:
            af += [flag, v]
    # Boolean assembly flags
    for key in ("trim", "no_stitch", "no_corr", "nanohq", "no_miniasm",
                "reassemble", "no_rotate"):
        if f.get(key):
            af.append(f"--{key}")
    # skip_qc_plots (plural) — Bactopia's declared param name
    if f.get("skip_qc_plot"):
        af.append("--skip_qc_plots")
    if f.get("no_polish"):
        af.append("--no_polish")
    # min_contig_len: BEAR-HUB default 1000 (Bactopia default 500). Always emit.
    mcl = o.get("min_contig_len", "1000")
    af += ["--min_contig_len", str(mcl)]
    # min_contig_cov: BEAR-HUB default 10 (Bactopia default 2). Only emit if ≠ default.
    mcc = o.get("min_contig_cov", "10")
    if mcc and mcc != "2":
        af += ["--min_contig_cov", str(mcc)]
    # NOTE: AMRFinder+ (--ident_min/--coverage_min/--organism) and MLST
    # (--scheme/--minscore/--nopath) are NOT declared in the MAIN Bactopia
    # pipeline — they are Bactopia *Tools* params (--wf amrfinderplus / --wf mlst).
    # In the main pipeline these tools run with defaults. Passing them here
    # makes Nextflow abort ("Parameter X is not declared"). To configure them,
    # use the Bactopia Tools page. See docs/bactopia/PARAM_AUDIT.md.
    # Polishing
    for key, flag, default in [
        ("polypolish_rounds", "--polypolish_rounds", "1"),
        ("pilon_rounds", "--pilon_rounds", "0"),
        ("racon_rounds", "--racon_rounds", "1"),
        ("medaka_rounds", "--medaka_rounds", "0"),
    ]:
        v = o.get(key, default)
        if v and v != default:
            af += [flag, str(v)]
    mm = o.get("medaka_model", "").strip()
    if mm:
        af += ["--medaka_model", mm]
    return af


def _typing_flags(o: dict, f: dict) -> list[str]:
    """
    Main-pipeline typing & annotation flags. These use the PREFIXED names
    (amrfinderplus_*, mlst_*, prokka_*, bakta_*) — the unprefixed forms are
    Bactopia Tools params and are rejected by the main pipeline.
    All blank by default → Bactopia defaults; emitted only when the user sets them.
    """
    import importlib
    cat = importlib.import_module("bearhub.data.catalog")
    tf: list[str] = []

    # AMRFinder+ — only organism is safely configurable in the main pipeline.
    # ident_min/coverage_min are floats (rejected by nf-schema from the CLI) AND
    # are already passed internally by Bactopia (so --amrfinderplus_opts can't
    # re-pass them — "used more than once"). They run with defaults here.
    org = o.get("amrfinderplus_organism", "").strip()
    if org:
        tf += ["--amrfinderplus_organism", org]
    if f.get("amrfinderplus_noplus"):
        tf.append("--amrfinderplus_noplus")

    # MLST
    scheme_disp = o.get("mlst_scheme", "(auto/none)")
    if scheme_disp and scheme_disp != "(auto/none)":
        code = cat.MLST_SCHEMES.get(scheme_disp, scheme_disp)
        if code:
            tf += ["--mlst_scheme", code]
    for key, flag in [
        ("mlst_minid",    "--mlst_minid"),
        ("mlst_mincov",   "--mlst_mincov"),
        ("mlst_minscore", "--mlst_minscore"),
    ]:
        v = o.get(key, "").strip()
        if v:
            tf += [flag, v]
    if f.get("mlst_nopath"):
        tf.append("--mlst_nopath")

    # Annotation — Prokka (default) or Bakta
    annotator = o.get("annotator", "Prokka")
    if annotator == "Bakta":
        db = o.get("bakta_db", "").strip()
        if db:  # --use_bakta requires --bakta_db
            tf += ["--use_bakta", "--bakta_db", db]
            opts = o.get("bakta_opts", "").strip()
            if opts:
                tf += ["--bakta_opts", opts]
    else:  # Prokka
        pp = o.get("prokka_proteins", "").strip()
        if pp:
            tf += ["--prokka_proteins", pp]
        po = o.get("prokka_opts", "").strip()
        if po:
            tf += ["--prokka_opts", po]
        if f.get("prokka_compliant"):
            tf.append("--prokka_compliant")
    return tf


def _main_cmd(outdir: str, fofn_path: str, o: dict, f: dict,
               threads: int, memory: int, resume: bool,
               preview: bool = False, profile: str = "docker") -> str:
    """Build the full Nextflow command for the main Bactopia pipeline."""
    nf = system.get_nextflow_bin()
    base: list[str] = [nf, "run", "bactopia/bactopia"]
    ver = system.get_bactopia_version()
    if ver:
        base += ["-r", f"v{ver}"]
    base += ["-profile", profile or "docker",
             "--outdir", str(_pathlib.Path(outdir).expanduser().resolve())]
    datasets = o.get("datasets", "").strip()
    if datasets:
        base += ["--datasets", datasets]
    # QC gate thresholds — only emit when user overrides the Bactopia default.
    for key, flag in [
        ("min_coverage",    "--min_coverage"),
        ("min_basepairs",   "--min_basepairs"),
        ("min_reads",       "--min_reads"),
        ("min_genome_size", "--min_genome_size"),
        ("max_genome_size", "--max_genome_size"),
    ]:
        v = o.get(key, "").strip()
        if v:
            base += [flag, v]
    if f.get("with_report"):
        base += ["-with-report", str(_pathlib.Path(outdir) / "nf-report.html")]
    if f.get("with_timeline"):
        base += ["-with-timeline", str(_pathlib.Path(outdir) / "nf-timeline.html")]
    if f.get("with_trace"):
        base += ["-with-trace", str(_pathlib.Path(outdir) / "nf-trace.txt")]
    # --fastp_opts only applies to Illumina reads. Omit it for pure ONT runs
    # (Dragonflye long-read QC uses nanoq/filtlong, not fastp). Hybrid modes keep
    # it because they include Illumina R1/R2.
    mode = o.get("assembly_mode", "")
    if mode != "ONT (Dragonflye)":
        fp = _fastp_opts(o, f).strip()
        if fp:
            base += ["--fastp_opts", fp]
    # Assembler-specific flags (unicycler_mode, skip_qc_plots, etc.)
    base += _assembler_flags(o, f)
    # Typing & annotation flags (amrfinderplus_*, mlst_*, prokka_*, bakta_*)
    base += _typing_flags(o, f)
    if threads > 0:
        base += ["--max_cpus", str(threads)]
    if memory > 0:
        # Bactopia / Nextflow accepts dotted notation without space: 16.GB
        base += ["--max_memory", f"{memory}.GB"]
    if resume:
        base += ["-resume"]
    base += ["--samples", str(fofn_path)]
    extra = o.get("extra_params", "").strip()
    if extra:
        base += _split(extra)
    nf_cmd = " ".join(_q(x) for x in base)
    if preview:
        return nf_cmd
    return f"cd {_q(str(_pathlib.Path(outdir).expanduser().resolve()))} && {nf_cmd}"


# ── BactopiaState ──────────────────────────────────────────────────────────────

class BactopiaState(WizardMixin, rx.State):
    base_dir: str = ""
    bopts: dict[str, str] = dict(DEFAULT_BOPTS)
    bflags: dict[str, bool] = dict(DEFAULT_BFLAGS)
    fofn_path: str = ""
    fofn_summary: str = ""
    fofn_issues: list[str] = []
    fofn_built: bool = False

    def set_bopt(self, key: str, value):
        if isinstance(value, list):
            value = value[0] if value else ""
        self.bopts[key] = str(value)

    def set_bflag(self, key: str, value):
        self.bflags[key] = bool(value)

    @rx.var
    def fofn_target(self) -> str:
        out = bactopia.safe_dir(self.outdir)
        return str(_pathlib.Path(out) / "samples.txt")

    def scan_fofn(self):
        outdir = bactopia.safe_dir(self.outdir)
        fofn_out = str(_pathlib.Path(outdir) / "samples.txt")
        gsize = _fofn.parse_genome_size(self.bopts.get("genome_size", ""))
        try:
            res = _fofn.build_fofn(
                self.base_dir or outdir,
                recursive=self.bflags.get("recursive", True),
                species=self.bopts.get("species", "UNKNOWN_SPECIES"),
                gsize=gsize,
                fofn_path=fofn_out,
                treat_se_as_ont=self.bflags.get("treat_se_as_ont", False),
                infer_ont_by_name=self.bflags.get("infer_ont_by_name", True),
                merge_multi=self.bflags.get("merge_multi", True),
                include_assemblies=self.bflags.get("include_assemblies", True),
                # Thread the chosen hybrid strategy so build_fofn writes the correct
                # runtype per row ("hybrid" for Unicycler, "short_polish" for Dragonflye)
                # instead of emitting --hybrid / --short_polish as global CLI flags.
                hybrid_strategy=self.bopts.get("assembly_mode", ""),
            )
        except Exception as e:
            self.fofn_built = False
            self.fofn_summary = f"Failed: {e}"
            yield rx.toast.error(str(e))
            return
        self.fofn_path = res["fofn_path"]
        self.fofn_built = res["rows"] > 0
        self.fofn_issues = res["issues"][:30]
        counts_str = ", ".join(f"{k}={v}" for k, v in res["counts"].items() if v)
        self.fofn_summary = f"{res['rows']} samples · {counts_str}"
        yield rx.toast.success(f"FOFN written: {res['rows']} samples")

    @rx.var
    def preview(self) -> str:
        outdir = self.outdir or "<outdir>"
        fofn = (self.fofn_path or
                str(_pathlib.Path(outdir) / "samples.txt"))
        return _main_cmd(
            outdir, fofn, self.bopts, self.bflags,
            int(self.threads or 0), int(self.memory or 0),
            bool(self.resume), preview=True, profile=self.profile,
        )

    def _build(self):
        if not system.nextflow_available():
            return ("", "Nextflow not found (PATH / BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN).")
        if not self.outdir.strip():
            return ("", "Choose an output directory.")
        outdir = bactopia.safe_dir(self.outdir)
        _pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)
        fofn_out = str(_pathlib.Path(outdir) / "samples.txt")
        if not _pathlib.Path(fofn_out).is_file():
            return ("", "Generate the FOFN first (Scan & build FOFN).")
        cmd = _main_cmd(outdir, fofn_out, self.bopts, self.bflags,
                         int(self.threads or 0), int(self.memory or 0),
                         bool(self.resume), preview=False, profile=self.profile)
        return (cmd, "")

    @rx.event(background=True)
    async def run(self):
        async with self:
            cmd, err = self._build()
        if err:
            yield rx.toast.error(err)
            return
        async for _ in runner.stream(
            self, cmd, "bactopia",
            work_dir=bactopia.safe_dir(self.outdir),
            page="Bactopia",
            n_samples=self.n_selected,
        ):
            yield _
        async with self:
            self.refresh_merged()

    @rx.event(background=True)
    async def stop_run(self):
        await runner.stop("bactopia")
        async with self:
            self.status = "stopped"
            self.running = False


# ── RunsState ─────────────────────────────────────────────────────────────────

from bearhub.core import history as _history


class RunsState(rx.State):
    """Runs page state: history list + selected run log viewer."""
    records: list[dict] = []
    selected_id: str = ""
    selected_cmd: str = ""

    @staticmethod
    def _enrich(r: dict) -> dict:
        """Add pre-formatted display fields so Reflex Vars can render them."""
        return {**r,
            "started_fmt":  _history.fmt_time(r.get("started")),
            "duration_fmt": _history.fmt_duration(r.get("duration")),
            "samples_fmt":  f"{r.get('n_samples',0)} samples" if r.get("n_samples") else "—",
            "color":        _history.STATUS_COLOR.get(r.get("status",""), "gray"),
        }

    def load(self):
        _history.cancel_stale()
        self.records = [self._enrich(r) for r in _history.load_recent(100)]

    def select(self, run_id: str):
        self.selected_id = run_id
        for r in self.records:
            if r["id"] == run_id:
                self.selected_cmd = r.get("cmd", "")
                break

    def clear_selected(self):
        self.selected_id = ""
        self.selected_cmd = ""

    def refresh(self):
        self.records = [self._enrich(r) for r in _history.load_recent(100)]

    @rx.var
    def has_records(self) -> bool:
        return len(self.records) > 0

    @rx.var
    def active_count(self) -> int:
        return sum(1 for r in self.records if r.get("status") == "running")


# ── StatusState ────────────────────────────────────────────────────────────────

class StatusState(rx.State):
    versions: dict[str, str] = {}
    loading: bool = True

    @rx.event(background=True)
    async def load(self):
        from bearhub.core import versions
        async with self:
            self.loading = True
        data = versions.get_versions()
        async with self:
            self.versions = data
            self.loading = False
