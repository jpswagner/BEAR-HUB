"""UI test suite via CDP headless Chrome."""
import asyncio, json, urllib.request, base64, sys, pathlib
import websockets

BASE = "http://localhost:3200"
PASS = "✅"; FAIL = "❌"
results = []

def check(name, cond):
    ok = bool(cond)
    results.append((ok, name))
    print(f"  {PASS if ok else FAIL}  {name}")
    return ok

def section(t):
    print(f"\n{'='*55}\n  {t}\n{'='*55}")

async def setup():
    targets = json.load(urllib.request.urlopen(f"{BASE.replace('3200','9222')}/json"))
    ws_url = next(t for t in targets if t.get("type") == "page")["webSocketDebuggerUrl"]
    return await websockets.connect(ws_url, max_size=20_000_000)

async def cdp(ws, m, p=None, _id=[0]):
    _id[0] += 1; mid = _id[0]
    await ws.send(json.dumps({"id": mid, "method": m, "params": p or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == mid: return msg.get("result", {})

async def js(ws, expr):
    r = await cdp(ws, "Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r.get("result", {}).get("value")

async def nav(ws, route, sentinel="v4.0.0", timeout=25):
    """Hard-reload to reset Reflex state, then wait for sentinel text."""
    # window.location.href forces a full reload (resets backend state)
    await js(ws, f"window.location.href = '{BASE}{route}'")
    for _ in range(timeout * 2):
        t = await js(ws, "document.body.innerText")
        if isinstance(t, str) and sentinel in t:
            return
        await asyncio.sleep(0.5)


async def text(ws):
    return await js(ws, "document.body.innerText")

async def shot(ws, name):
    r = await cdp(ws, "Page.captureScreenshot", {"format": "png"})
    p = f"/tmp/ui_{name}.png"
    pathlib.Path(p).write_bytes(base64.b64decode(r["data"]))
    return p

async def click_next(ws, n=1, wait_for=None):
    for _ in range(n):
        await js(ws, "Array.from(document.querySelectorAll('button')).find(b=>/Next|Review/i.test(b.innerText))?.click()")
        if wait_for:
            for _ in range(20):
                t = await js(ws, "document.body.innerText")
                if wait_for in (t or ""):
                    break
                await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(2.5)

async def main():
    ws = await setup()
    await cdp(ws, "Page.enable")
    await cdp(ws, "Emulation.setVisibleSize", {"width": 1400, "height": 900})

    # ── 1. Route availability ─────────────────────────────────────────────
    section("1. Route availability (HTTP 200)")
    import urllib.request as ur
    for route in ["/", "/bactopia", "/tools", "/merlin", "/runs", "/status"]:
        try:
            code = ur.urlopen(f"{BASE}{route}", timeout=5).getcode()
            check(f"GET {route} → 200", code == 200)
        except Exception as e:
            check(f"GET {route} → 200", False)

    # ── 2. Hub page ───────────────────────────────────────────────────────
    section("2. Hub — cards equal height")
    await nav(ws, "/")
    t = await text(ws)
    check("Hub: 'BEAR-HUB' title present",      "BEAR-HUB" in t)
    check("Hub: all 4 cards present",
          all(x in t for x in ["Bactopia", "Bactopia Tools", "MERLIN", "Status"]))
    check("Hub: Runs in sidebar",               "Runs" in t)
    check("Hub: version badge present",         "v4.0.0" in t)
    # Check cards have same height via DOM
    heights = await js(ws, """
        (()=>{
          const cards = document.querySelectorAll('a[href] .rt-CardRoot, a[href] [data-radix-scroll-area-viewport], a[href] .rt-BaseCard');
          if(!cards.length) {
            // fallback: get all card elements inside the grid
            const grid = document.querySelector('[style*="grid"]');
            if(!grid) return [];
            return Array.from(grid.querySelectorAll('a')).map(a=>Math.round(a.offsetHeight));
          }
          return Array.from(cards).map(c=>Math.round(c.offsetHeight));
        })()
    """)
    if heights and len(heights) >= 4:
        check("Hub: all 4 cards same height", len(set(heights[:4])) == 1)
    else:
        check("Hub: card heights DOM accessible", bool(heights))
    await shot(ws, "hub")

    # ── 3. Bactopia wizard — all 6 steps ─────────────────────────────────
    section("3. Bactopia — 6-step wizard navigation")
    await nav(ws, "/bactopia")
    t = await text(ws)
    check("Step 1 active: 'Input & FOFN'",       "Input & FOFN" in t)
    check("Step bar shows 6 steps",
          all(s in t for s in ["Read cleaning","Assembler","Typing","Extras","Run"]))
    check("Step 1: Output directory field",       "--outdir" in t)
    check("Step 1: Generate FOFN card",           "Generate FOFN" in t)
    check("Step 1: QC thresholds accordion",      "QC thresholds" in t)

    # step 2
    await click_next(ws, wait_for="fastp")
    t = await text(ws)
    check("Step 2: fastp options shown",          "fastp" in t.lower())

    # step 3
    await click_next(ws, wait_for="Assembly mode")
    t = await text(ws)
    check("Step 3: Assembly mode selector",       "Assembly mode" in t)
    check("Step 3: assembler options present",    "Shovill" in t or "assembler" in t.lower())

    # step 4 Typing
    await click_next(ws, wait_for="AMRFinder")
    t = await text(ws)
    check("Step 4: AMRFinderPlus present",        "AMRFinder" in t)
    check("Step 4: MLST present",                 "MLST" in t)

    # step 5 Extras
    await click_next(ws, wait_for="-profile")
    t = await text(ws)
    check("Step 5: -profile selector",            "-profile" in t)
    check("Step 5: -resume switch",               "-resume" in t)
    check("Step 5: Nextflow reports",             "-with-report" in t)

    # step 6 Run
    await click_next(ws, wait_for="nextflow run")
    t = await text(ws)
    check("Step 6: Command preview block",        "nextflow run" in t)
    # Validate command flags
    cmd = ""
    idx = t.find("nextflow run")
    if idx != -1:
        cmd = t[idx:idx+1000]
    check("Cmd: --use_unicycler present",         "--use_unicycler" in cmd)
    check("Cmd: --unicycler_mode present",        "--unicycler_mode" in cmd)
    check("Cmd: --skip_qc_plots (plural)",        "--skip_qc_plots" in cmd)
    check("Cmd: --min_contig_len 1000",           "--min_contig_len 1000" in cmd)
    check("Cmd: --ident_min 0.9",                 "--ident_min 0.9" in cmd)
    check("Cmd: --hybrid ABSENT",                 "--hybrid" not in cmd)
    check("Cmd: --unicycler_opts ABSENT",         "--unicycler_opts" not in cmd)
    check("Cmd: --short_polish ABSENT",           "--short_polish" not in cmd)
    check("Cmd: --skip_qc_plot  (singular) ABSENT","--skip_qc_plot " not in cmd)
    await shot(ws, "bactopia_run")

    # ── 4. QC thresholds accordion ────────────────────────────────────────
    section("4. Bactopia step 1 — QC thresholds")
    await nav(ws, "/bactopia")
    # Open accordion — wait for open state
    for _ in range(3):
        await js(ws, """
            const h3 = Array.from(document.querySelectorAll('h3'))
                           .find(el=>/QC/i.test(el.textContent));
            if(h3){const btn=h3.querySelector('button')||h3; btn.click();}
        """)
        await asyncio.sleep(2)
        t = await text(ws)
        if "--min_coverage" in t:
            break
    check("QC accordion: min_coverage field",    "--min_coverage" in t)
    check("QC accordion: min_basepairs field",   "--min_basepairs" in t)
    check("QC accordion: defaults note shown",   "coverage=10" in t)

    # ── 5. Browse dialog ──────────────────────────────────────────────────
    section("5. Browse dialog (directory picker)")
    await nav(ws, "/bactopia")
    # Click Browse and wait for dialog
    for _ in range(3):
        await js(ws, "Array.from(document.querySelectorAll('button')).find(b=>/Browse/i.test(b.innerText))?.click()")
        await asyncio.sleep(3)
        t = await text(ws)
        if "Select a directory" in t:
            break
    check("Browse: dialog opens",               "Select a directory" in t)
    check("Browse: Up button present",           "Up" in t)
    check("Browse: Home button present",         "Home" in t)
    check("Browse: Cancel button present",       "Cancel" in t)

    # ── 6. Bactopia Tools page ────────────────────────────────────────────
    section("6. Bactopia Tools")
    await nav(ws, "/tools")
    t = await text(ws)
    check("Tools: hero title present",           "Bactopia Tools" in t)
    check("Tools: 4-step wizard",                "Tools" in t and "Parameters" in t)
    check("Tools: samples field",                "samples" in t.lower())

    # step 2 tools
    await click_next(ws, wait_for="Antimicrobial")
    t = await text(ws)
    check("Tools step 2: tool categories",
          any(cat in t for cat in ["Antimicrobial","Typing","Quality"]))

    # ── 7. MERLIN page ────────────────────────────────────────────────────
    section("7. MERLIN")
    await nav(ws, "/merlin")
    t = await text(ws)
    check("MERLIN: hero title present",          "MERLIN" in t)
    check("MERLIN: 4-step wizard",               "Species tools" in t)
    await click_next(ws, wait_for="Escherichia")
    t = await text(ws)
    check("MERLIN step 2: species listed",
          any(s in t for s in ["Escherichia","Staphylococcus","Klebsiella","Salmonella"]))

    # ── 8. Runs page ──────────────────────────────────────────────────────
    section("8. Runs & History")
    await nav(ws, "/runs")
    t = await text(ws)
    check("Runs: hero title present",            "Runs" in t)
    check("Runs: Refresh button present",        "Refresh" in t)
    check("Runs: empty state or table shown",
          "No runs yet" in t or "ID" in t)

    # ── 9. Status page ───────────────────────────────────────────────────
    section("9. Status page")
    await nav(ws, "/status")
    t = await text(ws)
    check("Status: hero title present",          "System Status" in t)
    check("Status: tool rows present",
          all(x in t for x in ["Bactopia","Nextflow","Java","Docker"]))
    check("Status: Refresh button",              "Refresh" in t)
    await shot(ws, "status")

    # ── 10. install_bear.sh ───────────────────────────────────────────────
    section("10. install_bear.sh — static checks")
    import subprocess
    r = subprocess.run(["bash", "-n", str(BEARHUB_RX.parent / "install_bear.sh")],
                       capture_output=True, text=True)
    check("install_bear.sh syntax valid",        r.returncode == 0)
    content = pathlib.Path(str(BEARHUB_RX.parent / "install_bear.sh")).read_text()
    check("install_bear.sh: no streamlit in env create", "streamlit" not in content.split("setup_bear_hub_env")[1].split("setup_bactopia_env")[0] if "setup_bear_hub_env" in content else False)
    check("install_bear.sh: reflex in env create",       "reflex" in content)
    check("install_bear.sh: configure_reflex exists",    "configure_reflex" in content)
    check("install_bear.sh: run.sh in next steps",       "run.sh" in content)

    # ── 11. run.sh + rxconfig.py ─────────────────────────────────────────
    section("11. run.sh + rxconfig.py")
    r2 = subprocess.run(["bash", "-n", str(BEARHUB_RX / "run.sh")],
                        capture_output=True, text=True)
    check("run.sh syntax valid",                 r2.returncode == 0)
    rx_cfg = pathlib.Path(str(BEARHUB_RX / "rxconfig.py")).read_text()
    check("rxconfig: app_name='bearhub'",        "bearhub" in rx_cfg)
    check("rxconfig: frontend_port=3200",        "3200" in rx_cfg)
    check("rxconfig: backend_port=8200",         "8200" in rx_cfg)

    await ws.close()

    # ── Summary ───────────────────────────────────────────────────────────
    section("SUMMARY")
    passed = sum(1 for ok, _ in results if ok)
    total  = len(results)
    failed = [name for ok, name in results if not ok]
    print(f"\n  {passed}/{total} UI tests passed")
    if failed:
        print(f"\n  FAILED ({len(failed)}):")
        for name in failed: print(f"    {FAIL} {name}")
        return 1
    print(f"\n  ALL {total} UI TESTS PASSED ✅")
    return 0

sys.exit(asyncio.run(main()))
