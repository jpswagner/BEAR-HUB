"""
Parameter documentation shown in the "?" popovers.

Condensed from the legacy Streamlit HELP texts and the Bactopia documentation
(https://bactopia.github.io/). Markdown is rendered inside rx.popover.
"""

HELP: dict[str, str] = {
    # ── General ──
    "general": (
        "**General Nextflow/Bactopia parameters**\n\n"
        "- **`-profile`** — execution environment: `docker`, `singularity` (Apptainer) "
        "or `standard` (no containers).\n"
        "- **`--max_cpus`** — global CPU limit for the Nextflow scheduler (not per task).\n"
        "- **`--max_memory`** — global memory limit (e.g. `64 GB`).\n"
        "- **`-resume`** — reuse completed steps from Nextflow's cache. Keep it **on**.\n"
        "- **Extras** — any extra Nextflow/Bactopia flags (e.g. `-with-report report.html`)."
    ),
    # ── FOFN ──
    "fofn": (
        "**FOFN generator**\n\n"
        "Scans a base folder and writes a Bactopia `samples.txt`, auto-detecting each "
        "sample's **runtype**: `paired-end`, `single-end`, `ont`, `hybrid` (PE+ONT) and "
        "`assembly` (FASTA).\n\n"
        "Columns: `sample  runtype  genome_size  species  r1  r2  extra`.\n\n"
        "- R1/R2 are matched by common patterns (R1/R2, _1/_2, A/B…).\n"
        "- Long reads (ONT) are detected by name (ont|nanopore|minion…) or via "
        "**Treat SE as ONT**.\n"
        "- **Merge multi-files** concatenates multiple files per category with commas; "
        "otherwise the largest file is used."
    ),
    "genome_size": (
        "**genome_size** — reference point for QC subsampling.\n\n"
        "- Bactopia keeps up to `genome_size × coverage` (default 100×) and **fails** a "
        "sample below `genome_size × min_coverage` (default 20×).\n"
        "- **Size = 0** disables subsampling (all reads go to the assembler).\n"
        "- Enter a value like `5.0 Mb` or pick *Custom* and type bp directly."
    ),
    # ── fastp ──
    "fastp_window": (
        "**Sliding window / cutting (fastp)**\n\n"
        "- **`-3` / `--cut_tail`** — slide the window from the 3' (tail) end.\n"
        "- **`-5` / `--cut_front`** — slide the window from the 5' (front) end.\n"
        "- **`-r` / `--cut_right`** — slide front→tail, dropping the rest on failure.\n"
        "- **`-M`** — minimum mean quality inside the window (default 20).\n"
        "- **`-W`** — window size (default 5)."
    ),
    "fastp_filters": (
        "**Quality & length filters (fastp)**\n\n"
        "- **`-q`** — minimum quality for a *qualified* base.\n"
        "- **`-l`** — minimum read length kept.\n"
        "- **`-n`** — maximum N bases allowed.\n"
        "- **`-u`** — maximum % of unqualified bases allowed."
    ),
    "fastp_adapters": (
        "**Adapters (fastp)**\n\n"
        "- **`--detect_adapter_for_pe`** — auto-detect adapters for paired-end data.\n"
        "- **`-a`** — adapter sequence for Read 1.\n"
        "- **`--adapter_sequence_r2`** — adapter sequence for Read 2."
    ),
    "fastp_processing": (
        "**Additional processing (fastp)**\n\n"
        "- **`-D` / `--dedup`** — remove duplicated reads.\n"
        "- **`-c` / `--correction`** — base correction in overlapped regions (PE only).\n"
        "- **`-g`** — trim polyG tails (NextSeq/NovaSeq).\n"
        "- **`-x` / `--trim_poly_x`** — trim polyX tails.\n"
        "- **`-p`** — overrepresented-sequence analysis.\n"
        "- **`-U` / `--umi`** — UMI processing (set location and length)."
    ),
    # ── Assembler ──
    "assembly_mode": (
        "**Assembly mode** selects the assembler and polishing for your data type.\n\n"
        "| Mode | Assembler | Polishing |\n|---|---|---|\n"
        "| Illumina PE (Shovill) | Shovill | — |\n"
        "| Illumina PE (Unicycler) | Unicycler | — |\n"
        "| Illumina SE (Shovill-SE) | Shovill | — |\n"
        "| ONT (Dragonflye) | Dragonflye | Racon / Medaka |\n"
        "| Hybrid (Unicycler --hybrid) | Unicycler | Polypolish / Pilon |\n"
        "| Hybrid (Dragonflye --short_polish) | Dragonflye | Polypolish / Pilon |"
    ),
    "shovill": (
        "**Shovill (Illumina)**\n\n"
        "- **Assembler** — `skesa` (default), `spades`, `velvet`, `megahit`.\n"
        "- **`--shovill_opts`** — extra options forwarded to Shovill.\n"
        "- **`--shovill_kmers`** — k-mer list (e.g. `31,55,79`).\n"
        "- **`--trim`** adapter trimming · **`--no_stitch`** disable PE stitching · "
        "**`--no_corr`** disable post-correction."
    ),
    "dragonflye": (
        "**Dragonflye (ONT)**\n\n"
        "- **Assembler** — `flye` (default), `miniasm`, `raven`.\n"
        "- **`--dragonflye_opts`** — extra options forwarded to Dragonflye.\n"
        "- **`--nanohq`** — Flye NanoHQ mode · **`--no_miniasm`** skip miniasm bridging."
    ),
    "unicycler": (
        "**Unicycler**\n\n"
        "- **Mode** — `conservative`, `normal` (default), `bold` (trade contiguity vs "
        "mis-assembly risk).\n"
        "- **`--min_fasta_length`** — drop contigs shorter than this (default 1000)."
    ),
    "general_assembly": (
        "**General assembly options**\n\n"
        "- **`--min_contig_len`** — drop contigs shorter than this (default 500).\n"
        "- **`--min_contig_cov`** — drop contigs below this coverage.\n"
        "- **`--reassemble`** — re-assemble simulated reads.\n"
        "- **`--no_rotate`** — do not rotate the assembly to the dnaA start gene.\n"
        "- **`--skip_qc_plot`** — skip QC plot generation."
    ),
    "polishing": (
        "**Polishing**\n\n"
        "- **`--no_polish`** — skip all polishing.\n"
        "- Short-read (hybrid): **Polypolish** (default 1 round) and **Pilon**.\n"
        "- Long-read (ONT): **Racon** (default 1 round) and **Medaka** (set a model "
        "with `--medaka_model`)."
    ),
    # ── Typing ──
    "amrfinder": (
        "**AMRFinderPlus**\n\n"
        "- **`--ident_min`** — minimum identity (0–1).\n"
        "- **`--coverage_min`** — minimum coverage (0–1).\n"
        "Detects resistance/virulence genes & point mutations (NCBI)."
    ),
    "rgi": (
        "**RGI (CARD)**\n\n"
        "- **`--use_diamond`** — faster search via DIAMOND (recommended).\n"
        "- **`--include_loose`** — include *loose* hits · **`--exclude_nudge`** drop nudged hits.\n"
        "- `--frequency`, `--category`, `--cluster`, `--display` further tune output."
    ),
    "mlst": (
        "**MLST**\n\n"
        "- **`--mlst_scheme`** — force a scheme (e.g. `ecoli`, `saureus`); leave *auto/none* "
        "to let Bactopia decide.\n"
        "- **`--mlst_minid` / `--mlst_mincov` / `--mlst_minscore`** — thresholds to accept an ST "
        "(Bactopia defaults 95 / 10 / 50).\n"
        "- **`--mlst_nopath`** — disable path resolution for specific schemes."
    ),
    "plasmidfinder": (
        "**PlasmidFinder**\n\n"
        "- **`--plasmidfinder_mincov`** — minimum coverage (0–1, default 0.6).\n"
        "- **`--plasmidfinder_threshold`** — minimum identity (0–1, default 0.9).\n"
        "Both are floats passed via `-params-file`. Identifies plasmid replicons in assemblies."
    ),
    "mashtree": (
        "**Mashtree** — fast neighbour-joining trees from Mash sketches.\n\n"
        "- **`--mashtree_kmerlength` / `--mashtree_sketchsize`** control resolution vs cost.\n"
        "- **`--mashtree_trunclength`, `--mashtree_genomesize`, `--mashtree_mindepth`, "
        "`--mashtree_sortorder`** fine-tune the build.\n"
        "- **`--mashtree_save_sketches`** keeps sketches for reuse."
    ),
    "pangenome": (
        "**Pangenome**\n\n"
        "- **Engine** — Panaroo (default, graph-based), PIRATE (multi-threshold), Roary (classic).\n"
        "- Anchor on references with **`--species`** or **`--accessions`**.\n"
        "- Phylogeny via **IQ-TREE** (`--iqtree_model`, `--iqtree_bb` ultrafast bootstrap, `--iqtree_alrt`).\n"
        "- **Scoary** gene–phenotype association via **`--scoary_traits`** (CSV/TSV).\n"
        "- **`--skip_recombination`** skips ClonalFrameML. Float thresholds "
        "(`--panaroo_threshold`, `--scoary_p_value_cutoff`) go via `-params-file`."
    ),
    # ── MERLIN ──
    "merlin": (
        "**MERLIN** — MinMER-assisted species-specific tool selection.\n\n"
        "Each ticked workflow runs as its own `nextflow run bactopia/bactopia --wf <tool>` "
        "over the selected samples. Pick the tools matching your organism."
    ),
    "samples": (
        "**Sample selection**\n\n"
        "Samples are the subfolders of the chosen Bactopia output directory (one folder "
        "per sample). An `--include` file with the selected samples is generated "
        "automatically for the run."
    ),
    "merged": (
        "**merged-results** — after a run, Bactopia aggregates per-tool TSV summaries "
        "under `<outdir>/bactopia-runs/<run>/merged-results/`. The most recent run's "
        "tables are listed here."
    ),
    # ── Step-level help (the "?" on each wizard step) ──────────────────────────
    # Each explains what the step does AND what it contributes to the command,
    # so building the pipeline command is legible step by step.
    "step_input": (
        "**Step · Input & FOFN**\n\n"
        "Pick the output directory, then scan a reads/assemblies folder to build the "
        "sample sheet (`samples.txt`). Each sample's runtype (paired-end, single-end, ont, "
        "hybrid, assembly) is detected automatically; edit it in the sample-sheet table.\n\n"
        "**Adds to the command:** `--samples samples.txt`, plus any QC-gate thresholds you set "
        "(`--min_coverage`, `--min_basepairs`, `--min_reads`, `--min_genome_size`, `--max_genome_size`)."
    ),
    "step_cleaning": (
        "**Step · Read cleaning (fastp)**\n\n"
        "Configure fastp trimming and filtering of the raw reads. Simple mode builds the "
        "option string for you; Advanced lets you type the full fastp line.\n\n"
        "**Adds to the command:** `--fastp_opts '<options>'` (skipped for pure ONT runs)."
    ),
    "step_assembler": (
        "**Step · Assembler**\n\n"
        "Choose the assembler and contig filtering for your data type. Hybrid modes combine "
        "Illumina + ONT (set per-sample via the FOFN runtype).\n\n"
        "**Adds to the command:** `--use_unicycler` / assembler flags, `--unicycler_mode`, "
        "`--min_contig_len`, `--min_contig_cov`, and polishing rounds."
    ),
    "step_typing": (
        "**Step · Typing & annotation**\n\n"
        "MLST, AMRFinderPlus and the annotator (Prokka or Bakta) run inside the main "
        "pipeline. Leave fields blank to keep Bactopia's defaults.\n\n"
        "**Adds to the command:** `--mlst_scheme`, `--amrfinderplus_organism`, `--prokka_*` or "
        "`--use_bakta --bakta_db`; float thresholds go via `-params-file`."
    ),
    "step_extras": (
        "**Step · Extras**\n\n"
        "Execution resources, Nextflow reports and any raw extra flags.\n\n"
        "**Adds to the command:** `--max_cpus`, `--max_memory`, `-resume`, "
        "`-with-report` / `-with-timeline` / `-with-trace`, plus your extra parameters."
    ),
    "step_run": (
        "**Step · Run**\n\n"
        "Review the assembled command (shown above) and launch. Nextflow streams its log "
        "here; progress and any failure are summarised as it runs."
    ),
    "step_data": (
        "**Step · Data**\n\n"
        "Choose a Bactopia output directory — its subfolders are the samples. An "
        "`--include` file with your selection is generated for the run."
    ),
    "step_tools": (
        "**Step · Tools**\n\n"
        "Pick one or more Bactopia Tools. Each runs as its own `--wf` workflow, one after "
        "another, over the selected samples."
    ),
    "step_params": (
        "**Step · Parameters**\n\n"
        "General Nextflow settings (profile, CPUs, memory, resume) plus per-tool options for "
        "the tools you picked. Empty fields keep each tool's defaults."
    ),
    "step_merlin_species": (
        "**Step · Species tools**\n\n"
        "Pick the species-specific workflows to run. Each launches as its own "
        "`nextflow run bactopia/bactopia --wf <tool>` over the selected samples."
    ),
}
