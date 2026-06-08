# Recovered Reflex source (decompiled) — reference only

The Reflex app's `.py` source was lost (never committed; only `.pyc` bytecode remained).
This folder is the **recovery**, produced on the dev box from the surviving bytecode.

- `src/` — decompiled Python (via `pycdc`, from the **3.10** bytecode, which decompiles
  more completely than the 3.11 build). **Not runnable.** Functions that the decompiler
  could not fully reconstruct are marked `# WARNING: Decompyle incomplete`.

> **Archive lives on the `reflex` branch.** To keep `dev` clean, only the decompiled
> `src/` reference is kept here. The raw `.pyc` bytecode (`_recovered/bytecode/`) and the
> full `pycdas` disassembly (`_recovered/disasm/`) — authoritative when `src/` has a gap —
> are committed on the **`reflex`** branch. Get them with:
> `git checkout reflex -- bearhub_rx/_recovered/bytecode bearhub_rx/_recovered/disasm`

**Do not import or ship this.** Use it together with the working Streamlit app
(`pages/BACTOPIA.py`, `utils/`) and the surviving `bearhub/data/` to rebuild clean source.
See `docs/reflex/MIGRATION.md` for the plan. Delete this folder once `bearhub/` is rebuilt.
