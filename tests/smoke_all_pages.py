"""Headless functional smoke test of the Streamlit app (fresh app instance per page + real button clicks).
Run:  python tests/smoke_all_pages.py
"""
import sys, time
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["🏠  Home", "🧭  Journey Explorer", "♿  Accessibility & Inclusion", "🚌  Routes & Schedules", "🕸️  Network Intelligence", "📖  How to use", "📚  Methods & Data"]
fails = 0


def fresh(page):
    at = AppTest.from_file(APP, default_timeout=300)
    at.session_state["nav"] = page
    return at


def report(name, at, t):
    global fails
    bad = len(at.exception)
    fails += bad
    print(f"{'FAIL' if bad else 'ok  '} {name:<48} {time.time() - t:5.1f}s  markdown={len(at.markdown)} tabs={len(at.tabs)} dataframes={len(at.dataframe)}")
    for e in at.exception:
        print("      ", e.value[:600])


for p in PAGES:
    at = fresh(p); t = time.time(); at.run(); report(p.strip(), at, t)

# --- interaction: plan a journey
at = fresh(PAGES[1]); at.run()
t = time.time(); [b for b in at.button if "Find scheduled" in b.label][0].click().run(); report("Journey: click 'Find scheduled journeys'", at, t)
assert at.session_state["jr"]["js"], "journey search returned no options"
print("      options:", [(round(j['duration_s'] / 60), j['transfers']) for j in at.session_state["jr"]["js"]])
t = time.time(); [b for b in at.button if "reachable" in b.label][0].click().run(); report("Journey: click 'Show reachable stops'", at, t)
assert len(at.session_state["reach"]["df"]) > 100
# nearest-stops tab: type coordinates / pick a place
at.radio(key="nn_mode").set_value("Type coordinates"); t = time.time(); at.run(); report("Journey: nearest stops (coordinates)", at, t)
at.radio(key="nn_mode").set_value("Pick a place or facility"); t = time.time(); at.run(); report("Journey: nearest stops (place)", at, t)
at.radio(key="nn_mode").set_value("Click on the map"); t = time.time(); at.run(); report("Journey: nearest stops (map mode, no click yet)", at, t)
at.session_state["nn_pt"] = (19.0760, 72.8777); t = time.time(); at.run(); report("Journey: nearest stops (map mode, pin dropped)", at, t)
# --- interaction: accessibility controls
at = fresh(PAGES[2]); at.run()
for r in (300, 800):
    t = time.time(); at.radio(key="a_r").set_value(r).run(); report(f"Accessibility: radius {r} m", at, t)
t = time.time(); at.multiselect(key="a_w").set_value(["P - North", "K - East"]).run(); report("Accessibility: ward filter", at, t)
at.radio(key="a_tab").set_value("Coverage map").run()
t = time.time(); at.multiselect(key="a_layers").set_value(["Bus stops", "Colleges & universities", "Health facilities", "Suggested new stop catchments", "Residents without a stop (heat)"]).run(); report("Accessibility: all map layers", at, t)
at.radio(key="a_tab").set_value("Colleges & health facilities").run()
t = time.time(); at.radio(key="f_g").set_value("Public hospital").run(); report("Accessibility: facility type = public hospital", at, t)
for sec in ["Service quality", "Inclusion & equity", "Colleges & health facilities", "Reach by transit"]:
    t = time.time(); at.radio(key="a_tab").set_value(sec).run(); report(f"Accessibility section: {sec}", at, t)
# --- interaction: network + routes
at = fresh(PAGES[4]); at.run()
for sec in ["Stop typology", "Route typology", "Connectivity index & archetypes", "Gaps & recommendations"]:
    t = time.time(); at.radio(key="n_tab").set_value(sec).run(); report(f"Network section: {sec}", at, t)
at.radio(key="n_tab").set_value("Connectivity index & archetypes").run()
t = time.time(); at.radio(key="n_view").set_value("Archetype").run(); report("Network: archetype colouring", at, t)
t = time.time(); at.selectbox(key="n_pick").set_value(103).run(); report("Network: inspect prabhag 103", at, t)
at = fresh(PAGES[3]); at.run()
sel = at.selectbox(key="r_sel"); t = time.time(); sel.set_value(sel.options[40]).run(); report("Routes: select another route", at, t)
t = time.time(); at.selectbox(key="b_p").set_value("Mumbai Central Station").run(); report("Routes: stop departure board for another stop", at, t)
print("\nRESULT:", "ALL PASSED" if not fails else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
