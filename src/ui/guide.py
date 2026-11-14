import streamlit as st
from .style import hero, note


def render(d, tt):
    hero("How to use this app", "A five-minute tour: what each page is for, what to click, and how to read the results.")
    st.markdown("**Start here:** use the menu on the left. Every page uses *scheduled* timetable data - nothing is live.")
    with st.expander("1 · Plan a journey (Journey Explorer → Plan a journey)", expanded=True):
        st.markdown("""
1. Under **From** pick a bus stop or area (type to search). You can also switch to *College or university* or *Public health facility*.
2. Do the same under **To**.
3. Choose the **date** (the feed is valid 19 Aug 2026 – 15 Feb 2027) and **Leave after** time.
4. Click **Find scheduled journeys**.
5. Pick an option (e.g. *09:02 → 10:01 · 59 min · 2 transfers*). You get:
   - the **time summary** - how much of your trip is walking, waiting and riding, and when you must leave home;
   - the **step-by-step itinerary** (which bus, where to board and get off);
   - a **map** of the route; and an **indicative fare** (open the expander and read the caveats).
""")
    with st.expander("2 · See how far you can get (Where can I reach?)"):
        st.markdown("Pick a start point, a departure time and a time budget (15-90 min). Each dot is a stop you can reach; **darker = quicker**. Good for questions like *\"what can I reach from home in 45 minutes?\"*")
    with st.expander("3 · Find the nearest stops (Nearest bus stops)"):
        st.markdown("""
Choose how to say where you are: **click the map** to drop a pin, **type coordinates** (right-click a spot in Google Maps to copy them), or **pick a place**.
You get the closest stops with distance, walking time, the route numbers that serve them and the next scheduled departures.
A warning appears if no stop is within 800 m - that spot is a *coverage gap*.
""")
    with st.expander("4 · Who has access? (Accessibility & Inclusion)"):
        st.markdown("""
- **Coverage map:** pick 300 / 500 / 800 m. Each prabhag (ward subdivision) is shaded by the share of residents within that distance of a stop. Tick *Map layers* to add stops, colleges, health facilities, or suggested new stops.
- **Service quality:** how many scheduled trips per peak hour serve people's nearby stops.
- **Inclusion & equity:** coverage for Scheduled Castes/Tribes and slum clusters.
- **Colleges & health facilities:** is each one within walking distance of a stop? *Certainly* / *possibly* appear because health-facility coordinates are rounded.
- **Reach by transit:** how many minutes by bus (09:00 weekday) from each area to the nearest college or hospital.
""")
    with st.expander("5 · Routes, stops and timetables (Routes & Schedules)"):
        st.markdown("Search a **route** to see its stops on a map, every scheduled trip, and an hourly timetable. Use **Stop departure board** for a stop's next buses, and **Service availability** to check a date is covered by the feed.")
    with st.expander("6 · Where are the problems? (Network Intelligence)"):
        st.markdown("""
Network structure and critical stops · stop and route typologies (clusters) · the **Connectivity Index** and prabhag archetypes · **Gaps & recommendations** with 25 suggested new-stop areas and CSV downloads.
""")
    st.subheader("Glossary")
    st.markdown("""
| Term | Meaning |
|---|---|
| **Prabhag** | One of 227 BMC electoral-ward areas (about 55,000 residents each) - the smallest unit with Census population |
| **Coverage (500 m)** | Share of residents with a bus stop within 500 m in a straight line |
| **Peak service** | Unique scheduled trips per hour, 08:00-10:00, serving stops within 500 m |
| **Connectivity Index** | 0-100 score combining six measures (coverage, walking distance, service, route choice, reach, facility reach) |
| **Hotspot** | A low-index prabhag whose neighbours are also low |
| **Transfer** | Changing buses during one journey |
""")
    note("<b>Remember:</b> times are timetable values (±5 min because most intermediate times are interpolated); fares are indicative; walking time is estimated from straight-line distance × 1.3. "
         "See <i>Methods & Data</i> for all limitations.")
