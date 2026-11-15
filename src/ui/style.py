import streamlit as st
from ..config import PALETTE as C

CSS = f"""
<style>
.block-container {{padding-top: 1.4rem; max-width: 1400px;}}
h1, h2, h3 {{color: {C['ink']}; letter-spacing: -0.01em;}}
.hero {{background: linear-gradient(120deg, #E3ECEA 0%, #F1E9DA 100%); border: 1px solid #D8D2C3; border-radius: 16px; padding: 22px 28px; margin-bottom: 14px;}}
.hero h1 {{margin: 0 0 4px 0; font-size: 1.9rem;}}
.hero p {{margin: 0; color: {C['muted']}; font-size: 1.0rem;}}
.card {{background: {C['panel']}; border: 1px solid #E0DACB; border-radius: 14px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(60,70,80,.05);}}
.kpi {{background: {C['panel']}; border: 1px solid #E0DACB; border-radius: 14px; padding: 12px 16px;}}
.kpi .v {{font-size: 1.65rem; font-weight: 650; color: {C['teal']}; line-height: 1.15;}}
.kpi .l {{font-size: .80rem; color: {C['muted']}; text-transform: uppercase; letter-spacing: .04em;}}
.kpi .s {{font-size: .78rem; color: {C['muted']};}}
.chip {{display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; margin-right: 6px; background:{C['mist']}; color:{C['navy']};}}
.chip.real {{background:#DDEBE3; color:#35624A;}} .chip.derived {{background:#EFE6CF; color:#7A6430;}} .chip.assump {{background:#F0DDD6; color:#8A4B38;}}
.mode {{display:inline-block; min-width:52px; height:fit-content; text-align:center; padding:3px 8px; border-radius:6px; font-weight:700; font-size:.82rem; color:#fff; background:{C['teal']};}}
.mode.walk {{background:#B9A67C; font-size:.7rem; letter-spacing:.05em;}}
.leg {{display:flex; gap:12px; align-items:flex-start; padding:8px 10px; border-left:4px solid {C['teal']}; background:#FBF9F4; margin:6px 0; border-radius:0 10px 10px 0;}}
.leg.walk {{border-left-color:{C['sand']};}}
.note {{background:#FBF4E4; border:1px solid #EBDDB8; border-radius:10px; padding:8px 12px; font-size:.86rem; color:#6B5A2E;}}
.stTabs [data-baseweb="tab"] {{font-weight: 600;}}
section[data-testid="stSidebar"] {{background: #ECE7DA;}}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def num(x):
    return f"{int(round(x)):,}"
