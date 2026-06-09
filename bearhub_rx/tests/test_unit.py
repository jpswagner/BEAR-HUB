"""
BEAR-HUB comprehensive test suite.
Covers: core modules, command builder, FOFN logic, history persistence, state defaults.
Run from bearhub_rx/:  python /tmp/test_bearhub.py
"""
import sys, os, pathlib, tempfile, json, time
BEARHUB_RX = pathlib.Path(__file__).resolve().parent.parent
os.chdir(BEARHUB_RX)
sys.path.insert(0, str(BEARHUB_RX))

PASS = "✅"
FAIL = "❌"
results = []

def check(name, expr, expected=True):
    ok = bool(expr) == bool(expected)
    results.append((ok, name))
    print(f"  {PASS if ok else FAIL}  {name}")
    return ok

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── suppress Reflex noise ───────────────────────────────────────────────────
import warnings; warnings.filterwarnings("ignore")
os.environ.setdefault("TELEMETRY_ENABLED", "false")

# ── 1. core/system ─────────────────────────────────────────────────────────
section("1. core/system")
from bearhub.core.system import (
    get_nextflow_bin, nextflow_available, get_default_outdir,
    docker_available, APP_STATE_DIR
)
check("APP_STATE_DIR is Path",       isinstance(APP_STATE_DIR, pathlib.Path))
check("get_nextflow_bin() → str",    isinstance(get_nextflow_bin(), str))
check("get_default_outdir() → str",  isinstance(get_default_outdir(), str))
check("nextflow_available() → bool", isinstance(nextflow_available(), bool))
check("docker_available() → bool",   isinstance(docker_available(), bool))

# ── 2. core/bactopia ───────────────────────────────────────────────────────
section("2. core/bactopia")
from bearhub.core.bactopia import safe_dir, list_subdirs, discover_samples, guess_root_default

check("safe_dir('')        → home",     safe_dir("") == str(pathlib.Path.home()))
check("safe_dir(None)      → home",     safe_dir(None) == str(pathlib.Path.home()))
check("safe_dir('/tmp')    → /tmp",     safe_dir("/tmp") == "/tmp")
check("safe_dir('/no/path')→ existing", pathlib.Path(safe_dir("/no/such/path")).exists())
check("list_subdirs('/tmp')→ list",     isinstance(list_subdirs("/tmp"), list))
check("discover_samples('/tmp')→ list", isinstance(discover_samples("/tmp"), list))
check("guess_root_default()→ str",      isinstance(guess_root_default(), str))

# ── 3. core/fofn ───────────────────────────────────────────────────────────
section("3. core/fofn — FOFN builder")
from bearhub.core.fofn import build_fofn, parse_genome_size, FASTQ_PATTERNS, FA_PATTERNS

check("parse_genome_size('5.5 Mb')",   parse_genome_size("5.5 Mb") == "5500000")
check("parse_genome_size('5500000')",  parse_genome_size("5500000") == "5500000")
check("parse_genome_size('2.3 Gb')",   parse_genome_size("2.3 Gb") == "2300000000")
check("parse_genome_size('')      →''", parse_genome_size("") == "")
check("FASTQ_PATTERNS is tuple",       isinstance(FASTQ_PATTERNS, tuple))
check("FA_PATTERNS is tuple",          isinstance(FA_PATTERNS, tuple))

with tempfile.TemporaryDirectory() as d:
    base = pathlib.Path(d)
    # PE reads
    (base / "sampleA_R1.fastq.gz").touch()
    (base / "sampleA_R2.fastq.gz").touch()
    # ONT reads in nanopore subdir
    (base / "nanopore").mkdir()
    (base / "nanopore" / "sampleA.fastq.gz").touch()
    # Assembly only
    (base / "sampleB.fasta").touch()

    fofn = str(base / "s.txt")
    res = build_fofn(str(base), fofn_path=fofn, hybrid_strategy="Hybrid (Unicycler --hybrid)")
    rows = [r.split("\t") for r in pathlib.Path(fofn).read_text().splitlines()[1:] if r]

    check("build_fofn returns 2 rows",    res["rows"] == 2)
    check("sampleA runtype = hybrid",     any(r[0]=="sampleA" and r[1]=="hybrid"    for r in rows))
    check("sampleB runtype = assembly",   any(r[0]=="sampleB" and r[1]=="assembly"  for r in rows))

    # short_polish strategy
    fofn2 = str(base / "s2.txt")
    res2 = build_fofn(str(base), fofn_path=fofn2,
                      hybrid_strategy="Hybrid (Dragonflye --short_polish)")
    rows2 = [r.split("\t") for r in pathlib.Path(fofn2).read_text().splitlines()[1:] if r]
    check("short_polish strategy → runtype=short_polish",
          any(r[0]=="sampleA" and r[1]=="short_polish" for r in rows2))

# ── 4. core/history ────────────────────────────────────────────────────────
section("4. core/history — persistence")
from bearhub.core import history as h

orig_file = h._HISTORY_FILE
h._HISTORY_FILE = pathlib.Path(tempfile.mktemp(suffix=".jsonl"))
try:
    r1 = h.new_record("bactopia", "Bactopia", "nextflow run ...", "/outdir", 10)
    check("new_record status=running",  r1["status"] == "running")
    check("new_record has id",          len(r1["id"]) == 8)
    h.append_record(r1)
    h.finish_record(r1["id"], 0)
    loaded = h.load_recent()
    check("load_recent finds record",   len(loaded) == 1)
    check("finished status=success",    loaded[0]["status"] == "success")
    check("duration recorded",          loaded[0]["duration"] is not None)
    check("exit_code=0",                loaded[0]["exit_code"] == 0)

    r2 = h.new_record("tools", "Tools", "nextflow run ...", "/outdir", 5)
    h.append_record(r2)
    h.finish_record(r2["id"], 1)
    loaded2 = h.load_recent()
    check("two records saved",          len(loaded2) == 2)
    check("failed status recorded",     any(r["status"]=="failed" for r in loaded2))

    # cancel_stale
    r3 = h.new_record("merlin", "MERLIN", "nf run", "/o", 0)
    r3["started"] = time.time() - 90000   # > 24h ago
    h.append_record(r3)
    h.cancel_stale()
    loaded3 = h.load_recent()
    check("cancel_stale marks old running as interrupted",
          any(r["id"]==r3["id"] and r["status"]=="interrupted" for r in loaded3))

    # fmt helpers
    check("fmt_duration(90)  → '1m 30s'",  h.fmt_duration(90) == "1m 30s")
    check("fmt_duration(3661)→ '1h 01m'",  h.fmt_duration(3661) == "1h 01m")
    check("fmt_duration(None)→ '—'",       h.fmt_duration(None) == "—")
    check("STATUS_COLOR has green/red",
          h.STATUS_COLOR["success"]=="green" and h.STATUS_COLOR["failed"]=="red")
finally:
    h._HISTORY_FILE.unlink(missing_ok=True)
    h._HISTORY_FILE = orig_file

# ── 5. state — defaults & command builder ─────────────────────────────────
section("5. state — DEFAULT_BOPTS / DEFAULT_BFLAGS / command builder")
from bearhub.state import DEFAULT_BOPTS, DEFAULT_BFLAGS, _assembler_flags, _fastp_opts, _main_cmd

# Default values
check("min_contig_len default = 1000",  DEFAULT_BOPTS["min_contig_len"] == "1000")
check("min_contig_cov default = 10",    DEFAULT_BOPTS["min_contig_cov"] == "10")
check("amr_ident_min default = 0.9",    DEFAULT_BOPTS["amr_ident_min"] == "0.9")
check("amr_coverage_min default = 0.5", DEFAULT_BOPTS["amr_coverage_min"] == "0.5")
check("unicycler_mode default = normal",DEFAULT_BOPTS["unicycler_mode"] == "normal")
check("assembly_mode = PE Unicycler",   "Unicycler" in DEFAULT_BOPTS["assembly_mode"])
check("skip_qc_plot default = True",    DEFAULT_BFLAGS["skip_qc_plot"] == True)
check("with_report default = True",     DEFAULT_BFLAGS["with_report"] == True)
check("fastp_dash3 default = True",     DEFAULT_BFLAGS["fastp_dash3"] == True)
# QC gate keys present
for k in ["min_coverage","min_basepairs","min_reads","min_genome_size","max_genome_size"]:
    check(f"DEFAULT_BOPTS has {k}", k in DEFAULT_BOPTS)

# assembler_flags for each mode
for mode, must, must_not in [
    ("Illumina PE (Unicycler)",
        ["--use_unicycler","--unicycler_mode","--skip_qc_plots","--min_contig_len"],
        ["--unicycler_opts","--hybrid","--short_polish","--skip_qc_plot "]),
    ("Hybrid (Dragonflye --short_polish)",
        ["--skip_qc_plots","--min_contig_len"],
        ["--short_polish","--hybrid","--unicycler_opts"]),
    ("Hybrid (Unicycler --hybrid)",
        ["--use_unicycler","--unicycler_mode","--min_contig_len","--skip_qc_plots"],
        ["--hybrid","--unicycler_opts","--short_polish"]),
    ("ONT (Dragonflye)",
        ["--skip_qc_plots","--min_contig_len"],
        ["--hybrid","--short_polish","--unicycler_opts"]),
]:
    o = {**DEFAULT_BOPTS, "assembly_mode": mode}
    af = _assembler_flags(o, DEFAULT_BFLAGS)
    af_str = " ".join(af)
    for flag in must:
        check(f"[{mode[:20]}] has {flag}", flag in af_str)
    for flag in must_not:
        check(f"[{mode[:20]}] no {flag}", flag not in af_str)

# fastp opts
fo = _fastp_opts(DEFAULT_BOPTS, DEFAULT_BFLAGS)
check("fastp default: -3 present",  "-3" in fo)
check("fastp default: -M 20",       "-M 20" in fo)
check("fastp default: -W 5",        "-W 5" in fo)

# QC thresholds only emitted when set
o_qc = {**DEFAULT_BOPTS, "min_coverage": "5"}
cmd = _main_cmd("/outdir", "/outdir/s.txt", o_qc, DEFAULT_BFLAGS, 0, 0, True, preview=True)
check("--min_coverage 5 emitted",   "--min_coverage 5" in cmd)
check("--min_basepairs not emitted (blank)", "--min_basepairs" not in cmd)

# Full command 19 checks
cmd_full = _main_cmd("/outdir", "/outdir/s.txt", DEFAULT_BOPTS, DEFAULT_BFLAGS, 4, 16, True, preview=True)
for flag, expected in [
    ("nextflow run bactopia/bactopia", True),
    ("--use_unicycler",     True),
    ("--unicycler_mode",    True),
    ("--skip_qc_plots",     True),
    ("--min_contig_len 1000", True),
    ("--min_contig_cov 10", True),
    ("--ident_min 0.9",     True),
    ("--coverage_min 0.5",  True),
    ("-with-report",        True),
    ("--fastp_opts",        True),
    ("--max_cpus 4",        True),
    ("--max_memory 16.GB",  True),
    ("-resume",             True),
    ("--hybrid",            False),
    ("--short_polish",      False),
    ("--unicycler_opts",    False),
    ("--skip_qc_plot ",     False),
]:
    ok = (flag in cmd_full) == expected
    check(f"cmd: {flag!r} {'present' if expected else 'absent'}", ok)

# ── 6. state — RunsState._enrich ──────────────────────────────────────────
section("6. state — RunsState._enrich")
from bearhub.state import RunsState

r = {"id":"abc123","status":"success","page":"Bactopia","cmd":"nf run ...",
     "started":1000000.0,"finished":1003600.0,"duration":3600,"n_samples":12}
e = RunsState._enrich(r)
check("_enrich: color=green",           e["color"] == "green")
check("_enrich: duration_fmt=1h 00m",   e["duration_fmt"] == "1h 00m")
check("_enrich: samples_fmt has '12'",  "12" in e["samples_fmt"])
check("_enrich: started_fmt non-empty", len(e["started_fmt"]) > 0)

r2 = {**r, "status":"failed","n_samples":0}
e2 = RunsState._enrich(r2)
check("_enrich: failed → color=red",    e2["color"] == "red")
check("_enrich: 0 samples → '—'",       e2["samples_fmt"] == "—")

# ── Summary ────────────────────────────────────────────────────────────────
section("SUMMARY")
passed = sum(1 for ok, _ in results if ok)
total  = len(results)
failed = [(name) for ok, name in results if not ok]
print(f"\n  {passed}/{total} tests passed")
if failed:
    print(f"\n  FAILED ({len(failed)}):")
    for name in failed: print(f"    {FAIL} {name}")
    sys.exit(1)
else:
    print(f"\n  ALL {total} TESTS PASSED ✅")
