# Recovered Reflex source (decompiled) — reference only

The Reflex app's `.py` source was lost (never committed; only `.pyc` bytecode remained).
This folder is the **recovery**, produced on the dev box from the surviving bytecode.

- `src/` — decompiled Python (via `pycdc`, from the **3.10** bytecode, which decompiles
  more completely than the 3.11 build). **Not runnable.** Functions that the decompiler
  could not fully reconstruct are marked `# WARNING: Decompyle incomplete`.
- `disasm/` — full `pycdas` disassembly of the **latest 3.11** bytecode. Authoritative
  when `src/` has a gap: the exact logic can be read/reconstructed from the disassembly.

**Do not import or ship this.** Use it together with the working Streamlit app
(`pages/BACTOPIA.py`, `utils/`) and the surviving `bearhub/data/` to rebuild clean source.
See `docs/reflex/MIGRATION.md` for the plan. Delete this folder once `bearhub/` is rebuilt.
