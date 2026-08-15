"""
GSP Franchise Valuation Quick-Calc
Sports investment bank screening tool for franchise enterprise values.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# League assumptions (illustrative EV / Revenue screening multiples)
# ---------------------------------------------------------------------------
LEAGUE_MULTIPLES = {
    "NFL": 10.5,
    "NBA": 9.2,
    "MLB": 7.5,
    "NHL": 6.0,
    "MLS": 5.0,
    "European Soccer": 4.0,
}

# Estimated revenue mix used to allocate the user's total revenue input.
# Mixes are directional (league-typical), not club-specific actuals.
REVENUE_MIX = {
    "NFL": {
        "National Media": 0.70,
        "Local Ticketing / Sponsorship": 0.22,
        "Merchandising / Other": 0.08,
    },
    "NBA": {
        "National Media": 0.45,
        "Local Ticketing / Sponsorship": 0.42,
        "Merchandising / Other": 0.13,
    },
    "MLB": {
        "National Media": 0.38,
        "Local Ticketing / Sponsorship": 0.48,
        "Merchandising / Other": 0.14,
    },
    "NHL": {
        "National Media": 0.32,
        "Local Ticketing / Sponsorship": 0.53,
        "Merchandising / Other": 0.15,
    },
    "MLS": {
        "National Media": 0.22,
        "Local Ticketing / Sponsorship": 0.63,
        "Merchandising / Other": 0.15,
    },
    "European Soccer": {
        "National Media": 0.50,
        "Local Ticketing / Sponsorship": 0.35,
        "Merchandising / Other": 0.15,
    },
}

LARGE_MARKET_PREMIUM = 0.15  # +15% multiple for Tier-1 media hubs
RANGE_LOW = -0.10  # Low case vs. adjusted mid-point
RANGE_HIGH = 0.15  # High case vs. adjusted mid-point

# Accent colors by league (used on KPI cards and charts)
LEAGUE_ACCENT = {
    "NFL": "#c9a227",
    "NBA": "#c2410c",
    "MLB": "#1d4ed8",
    "NHL": "#94a3b8",
    "MLS": "#16a34a",
    "European Soccer": "#d4af37",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_usd_from_millions(amount_mm: float) -> str:
    """Pretty-print a USD figure supplied in millions (e.g. 4200 -> $4.20 Billion)."""
    if abs(amount_mm) >= 1000:
        return f"${amount_mm / 1000:,.2f} Billion"
    return f"${amount_mm:,.1f} Million"


def format_multiple(multiple: float) -> str:
    return f"{multiple:.2f}x"


def compute_valuation(
    revenue_mm: float,
    base_multiple: float,
    apply_market_premium: bool,
    minority_discount: float,
) -> dict:
    """
    Screening valuation:
      1) Base EV = Revenue × league multiple
      2) Market-adjusted multiple = league multiple × (1 + 15%) if Tier-1 hub
      3) Adjusted EV  = Revenue × market-adjusted multiple × (1 − minority discount)
      4) Range around the adjusted mid-point: −10% / +15%
    """
    premium_factor = 1.0 + LARGE_MARKET_PREMIUM if apply_market_premium else 1.0
    control_factor = 1.0 - minority_discount

    market_adjusted_multiple = base_multiple * premium_factor
    applied_multiple = market_adjusted_multiple * control_factor

    base_ev_mm = revenue_mm * base_multiple
    adjusted_ev_mm = revenue_mm * applied_multiple

    return {
        "premium_factor": premium_factor,
        "control_factor": control_factor,
        "market_adjusted_multiple": market_adjusted_multiple,
        "applied_multiple": applied_multiple,
        "base_ev_mm": base_ev_mm,
        "adjusted_ev_mm": adjusted_ev_mm,
        "low_ev_mm": adjusted_ev_mm * (1.0 + RANGE_LOW),
        "high_ev_mm": adjusted_ev_mm * (1.0 + RANGE_HIGH),
    }


def inject_theme(accent: str) -> None:
    """Dark financial-dashboard styling layered on top of Streamlit's default chrome."""
    st.markdown(
        f"""
        <style>
            @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap");

            html, body, [class*="css"] {{
                font-family: "IBM Plex Sans", sans-serif;
            }}

            .stApp {{
                background: radial-gradient(1200px 600px at 10% -10%, #152238 0%, #0b1220 45%, #070b14 100%);
                color: #e5e7eb;
            }}

            [data-testid="stSidebar"] {{
                background: linear-gradient(180deg, #0f172a 0%, #0b1220 100%);
                border-right: 1px solid #1e293b;
            }}
            [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {{
                color: #e5e7eb !important;
            }}

            [data-testid="stHeader"] {{
                background: rgba(11, 18, 32, 0.6);
            }}

            .hero-kicker {{
                letter-spacing: 0.22em;
                text-transform: uppercase;
                font-size: 0.72rem;
                color: {accent};
                font-weight: 600;
                margin-bottom: 0.35rem;
            }}
            .hero-title {{
                font-size: 2.05rem;
                font-weight: 700;
                letter-spacing: -0.03em;
                color: #f8fafc;
                margin: 0 0 0.35rem 0;
            }}
            .hero-sub {{
                color: #94a3b8;
                font-size: 0.98rem;
                margin-bottom: 1.4rem;
            }}

            .kpi-card {{
                background: linear-gradient(180deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
                border: 1px solid #243044;
                border-top: 3px solid {accent};
                border-radius: 14px;
                padding: 1.05rem 1.15rem 1.15rem 1.15rem;
                min-height: 142px;
                box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
            }}
            .kpi-label {{
                font-size: 0.72rem;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                color: #94a3b8;
                font-weight: 600;
                margin-bottom: 0.55rem;
            }}
            .kpi-value {{
                font-family: "IBM Plex Mono", monospace;
                font-size: 1.55rem;
                font-weight: 600;
                color: #f8fafc;
                line-height: 1.2;
            }}
            .kpi-sub {{
                margin-top: 0.45rem;
                color: #64748b;
                font-size: 0.82rem;
            }}

            .section-title {{
                font-size: 1.05rem;
                font-weight: 600;
                color: #f1f5f9;
                margin: 0.4rem 0 0.75rem 0;
            }}

            .panel {{
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid #1e293b;
                border-radius: 14px;
                padding: 1rem 1.1rem 0.3rem 1.1rem;
            }}

            .bridge-row {{
                display: flex;
                justify-content: space-between;
                padding: 0.45rem 0;
                border-bottom: 1px solid #1e293b;
                font-size: 0.9rem;
            }}
            .bridge-row:last-child {{
                border-bottom: none;
                font-weight: 600;
            }}
            .bridge-key {{ color: #94a3b8; }}
            .bridge-val {{
                font-family: "IBM Plex Mono", monospace;
                color: #e2e8f0;
            }}

            .run-box {{
                background: #0f172a;
                border: 1px dashed #334155;
                border-radius: 12px;
                padding: 1rem 1.15rem;
                color: #cbd5e1;
                font-size: 0.9rem;
            }}
            .run-box code {{
                color: {accent};
            }}

            .disclaimer {{
                color: #64748b;
                font-size: 0.78rem;
                line-height: 1.45;
                margin-top: 0.75rem;
            }}

            div[data-testid="stDataFrame"] {{
                border: 1px solid #1e293b;
                border-radius: 10px;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, subtitle: str) -> str:
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{subtitle}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GSP Franchise Valuation Quick-Calc",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Deal Inputs")
    st.caption("Screening assumptions for a franchise or club sale process.")

    league = st.selectbox(
        "League",
        options=list(LEAGUE_MULTIPLES.keys()),
        index=0,
        help="Sets the base EV / Revenue multiple used in the screening calc.",
    )

    revenue_mm = st.number_input(
        "Annual Revenue ($ millions)",
        min_value=1.0,
        max_value=10_000.0,
        value=400.0,
        step=10.0,
        format="%.1f",
        help="Trailing-twelve-month or latest fiscal-year club revenue.",
    )

    st.markdown("---")
    st.markdown("### Valuation Adjustments")

    premium_market = st.checkbox(
        "Large Market / Tier-1 Media Hub",
        value=False,
        help="Applies a 15% premium to the league multiple for top media markets.",
    )

    minority_discount_pct = st.slider(
        "Minority Stake Discount",
        min_value=0,
        max_value=30,
        value=15,
        format="%d%%",
        help="Illiquidity and lack-of-control discount applied to implied EV.",
    )

    st.markdown("---")
    st.caption(
        f"Base {league} multiple: **{LEAGUE_MULTIPLES[league]:.1f}x EV / Revenue**"
    )
    if premium_market:
        st.caption("Market premium: **+15.0%**")
    st.caption(f"Minority / illiquidity discount: **{minority_discount_pct:.0f}%**")

# Resolve derived inputs after the sidebar is drawn.
accent = LEAGUE_ACCENT[league]
base_multiple = LEAGUE_MULTIPLES[league]
minority_discount = minority_discount_pct / 100.0
result = compute_valuation(
    revenue_mm=revenue_mm,
    base_multiple=base_multiple,
    apply_market_premium=premium_market,
    minority_discount=minority_discount,
)
inject_theme(accent)

# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------
st.markdown('<div class="hero-kicker">Sports Investment Banking · Screening Desk</div>', unsafe_allow_html=True)
st.markdown('<p class="hero-title">GSP Franchise Valuation Quick-Calc</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="hero-sub">Illustrative enterprise-value screen for a {league} franchise '
    f"based on {format_usd_from_millions(revenue_mm)} of annual revenue.</p>",
    unsafe_allow_html=True,
)

# KPI row
k1, k2, k3 = st.columns(3)
with k1:
    st.markdown(
        kpi_card(
            "Implied Enterprise Value",
            format_usd_from_millions(result["adjusted_ev_mm"]),
            "Mid-point · after market premium & minority discount",
        ),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        kpi_card(
            "Valuation Range",
            f"{format_usd_from_millions(result['low_ev_mm'])} – {format_usd_from_millions(result['high_ev_mm'])}",
            "Low −10% · High +15% vs. adjusted mid-point",
        ),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        kpi_card(
            "Applied Multiple",
            format_multiple(result["applied_multiple"]),
            f"Base {format_multiple(base_multiple)} → effective EV / Revenue",
        ),
        unsafe_allow_html=True,
    )

st.write("")

# Chart + calculation bridge
chart_col, bridge_col = st.columns([1.45, 1.0])

with chart_col:
    st.markdown('<div class="section-title">Valuation Range</div>', unsafe_allow_html=True)

    scenario_labels = ["Low (−10%)", "Mid-Point", "High (+15%)"]
    scenario_values = [
        result["low_ev_mm"],
        result["adjusted_ev_mm"],
        result["high_ev_mm"],
    ]
    bar_colors = ["#475569", accent, "#34d399"]

    fig = go.Figure(
        data=[
            go.Bar(
                x=scenario_labels,
                y=scenario_values,
                marker=dict(color=bar_colors, line=dict(width=0)),
                text=[format_usd_from_millions(v) for v in scenario_values],
                textposition="outside",
                hovertemplate="%{x}<br>%{customdata}<extra></extra>",
                customdata=[format_usd_from_millions(v) for v in scenario_values],
            )
        ]
    )
    # Headroom so outside labels don't clip
    y_max = max(scenario_values) * 1.22
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#cbd5e1", size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        height=340,
        yaxis=dict(
            title="Enterprise Value",
            range=[0, y_max],
            gridcolor="#1e293b",
            zerolinecolor="#1e293b",
            tickprefix="$",
            ticksuffix="M",
        ),
        xaxis=dict(title=""),
        bargap=0.42,
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

with bridge_col:
    st.markdown('<div class="section-title">Multiple Bridge</div>', unsafe_allow_html=True)
    premium_label = "+15.0%" if premium_market else "None"
    st.markdown(
        f"""
        <div class="panel">
            <div class="bridge-row"><span class="bridge-key">Annual revenue</span>
                <span class="bridge-val">{format_usd_from_millions(revenue_mm)}</span></div>
            <div class="bridge-row"><span class="bridge-key">{league} base multiple</span>
                <span class="bridge-val">{format_multiple(base_multiple)}</span></div>
            <div class="bridge-row"><span class="bridge-key">Base implied EV</span>
                <span class="bridge-val">{format_usd_from_millions(result["base_ev_mm"])}</span></div>
            <div class="bridge-row"><span class="bridge-key">Tier-1 market premium</span>
                <span class="bridge-val">{premium_label}</span></div>
            <div class="bridge-row"><span class="bridge-key">Market-adjusted multiple</span>
                <span class="bridge-val">{format_multiple(result["market_adjusted_multiple"])}</span></div>
            <div class="bridge-row"><span class="bridge-key">Minority / illiquidity discount</span>
                <span class="bridge-val">{minority_discount_pct:.0f}%</span></div>
            <div class="bridge-row"><span class="bridge-key">Adjusted EV (mid)</span>
                <span class="bridge-val">{format_usd_from_millions(result["adjusted_ev_mm"])}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# Revenue mix table + donut
st.markdown('<div class="section-title">Estimated Revenue Stream Split</div>', unsafe_allow_html=True)
mix = REVENUE_MIX[league]
mix_rows = []
for stream, weight in mix.items():
    dollars_mm = revenue_mm * weight
    mix_rows.append(
        {
            "Revenue Stream": stream,
            "Share of Revenue": f"{weight * 100:.0f}%",
            "Estimated Dollars": format_usd_from_millions(dollars_mm),
            "Amount ($M)": round(dollars_mm, 1),
        }
    )
mix_df = pd.DataFrame(mix_rows)

table_col, mix_chart_col = st.columns([1.35, 1.0])
with table_col:
    st.dataframe(
        mix_df[["Revenue Stream", "Share of Revenue", "Estimated Dollars"]],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        f"League-typical mix applied to the {format_usd_from_millions(revenue_mm)} "
        f"{league} revenue input. For screening only — replace with club actuals in a live process."
    )

with mix_chart_col:
    donut = go.Figure(
        data=[
            go.Pie(
                labels=mix_df["Revenue Stream"],
                values=mix_df["Amount ($M)"],
                hole=0.62,
                marker=dict(colors=["#1d4ed8", accent, "#334155"], line=dict(color="#0b1220", width=2)),
                textinfo="percent",
                hovertemplate="%{label}<br>%{customdata}<extra></extra>",
                customdata=mix_df["Estimated Dollars"],
            )
        ]
    )
    donut.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color="#cbd5e1", size=12),
        margin=dict(l=0, r=0, t=10, b=10),
        height=280,
        legend=dict(orientation="h", y=-0.08),
        annotations=[
            dict(
                text="Revenue<br>Mix",
                x=0.5,
                y=0.5,
                font=dict(size=13, color="#94a3b8"),
                showarrow=False,
            )
        ],
    )
    st.plotly_chart(donut, width="stretch")

st.markdown(
    '<p class="disclaimer">This Quick-Calc is an illustrative screening model for internal discussion. '
    "It is not a fairness opinion, appraisal, or offer. Multiples are directional league averages and "
    "do not capture club-level media rights, stadium economics, tax attributes, net debt, or control premiums "
    "that would be diligence items in a live mandate.</p>",
    unsafe_allow_html=True,
)

st.markdown("---")
st.markdown('<div class="section-title">Run locally</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="run-box">
        From a terminal in this project folder:
        <br><br>
        <code>pip install -r requirements.txt</code>
        <br>
        <code>streamlit run app.py</code>
        <br><br>
        Streamlit will open the dashboard in your browser (typically <code>http://localhost:8501</code>).
    </div>
    """,
    unsafe_allow_html=True,
)
