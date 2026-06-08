# Source Generated with Decompyle++
# File: fofn.cpython-311.pyc (Python 3.11)

"""
FOFN generator (File Of File Names) for the Bactopia main pipeline.

Ported from the legacy Streamlit page (pages/BACTOPIA.py): scans a folder for
FASTQ/FASTA files, infers each sample's runtype (paired-end, single-end, ont,
hybrid, assembly) and writes a Bactopia `samples.txt`. Reflex-free.
"""
from __future__ import annotations
import pathlib
import re
FASTQ_PATTERNS = [
    '*.fastq.gz',
    '*.fq.gz',
    '*.fastq',
    '*.fq']
FA_PATTERNS = [
    '*.fna.gz',
    '*.fa.gz',
    '*.fasta.gz',
    '*.fna',
    '*.fa',
    '*.fasta']
_EXTS = [
    '.fastq.gz',
    '.fq.gz',
    '.fastq',
    '.fq',
    '.fna.gz',
    '.fa.gz',
    '.fasta.gz',
    '.fna',
    '.fa',
    '.fasta']
PE1_PATTERNS = [
    re.compile('^(?P<root>.+?)[._-](?:R?1|1|[Aa])(?:_[0-9]{3})?$', re.IGNORECASE),
    re.compile('^(?P<root>.+?)_L\\d{3,4}_[Rr]1_\\d{3}$'),
    re.compile('^(?P<root>.+?)_L\\d{3,4}_1_\\d{3}$')]
PE2_PATTERNS = [
    re.compile('^(?P<root>.+?)[._-](?:R?2|2|[Bb])(?:_[0-9]{3})?$', re.IGNORECASE),
    re.compile('^(?P<root>.+?)_L\\d{3,4}_[Rr]2_\\d{3}$'),
    re.compile('^(?P<root>.+?)_L\\d{3,4}_2_\\d{3}$')]
LANE_SUFFIX = re.compile('(_L\\d{3,4})?(_\\d{3})?$', re.IGNORECASE)

def _drop_exts(name = None):
    for ext in _EXTS:
        if name.endswith(ext):
            
            return None, name[:-len(ext)]
        return name


def _infer_root_and_tag(path = None):
    name = LANE_SUFFIX.sub('', _drop_exts(path.name))
    for pat in PE1_PATTERNS:
        m = pat.match(name)
        if m:
            
            return None, (m.group('root'), 'PE1')
        for pat.match(name) in PE2_PATTERNS:
            if m:
                
                return None, (m.group('root'), 'PE2')
            return (name, 'SE')


def _is_probably_ont(p = None):
    pass
# WARNING: Decompyle incomplete


def _collect(base = None, patterns = None, recursive = None):
    out = []
    for pat in patterns:
        out += list(base.rglob(pat) if recursive else base.glob(pat))
        clean = []
        for p in out:
            if p.is_file():
                clean.append(p.resolve())
            except OSError:
                continue
            return sorted(set(clean))


def parse_genome_size(raw = None):
    """'5.5 Mb' -> '5500000'; placeholders -> '0'."""
    if not raw:
        raw = ''.strip()
        if raw or raw in ('(Select or Custom)', 'Custom'):
            return '0'
        
        try:
            clean = re.sub('\\s*Mb$', '', raw, flags = re.IGNORECASE).strip()
            val = float(clean)
            if val < 1000:
                val *= 1000000
            return str(int(val))
        except ValueError:
            return 



def build_fofn(*, base_dir, recursive, species, gsize, fofn_path, treat_se_as_ont, infer_ont_by_name, merge_multi, include_assemblies):
    '''Scan *base_dir* and write a Bactopia FOFN to *fofn_path*. Returns a summary.'''
    pass
# WARNING: Decompyle incomplete

