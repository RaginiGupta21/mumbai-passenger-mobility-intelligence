"""Folium helpers with a soft, muted look (no neon, no black)."""
import folium
from .config import PALETTE as C

BASE = [19.07, 72.88]
TILES = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"   # keyless CARTO light basemap (free, attribution required)
ATTR = "© OpenStreetMap contributors © CARTO"
LEG_COLORS = [C["teal"], C["clay"], C["navy"], C["sage"], C["rose"], C["gold"]]
TYPE_COLORS = {"Major hubs": "#B5707A", "Trunk-corridor stops": "#C9A25B", "Local stops": "#7FA38F", "Minor local stops": "#7FA38F",
               "Thin-service stops": "#41596E"}


def base_map(center=None, zoom=11, height=None):
    m = folium.Map(location=center or BASE, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer(tiles=TILES, attr=ATTR, name="Light basemap", max_zoom=19, subdomains="abcd").add_to(m)
    return m


def fit(m, points):
    if points:
        la = [p[0] for p in points]; lo = [p[1] for p in points]
        m.fit_bounds([[min(la), min(lo)], [max(la), max(lo)]], padding=(30, 30))


def ramp(v, vmin, vmax, colors=("#E9D8C4", "#D9A86B", "#8FB3A5", "#3F7C85", "#2F4F63")):
    """Piece-wise linear colour ramp -> hex."""
    t = 0 if vmax == vmin else max(0.0, min(1.0, (v - vmin) / (vmax - vmin)))
    n = len(colors) - 1; i = min(int(t * n), n - 1); f = t * n - i
    a = [int(colors[i][k:k + 2], 16) for k in (1, 3, 5)]; b = [int(colors[i + 1][k:k + 2], 16) for k in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[j] + (b[j] - a[j]) * f) for j in range(3))


def points_layer(m, df, lat, lon, tip_cols, tip_aliases, color="#2F4F63", color_col=None, radius=2.5, radius_col=None, opacity=.8, name=None):
    """Fast point layer: one GeoJSON blob rendered client-side (instead of thousands of Python marker objects)."""
    feats = []
    for r in df.itertuples(index=False):
        d = r._asdict(); p = {c: (round(d[c], 3) if isinstance(d[c], float) else d[c]) for c in tip_cols}
        p["_c"] = d[color_col] if color_col else color
        p["_r"] = float(d[radius_col]) if radius_col else radius
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(d[lon]), float(d[lat])]}, "properties": p})
    folium.GeoJson({"type": "FeatureCollection", "features": feats}, name=name,
                   marker=folium.CircleMarker(radius=radius, weight=0, fill=True, fill_opacity=opacity),
                   style_function=lambda f: {"fillColor": f["properties"]["_c"], "color": f["properties"]["_c"], "radius": f["properties"]["_r"], "fillOpacity": opacity, "weight": 0},
                   tooltip=folium.GeoJsonTooltip(fields=list(tip_cols), aliases=list(tip_aliases), sticky=False)).add_to(m)
