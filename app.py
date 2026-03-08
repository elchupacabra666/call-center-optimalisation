import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from calculator import optimize_schedule, load_demand_data

st.set_page_config(page_title="Call Center Optimalizace", layout="wide")

st.title("Optimalizace personálu call centra")
st.markdown("---")

# Sidebar - Configuration
with st.sidebar:
    st.header("Konfigurace")
    
    st.subheader("Skupiny agentů")
    col1, col2 = st.columns(2)
    with col1:
        cost_g1 = st.number_input("G1 - Kč/hod", value=150, step=10)
        cost_g2 = st.number_input("G2 - Kč/hod", value=220, step=10)
        cost_g3 = st.number_input("G3 - Kč/hod", value=350, step=10)
    with col2:
        limit_g1 = st.number_input("G1 - Max", value=50, step=5)
        limit_g2 = st.number_input("G2 - Max", value=50, step=5)
        limit_g3 = st.number_input("G3 - Max", value=50, step=5)
    
    st.markdown("---")
    st.subheader("Směny")
    
    # Dynamic shift starts
    num_shifts = st.number_input("Počet směn", min_value=1, max_value=10, value=5, step=1)
    shift_starts = []
    
    cols = st.columns(2)
    for i in range(num_shifts):
        default_hour = [8, 10, 12, 14, 16, 18, 20, 22, 6][i] if i < 9 else 8
        with cols[i % 2]:
            hour = st.number_input(f"Směna {i+1} začíná", min_value=0, max_value=23, 
                                  value=default_hour, step=1, key=f"shift_{i}")
            shift_starts.append(hour)
    
    shift_length = st.slider("Délka směny (hodiny)", min_value=4, max_value=12, value=8, step=1)
    
    st.markdown("---")
    st.subheader("Parametry")
    occupancy = st.slider("Occupancy (%)", min_value=10, max_value=100, value=50, step=5) / 100
    
    st.subheader("Rozdělení hovorů")
    split_hard = st.slider("G3 Hard (%)", min_value=0, max_value=100, value=25, step=5) / 100
    split_med = st.slider("G2 Medium (%)", min_value=0, max_value=100, value=50, step=5) / 100
    split_easy = 1.0 - split_hard - split_med
    st.info(f"G1 Easy: {split_easy*100:.0f}%")
    
    if abs(split_hard + split_med + split_easy - 1.0) > 0.01:
        st.warning("Součet musí být 100%!")

# Main area - File upload and results
uploaded_file = st.file_uploader("Nahrajte CSV soubor s daty hovorů", type=['csv'])

if uploaded_file is not None:
    try:
        # Load data
        df = pd.read_csv(uploaded_file)
        
        # Validate columns
        if 'timestamp' not in df.columns or 'duration_s' not in df.columns:
            st.error("CSV musí obsahovat sloupce: 'timestamp' a 'duration_s'")
            st.stop()
        
        st.success(f"Soubor '{uploaded_file.name}' úspěšně nahrán ({len(df)} záznamů)")
        
    except Exception as e:
        st.error(f"Chyba při načítání souboru: {str(e)}")
        st.stop()
    
    # Show data preview
    with st.expander("Náhled dat"):
        st.dataframe(df.head(10))
        st.write(f"Celkem záznamů: {len(df)}")
        
    # Load demand
    demand_hours = load_demand_data(df)
    
    st.markdown("---")
    
    # Run optimization button
    if st.button("Spustit optimalizaci", type="primary", use_container_width=True):
        with st.spinner("Optimalizuji rozvrh..."):
            # Prepare parameters
            groups = ['G1', 'G2', 'G3']
            cost_per_hour = {'G1': cost_g1, 'G2': cost_g2, 'G3': cost_g3}
            limit = {'G1': limit_g1, 'G2': limit_g2, 'G3': limit_g3}
            split = {'G3_Hard': split_hard, 'G2_Med': split_med, 'G1_Easy': split_easy}
            
            # Run optimization
            results = optimize_schedule(
                data_source=df,
                groups=groups,
                cost_per_hour=cost_per_hour,
                limit=limit,
                shift_starts=sorted(shift_starts),
                shift_length=shift_length,
                occupancy=occupancy,
                split=split
            )
            
            # Store results in session state
            st.session_state['results'] = results
            st.session_state['params'] = {
                'groups': groups,
                'cost_per_hour': cost_per_hour,
                'shift_starts': sorted(shift_starts),
                'shift_length': shift_length
            }

# Display results if available
if 'results' in st.session_state:
    results = st.session_state['results']
    params = st.session_state['params']
    
    if results['status'] != 'Optimal':
        st.error(f"Optimalizace selhala: {results['status']}")
        st.stop()
    
    st.success(f"Optimalizace dokončena: {results['status']}")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_agents = sum(info['total_agents'] for info in results['agents_by_group'].values())
    avg_util = sum(row['utilization'] for row in results['hourly_coverage']) / len(results['hourly_coverage'])
    peak_hour = max(results['hourly_coverage'], key=lambda x: x['demand'])
    
    with col1:
        st.metric("Celkové náklady", f"{results['total_cost']:,.0f} Kč")
    with col2:
        st.metric("Celkem agentů", f"{total_agents}")
    with col3:
        st.metric("Průměrné využití", f"{avg_util:.1f}%")
    with col4:
        st.metric("Špička", f"{peak_hour['hour']}:00 ({peak_hour['demand']:.0f} min)")
    
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
            for g in params['groups']
            if results['agents_by_group'][g]['total_cost'] > 0
        ])
        
        if not cost_breakdown.empty:
            fig_pie = px.pie(cost_breakdown, values='Náklady', names='Skupina', 
                            color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#45B7D1'])
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_right:
        st.subheader("Hodinová poptávka a kapacita")
        
        # Hourly coverage chart
        df_hourly = pd.DataFrame(results['hourly_coverage'])
        
        fig = go.Figure()
        
        # Demand line
        fig.add_trace(go.Scatter(
            x=df_hourly['hour'],
            y=df_hourly['demand'],
            mode='lines+markers',
            name='Poptávka',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=8)
        ))
        
        # Capacity line
        fig.add_trace(go.Scatter(
            x=df_hourly['hour'],
            y=df_hourly['capacity'],
            mode='lines+markers',
            name='Kapacita',
            line=dict(color='#4ECDC4', width=3, dash='dash'),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            xaxis_title="Hodina",
            yaxis_title="Minuty",
            hovermode='x unified',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
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
        
        st.plotly_chart(fig_util, use_container_width=True)
        
        st.markdown("---")
        
        # Staffing timeline
        st.subheader("Počet agentů v čase")
        
        fig_staff = go.Figure()
        
        for g in ['G3', 'G2', 'G1']:
            fig_staff.add_trace(go.Bar(
                x=df_hourly['hour'],
                y=df_hourly[g],
                name=g,
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
        
        st.plotly_chart(fig_staff, use_container_width=True)
    
    # Detailed hourly table at bottom
    st.markdown("---")
    st.subheader("Detailní pokrytí po hodinách")
    
    df_detail = pd.DataFrame(results['hourly_coverage'])
    df_detail = df_detail.rename(columns={
        'hour': 'Hodina',
        'demand': 'Poptávka (min)',
        'capacity': 'Kapacita (min)',
        'total_agents': 'Celkem agentů',
        'utilization': 'Využití (%)'
    })
    
    df_detail['Hodina'] = df_detail['Hodina'].apply(lambda x: f"{x}:00")
    df_detail['Poptávka (min)'] = df_detail['Poptávka (min)'].round(1)
    df_detail['Kapacita (min)'] = df_detail['Kapacita (min)'].round(0)
    df_detail['Využití (%)'] = df_detail['Využití (%)'].round(1)
    
    st.dataframe(df_detail, use_container_width=True, hide_index=True)

else:
    st.info("Nahrajte CSV soubor pro začátek optimalizace")
    
    st.markdown("---")
    st.subheader("Formát CSV souboru")
    st.markdown("""
    Soubor musí obsahovat následující sloupce:
    - `timestamp`: Časové razítko hovoru (formát: YYYY-MM-DD HH:MM:SS)
    - `duration_s`: Délka hovoru v sekundách
    
    **Příklad:**
    ```
    timestamp,duration_s
    2024-01-15 08:23:45,180
    2024-01-15 08:45:12,240
    2024-01-15 09:12:33,156
    ```
    """)
