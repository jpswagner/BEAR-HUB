"""Real-data test: FOFN classification + command generation for PE/ONT/hybrid/assembly."""
import sys, os, pathlib, tempfile, shutil
sys.path.insert(0, "/home/cdctserver/BEAR-HUB/BEAR-HUB/bearhub_rx")
os.chdir("/home/cdctserver/BEAR-HUB/BEAR-HUB/bearhub_rx")
import warnings; warnings.filterwarnings("ignore")

from bearhub.core.fofn import build_fofn
from bearhub.state import DEFAULT_BOPTS, DEFAULT_BFLAGS, _main_cmd

PASS, FAIL = "✅", "❌"
results = []
def check(name, cond):
    results.append(bool(cond)); print(f"  {PASS if cond else FAIL}  {name}")

# Real data sources
PE = pathlib.Path("/home/cdctserver/joao/pyogenes")
ONT = pathlib.Path("/home/cdctserver/Downloads/genomas_enterobacter")
FA = pathlib.Path("/home/cdctserver/joao/ref_strains/BEN2908.fa")

ROOT = pathlib.Path("/tmp/bearhub_realdata")
if ROOT.exists(): shutil.rmtree(ROOT)
ROOT.mkdir()

def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists(): dst.symlink_to(src)

# ── Scenario A: paired-end (Illumina) ──────────────────────────────────────
print("\n" + "="*60 + "\n  A. Short reads — Illumina paired-end (pyogenes)\n" + "="*60)
sa = ROOT / "PE"
link(PE/"pyogenes-10_R1.fastq.gz", sa/"pyogenes-10_R1.fastq.gz")
link(PE/"pyogenes-10_R2.fastq.gz", sa/"pyogenes-10_R2.fastq.gz")
link(PE/"pyogenes-254_R1.fastq.gz", sa/"pyogenes-254_R1.fastq.gz")
link(PE/"pyogenes-254_R2.fastq.gz", sa/"pyogenes-254_R2.fastq.gz")
res = build_fofn(str(sa), fofn_path=str(sa/"samples.txt"))
rows = [r.split("\t") for r in (sa/"samples.txt").read_text().splitlines()[1:] if r]
print(f"  FOFN rows: {res['rows']}, counts: {res['counts']}")
for r in rows: print(f"    {r[0]:25} runtype={r[1]:12} r1={pathlib.Path(r[4]).name if r[4] else '-'}")
check("PE: 2 samples found", res["rows"] == 2)
check("PE: both runtype=paired-end", all(r[1]=="paired-end" for r in rows))
check("PE: R1 and R2 populated", all(r[4] and r[5] for r in rows))

# ── Scenario B: ONT long reads ─────────────────────────────────────────────
print("\n" + "="*60 + "\n  B. Long reads — ONT (genomas_enterobacter, in nanopore/)\n" + "="*60)
sb = ROOT / "ONT"
link(ONT/"GECL0521.fastq.gz", sb/"nanopore"/"GECL0521.fastq.gz")
link(ONT/"GECL0524.fastq.gz", sb/"nanopore"/"GECL0524.fastq.gz")
res = build_fofn(str(sb), fofn_path=str(sb/"samples.txt"), infer_ont_by_name=True)
rows = [r.split("\t") for r in (sb/"samples.txt").read_text().splitlines()[1:] if r]
print(f"  FOFN rows: {res['rows']}, counts: {res['counts']}")
for r in rows: print(f"    {r[0]:25} runtype={r[1]:12} r1={pathlib.Path(r[4]).name if r[4] else '-'}")
check("ONT: 2 samples found", res["rows"] == 2)
check("ONT: runtype=ont (inferred by 'nanopore' path)", all(r[1]=="ont" for r in rows))

# ── Scenario B2: ONT via treat_se_as_ont (no path hint) ────────────────────
print("\n" + "="*60 + "\n  B2. ONT via treat_se_as_ont flag (no path hint)\n" + "="*60)
sb2 = ROOT / "ONT_flat"
link(ONT/"GECL0521.fastq.gz", sb2/"GECL0521.fastq.gz")
res = build_fofn(str(sb2), fofn_path=str(sb2/"samples.txt"), treat_se_as_ont=True)
rows = [r.split("\t") for r in (sb2/"samples.txt").read_text().splitlines()[1:] if r]
print(f"  counts: {res['counts']}")
for r in rows: print(f"    {r[0]:25} runtype={r[1]}")
check("ONT_flat: treat_se_as_ont → runtype=ont", rows and rows[0][1]=="ont")
# and without the flag → single-end
res2 = build_fofn(str(sb2), fofn_path=str(sb2/"s2.txt"), treat_se_as_ont=False, infer_ont_by_name=False)
rows2 = [r.split("\t") for r in (sb2/"s2.txt").read_text().splitlines()[1:] if r]
check("ONT_flat: without flag → runtype=single-end", rows2 and rows2[0][1]=="single-end")

# ── Scenario C: Hybrid (PE + ONT, same sample) ─────────────────────────────
print("\n" + "="*60 + "\n  C. Hybrid — PE + ONT same sample\n" + "="*60)
sc = ROOT / "hybrid"
link(PE/"pyogenes-10_R1.fastq.gz", sc/"strain1_R1.fastq.gz")
link(PE/"pyogenes-10_R2.fastq.gz", sc/"strain1_R2.fastq.gz")
link(ONT/"GECL0521.fastq.gz", sc/"nanopore"/"strain1.fastq.gz")
# Unicycler hybrid
res = build_fofn(str(sc), fofn_path=str(sc/"samples.txt"),
                 hybrid_strategy="Hybrid (Unicycler --hybrid)")
rows = [r.split("\t") for r in (sc/"samples.txt").read_text().splitlines()[1:] if r]
print(f"  Unicycler hybrid → counts: {res['counts']}")
for r in rows: print(f"    {r[0]:20} runtype={r[1]:14} r1={pathlib.Path(r[4]).name if r[4] else '-'} extra={pathlib.Path(r[6]).name if r[6] else '-'}")
check("Hybrid: 1 sample (PE+ONT merged)", res["rows"] == 1)
check("Hybrid Unicycler: runtype=hybrid", rows and rows[0][1]=="hybrid")
check("Hybrid: r1, r2, extra(ONT) all populated", rows and rows[0][4] and rows[0][5] and rows[0][6])
# Dragonflye short_polish
res2 = build_fofn(str(sc), fofn_path=str(sc/"s2.txt"),
                  hybrid_strategy="Hybrid (Dragonflye --short_polish)")
rows2 = [r.split("\t") for r in (sc/"s2.txt").read_text().splitlines()[1:] if r]
check("Hybrid Dragonflye: runtype=short_polish", rows2 and rows2[0][1]=="short_polish")

# ── Scenario D: Assembly FASTA ─────────────────────────────────────────────
print("\n" + "="*60 + "\n  D. Assembly — FASTA input\n" + "="*60)
sd = ROOT / "assembly"
link(FA, sd/"BEN2908.fa")
res = build_fofn(str(sd), fofn_path=str(sd/"samples.txt"))
rows = [r.split("\t") for r in (sd/"samples.txt").read_text().splitlines()[1:] if r]
print(f"  counts: {res['counts']}")
for r in rows: print(f"    {r[0]:20} runtype={r[1]:12} input={pathlib.Path(r[4]).name if r[4] else '-'}")
check("Assembly: runtype=assembly", rows and rows[0][1]=="assembly")
check("Assembly: FASTA in r1 column", rows and rows[0][4].endswith(".fa"))

# ── Scenario E: recursive scan (LACEN-style subdirs) ──────────────────────
print("\n" + "="*60 + "\n  E. Recursive scan (samples in subdirs)\n" + "="*60)
se = ROOT / "recursive"
link(PE/"pyogenes-10_R1.fastq.gz", se/"run1"/"s1_R1.fastq.gz")
link(PE/"pyogenes-10_R2.fastq.gz", se/"run1"/"s1_R2.fastq.gz")
link(PE/"pyogenes-254_R1.fastq.gz", se/"run2"/"s2_R1.fastq.gz")
link(PE/"pyogenes-254_R2.fastq.gz", se/"run2"/"s2_R2.fastq.gz")
res = build_fofn(str(se), fofn_path=str(se/"samples.txt"), recursive=True)
check("Recursive ON: finds 2 samples in subdirs", res["rows"] == 2)
res_off = build_fofn(str(se), fofn_path=str(se/"s_off.txt"), recursive=False)
check("Recursive OFF: finds 0 (subdirs ignored)", res_off["rows"] == 0)

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "="*60 + "\n  SUMMARY\n" + "="*60)
p = sum(results); t = len(results)
print(f"\n  {p}/{t} real-data FOFN tests passed")
sys.exit(0 if p == t else 1)
