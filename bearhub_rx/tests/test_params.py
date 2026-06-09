"""Parameter matrix test — verify each UI parameter flows correctly to the command."""
import sys, os
sys.path.insert(0, "/home/cdctserver/BEAR-HUB/BEAR-HUB/bearhub_rx")
os.chdir("/home/cdctserver/BEAR-HUB/BEAR-HUB/bearhub_rx")
import warnings; warnings.filterwarnings("ignore")
from bearhub.state import DEFAULT_BOPTS, DEFAULT_BFLAGS, _main_cmd, _fastp_opts, _assembler_flags

PASS, FAIL = "✅", "❌"
results = []
def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {PASS if cond else FAIL}  {name}" + (f"  [{detail}]" if detail and not cond else ""))

def build(bopts_over=None, bflags_over=None, threads=0, memory=0, resume=True):
    o = {**DEFAULT_BOPTS, **(bopts_over or {})}
    f = {**DEFAULT_BFLAGS, **(bflags_over or {})}
    return _main_cmd("/out", "/out/samples.txt", o, f, threads, memory, resume, preview=True)

def section(t): print("\n" + "="*64 + f"\n  {t}\n" + "="*64)

# ── 1. Assembler / Unicycler params ────────────────────────────────────────
section("1. Assembler — Unicycler params")
c = build({"unicycler_mode": "bold"})
check("unicycler_mode=bold → --unicycler_mode bold", "--unicycler_mode bold" in c)
c = build({"unicycler_mode": "conservative"})
check("unicycler_mode=conservative", "--unicycler_mode conservative" in c)
c = build({"assembly_mode":"Illumina PE (Unicycler)","min_component_size":"500","min_dead_end_size":"2000"})
check("--min_component_size 500", "--min_component_size 500" in c)
check("--min_dead_end_size 2000", "--min_dead_end_size 2000" in c)
c = build({"assembly_mode":"Illumina PE (Unicycler)"})
check("component/dead_end blank → not emitted", "--min_component_size" not in c and "--min_dead_end_size" not in c)

# ── 2. Shovill params ──────────────────────────────────────────────────────
section("2. Assembler — Shovill (PE Shovill mode)")
base_sh = {"assembly_mode": "Illumina PE (Shovill)"}
c = build({**base_sh, "shovill_assembler": "spades"})
check("shovill_assembler=spades", "--shovill_assembler spades" in c)
c = build({**base_sh, "shovill_assembler": "skesa"})  # default → not emitted
check("shovill_assembler=skesa (default) → not emitted", "--shovill_assembler" not in c)
c = build({**base_sh, "shovill_opts": "--depth 100"})
check("shovill_opts passthrough", "--shovill_opts" in c and "depth 100" in c)
c = build({**base_sh, "shovill_kmers": "31,55,71"})
check("shovill_kmers passthrough", "--shovill_kmers" in c and "31,55,71" in c)
c = build(base_sh, {"trim": True})
check("--trim flag", "--trim" in c)
c = build(base_sh, {"no_stitch": True})
check("--no_stitch flag", "--no_stitch" in c)

# ── 3. Dragonflye params (ONT mode) ────────────────────────────────────────
section("3. Assembler — Dragonflye (ONT mode)")
base_df = {"assembly_mode": "ONT (Dragonflye)"}
c = build({**base_df, "dragonflye_assembler": "miniasm"})
check("dragonflye_assembler=miniasm", "--dragonflye_assembler miniasm" in c)
c = build({**base_df, "dragonflye_assembler": "flye"})  # default
check("dragonflye_assembler=flye (default) → not emitted", "--dragonflye_assembler" not in c)
c = build({**base_df, "dragonflye_opts": "--gsize 5m"})
check("dragonflye_opts passthrough", "--dragonflye_opts" in c and "gsize 5m" in c)
c = build(base_df, {"nanohq": True})
check("--nanohq flag", "--nanohq" in c)
c = build(base_df, {"no_miniasm": True})
check("--no_miniasm flag", "--no_miniasm" in c)

# ── 4. Contig filters ──────────────────────────────────────────────────────
section("4. Contig length / coverage filters")
c = build({"min_contig_len": "2000"})
check("min_contig_len=2000 (custom)", "--min_contig_len 2000" in c)
c = build({"min_contig_len": "500"})  # bactopia default but still always-emit
check("min_contig_len=500 still emitted (always)", "--min_contig_len 500" in c)
c = build({"min_contig_cov": "5"})
check("min_contig_cov=5 (custom)", "--min_contig_cov 5" in c)
c = build({"min_contig_cov": "2"})  # bactopia default → not emitted
check("min_contig_cov=2 (bactopia default) → not emitted", "--min_contig_cov" not in c)

# ── 5. Polishing rounds ────────────────────────────────────────────────────
section("5. Polishing rounds")
c = build({"polypolish_rounds": "3"})
check("polypolish_rounds=3", "--polypolish_rounds 3" in c)
c = build({"polypolish_rounds": "1"})  # default → not emitted
check("polypolish_rounds=1 (default) → not emitted", "--polypolish_rounds" not in c)
c = build({"pilon_rounds": "2"})
check("pilon_rounds=2", "--pilon_rounds 2" in c)
c = build({"racon_rounds": "4"})
check("racon_rounds=4", "--racon_rounds 4" in c)
c = build({"medaka_rounds": "1"})
check("medaka_rounds=1", "--medaka_rounds 1" in c)
c = build({"medaka_model": "r941_min_hac_g507"})
check("medaka_model passthrough", "--medaka_model r941_min_hac_g507" in c)
c = build(None, {"no_polish": True})
check("--no_polish flag", "--no_polish" in c)

# ── 6. fastp params ────────────────────────────────────────────────────────
section("6. fastp — read cleaning")
c = build({"fastp_M": "30", "fastp_W": "8"})
check("fastp -M 30 -W 8", "-M 30" in c and "-W 8" in c)
c = build({}, {"fastp_q_enable": True})
fo = _fastp_opts({**DEFAULT_BOPTS}, {**DEFAULT_BFLAGS, "fastp_q_enable": True})
check("fastp -q enabled", "-q" in fo.split())
fo = _fastp_opts({**DEFAULT_BOPTS}, {**DEFAULT_BFLAGS, "fastp_dedup": True})
check("fastp -D (dedup)", "-D" in fo.split())
fo = _fastp_opts({**DEFAULT_BOPTS}, {**DEFAULT_BFLAGS, "fastp_poly_g": True})
check("fastp -g (polyG)", "-g" in fo.split())
fo = _fastp_opts({**DEFAULT_BOPTS, "fastp_adapter_r1": "AGATCGGAAGAGC"}, DEFAULT_BFLAGS)
check("fastp adapter R1", "AGATCGGAAGAGC" in fo)
fo = _fastp_opts({**DEFAULT_BOPTS, "fastp_extra": "--trim_front1 10"}, DEFAULT_BFLAGS)
check("fastp extra passthrough", "--trim_front1 10" in fo)
# Advanced fastp mode (raw line)
fo = _fastp_opts({**DEFAULT_BOPTS, "fastp_mode": "Advanced", "fastp_raw": "-3 -M 25 --cut_tail"}, DEFAULT_BFLAGS)
check("fastp Advanced mode uses raw line", fo == "-3 -M 25 --cut_tail")

# ── 7. AMRFinder / MLST must NOT appear (Tools-only params) ────────────────
section("7. Annotation / Typing — AMRFinder/MLST params NOT in main pipeline")
# These are Bactopia Tools params (--wf amrfinderplus / --wf mlst), invalid in
# the main pipeline. The command must never emit them (Nextflow would abort).
c = build({"amr_ident_min": "0.95", "amr_coverage_min": "0.7",
           "mlst_scheme": "saureus", "mlst_minscore": "100"})
check("--ident_min NEVER emitted (Tools-only)",    "--ident_min" not in c)
check("--coverage_min NEVER emitted (Tools-only)", "--coverage_min" not in c)
check("--scheme NEVER emitted (Tools-only)",       "--scheme" not in c)
check("--minscore NEVER emitted (Tools-only)",     "--minscore" not in c)
check("--nopath NEVER emitted (Tools-only)",       "--nopath" not in c)

# ── 8. QC gate thresholds ──────────────────────────────────────────────────
section("8. QC gate thresholds")
c = build({"min_coverage": "20"})
check("min_coverage=20", "--min_coverage 20" in c)
c = build({"min_basepairs": "1000000"})
check("min_basepairs=1000000", "--min_basepairs 1000000" in c)
c = build({"min_reads": "5000"})
check("min_reads=5000", "--min_reads 5000" in c)
c = build({"min_genome_size": "2000000", "max_genome_size": "8000000"})
check("min/max_genome_size", "--min_genome_size 2000000" in c and "--max_genome_size 8000000" in c)
c = build({})  # all blank → none emitted
check("blank QC gates → none emitted",
      not any(x in c for x in ["--min_coverage","--min_basepairs","--min_reads","--min_genome_size"]))

# ── 9. Execution params ────────────────────────────────────────────────────
section("9. Execution (profile / cpus / memory / resume / reports)")
c = build({}, {}, threads=8, memory=32)
check("--max_cpus 8", "--max_cpus 8" in c)
check("--max_memory 32.GB (dotted)", "--max_memory 32.GB" in c)
c = build({}, {}, threads=0, memory=0)
check("0 cpus/mem → not emitted", "--max_cpus" not in c and "--max_memory" not in c)
c = build({}, {}, resume=False)
check("resume=False → no -resume", "-resume" not in c)
c = build({}, {"with_report": False, "with_timeline": False, "with_trace": False})
check("reports off → no -with-* flags",
      not any(x in c for x in ["-with-report","-with-timeline","-with-trace"]))
c = build({"datasets": "/path/to/datasets"})
check("datasets path", "--datasets /path/to/datasets" in c)
c = build({"extra_params": "-with-dag flow.html"})
check("extra_params appended", "-with-dag flow.html" in c)

# ── 10. Profile ────────────────────────────────────────────────────────────
section("10. Profile (now threaded explicitly)")
c = _main_cmd("/out", "/out/samples.txt", DEFAULT_BOPTS, DEFAULT_BFLAGS, 0, 0, True, preview=True, profile="docker")
check("profile=docker → -profile docker", "-profile docker" in c)
c = _main_cmd("/out", "/out/samples.txt", DEFAULT_BOPTS, DEFAULT_BFLAGS, 0, 0, True, preview=True, profile="singularity")
check("profile=singularity → -profile singularity", "-profile singularity" in c)
check("profile=singularity → NOT forced to docker", "-profile docker" not in c)
c = _main_cmd("/out", "/out/samples.txt", DEFAULT_BOPTS, DEFAULT_BFLAGS, 0, 0, True, preview=False, profile="standard")
check("profile=standard (real build)", "-profile standard" in c)


# ── 11. fastp omitted for pure ONT (applies only to Illumina) ──────────────
section("11. fastp omission for pure ONT mode")
def _has_fastp(mode):
    o = {**DEFAULT_BOPTS, "assembly_mode": mode}
    return "--fastp_opts" in _main_cmd("/o","/o/s.txt",o,DEFAULT_BFLAGS,0,0,True,preview=True)
check("PE Unicycler keeps --fastp_opts", _has_fastp("Illumina PE (Unicycler)"))
check("ONT (Dragonflye) OMITS --fastp_opts", not _has_fastp("ONT (Dragonflye)"))
check("Hybrid Unicycler keeps --fastp_opts (has Illumina)", _has_fastp("Hybrid (Unicycler --hybrid)"))
check("Hybrid Dragonflye keeps --fastp_opts (has Illumina)", _has_fastp("Hybrid (Dragonflye --short_polish)"))


# ── 12. Typing/annotation params (prefixed, main-pipeline) ─────────────────
section("12. Typing & annotation — prefixed names")
from bearhub.state import _typing_flags
# Default = no typing flags
check("default → no typing flags", _typing_flags(DEFAULT_BOPTS, DEFAULT_BFLAGS) == [])
# AMRFinder+ (organism/opts/noplus; floats ident_min/coverage_min excluded)
o = {**DEFAULT_BOPTS, "amrfinderplus_organism":"Streptococcus_pyogenes",
     }
c = _main_cmd("/o","/o/s.txt",o,DEFAULT_BFLAGS,0,0,True,preview=True)
check("--amrfinderplus_organism", "--amrfinderplus_organism Streptococcus_pyogenes" in c)
check("float --amrfinderplus_ident_min NOT a CLI flag", "--amrfinderplus_ident_min" not in c)
c = _main_cmd("/o","/o/s.txt",DEFAULT_BOPTS,{**DEFAULT_BFLAGS,"amrfinderplus_noplus":True},0,0,True,preview=True)
check("--amrfinderplus_noplus flag", "--amrfinderplus_noplus" in c)
# MLST
o = {**DEFAULT_BOPTS, "mlst_scheme":"spyogenes", "mlst_minid":"95", "mlst_mincov":"10"}
c = _main_cmd("/o","/o/s.txt",o,DEFAULT_BFLAGS,0,0,True,preview=True)
check("--mlst_scheme spyogenes", "--mlst_scheme spyogenes" in c)
check("--mlst_minid 95", "--mlst_minid 95" in c)
check("unprefixed --scheme NEVER emitted", "--scheme " not in c)
check("mlst_scheme (auto/none) → not emitted", "--mlst_scheme" not in _main_cmd("/o","/o/s.txt",DEFAULT_BOPTS,DEFAULT_BFLAGS,0,0,True,preview=True))
# Annotation: Prokka default
o = {**DEFAULT_BOPTS, "prokka_proteins":"/db/p.faa"}
c = _main_cmd("/o","/o/s.txt",o,{**DEFAULT_BFLAGS,"prokka_compliant":True},0,0,True,preview=True)
check("--prokka_proteins", "--prokka_proteins /db/p.faa" in c)
check("--prokka_compliant", "--prokka_compliant" in c)
# Bakta requires db
o = {**DEFAULT_BOPTS, "annotator":"Bakta"}
check("Bakta without db → no --use_bakta", "--use_bakta" not in _main_cmd("/o","/o/s.txt",o,DEFAULT_BFLAGS,0,0,True,preview=True))
o = {**DEFAULT_BOPTS, "annotator":"Bakta", "bakta_db":"/db/bakta"}
c = _main_cmd("/o","/o/s.txt",o,DEFAULT_BFLAGS,0,0,True,preview=True)
check("Bakta with db → --use_bakta --bakta_db", "--use_bakta" in c and "--bakta_db /db/bakta" in c)

# ── Summary ────────────────────────────────────────────────────────────────
section("SUMMARY")
p = sum(results); t = len(results)
print(f"\n  {p}/{t} parameter-flow tests passed")
sys.exit(0 if p == t else 1)
