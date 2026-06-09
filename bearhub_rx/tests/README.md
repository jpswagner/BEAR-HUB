# BEAR-HUB test suite

Two test files, run with the bear-hub conda env's Python:

## Unit tests (no server needed)
```bash
cd bearhub_rx
conda run -n bear-hub python tests/test_unit.py
```
Covers: core/system, core/bactopia, core/fofn (FOFN builder + runtype logic),
core/history (run persistence), state defaults, command builder (all assembly
modes + flag validation), RunsState formatting. 102 assertions.

## UI tests (needs the app + headless Chrome on :9222)
```bash
# 1. start the app
bash run.sh &
# 2. start headless chrome with remote debugging
google-chrome --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/cdp about:blank &
# 3. run
cd bearhub_rx
conda run -n bear-hub python tests/test_ui.py
```
Covers: all 6 routes, hub equal cards, Bactopia 6-step wizard navigation +
command validation, QC thresholds accordion, Browse dialog, Tools/MERLIN
wizards, Runs & Status pages, installer/run.sh/rxconfig static checks. 63 checks.
