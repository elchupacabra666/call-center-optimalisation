import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from state_utils import persist_state

st.set_page_config(page_title="Výsledky", layout="wide")
persist_state()  # Ochrana session_state klíčů před GC při navigaci mezi stránkami

# Skrýt Streamlit element toolbar (fullscreen / download / search ikonky,
# které se objeví při najetí myší na dataframe a grafy). Uživatel je na
# této stránce nechce vidět ani u tabulek, ani u grafů.
st.markdown(
    """
    <style>
    [data-testid="stElementToolbar"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Plotly charts si navíc řídíme vlastní `displayModeBar` – viz PLOTLY_CONFIG níže.
PLOTLY_CONFIG = {"displayModeBar": False}

st.title("Výsledky optimalizace")

# Check if results exist
if 'results' not in st.session_state:
    st.warning("Nejprve spusťte optimalizaci na stránce **Konfigurace**")
    st.stop()

results = st.session_state['results']
params = st.session_state['params']

GROUP_ORDER = [g for g in ['G1', 'G2', 'G3'] if g in params['groups']]
PIE_GROUP_ORDER = [g for g in ['G3', 'G2', 'G1'] if g in params['groups']]
GROUP_COLORS = {
    'G1': '#90EE90',
    'G2': '#FFB703',
    'G3': '#FF6B6B',
}
BATCH_GROUP_COLORS = {
    'G1': '#669966',
    'G2': '#AA7700',
    'G3': '#AA3333',
}

if results['status'] != 'Optimal':
    status_text = str(results['status'])

    if status_text == 'Infeasible':
        st.error("❌ Optimalizace nenašla proveditelné řešení.")
        st.info(
            "Pravděpodobná příčina je nedostatek kapacit vůči požadované poptávce "
            "(např. nízké limity agentů, příliš vysoká occupancy omezení nebo příliš přísný batch deadline)."
        )
        st.markdown("**Co zkusit upravit:**")
        st.markdown("- zvýšit limity agentů ve skupinách G1/G2/G3")
        st.markdown("- přidat směny nebo prodloužit délku směny")
        st.markdown("- posunout `batch deadline` na pozdější hodinu")
        st.markdown("- případně snížit vstupní poptávku / zkontrolovat kvalitu dat")
        st.caption(f"Technický status solveru: {status_text}")
    else:
        st.error(f"Optimalizace selhala: {status_text}")
    st.stop()

st.success(f"Optimalizace dokončena: {results['status']}")

# Key metrics
col1, col2, col3, col4 = st.columns(4)

total_agents = sum(info['total_agents'] for info in results['agents_by_group'].values())
avg_util = sum(row['utilization'] for row in results['hourly_coverage']) / len(results['hourly_coverage'])
peak_hour = max(results['hourly_coverage'], key=lambda x: x['total_demand'])

with col1:
    st.metric("Celkové náklady", f"{results['total_cost']:,.0f} Kč")
with col2:
    st.metric("Celkem agentů", f"{total_agents}")
with col3:
    st.metric("Průměrné využití", f"{avg_util:.1f}%")
with col4:
    st.metric("Špička", f"{peak_hour['hour']}:00 ({peak_hour['total_demand']:.0f} min)")

st.markdown("---")

# Two column layout for tables and charts
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Rozložení směn")
    
    # Shift schedule table
    shift_data = []
    for start in params['shift_starts']:
        for g in params['groups']:
            count = results['shifts'].get((start, g), 0)
            if count > 0:
                cost = count * params['shift_length'] * params['cost_per_hour'][g]
                shift_data.append({
                    'Směna': f"{start}:00-{(start + params['shift_length']) % 24}:00",
                    'Skupina': g,
                    'Agenti': count,
                    'Náklady (Kč)': f"{cost:,.0f}"
                })
    
    if shift_data:
        df_shifts = pd.DataFrame(shift_data)
        st.dataframe(df_shifts, use_container_width=True, hide_index=True)
    else:
        st.info("Žádní agenti nebyli přiřazeni.")
    
    st.markdown("---")
    
    # Group totals
    st.subheader("Celkový počet agentů")
    group_data = []
    for g in params['groups']:
        info = results['agents_by_group'][g]
        group_data.append({
            'Skupina': g,
            'Agenti': info['total_agents'],
            'Náklady (Kč)': f"{info['total_cost']:,.0f}"
        })
    
    df_groups = pd.DataFrame(group_data)
    st.dataframe(df_groups, use_container_width=True, hide_index=True)
    
    # Cost breakdown pie chart
    st.markdown("---")
    st.subheader("Rozdělení nákladů")
    
    cost_breakdown = pd.DataFrame([
        {'Skupina': g, 'Náklady': results['agents_by_group'][g]['total_cost']}
        for g in GROUP_ORDER
        if results['agents_by_group'][g]['total_cost'] > 0
    ])
    
    if not cost_breakdown.empty:
        fig_pie = px.pie(
            cost_breakdown,
            values='Náklady',
            names='Skupina',
            color='Skupina',
            category_orders={'Skupina': PIE_GROUP_ORDER},
            color_discrete_map=GROUP_COLORS,
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True, config=PLOTLY_CONFIG)

with col_right:
    st.subheader("Hodinová poptávka a kapacita")
    
    # Hourly coverage chart - show stacked demand by group
    df_hourly = pd.DataFrame(results['hourly_coverage'])
    
    fig = go.Figure()
    
    # Stream demand for each group (stacked)
    for g in GROUP_ORDER:
        fig.add_trace(go.Bar(
            x=df_hourly['hour'],
            y=df_hourly[f'stream_demand_{g.lower()}'],
            name=f'Stream {g}',
            marker=dict(color=GROUP_COLORS[g]),
            hovertemplate='%{x}:00<br>Stream ' + g + ': %{y:.1f} min<extra></extra>'
        ))
    
    # Batch demand for each group (stacked on top)
    for g in GROUP_ORDER:
        fig.add_trace(go.Bar(
            x=df_hourly['hour'],
            y=df_hourly[f'batch_assigned_{g.lower()}'],
            name=f'Batch {g}',
            marker=dict(color=BATCH_GROUP_COLORS[g], pattern_shape="/"),
            hovertemplate='%{x}:00<br>Batch ' + g + ': %{y:.1f} min<extra></extra>'
        ))
    
    # Capacity line
    fig.add_trace(go.Scatter(
        x=df_hourly['hour'],
        y=df_hourly['capacity'],
        mode='lines+markers',
        name='Kapacita',
        line=dict(color='#4ECDC4', width=3, dash='dot'),
        marker=dict(size=8),
        hovertemplate='%{x}:00<br>Kapacita: %{y:.0f} min<extra></extra>'
    ))
    
    fig.update_layout(
        barmode='stack',
        xaxis_title="Hodina",
        yaxis_title="Minuty",
        hovermode='x unified',
        height=400,
        legend=dict(orientation="v", yanchor="top", y=0.99, xanchor="right", x=0.99)
    )
    
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    st.markdown("---")
    
    # Utilization bar chart
    st.subheader("Využití kapacity po hodinách")
    
    fig_util = px.bar(
        df_hourly,
        x='hour',
        y='utilization',
        labels={'hour': 'Hodina', 'utilization': 'Využití (%)'},
        color='utilization',
        color_continuous_scale=['#4ECDC4', '#FFE66D', '#FF6B6B']
    )
    
    fig_util.update_layout(
        showlegend=False,
        height=300,
        yaxis_range=[0, 100]
    )
    
    st.plotly_chart(fig_util, use_container_width=True, config=PLOTLY_CONFIG)
    
    st.markdown("---")
    
    # Staffing timeline
    st.subheader("Počet agentů v čase")
    
    fig_staff = go.Figure()
    
    for g in GROUP_ORDER:
        fig_staff.add_trace(go.Bar(
            x=df_hourly['hour'],
            y=df_hourly[g],
            name=g,
            marker=dict(color=GROUP_COLORS[g]),
            text=df_hourly[g],
            textposition='inside'
        ))
    
    fig_staff.update_layout(
        barmode='stack',
        xaxis_title="Hodina",
        yaxis_title="Počet agentů",
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_staff, use_container_width=True, config=PLOTLY_CONFIG)

# Detailed hourly table at bottom
st.markdown("---")
st.subheader("Detailní pokrytí po hodinách")

df_detail = pd.DataFrame(results['hourly_coverage'])

# Create display dataframe with group-split columns
df_display = pd.DataFrame({
    'Hodina': df_detail['hour'].apply(lambda x: f"{x}:00"),
    'Stream G1': df_detail['stream_demand_g1'].round(1),
    'Stream G2': df_detail['stream_demand_g2'].round(1),
    'Stream G3': df_detail['stream_demand_g3'].round(1),
    'Batch G1': df_detail['batch_assigned_g1'].round(1),
    'Batch G2': df_detail['batch_assigned_g2'].round(1),
    'Batch G3': df_detail['batch_assigned_g3'].round(1),
    'Celkem': df_detail['total_demand'].round(1),
    'Kapacita': df_detail['capacity'].round(0),
    'Využití %': df_detail['utilization'].round(1),
    'G1': df_detail['G1'].astype(int),
    'G2': df_detail['G2'].astype(int),
    'G3': df_detail['G3'].astype(int),
})

st.dataframe(df_display, use_container_width=True, hide_index=True)
