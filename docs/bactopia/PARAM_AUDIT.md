# BEAR-HUB ↔ Bactopia v4.0.0 — Main-Pipeline Parameter Audit

Legend: ✅ exposed in BEAR-HUB · 🟡 via FOFN column · ⬜ not exposed (candidate to add)

**Coverage:** 122 main-pipeline params audited · 21 exposed · 93 not yet exposed.

> Source of truth: `docs/bactopia/bactopia_params_v4.0.0.json` (extracted from the
> pinned Bactopia v4.0.0 `nextflow_schema.json` + every module `params.config`).
> Regenerate after a Bactopia bump; never hand-edit param names — validate against this file.

---

## 🐞 Confirmed parameter bugs (name mismatches that crash Nextflow)

Nextflow runs in strict mode: any `--flag` not declared in Bactopia's config aborts the
run with *"Parameter X ... is not declared in the script or config"*. Three were found:

| BEAR-HUB emitted | Correct Bactopia param | Status | Impact |
|---|---|---|---|
| `--unicycler_opts "..."` | *(none)* — use `--unicycler_mode` + `--min_contig_len` | **fixed** | crashed every Unicycler/hybrid run |
| `--skip_qc_plot` | `--skip_qc_plots` (plural) | **fixed** | checkbox defaults **True** → crashed *every* run |
| `--short_polish` / `--hybrid` | *(not CLI params)* — set FOFN `runtype` column | **fixed** (Reflex) | wrong with FOFN; now per-row runtype |
| `--ident_min` `--coverage_min` (AMRFinder) | *(Tools-only)* — `--wf amrfinderplus` | **fixed** (Reflex) | **caught by real run** — not declared in MAIN pipeline |
| `--scheme` `--minscore` `--nopath` (MLST) | *(Tools-only)* — `--wf mlst` | **fixed** (Reflex) | not declared in MAIN pipeline |

> ⚠️ **Main pipeline vs Bactopia Tools params are different sets.** The earlier
> `bactopia_params_v4.0.0.json` summed *all* module params (incl. `bactopia-tools/*`),
> so AMRFinder/MLST tool params looked "declared". They are valid only under
> `--wf <tool>`, **not** the top-level `bactopia` pipeline (which runs those tools
> with defaults). A real run (`nextflow run bactopia/bactopia ... --ident_min 0.9`)
> aborts with *"Parameter ident_min is not declared"*. The main-pipeline param set
> = top `nextflow_schema.json` + `modules/local/**/params.config` (NOT bactopia-tools).

### 2026-07 round: Pangenome / Panaroo + Bakta

All verified by running Bactopia 4.0.0's own param validation (nf-bactopia 2.1.1,
Nextflow 26.04.4) until it printed *"Validation complete."*

| Issue | Finding | Status |
|---|---|---|
| `--panaroo_opts --remove-invalid-genes` | Nextflow parses the value as a **separate param** (`removeInvalidGenes` → "not declared", run aborts). Any `*_opts` value starting with `-` was affected: panaroo/iqtree/prokka/bakta/shovill/dragonflye/fastp/clonalframeml. | **fixed** — `catalog.emit_param()` emits `--flag=value` when the value starts with `-` |
| `--scoary_correction` | Help said *"e.g. BH, bonferroni"*; real enum is `[I, B, BH, PW, EPW, P]`. `bonferroni` is `B` and the spelled-out form **fails schema validation**. | **fixed** — now a select |
| `--panaroo_mode` | Was free text; real enum `[strict, moderate, sensitive]`. | **fixed** — now a select |
| Bakta without `--bakta_db` | BEAR-HUB emitted **no** annotation flags, so Bactopia silently ran **Prokka** while the UI claimed Bakta. Scientifically wrong output, no warning. | **fixed** — `bakta_ready()` blocks the run |
| `--download_bakta` as a `--bakta_db` substitute | It is **not**. nf-bactopia enforces *"requires --bakta_db to be set when using --use_bakta"* unconditionally. With `--download_bakta` the path is the **download destination** (existence unchecked); without it, it must already contain `bakta.db`. | documented + enforced |
| `bakta_db: null` in the tool params-file | The `bakta` tool types it `Path` (not `Path?`) → *"Required parameters are missing: --bakta_db"*. It can never be nulled. | **fixed** — removed from `TOOL_NULL_PATHS` |
| `replicons` vs `bakta_replicons` | **Bactopia bug**: the two entry points are *inverted*. Main pipeline accepts only `--bakta_replicons`; the `--wf bakta` tool declares `bakta_replicons` in its schema but only `--replicons` works (the prefixed form is rejected as undeclared). | both handled per entry point |

### Assembler param scope — which assembler actually consumes what

`modules/bactopia/assembler/module.config` builds three arg blocks and
`main.nf` routes them: `ext.args`→Shovill, `ext.args2`→Dragonflye,
`ext.args3`→Unicycler. A param absent from a block is **silently ignored** by
that assembler — it still passes schema validation, so there is no error.

| Param | Shovill | Dragonflye | Unicycler |
|---|:--:|:--:|:--:|
| `min_contig_len` | ✅ `--minlen` | ✅ `--minlen` | ✅ `--min_fasta_length` |
| `min_contig_cov` | ✅ `--mincov` | ✅ `--mincov` | ❌ **no coverage filter** |
| `shovill_assembler` / `shovill_opts` / `shovill_kmers` / `no_stitch` / `no_corr` | ✅ | ❌ | ❌ |
| `dragonflye_assembler` / `dragonflye_opts` / `nanohq` / `no_polish` / `medaka_*` / `pilon_rounds` / `polypolish_rounds` / `racon_rounds` | ❌ | ✅ | ❌ |
| `unicycler_mode` / `min_component_size` / `min_dead_end_size` / `no_miniasm` / `no_rotate` | ❌ | ❌ | ✅ |

`min_contig_len` is **not** a Unicycler-only knob (the `--unicycler_opts` row
above reads that way) — it is global and reaches all three.

**`min_contig_cov` is the trap**: BEAR-HUB shows it beside `min_contig_len` under
"General assembly", implying the same scope, but Unicycler ignores it. With the
default mode (Illumina PE Unicycler) the emitted `--min_contig_cov 10` did
nothing and nothing said so. Now labelled in the UI.

**Why the flags are still emitted unconditionally:** `core/fofn.py` classifies
`runtype` **per sample from its files**, not from the UI's assembly-mode
selector. One FOFN can mix `paired-end`, `ont`, `hybrid` and `single-end` rows,
so Bactopia may run all three assemblers in a single job. Gating emission on the
UI mode would silently drop options that matching rows do need. The panels hide
by mode; the values stay live. This is deliberate — do not "fix" it by gating.

BEAR-HUB's `min_contig_len` default was **1000**, overriding Bactopia's 500;
reverted to **500** so the pipeline default is not silently changed.

Coverage after this round: pangenome **25 → 56** fields (all 9 Panaroo params, incl. the
4 that were missing: `panaroo_alignment`, `panaroo_aligner`, `panaroo_family_threshold`,
`panaroo_len_dif_percent`); main-pipeline Bakta **2 → 21**; `bakta` promoted to a
`DETAILED` tool panel. The `number`-typed params (`panaroo_family_threshold`,
`panaroo_len_dif_percent`, `roary_iv`) were added to `FLOAT_TOOL_PARAMS` so they route
through `-params-file` — nf-schema rejects them from the CLI.

### The `--hybrid` / `--short_polish` design issue (needs the restructure)

`--hybrid` and `--ont` are **single-sample input modifiers** (used with `--sample/--r1/--r2/--se`).
BEAR-HUB always runs from a **FOFN** (`--samples samples.txt`), where assembly type is set
**per row** via the `runtype` column (`hybrid`, `short_polish`, `ont`, `paired-end`, …).
So the global `--hybrid` flag is redundant and `--short_polish` is invalid.

**Correct fix (apply during the Reflex port / FOFN builder):**
- Drop the `--hybrid` / `--short_polish` CLI flags from the assembler flags.
- Thread the chosen hybrid strategy into the FOFN builder: for PE+ONT rows, emit
  `runtype = "short_polish"` for the Dragonflye strategy, `runtype = "hybrid"` for Unicycler.
- `pages/BACTOPIA.py:309-313` already writes `runtype="hybrid"` for PE+ONT; that branch is the hook point.

## 🔧 BEAR-HUB intentional overrides (differ from Bactopia defaults)

These values are set in `state.py` (`DEFAULT_BOPTS` / `DEFAULT_BFLAGS`) and emitted
unconditionally so they always reach Bactopia regardless of its own defaults.
Change here **and** in `state.py` if a different value is wanted.

| Param | Flag | BEAR-HUB default | Bactopia default | Reason |
|---|---|---|---|---|
| `min_contig_len` | `--min_contig_len` | 500 (always emitted) | 500 | ~~1000~~ **reverted 2026-07** to match Bactopia. No longer an override. Global: reaches Shovill/Dragonflye `--minlen` **and** Unicycler `--min_fasta_length` |
| `min_contig_cov` | `--min_contig_cov` | **10** | 2 | Realistic minimum coverage for Illumina data. ⚠️ Shovill/Dragonflye only — **Unicycler ignores it** (no coverage filter in its arg block) |
| `amr_ident_min` | `--ident_min` | **0.9** | -1 (auto) | Explicit threshold instead of the tool's auto-calibration |
| `amr_coverage_min` | `--coverage_min` | **0.5** | 0.5 | Matches Bactopia — no override |
| `fastp_M` | `-M` in `--fastp_opts` | **20** | 15 | Stricter sliding-window quality threshold |
| `fastp_W` | `-W` in `--fastp_opts` | **5** | 4 | Slightly wider sliding window |
| `skip_qc_plot` (UI key) | `--skip_qc_plots` | **True** | false | Skip QC plot generation (speeds up runs; uncheck to re-enable) |
| `with_report` | `-with-report` | **True** | false | Nextflow HTML report enabled by default |
| `with_timeline` | `-with-timeline` | **True** | false | Nextflow timeline enabled by default |
| `with_trace` | `-with-trace` | **True** | false | Nextflow trace enabled by default |

> `fastp_dash3` (`-3` cut-tail) is also **True** by default — it is not a Bactopia
> param directly but is embedded in the `--fastp_opts` string built by `_fastp_opts()`.

## ⭐ High-value params to add (currently unexposed, sensible to surface)

- **QC gates** (Gather/QC): `min_coverage` (10), `min_basepairs` (2241820), `min_reads` (7472),
  `min_genome_size` / `max_genome_size`, `coverage` (target, default 100) — these define when a
  sample fails QC; users frequently need to relax them for low-yield isolates.
- **Assembly QC:** contig-length filters, `checkm` / `busco` toggles.
- **Annotation:** `--genus` / `--species` / `--proteins` (Prokka/Bakta), `use_bakta`.

See the per-group tables below for the full ⬜ list.

## Required Parameters  (10)

| param | default | status | note |
|---|---|---|---|
| `accession` | `null` | 🟡 | Sample name to use for the input sequences
 |
| `accessions` | `null` | 🟡 | A file containing ENA/SRA Experiment accessions or NCBI Assembly acces |
| `assembly` | `` | 🟡 | A assembled genome in compressed FASTA format. (requires --sample) |
| `fastqs` | `` | ⬜ | A FOFN with sample names and paths to FASTQ/FASTAs to process
 |
| `hybrid` | `` | ✅ | Treat `--se` as long reads for hybrid assembly.  (requires --r1, --r2, |
| `ont` | `` | 🟡 | Treat `--se` as long reads for analysis. (requires --sample) |
| `r1` | `` | 🟡 | First set of compressed (gzip) paired-end FASTQ reads (requires --r2 a |
| `r2` | `` | 🟡 | Second set of compressed (gzip) paired-end FASTQ reads (requires --r1  |
| `sample` | `` | 🟡 | Sample name to use for the input sequences
 |
| `se` | `` | 🟡 | Compressed (gzip) single-end FASTQ reads  (requires --sample) |

## Gather Samples Parameters  (10)

| param | default | status | note |
|---|---|---|---|
| `attempts` | `3` | ⬜ | Maximum times to attempt downloads |
| `max_genome_size` | `18040666` | ⬜ | The maximum estimated genome size allowed for the input sequence to co |
| `min_basepairs` | `2241820` | ⬜ | The minimum amount of basepairs required to continue downstream analys |
| `min_coverage` | `10` | ⬜ | The minimum amount of coverage required to continue downstream analyse |
| `min_genome_size` | `100000` | ⬜ | The minimum estimated genome size allowed for the input sequence to co |
| `min_proportion` | `0.5` | ⬜ | The minimum proportion of basepairs for paired-end reads to continue d |
| `min_reads` | `7472` | ⬜ | The minimum amount of reads required to continue downstream analyses. |
| `no_cache` | `false` | ⬜ | Skip caching the assembly summary file from ncbi-genome-download |
| `skip_fastq_check` | `false` | ⬜ | Skip minimum requirement checks for input FASTQs |
| `use_ena` | `false` | ⬜ | Download FASTQs from ENA |

## QC Reads Parameters  (25)

| param | default | status | note |
|---|---|---|---|
| `adapter_k` | `23` | ⬜ | Kmer length used for finding adapters. |
| `adapters` | `"${baseDir}/data/EMPTY_ADAPTERS"` | ⬜ | A FASTA file containing adapters to remove |
| `ftm` | `5` | ⬜ | If positive, right-trim length to be equal to zero, modulo this number |
| `hdist` | `1` | ⬜ | Maximum Hamming distance for ref kmers (subs only) |
| `ktrim` | `r` | ⬜ | Trim reads to remove bases matching reference kmers |
| `maq` | `10` | ⬜ | Reads with average quality (after trimming) below this will be discard |
| `maxcor` | `1` | ⬜ | Max number of corrections within a 20bp window |
| `mink` | `11` | ⬜ | Look for shorter kmers at read tips down to this length, when k-trimmi |
| `minlength` | `35` | ⬜ | Reads shorter than this after trimming will be discarded |
| `nanoplot_opts` | `""` | ⬜ | Extra NanoPlot options in quotes |
| `ont_minlength` | `1000` | ⬜ | ONT Reads shorter than this will be discarded |
| `ont_minqual` | `0` | ⬜ | Minimum average read quality filter of ONT reads |
| `phix` | `"${baseDir}/data/EMPTY_PHIX"` | ⬜ | phiX174 reference genome to remove |
| `phix_k` | `31` | ⬜ | Kmer length used for finding phiX174. |
| `porechop_opts` | `""` | ⬜ | Extra Porechop options in quotes |
| `qout` | `33` | ⬜ | PHRED offset to use for output FASTQs |
| `qtrim` | `rl` | ⬜ | Trim read ends to remove bases with quality below trimq. |
| `sampleseed` | `42` | ⬜ | Set to a positive number to use as the random number generator seed fo |
| `skip_error_correction` | `false` | ⬜ | FLASH error correction of reads will be skipped. |
| `skip_qc` | `false` | ⬜ | The QC step will be skipped and it will be assumed the inputs sequence |
| `skip_qc_plots` | `false` | ✅ | QC Plot creation by FastQC or Nanoplot will be skipped |
| `tbo` | `t` | ⬜ | Trim adapters based on where paired reads overlap |
| `tossjunk` | `t` | ⬜ | Discard reads with invalid characters as bases |
| `tpe` | `t` | ⬜ | When kmer right-trimming, trim both reads to the minimum length of eit |
| `trimq` | `6` | ⬜ | Regions with average quality BELOW this will be trimmed if qtrim is se |

## Assemble Genome Parameters  (22)

| param | default | status | note |
|---|---|---|---|
| `contig_namefmt` | `null` | ⬜ | Format of contig FASTA IDs in 'printf' style |
| `dragonflye_assembler` | `flye` | ✅ | Assembler to be used by Dragonflye |
| `medaka_model` | `''` | ✅ | The model to use for Medaka polishing |
| `medaka_steps` | `0` | ⬜ | The number of Medaka polishing steps to conduct |
| `min_component_size` | `1000` | ⬜ | Graph dead ends smaller than this size (bp) will be removed from the f |
| `min_contig_cov` | `2` | ✅ | Minimum contig coverage <0=AUTO> |
| `min_contig_len` | `500` | ✅ | Minimum contig length <0=AUTO> |
| `min_dead_end_size` | `1000` | ⬜ | Graph dead ends smaller than this size (bp) will be removed from the f |
| `min_polish_size` | `10000` | ⬜ | Contigs shorter than this value (bp) will not be polished using Pilon |
| `no_corr` | `null` | ✅ | Disable post-assembly correction |
| `no_miniasm` | `false` | ✅ | Skip miniasm+Racon bridging |
| `no_polish` | `false` | ✅ | Skip the assembly polishing step |
| `no_rotate` | `false` | ✅ | Do not rotate completed replicons to start at a standard gene |
| `no_stitch` | `null` | ✅ | Disable read stitching for paired-end reads |
| `racon_steps` | `1` | ⬜ | The number of Racon polishing steps to conduct |
| `reassemble` | `` | ✅ | If reads were simulated, they will be used to create a new assembly. |
| `shovill_assembler` | `skesa` | ✅ | Assembler to be used by Shovill |
| `shovill_kmers` | `null` | ✅ | K-mers to use <blank=AUTO> |
| `shovill_opts` | `null` | ✅ | Extra assembler options in quotes |
| `trim` | `null` | ✅ | Enable adaptor trimming |
| `unicycler_mode` | `normal` | ✅ | Bridging mode used by Unicycler |
| `use_unicycler` | `false` | ✅ | Use unicycler for paired end assembly |

## Assembly QC Parameters  (16)

| param | default | status | note |
|---|---|---|---|
| `aai_strain` | `0.9` | ⬜ | AAI threshold used to identify strain heterogeneity |
| `checkm_ali` | `null` | ⬜ | Generate HMMER alignment file for each bin |
| `checkm_length` | `0.7` | ⬜ | Percent overlap between target and query |
| `checkm_multi` | `10` | ⬜ | Maximum number of multi-copy phylogenetic markers before defaulting to |
| `checkm_nt` | `null` | ⬜ | Generate nucleotide gene sequences for each bin |
| `checkm_unique` | `10` | ⬜ | Minimum number of unique phylogenetic markers required to use lineage- |
| `contig_thresholds` | `0,1000,10000,100000,250000,1000000` | ⬜ | Comma-separated list of contig length thresholds |
| `force_domain` | `null` | ⬜ | Use domain-level sets for all bins |
| `full_tree` | `null` | ⬜ | Use the full tree (requires ~40GB of memory) for determining lineage o |
| `ignore_thresholds` | `null` | ⬜ | Ignore model-specific score thresholds |
| `individual_markers` | `null` | ⬜ | Treat marker as independent |
| `no_refinement` | `null` | ⬜ | Do not perform lineage-specific marker set refinement |
| `plots_format` | `pdf` | ⬜ | Save plots in specified format |
| `run_checkm` | `` | ⬜ | Run CheckM in the assembly QC step |
| `skip_adj_correction` | `null` | ⬜ | Do not exclude adjacent marker genes when estimating contamination |
| `skip_pseudogene_correction` | `null` | ⬜ | Skip identification and filtering of pseudogene |

## Annotate Genome Parameters  (13)

| param | default | status | note |
|---|---|---|---|
| `addmrna` | `` | ⬜ | Add 'mRNA' features for each 'CDS' feature |
| `cdsrnaolap` | `` | ⬜ | Allow [tr]RNA to overlap CDS |
| `centre` | `Bactopia` | ⬜ | Sequencing centre ID |
| `compliant` | `false` | ⬜ | Force Genbank/ENA/DDJB compliance |
| `nogenes` | `` | ⬜ | Do not add 'gene' features for each 'CDS' feature |
| `norrna` | `` | ⬜ | Don't run rRNA search |
| `notrna` | `` | ⬜ | Don't run tRNA search |
| `prokka_coverage` | `80` | ⬜ | Minimum coverage on query protein |
| `prokka_evalue` | `1e-09` | ⬜ | Similarity e-value cut-off |
| `rawproduct` | `` | ⬜ | Do not clean up /product annotation |
| `rfam` | `` | ⬜ | Enable searching for ncRNAs with Infernal+Rfam |
| `rnammer` | `` | ⬜ | Prefer RNAmmer over Barrnap for rRNA prediction |
| `skip_prodigal_tf` | `` | ⬜ | If a Prodigal training file was found, it will not be used |

## Sequence Type Parameters  (10)

| param | default | status | note |
|---|---|---|---|
| `mlst_ariba_no_clean` | `` | ⬜ | Do not clean up intermediate files created by Ariba. |
| `mlst_assembled_threshold` | `0.95` | ⬜ | If proportion of gene assembled (regardless of into how many contigs)  |
| `mlst_assembly_cov` | `50` | ⬜ | Target read coverage when sampling reads for assembly |
| `mlst_gene_nt_extend` | `30` | ⬜ | Max number of nucleotides to extend ends of gene matches to look for s |
| `mlst_min_scaff_depth` | `10` | ⬜ | Minimum number of read pairs needed as evidence for scaffold link betw |
| `mlst_nucmer_breaklen` | `200` | ⬜ | Value to use for -breaklen when running nucmer |
| `mlst_nucmer_min_id` | `90` | ⬜ | Minimum alignment identity (delta-filter -i) |
| `mlst_nucmer_min_len` | `20` | ⬜ | Minimum alignment identity (delta-filter -i) |
| `mlst_spades_options` | `` | ⬜ | Extra options to pass to Spades assembler |
| `mlst_unique_threshold` | `0.03` | ⬜ | If proportion of bases in gene assembled more than once is <= this val |

## Antimicrobial Resistance Parameters  (7)

| param | default | status | note |
|---|---|---|---|
| `amr_coverage_min` | `0.5` | ⬜ | Minimum coverage of the reference protein |
| `amr_ident_min` | `-1` | ⬜ | Minimum identity for nucleotide hit (0..1). -1 means use a curated thr |
| `amr_organism` | `` | ⬜ | Taxonomy group: Campylobacter, Escherichia, Klebsiella Salmonella, Sta |
| `amr_plus` | `` | ⬜ | Add the plus genes to the report |
| `amr_report_common` | `` | ⬜ | Suppress proteins common to a taxonomy group |
| `amr_translation_table` | `11` | ⬜ | NCBI genetic code for translated BLAST |
| `skip_amr` | `` | ⬜ | Skip running AMRFinder+. |

## Max Job Request Parameters  (5)

| param | default | status | note |
|---|---|---|---|
| `max_cpus` | `4` | ✅ | Maximum number of CPUs that can be requested for any single job. |
| `max_downloads` | `3` | ⬜ | Maximum number of samples to download at a time |
| `max_memory` | `32` | ✅ | Maximum amount of memory (in GB) that can be requested for any single  |
| `max_retry` | `3` | ⬜ | Maximum times to retry a process before allowing it to fail. |
| `max_time` | `120` | ⬜ | Maximum amount of time (in minutes) that can be requested for any sing |

## Optional Parameters  (4)

| param | default | status | note |
|---|---|---|---|
| `keep_all_files` | `false` | ⬜ | Keeps all analysis files created |
| `outdir` | `./` | ✅ | Base directory to write results to |
| `run_name` | `bactopia` | ⬜ | Name of the directory to hold results |
| `skip_compression` | `false` | ⬜ | Ouput files will not be compressed |
