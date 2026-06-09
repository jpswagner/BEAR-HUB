"""FOFN (samples.txt) builder for Bactopia.

Scans a folder for FASTQ/FASTA files, infers read types per sample (paired-end,
single-end, ont, hybrid, assembly), and writes a Bactopia-compatible tab-separated
samples file with columns: sample, runtype, genome_size, species, r1, r2, extra.
"""
from __future__ import annotations

import pathlib
import re

# ── File-type patterns ─────────────────────────────────────────────────────────

FASTQ_PATTERNS: tuple[str, ...] = ("*.fastq.gz", "*.fq.gz", "*.fastq", "*.fq")
FA_PATTERNS: tuple[str, ...] = (
    "*.fna.gz", "*.fa.gz", "*.fasta.gz", "*.fna", "*.fa", "*.fasta"
)
_EXTS: tuple[str, ...] = (
    ".fastq.gz", ".fq.gz", ".fastq", ".fq",
    ".fna.gz", ".fa.gz", ".fasta.gz", ".fna", ".fa", ".fasta",
)

# R1/R2 detection patterns
PE1_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^(?P<root>.+?)[._-](?:R?1|1|[Aa])(?:_[0-9]{3})?$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]1_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_1_\d{3}$"),
)
PE2_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^(?P<root>.+?)[._-](?:R?2|2|[Bb])(?:_[0-9]{3})?$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]2_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_2_\d{3}$"),
)
LANE_SUFFIX: re.Pattern = re.compile(r"(_L\d{3,4})?(_\d{3})?$")

# ONT path keywords (for infer_ont_by_name)
_ONT_KEYWORDS = ("ont", "nanopore", "minion", "oxford", "promethion")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _drop_exts(name: str) -> str:
    for ext in _EXTS:
        if name.endswith(ext):
            return name[: len(name) - len(ext)]
    return name


def _infer_root_and_tag(path: pathlib.Path) -> tuple[str, str]:
    """Return (sample_root, 'PE1'|'PE2'|'SE') for a FASTQ path."""
    name = _drop_exts(path.name)
    name = LANE_SUFFIX.sub("", name)
    for pat in PE1_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE1"
    for pat in PE2_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE2"
    return name, "SE"


def _is_probably_ont(p: pathlib.Path, s: str) -> bool:
    """True if the file path or sample name hints at Oxford Nanopore."""
    return any(k in str(p.as_posix()).lower() or k in s.lower()
               for k in _ONT_KEYWORDS)


def _collect(base: pathlib.Path, patterns: tuple[str, ...],
             recursive: bool) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    try:
        for pat in patterns:
            fn = base.rglob if recursive else base.glob
            for p in sorted(fn(pat)):
                if p.is_file():
                    out.append(p.resolve())
    except OSError:
        pass
    return list(dict.fromkeys(out))  # deduplicate preserving order


def parse_genome_size(raw: str) -> str:
    """Convert human-readable genome size (e.g. '5.5 Mb', '5500000') to bp string."""
    if not raw:
        return ""
    clean = re.sub(r"\s+", "", raw, flags=re.IGNORECASE)
    # numeric Mb/Gb suffix
    m = re.match(r"^([\d.]+)[Mm][Bb]?$", clean, re.IGNORECASE)
    if m:
        try:
            return str(int(float(m.group(1)) * 1_000_000))
        except ValueError:
            pass
    m = re.match(r"^([\d.]+)[Gg][Bb]?$", clean, re.IGNORECASE)
    if m:
        try:
            return str(int(float(m.group(1)) * 1_000_000_000))
        except ValueError:
            pass
    # plain integer
    digits = re.sub(r"[^\d]", "", clean)
    if digits:
        return digits
    return ""


def _pick(paths: list[pathlib.Path], merge_multi: bool) -> str:
    """Return a single path string (or comma-joined if merge_multi)."""
    if not paths:
        return ""
    try:
        return ",".join(str(p) for p in sorted(paths))
    except OSError:
        return str(paths[0])


def build_fofn(
    base_dir: str,
    *,
    recursive: bool = True,
    species: str = "UNKNOWN_SPECIES",
    gsize: str = "",
    fofn_path: str,
    treat_se_as_ont: bool = False,
    infer_ont_by_name: bool = True,
    merge_multi: bool = True,
    include_assemblies: bool = True,
) -> dict:
    """
    Scan base_dir for reads/assemblies and write a Bactopia samples.txt FOFN.

    Returns a dict with keys: fofn_path, rows, issues, counts.
    The runtype column follows Bactopia 4 conventions:
      paired-end, single-end, ont, hybrid, short_polish, assembly.
    """
    base = pathlib.Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"Base folder does not exist: {base_dir}")
    pathlib.Path(fofn_path).parent.mkdir(parents=True, exist_ok=True)

    fastqs = _collect(base, FASTQ_PATTERNS, recursive)
    fastas = _collect(base, FA_PATTERNS, recursive) if include_assemblies else []

    # Group fastqs by (sample_root, tag)
    by_sample: dict[str, dict[str, list[pathlib.Path]]] = {}
    for p in fastqs:
        root, tag = _infer_root_and_tag(p)
        # Override SE→ONT if hint present
        if tag == "SE" and (treat_se_as_ont or
                            (infer_ont_by_name and _is_probably_ont(p, root))):
            tag = "ont"
        by_sample.setdefault(root, {}).setdefault(tag, []).append(p)

    # Group fastas by stem
    fa_by_sample: dict[str, list[pathlib.Path]] = {}
    for p in fastas:
        root = _drop_exts(p.name)
        fa_by_sample.setdefault(root, []).append(p)

    all_samples = sorted(set(list(by_sample.keys()) + list(fa_by_sample.keys())))

    header = ["sample", "runtype", "genome_size", "species", "r1", "r2", "extra"]
    rows: list[list[str]] = []
    issues: list[str] = []
    counts: dict[str, int] = {}

    for sample in all_samples:
        fq = by_sample.get(sample, {})
        fa = fa_by_sample.get(sample, [])

        pe1 = fq.get("PE1", [])
        pe2 = fq.get("PE2", [])
        se  = fq.get("SE", [])
        ont = fq.get("ont", [])

        # Validate PE pairing
        if pe1 and not pe2:
            issues.append(f"{sample}: R1 found without R2.")
        if pe2 and not pe1:
            issues.append(f"{sample}: R2 found without R1.")

        # Classify
        if fa and not (pe1 or pe2 or se or ont):
            runtype = "assembly"
            r1 = _pick(fa, merge_multi)
            r2, extra = "", ""
        elif pe1 and pe2 and ont:
            runtype = "hybrid"
            r1 = _pick(pe1, merge_multi)
            r2 = _pick(pe2, merge_multi)
            extra = _pick(ont, merge_multi)
        elif pe1 and pe2:
            runtype = "paired-end"
            r1 = _pick(pe1, merge_multi)
            r2 = _pick(pe2, merge_multi)
            extra = ""
        elif ont and not (pe1 or pe2):
            runtype = "ont"
            r1 = _pick(ont, merge_multi)
            r2, extra = "", ""
        elif se and not (pe1 or pe2 or ont):
            runtype = "single-end"
            r1 = _pick(se, merge_multi)
            r2, extra = "", ""
        elif fa and (pe1 or pe2 or se or ont):
            issues.append(
                f"{sample}: FASTA and FASTQ detected; ignoring assembly in FOFN."
            )
            if pe1 and pe2 and ont:
                runtype = "hybrid"
                r1 = _pick(pe1, merge_multi)
                r2 = _pick(pe2, merge_multi)
                extra = _pick(ont, merge_multi)
            elif pe1 and pe2:
                runtype = "paired-end"
                r1 = _pick(pe1, merge_multi)
                r2 = _pick(pe2, merge_multi)
                extra = ""
            elif ont:
                runtype = "ont"
                r1 = _pick(ont, merge_multi)
                r2, extra = "", ""
            else:
                runtype = "single-end"
                r1 = _pick(se, merge_multi)
                r2, extra = "", ""
        else:
            issues.append(f"{sample}: could not classify sample (missing files?).")
            continue

        counts[runtype] = counts.get(runtype, 0) + 1
        rows.append([sample, runtype, gsize, species or "UNKNOWN_SPECIES", r1, r2, extra])

    # Write FOFN
    lines = ["\t".join(header)]
    for row in rows:
        lines.append("\t".join(row))
    pathlib.Path(fofn_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"fofn_path": fofn_path, "rows": len(rows), "issues": issues, "counts": counts}


def write_include_file(outdir: str, samples: list[str]) -> str:
    """Write an --include file (one sample per line) and return its path."""
    from bearhub.core.runner import write_include_file as _wif
    return _wif(outdir, samples)
