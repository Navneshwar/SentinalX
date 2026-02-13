"""
SentinelX Live Dashboard (Streamlit)
Version: 2.1 - Fixed time axis and graph interpolation

Displays real‑time risk scores, anomaly alerts, and session summary.
Features:
- Multiple tabs for different views
- Real-time anomaly explanations
- Beautiful visualizations
- Session history and analytics
- Proctor-friendly interface
- Proper risk classification (Normal/Low/Medium/High/Critical)
- Fixed time axis - shows only actual data points

Privacy: No raw interaction data is displayed – only aggregated risk metrics.
All data shown is derived from timing metadata only.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text, func
import os
import sys
import time
import json
from datetime import datetime, timedelta
import numpy as np

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="SentinelX Proctoring Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS FOR MODERN LOOK
# ============================================================================

st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 0rem 1rem;
    }
    
    /* Risk score colors */
    .risk-critical { 
        color: #ff1744; 
        font-weight: 800;
        text-shadow: 0 0 10px rgba(255,23,68,0.3);
    }
    .risk-high { 
        color: #ff4b4b; 
        font-weight: bold;
        background: linear-gradient(135deg, #ff4b4b20 0%, #ff4b4b40 100%);
        padding: 10px;
        border-radius: 10px;
    }
    .risk-medium { 
        color: #ffa64b; 
        font-weight: bold;
        background: linear-gradient(135deg, #ffa64b20 0%, #ffa64b40 100%);
        padding: 10px;
        border-radius: 10px;
    }
    .risk-low { 
        color: #4bff4b; 
        font-weight: bold;
        background: linear-gradient(135deg, #4bff4b20 0%, #4bff4b40 100%);
        padding: 10px;
        border-radius: 10px;
    }
    .risk-normal { 
        color: #00e5ff; 
        font-weight: bold;
    }
    
    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a3a 100%);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: 1px solid #33334e;
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }
    
    /* Alert boxes */
    .alert-critical {
        background: linear-gradient(135deg, #ff174420 0%, #ff174460 100%);
        border-left: 5px solid #ff1744;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        animation: pulse 2s infinite;
    }
    .alert-high {
        background: linear-gradient(135deg, #ff4b4b20 0%, #ff4b4b40 100%);
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .alert-medium {
        background: linear-gradient(135deg, #ffa64b20 0%, #ffa64b40 100%);
        border-left: 5px solid #ffa64b;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .alert-low {
        background: linear-gradient(135deg, #4bff4b20 0%, #4bff4b40 100%);
        border-left: 5px solid #4bff4b;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: #1e1e2f;
        padding: 10px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
    }
    
    /* Header styling */
    .dashboard-header {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        padding: 25px;
        border-radius: 20px;
        margin-bottom: 30px;
        border-bottom: 3px solid #0f3460;
    }
    
    /* Animation */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.8; }
        100% { opacity: 1; }
    }
    
    /* Table styling */
    .dataframe {
        background: #1e1e2f;
        border-radius: 10px;
        padding: 10px;
    }
    
    /* Info boxes */
    .info-box {
        background: #1e1e2f;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #33334e;
        margin: 10px 0;
    }
    
    /* Risk badge */
    .risk-badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9rem;
    }
    
    /* Debug info */
    .debug-info {
        background: #0a0a0f;
        border: 1px solid #333;
        border-radius: 5px;
        padding: 5px 10px;
        font-family: monospace;
        font-size: 0.8rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

@st.cache_resource
def get_engine():
    """Create SQLAlchemy engine for SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sentinelx.db")
    engine_url = f"sqlite:///{db_path}"
    return create_engine(engine_url, connect_args={"check_same_thread": False})

engine = get_engine()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_risk_level(score):
    """Return risk level and color based on score."""
    if score >= 80:
        return "CRITICAL", "#ff1744", "🔥"
    elif score >= 60:
        return "HIGH", "#ff4b4b", "🔴"
    elif score >= 30:
        return "MEDIUM", "#ffa64b", "🟠"
    elif score >= 10:
        return "LOW", "#4bff4b", "🟡"
    else:
        return "NORMAL", "#00e5ff", "🟢"

def get_anomaly_explanation(scores_dict):
    """Generate explanation for anomalies."""
    explanations = []
    
    idle = scores_dict.get('idle_burst', 0)
    focus = scores_dict.get('focus_instability', 0)
    drift = scores_dict.get('behavioral_drift', 0)
    
    if idle > 60:
        explanations.append("🔴 Copy-paste behavior detected (Idle Burst)")
    elif idle > 30:
        explanations.append("🟠 Unusual typing pattern after idle")
        
    if focus > 60:
        explanations.append("🔴 Excessive window/tab switching")
    elif focus > 30:
        explanations.append("🟠 Frequent focus changes")
        
    if drift > 60:
        explanations.append("🔴 Typing speed drastically changed")
    elif drift > 30:
        explanations.append("🟠 Typing pattern shifted")
    
    return explanations if explanations else ["✅ Normal behavior"]

def format_timestamp(ts):
    """Format timestamp for display."""
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")

# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown("""
    <div style='text-align: center; padding: 20px 0;'>
        <h1 style='font-size: 2.5rem; margin: 0;'>🛡️</h1>
        <h2 style='margin: 0; color: #00e5ff;'>SentinelX</h2>
        <p style='color: #888;'>Privacy-First Proctoring</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Controls
    st.markdown("### ⚙️ Controls")
    
    refresh_rate = st.slider(
        "Refresh interval (seconds)", 
        min_value=1, 
        max_value=10, 
        value=2,
        help="How often to refresh the dashboard"
    )
    
    max_records = st.slider(
        "Records to display", 
        min_value=10, 
        max_value=200, 
        value=50,
        help="Number of recent risk records to show"
    )
    
    # Session filter
    st.markdown("### 🔍 Session Filter")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DISTINCT session_id FROM risk_records ORDER BY session_id DESC"))
            session_list = [row[0] for row in result.fetchall()]
        
        selected_session = st.selectbox(
            "Select Session",
            ["All Active Sessions"] + session_list if session_list else ["All Active Sessions"],
            help="Filter by specific session"
        )
    except Exception:
        selected_session = "All Active Sessions"
    
    # Time filter
    st.markdown("### ⏱️ Time Range")
    time_range = st.selectbox(
        "Show data from",
        ["Last 5 minutes", "Last 15 minutes", "Last hour", "Last 24 hours", "All time"],
        index=1
    )
    
    # Map time range to seconds
    time_map = {
        "Last 5 minutes": 300,
        "Last 15 minutes": 900,
        "Last hour": 3600,
        "Last 24 hours": 86400,
        "All time": None
    }
    time_filter = time_map[time_range]
    
    st.markdown("---")
    
    # System status
    st.markdown("### 📊 System Status")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM risk_records"))
            total_records = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(DISTINCT session_id) FROM risk_records"))
            total_sessions = result.scalar()
        
        st.markdown(f"""
        <div class='info-box'>
            <p>📀 Total Records: <b>{total_records}</b></p>
            <p>👥 Active Sessions: <b>{total_sessions}</b></p>
            <p>🔄 Auto-refresh: <b>{refresh_rate}s</b></p>
        </div>
        """, unsafe_allow_html=True)
    except:
        st.warning("Database not ready")
    
    st.markdown("---")
    
    # Manual refresh button
    if st.button("🔄 Manual Refresh", use_container_width=True):
        st.rerun()

# ============================================================================
# MAIN DASHBOARD HEADER
# ============================================================================

st.markdown("""
<div class='dashboard-header'>
    <h1 style='margin:0; color: white;'>🛡️ SentinelX Risk Dashboard</h1>
    <p style='color: #aaa; margin:5px 0 0 0;'>Real-time proctoring with privacy-first design • No keystroke content • No video • Just behavioral analytics</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# FETCH DATA
# ============================================================================

try:
    # Build query with time filter
    current_time = time.time()
    
    if selected_session != "All Active Sessions":
        if time_filter:
            query = text("""
                SELECT * FROM risk_records 
                WHERE session_id = :session_id 
                AND timestamp >= :min_time
                ORDER BY timestamp DESC 
                LIMIT :limit
            """)
            params = {
                "session_id": selected_session,
                "min_time": current_time - time_filter,
                "limit": max_records
            }
        else:
            query = text("""
                SELECT * FROM risk_records 
                WHERE session_id = :session_id 
                ORDER BY timestamp DESC 
                LIMIT :limit
            """)
            params = {"session_id": selected_session, "limit": max_records}
    else:
        if time_filter:
            query = text("""
                SELECT * FROM risk_records 
                WHERE timestamp >= :min_time
                ORDER BY timestamp DESC 
                LIMIT :limit
            """)
            params = {"min_time": current_time - time_filter, "limit": max_records}
        else:
            query = text("SELECT * FROM risk_records ORDER BY timestamp DESC LIMIT :limit")
            params = {"limit": max_records}
    
    # Fetch data
    with engine.connect() as conn:
        result = conn.execute(query, params)
        rows = result.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=result.keys())
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            # Sort by time ascending for proper graph display
            df = df.sort_values('datetime')
        else:
            df = pd.DataFrame()
            
except Exception as e:
    st.error(f"Database error: {str(e)}")
    df = pd.DataFrame()

# Debug info in sidebar
if not df.empty:
    st.sidebar.markdown(f"""
    <div class='debug-info'>
        📊 Current view: {len(df)} records<br>
        ⏱️ From: {df['datetime'].min().strftime('%H:%M:%S')}<br>
        ⏱️ To: {df['datetime'].max().strftime('%H:%M:%S')}<br>
        📈 Range: {(df['datetime'].max() - df['datetime'].min()).total_seconds():.0f}s
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN DASHBOARD TABS
# ============================================================================

if df.empty:
    # Show waiting state
    col1, col2, col3 = st.columns(3)
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 100px 0;'>
            <h1 style='font-size: 4rem;'>⏳</h1>
            <h3>Waiting for data...</h3>
            <p style='color: #888;'>Start the SentinelX client to begin monitoring</p>
        </div>
        """, unsafe_allow_html=True)
else:
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 LIVE MONITORING", 
        "📊 ANALYTICS", 
        "🚨 ALERT LOG", 
        "👥 SESSIONS",
        "ℹ️ HOW IT WORKS"
    ])
    
    # ========================================================================
    # TAB 1: LIVE MONITORING
    # ========================================================================
    
    with tab1:
        # Add risk level classification to dataframe
        df['risk_level'] = df['risk_score'].apply(
            lambda x: 'CRITICAL' if x >= 80 else 
                      'HIGH' if x >= 60 else 
                      'MEDIUM' if x >= 30 else 
                      'LOW' if x >= 10 else 'NORMAL'
        )
        
        df['risk_color'] = df['risk_score'].apply(
            lambda x: '#ff1744' if x >= 80 else   # Critical - Bright Red
                      '#ff4b4b' if x >= 60 else   # High - Red
                      '#ffa64b' if x >= 30 else   # Medium - Orange
                      '#4bff4b' if x >= 10 else   # Low - Green
                      '#00e5ff'                    # Normal - Cyan
        )
        
        # Top metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            current_risk = df.iloc[-1]['risk_score'] if not df.empty else 0  # Use last value
            level, color, icon = get_risk_level(current_risk)
            
            st.markdown(f"""
            <div class='metric-card' style='border-left: 5px solid {color};'>
                <h3 style='color: #888; margin:0;'>Current Risk</h3>
                <h1 style='color: {color}; font-size: 3rem; margin:0;'>{icon} {current_risk:.1f}</h1>
                <p style='color: {color}; margin:0; font-weight: bold;'>{level}</p>
                <p style='color: #888; margin:5px 0 0 0;'>Last updated: {df.iloc[-1]['datetime'].strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            avg_risk = df['risk_score'].mean()
            level, color, icon = get_risk_level(avg_risk)
            
            st.markdown(f"""
            <div class='metric-card'>
                <h3 style='color: #888; margin:0;'>Average Risk</h3>
                <h1 style='color: {color}; font-size: 3rem; margin:0;'>{avg_risk:.1f}</h1>
                <p style='color: {color}; margin:0;'>{level}</p>
                <p style='color: #888; margin:0;'>Over {len(df)} records</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            max_risk = df['risk_score'].max()
            level, color, icon = get_risk_level(max_risk)
            max_time = df.loc[df['risk_score'].idxmax(), 'datetime']
            
            st.markdown(f"""
            <div class='metric-card'>
                <h3 style='color: #888; margin:0;'>Peak Risk</h3>
                <h1 style='color: {color}; font-size: 3rem; margin:0;'>{max_risk:.1f}</h1>
                <p style='color: {color}; margin:0;'>{level}</p>
                <p style='color: #888; margin:0;'>at {max_time.strftime('%H:%M:%S')}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            high_risk_count = len(df[df['risk_score'] >= 60])
            critical_count = len(df[df['risk_score'] >= 80])
            
            st.markdown(f"""
            <div class='metric-card'>
                <h3 style='color: #888; margin:0;'>Alert Summary</h3>
                <h1 style='color: #ff4b4b; font-size: 2rem; margin:0;'>🔴 {high_risk_count}</h1>
                <p style='color: #888; margin:0;'>High risk events</p>
                <h1 style='color: #ff1744; font-size: 2rem; margin:5px 0 0 0;'>🔥 {critical_count}</h1>
                <p style='color: #888; margin:0;'>Critical alerts</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Main risk chart
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("### 📈 Real-Time Risk Score")
            
            # Check if we have enough data points
            if len(df) >= 2:
                # Create figure with proper formatting
                fig = go.Figure()
                
                # Add risk score line - connect only actual data points
                fig.add_trace(go.Scatter(
                    x=df['datetime'],
                    y=df['risk_score'],
                    mode='lines+markers',
                    name='Risk Score',
                    line=dict(
                        color='#ffffff', 
                        width=2,
                        shape='linear'  # Connect only actual points
                    ),
                    marker=dict(
                        size=12,  # Larger markers
                        color=df['risk_color'],
                        line=dict(color='white', width=2),
                        symbol='circle',
                        showscale=False
                    ),
                    connectgaps=False,  # DON'T connect missing data
                    hovertemplate='<b>Time:</b> %{x|%H:%M:%S}<br>' +
                                  '<b>Risk:</b> %{y:.1f}<br>' +
                                  '<b>Level:</b> %{text}<br>' +
                                  '<extra></extra>',
                    text=df['risk_level']
                ))
                
                # Add threshold lines with labels
                fig.add_hline(y=80, line_dash="dash", line_color="#ff1744", 
                             line_width=2,
                             annotation_text="CRITICAL", 
                             annotation_position="top right",
                             annotation_font=dict(color="#ff1744", size=12))
                
                fig.add_hline(y=60, line_dash="dash", line_color="#ff4b4b", 
                             line_width=2,
                             annotation_text="HIGH", 
                             annotation_position="top right",
                             annotation_font=dict(color="#ff4b4b", size=12))
                
                fig.add_hline(y=30, line_dash="dash", line_color="#ffa64b", 
                             line_width=2,
                             annotation_text="MEDIUM", 
                             annotation_position="top right",
                             annotation_font=dict(color="#ffa64b", size=12))
                
                fig.add_hline(y=10, line_dash="dash", line_color="#4bff4b", 
                             line_width=2,
                             annotation_text="LOW", 
                             annotation_position="top right",
                             annotation_font=dict(color="#4bff4b", size=12))
                
                # Calculate time range
                time_min = df['datetime'].min()
                time_max = df['datetime'].max()
                time_range_seconds = (time_max - time_min).total_seconds()
                
                # Update layout with proper time formatting
                fig.update_layout(
                    title=dict(
                        text=f"Risk Score Over Time ({len(df)} data points)",
                        font=dict(size=20, color='white')
                    ),
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=500,
                    hovermode='x',
                    showlegend=False,
                    xaxis=dict(
                        title="Time",
                        gridcolor='#333',
                        tickformat='%H:%M:%S',
                        type='date',
                        tickmode='auto',
                        nticks=min(10, len(df)),  # Limit number of ticks
                        range=[time_min, time_max]  # Only show actual time range
                    ),
                    yaxis=dict(
                        title="Risk Score",
                        gridcolor='#333',
                        range=[0, 100],
                        tickmode='linear',
                        tick0=0,
                        dtick=10
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show data summary
                st.caption(f"📊 Showing {len(df)} data points from {time_min.strftime('%H:%M:%S')} to {time_max.strftime('%H:%M:%S')} (Δ {time_range_seconds:.0f}s)")
                
            elif len(df) == 1:
                # Single data point - show as a dot
                st.info("Only one data point available - showing current risk")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df['datetime'],
                    y=df['risk_score'],
                    mode='markers',
                    marker=dict(
                        size=20,
                        color=df.iloc[0]['risk_color'],
                        line=dict(color='white', width=2)
                    ),
                    showlegend=False
                ))
                
                fig.update_layout(
                    title="Current Risk Score",
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    xaxis=dict(range=[df['datetime'].iloc[0] - timedelta(seconds=30), 
                                     df['datetime'].iloc[0] + timedelta(seconds=30)]),
                    yaxis=dict(range=[0, 100])
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough data points to display graph")
        
        with col2:
            st.markdown("### ⚡ Current Anomaly")
            
            # Parse latest anomaly scores
            try:
                latest = df.iloc[-1]  # Get most recent
                scores = json.loads(latest['anomaly_scores'])
                explanations = get_anomaly_explanation(scores)
                
                # Show gauge for overall risk
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=latest['risk_score'],
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Current Risk Level", 'font': {'size': 16, 'color': 'white'}},
                    delta={'reference': 50, 'increasing': {'color': "#ff4b4b"}},
                    gauge={
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                        'bar': {'color': latest['risk_color']},
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, 10], 'color': '#00e5ff20'},
                            {'range': [10, 30], 'color': '#4bff4b20'},
                            {'range': [30, 60], 'color': '#ffa64b20'},
                            {'range': [60, 80], 'color': '#ff4b4b20'},
                            {'range': [80, 100], 'color': '#ff174420'}
                        ],
                        'threshold': {
                            'line': {'color': "white", 'width': 4},
                            'thickness': 0.75,
                            'value': latest['risk_score']
                        }
                    }
                ))
                
                fig.update_layout(
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=250,
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show explanations
                st.markdown("**Detected Patterns:**")
                for exp in explanations:
                    if "🔴" in exp:
                        st.error(exp)
                    elif "🟠" in exp:
                        st.warning(exp)
                    else:
                        st.success(exp)
                        
                # Show raw scores
                st.markdown("**Anomaly Scores:**")
                cols = st.columns(3)
                
                idle_score = scores.get('idle_burst', 0)
                focus_score = scores.get('focus_instability', 0)
                drift_score = scores.get('behavioral_drift', 0)
                
                # Color code the metrics
                def get_score_color(score):
                    if score >= 60:
                        return "#ff4b4b"
                    elif score >= 30:
                        return "#ffa64b"
                    else:
                        return "#4bff4b"
                
                cols[0].markdown(f"""
                <div style='text-align: center; background: #1e1e2f; padding: 10px; border-radius: 10px;'>
                    <p style='color: #888; margin:0;'>Idle Burst</p>
                    <h3 style='color: {get_score_color(idle_score)}; margin:0;'>{idle_score:.0f}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                cols[1].markdown(f"""
                <div style='text-align: center; background: #1e1e2f; padding: 10px; border-radius: 10px;'>
                    <p style='color: #888; margin:0;'>Focus Instability</p>
                    <h3 style='color: {get_score_color(focus_score)}; margin:0;'>{focus_score:.0f}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                cols[2].markdown(f"""
                <div style='text-align: center; background: #1e1e2f; padding: 10px; border-radius: 10px;'>
                    <p style='color: #888; margin:0;'>Behavioral Drift</p>
                    <h3 style='color: {get_score_color(drift_score)}; margin:0;'>{drift_score:.0f}</h3>
                </div>
                """, unsafe_allow_html=True)
                
            except Exception as e:
                st.info("No anomaly data available")
    
    # ========================================================================
    # TAB 2: ANALYTICS
    # ========================================================================
    
    with tab2:
        st.markdown("### 📊 Advanced Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Risk distribution histogram
            fig = px.histogram(
                df, 
                x='risk_score',
                nbins=20,
                title=f"Risk Score Distribution ({len(df)} records)",
                color_discrete_sequence=['#00e5ff'],
                labels={'risk_score': 'Risk Score', 'count': 'Frequency'}
            )
            
            # Add vertical lines for thresholds
            fig.add_vline(x=80, line_dash="dash", line_color="#ff1744",
                         annotation_text="Critical", annotation_position="top")
            fig.add_vline(x=60, line_dash="dash", line_color="#ff4b4b",
                         annotation_text="High", annotation_position="top")
            fig.add_vline(x=30, line_dash="dash", line_color="#ffa64b",
                         annotation_text="Medium", annotation_position="top")
            fig.add_vline(x=10, line_dash="dash", line_color="#4bff4b",
                         annotation_text="Low", annotation_position="top")
            
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                height=400,
                bargap=0.1,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Risk level pie chart
            risk_counts = df['risk_level'].value_counts().reset_index()
            risk_counts.columns = ['Level', 'Count']
            
            # Define colors for each level
            color_map = {
                'CRITICAL': '#ff1744',
                'HIGH': '#ff4b4b',
                'MEDIUM': '#ffa64b',
                'LOW': '#4bff4b',
                'NORMAL': '#00e5ff'
            }
            
            fig = px.pie(
                risk_counts,
                values='Count',
                names='Level',
                title="Risk Level Distribution",
                color='Level',
                color_discrete_map=color_map
            )
            fig.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Anomaly breakdown
        st.markdown("### 🔍 Anomaly Breakdown")
        
        # Prepare anomaly data
        anomaly_types = {'idle_burst': 0, 'focus_instability': 0, 'behavioral_drift': 0}
        
        for _, row in df.iterrows():
            try:
                scores = json.loads(row['anomaly_scores'])
                for key in anomaly_types.keys():
                    if scores.get(key, 0) > 30:  # Count significant anomalies
                        anomaly_types[key] += 1
            except:
                pass
        
        if sum(anomaly_types.values()) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                # Bar chart of anomaly types
                anomaly_df = pd.DataFrame([
                    {"Type": "Idle Burst", "Count": anomaly_types['idle_burst']},
                    {"Type": "Focus Instability", "Count": anomaly_types['focus_instability']},
                    {"Type": "Behavioral Drift", "Count": anomaly_types['behavioral_drift']}
                ])
                
                fig = px.bar(
                    anomaly_df,
                    x='Type',
                    y='Count',
                    title="Anomaly Type Frequency",
                    color='Type',
                    color_discrete_sequence=['#00e5ff', '#ff4b4b', '#ffa64b']
                )
                fig.update_layout(
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Time series of anomalies
                anomaly_df = []
                for _, row in df.iterrows():
                    try:
                        scores = json.loads(row['anomaly_scores'])
                        anomaly_df.append({
                            'datetime': row['datetime'],
                            'Idle Burst': scores.get('idle_burst', 0),
                            'Focus Instability': scores.get('focus_instability', 0),
                            'Behavioral Drift': scores.get('behavioral_drift', 0)
                        })
                    except:
                        pass
                
                if anomaly_df:
                    anomaly_df = pd.DataFrame(anomaly_df)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=anomaly_df['datetime'],
                        y=anomaly_df['Idle Burst'],
                        name='Idle Burst',
                        mode='lines+markers',
                        line=dict(color='#00e5ff', width=2),
                        marker=dict(size=6)
                    ))
                    fig.add_trace(go.Scatter(
                        x=anomaly_df['datetime'],
                        y=anomaly_df['Focus Instability'],
                        name='Focus Instability',
                        mode='lines+markers',
                        line=dict(color='#ff4b4b', width=2),
                        marker=dict(size=6)
                    ))
                    fig.add_trace(go.Scatter(
                        x=anomaly_df['datetime'],
                        y=anomaly_df['Behavioral Drift'],
                        name='Behavioral Drift',
                        mode='lines+markers',
                        line=dict(color='#ffa64b', width=2),
                        marker=dict(size=6)
                    ))
                    
                    fig.update_layout(
                        template="plotly_dark",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        height=400,
                        hovermode='x unified',
                        title="Anomaly Scores Over Time",
                        xaxis_title="Time",
                        yaxis_title="Score",
                        xaxis=dict(
                            tickformat='%H:%M:%S',
                            range=[df['datetime'].min(), df['datetime'].max()]
                        )
                    )
                    fig.update_xaxes(gridcolor='#333')
                    fig.update_yaxes(gridcolor='#333', range=[0, 100])
                    
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No significant anomalies detected in this time period")
    
    # ========================================================================
    # TAB 3: ALERT LOG
    # ========================================================================
    
    with tab3:
        st.markdown("### 🚨 Real-Time Alert Log")
        
        # Filter high-risk events
        alerts = []
        for _, row in df.iterrows():
            risk = row['risk_score']
            if risk >= 30:  # Show all non-normal alerts
                try:
                    scores = json.loads(row['anomaly_scores'])
                    
                    # Proper classification
                    if risk >= 80:
                        level = "CRITICAL"
                        icon = "🔥"
                        color = "#ff1744"
                        border_color = "#ff1744"
                        bg_color = "#ff174420"
                    elif risk >= 60:
                        level = "HIGH"
                        icon = "🔴"
                        color = "#ff4b4b"
                        border_color = "#ff4b4b"
                        bg_color = "#ff4b4b20"
                    elif risk >= 30:
                        level = "MEDIUM"
                        icon = "🟠"
                        color = "#ffa64b"
                        border_color = "#ffa64b"
                        bg_color = "#ffa64b20"
                    else:
                        continue
                    
                    explanations = get_anomaly_explanation(scores)
                    
                    alert_html = f"""
                    <div style='background: {bg_color}; border-left: 5px solid {border_color}; 
                                padding: 15px; border-radius: 10px; margin: 10px 0;
                                box-shadow: 0 2px 5px rgba(0,0,0,0.2);'>
                        <div style='display: flex; justify-content: space-between;'>
                            <span><b style='color: {color}; font-size: 1.1rem;'>{icon} {level} RISK</b> 
                                  <span style='color: white;'>({risk:.1f})</span></span>
                            <span style='color: #888;'>{row['datetime'].strftime('%H:%M:%S')}</span>
                        </div>
                        <p style='margin: 10px 0 0 0; color: #aaa;'>Session: {row['session_id'][:8]}...</p>
                        <ul style='margin: 5px 0 0 0; color: white;'>
                    """
                    
                    for exp in explanations:
                        alert_html += f"<li>{exp}</li>"
                    
                    alert_html += """
                        </ul>
                    </div>
                    """
                    
                    alerts.append(alert_html)
                except Exception as e:
                    pass
        
        if alerts:
            # Show most recent first (reverse order)
            for alert in reversed(alerts[-20:]):
                st.markdown(alert, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='text-align: center; padding: 50px; background: #1e1e2f; border-radius: 10px;'>
                <h2 style='color: #4bff4b;'>✅ No Active Alerts</h2>
                <p style='color: #888;'>All sessions showing normal behavior</p>
            </div>
            """, unsafe_allow_html=True)
    
    # ========================================================================
    # TAB 4: SESSIONS
    # ========================================================================
    
    with tab4:
        st.markdown("### 👥 Active Sessions")
        
        # Group by session
        sessions = df.groupby('session_id').agg({
            'risk_score': ['mean', 'max', 'min', 'count'],
            'timestamp': 'max'
        }).round(1)
        
        sessions.columns = ['Avg Risk', 'Max Risk', 'Min Risk', 'Records', 'Last Active']
        sessions = sessions.reset_index()
        sessions['Last Active'] = pd.to_datetime(sessions['Last Active'], unit='s')
        
        # Add status based on max risk
        def get_status(x):
            if x >= 80:
                return "🔥 CRITICAL"
            elif x >= 60:
                return "🔴 HIGH"
            elif x >= 30:
                return "🟠 MEDIUM"
            elif x >= 10:
                return "🟡 LOW"
            else:
                return "🟢 NORMAL"
        
        sessions['Status'] = sessions['Max Risk'].apply(get_status)
        
        # Add color for status
        def get_color(x):
            if x >= 80:
                return "#ff1744"
            elif x >= 60:
                return "#ff4b4b"
            elif x >= 30:
                return "#ffa64b"
            elif x >= 10:
                return "#4bff4b"
            else:
                return "#00e5ff"
        
        sessions['Color'] = sessions['Max Risk'].apply(get_color)
        
        # Sort by last active
        sessions = sessions.sort_values('Last Active', ascending=False)
        
        # Display as table with styling
        for _, session in sessions.iterrows():
            st.markdown(f"""
            <div style='background: #1e1e2f; border-left: 5px solid {session['Color']}; 
                        padding: 15px; border-radius: 10px; margin: 10px 0;'>
                <div style='display: flex; justify-content: space-between;'>
                    <span><b>Session:</b> {session['session_id'][:8]}...</span>
                    <span><b style='color: {session['Color']};'>{session['Status']}</b></span>
                </div>
                <div style='display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap;'>
                    <span><b>Avg Risk:</b> {session['Avg Risk']:.1f}</span>
                    <span><b>Max Risk:</b> {session['Max Risk']:.1f}</span>
                    <span><b>Min Risk:</b> {session['Min Risk']:.1f}</span>
                    <span><b>Records:</b> {session['Records']}</span>
                    <span><b>Last Active:</b> {session['Last Active'].strftime('%H:%M:%S')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Session details expander
        with st.expander("📊 Detailed Session View"):
            selected_detail = st.selectbox("Select Session for Details", sessions['session_id'].tolist())
            
            if selected_detail:
                session_df = df[df['session_id'] == selected_detail].copy()
                
                # Metrics for selected session
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Current Risk", f"{session_df.iloc[-1]['risk_score']:.1f}")
                col2.metric("Average Risk", f"{session_df['risk_score'].mean():.1f}")
                col3.metric("Max Risk", f"{session_df['risk_score'].max():.1f}")
                col4.metric("Total Records", len(session_df))
                
                # Chart for selected session
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=session_df['datetime'],
                    y=session_df['risk_score'],
                    mode='lines+markers',
                    name='Risk Score',
                    line=dict(color='#00e5ff', width=3),
                    marker=dict(
                        size=8,
                        color=session_df['risk_score'],
                        colorscale='RdYlGn_r',
                        showscale=True,
                        colorbar=dict(title="Risk Level")
                    )
                ))
                
                # Add threshold lines
                fig.add_hline(y=80, line_dash="dash", line_color="#ff1744", line_width=1)
                fig.add_hline(y=60, line_dash="dash", line_color="#ff4b4b", line_width=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#ffa64b", line_width=1)
                fig.add_hline(y=10, line_dash="dash", line_color="#4bff4b", line_width=1)
                
                fig.update_layout(
                    template="plotly_dark",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=300,
                    title=f"Session {selected_detail[:8]}... Risk Timeline",
                    xaxis_title="Time",
                    yaxis_title="Risk Score",
                    xaxis=dict(tickformat='%H:%M:%S')
                )
                fig.update_xaxes(gridcolor='#333')
                fig.update_yaxes(gridcolor='#333', range=[0, 100])
                
                st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # TAB 5: HOW IT WORKS
    # ========================================================================
    
    with tab5:
        st.markdown("### 🔍 Understanding SentinelX")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class='info-box'>
                <h3>🛡️ Privacy-First Design</h3>
                <p>SentinelX monitors behavior without invading privacy:</p>
                <ul>
                    <li>❌ NO keystroke content</li>
                    <li>❌ NO screen recording</li>
                    <li>❌ NO webcam/microphone</li>
                    <li>✅ ONLY timing metadata</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='info-box'>
                <h3>📊 Risk Levels Explained</h3>
                <p><span style='color: #00e5ff;'>🟢 NORMAL (0-9)</span>: Normal behavior</p>
                <p><span style='color: #4bff4b;'>🟡 LOW (10-29)</span>: Minor variations</p>
                <p><span style='color: #ffa64b;'>🟠 MEDIUM (30-59)</span>: Suspicious patterns</p>
                <p><span style='color: #ff4b4b;'>🔴 HIGH (60-79)</span>: Anomaly detected</p>
                <p><span style='color: #ff1744;'>🔥 CRITICAL (80-100)</span>: Immediate attention</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class='info-box'>
                <h3>🎯 Anomaly Detection Rules</h3>
                
                <p><b>1. Idle Burst Detection</b></p>
                <p>Long idle period followed by sudden fast typing.<br>
                <small>🔄 May indicate copy-paste behavior</small></p>
                
                <p><b>2. Focus Instability</b></p>
                <p>Excessive window/tab switching.<br>
                <small>🔍 May indicate searching for answers</small></p>
                
                <p><b>3. Behavioral Drift</b></p>
                <p>Typing speed significantly changes.<br>
                <small>👥 May indicate different person typing</small></p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='info-box'>
                <h3>⚙️ Technical Architecture</h3>
                <p>1. <b>Listener</b>: Captures system events</p>
                <p>2. <b>Extractor</b>: Computes behavioral features</p>
                <p>3. <b>Detector</b>: Identifies anomalies</p>
                <p>4. <b>Engine</b>: Calculates risk scores</p>
                <p>5. <b>Dashboard</b>: Real-time visualization</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Feature comparison
        st.markdown("### 📋 Feature Comparison")
        
        comparison_data = {
            "Feature": [
                "Keystroke Content",
                "Screen Recording",
                "Webcam/Mic",
                "Timing Analysis",
                "Pattern Detection",
                "Real-time Alerts",
                "Privacy Score"
            ],
            "Traditional Proctoring": [
                "❌ Often captures",
                "✅ Yes",
                "✅ Yes",
                "❌ No",
                "❌ Basic",
                "✅ Yes",
                "20%"
            ],
            "SentinelX": [
                "❌ NEVER",
                "❌ NEVER",
                "❌ NEVER",
                "✅ Yes",
                "✅ Advanced",
                "✅ Yes",
                "100%"
            ]
        }
        
        comparison_df = pd.DataFrame(comparison_data)
        
        st.dataframe(
            comparison_df,
            use_container_width=True,
            hide_index=True
        )

# Auto-refresh
time.sleep(refresh_rate)
st.rerun()