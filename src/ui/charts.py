import plotly.express as px
from ..config import PALETTE as C

SEQ = ["#E9D8C4", "#D9A86B", "#8FB3A5", "#3F7C85", "#2F4F63"]
CAT = [C["teal"], C["clay"], C["navy"], C["sage"], C["rose"], C["gold"], "#8C9DA5"]


def tidy(fig, h=330):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=36, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.55)",
                      font=dict(color=C["ink"], size=12), legend=dict(orientation="h", y=-0.2), colorway=CAT)
    fig.update_xaxes(gridcolor="#E4DECF", zeroline=False); fig.update_yaxes(gridcolor="#E4DECF", zeroline=False)
    return fig
