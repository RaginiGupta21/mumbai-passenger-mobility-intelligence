"""Opens both pages without a browser and clicks the main controls.   Run:  python tests/smoke_app.py"""
import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
fails = 0


def check(name, at):
    global fails
    bad = len(at.exception); fails += bad
    print(("FAIL " if bad else "ok   ") + name)
    for e in at.exception: print("     ", e.value[:500])


at = AppTest.from_file(APP, default_timeout=120); at.run(); check("Service gap map opens", at)
assert len(at.selectbox) >= 1
for label in list(at.selectbox(key="measure").options):
    at.selectbox(key="measure").set_value(label).run(); check(f"  map coloured by: {label}", at)
at.checkbox(key="show_stops").set_value(True).run(); check("  show bus stops", at)
at.checkbox(key="show_heat").set_value(True).run(); check("  show residents without a stop", at)
def submit(text):
    at.text_input(key="q").set_value(text)
    [b for b in at.button if b.label == "Find"][0].click().run()


submit("19.18, 72.84"); check("search: pasted coordinates", at); assert at.session_state["cands"][0]["kind"] == "coords"
submit("malad"); check("search: place name (no internet needed for stop names)", at); assert len(at.session_state["cands"]) >= 1
submit("zzzzqqqq"); check("search: nothing found", at)
submit("18.50, 72.50"); check("search: point outside Mumbai", at)
submit("19.20, 72.95"); check("search: point in another ward", at)
submit("19.18, 72.84")
at.radio(key="page").set_value("Where to fix it").run(); check("Where to fix it opens (with a searched pin)", at)
print("\nRESULT:", "ALL PASSED" if not fails else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
