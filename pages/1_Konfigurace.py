import streamlit as st
import pandas as pd
from calculator import optimize_schedule, load_demand_data
from generator import generuj_provoz

st.set_page_config(page_title="Konfigurace", layout="wide")

st.title("Konfigurace optimalizace")
st.markdown("Zde nastavte parametry a vygenerujte nebo nahrajte data hovorů.")

# Configuration section
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
num_shifts = st.number_input("Počet směn", min_value=1, max_value=10, value=2, step=1)
shift_starts = []

cols = st.columns(2)
for i in range(num_shifts):
    default_hour = [9, 13, 16, 20, 6, 10, 14, 18, 22][i] if i < 9 else 8
    with cols[i % 2]:
        hour = st.number_input(f"Směna {i+1} začíná", min_value=0, max_value=23, 
                              value=default_hour, step=1, key=f"shift_{i}")
        shift_starts.append(hour)

shift_length = st.slider("Délka směny (hodiny)", min_value=4, max_value=12, value=8, step=1)

st.markdown("---")
st.subheader("Parametry")
occupancy = st.slider("Occupancy (%)", min_value=10, max_value=100, value=50, step=5) / 100

st.markdown("---")
st.subheader("Batch parametry")
batch_deadline = st.number_input("Batch deadline (hodina)", min_value=9, max_value=21, value=14, step=1)
use_night_batch = st.checkbox("Použít night batch", value=True, key="use_night_batch")

st.markdown("---")

# Generator section
st.markdown("---")
st.subheader("Generátor dat")

gen_pocet = st.number_input("Počet hovorů", min_value=50, max_value=10000, value=500, step=50, key="gen_pocet")

gen_batch_ratio = st.slider(
    "Batch hovor (procenta)",
    min_value=0,
    max_value=100,
    value=70,
    step=5,
    key="gen_batch_ratio",
    disabled=not use_night_batch,
)
gen_batch_ratio_float = gen_batch_ratio / 100

if not use_night_batch:
    st.caption("Night batch je vypnutý: všechny hovory budou stream.")

st.markdown("**Rozdělení skupin hovorů**")
col_g1, col_g2 = st.columns(2)
with col_g1:
    gen_g1_pct = st.number_input("G1 (%)", min_value=0, max_value=100, value=25, step=1, key="gen_g1_pct")
with col_g2:
    gen_g2_pct = st.number_input("G2 (%)", min_value=0, max_value=100, value=50, step=1, key="gen_g2_pct")

gen_g3_pct = 100 - gen_g1_pct - gen_g2_pct
group_split_valid = gen_g3_pct >= 0

if group_split_valid:
    st.caption(f"G3 (%) dopočet: **{gen_g3_pct}**")
else:
    st.error("Součet G1 + G2 nesmí být větší než 100 %.")

gen_seed = st.number_input("Seed (0 = náhodný)", min_value=0, max_value=99999, value=0, step=1, key="gen_seed")
seed = None if gen_seed == 0 else int(gen_seed)

# Preview
batch_count = round(gen_pocet * gen_batch_ratio_float)
stream_count = gen_pocet - batch_count

if not use_night_batch:
    batch_count = 0
    stream_count = gen_pocet

g1_count = round(gen_pocet * (gen_g1_pct / 100)) if group_split_valid else 0
g2_count = round(gen_pocet * (gen_g2_pct / 100)) if group_split_valid else 0
g3_count = gen_pocet - g1_count - g2_count if group_split_valid else 0

st.caption(f"📊 Batch hovorů: **{batch_count}**")
st.caption(f"📊 Stream hovorů: **{stream_count}**")
st.caption(f"👤 G1 hovorů: **{g1_count}**, G2 hovorů: **{g2_count}**, G3 hovorů: **{g3_count}**")

if st.button("Generovat data", type="primary", use_container_width=True):
    with st.spinner("Generuji data..."):
        try:
            if not group_split_valid:
                st.error("Neplatné rozdělení skupin. Opravte G1/G2 procenta.")
                st.stop()

            split = {
                'G3_Hard': gen_g3_pct / 100,
                'G2_Med': gen_g2_pct / 100,
                'G1_Easy': gen_g1_pct / 100,
            }

            df = generuj_provoz(
                pocet_hovoru=gen_pocet,
                batch_ratio=gen_batch_ratio_float,
                output_path=None,
                seed=seed,
                split=split,
                use_night_batch=use_night_batch,
            )
            st.session_state["generated_df"] = df
            st.success(
                f"✅ Data vygenerována: {len(df)} hovorů ({batch_count} batch, {stream_count} stream, "
                f"G1 {g1_count}, G2 {g2_count}, G3 {g3_count})"
            )
        except Exception as e:
            st.error(f"Chyba při generování: {str(e)}")

st.markdown("---")

# Data loading section
st.subheader("Zdroj dat")

# Determine data source
uploaded_file = st.file_uploader("Nahrajte CSV soubor s daty hovorů", type=['csv'], key="file_uploader")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        data_source = "nahrán"
    except Exception as e:
        st.error(f"Chyba při načítání souboru: {str(e)}")
        df = None
        data_source = None
elif "generated_df" in st.session_state:
    df = st.session_state["generated_df"]
    data_source = "vygenerován"
else:
    df = None
    data_source = None

# Check if data is valid
if df is not None:
    if 'timestamp' not in df.columns or 'duration_s' not in df.columns:
        st.error("Data musí obsahovat sloupce: 'timestamp' a 'duration_s'")
        df = None
    else:
        st.success(f"✅ Zdroj: {data_source} ({len(df)} záznamů)")
        
        # Data preview
        with st.expander("Náhled dat"):
            st.dataframe(df.head(10))
            st.write(f"Celkem záznamů: {len(df)}")
            if 'source' in df.columns:
                st.write(f"Stream: {len(df[df['source'] == 'stream'])}, Batch: {len(df[df['source'] == 'batch'])}")
            if 'group' in df.columns:
                st.write(f"G3: {len(df[df['group'] == 'G3'])}, G2: {len(df[df['group'] == 'G2'])}, G1: {len(df[df['group'] == 'G1'])}")
else:
    st.info("💡 Nahrajte CSV soubor nebo vygenerujte data")
    st.stop()

st.markdown("---")

# Optimization button
if st.button("Spustit optimalizaci", type="primary", use_container_width=True):
    with st.spinner("Optimalizuji rozvrh..."):
        try:
            # Load demand
            current_use_night_batch = st.session_state.get("use_night_batch", use_night_batch)
            stream_demand_by_group, batch_total_by_group, batch_deadline_info = load_demand_data(
                df,
                batch_deadline,
                use_night_batch=current_use_night_batch,
            )
            
            # Prepare parameters
            groups = ['G1', 'G2', 'G3']
            cost_per_hour = {'G1': cost_g1, 'G2': cost_g2, 'G3': cost_g3}
            limit = {'G1': limit_g1, 'G2': limit_g2, 'G3': limit_g3}
            
            # Run optimization
            results = optimize_schedule(
                data_source=df,
                groups=groups,
                cost_per_hour=cost_per_hour,
                limit=limit,
                shift_starts=sorted(shift_starts),
                shift_length=shift_length,
                occupancy=occupancy,
                batch_deadline=batch_deadline,
                use_night_batch=current_use_night_batch,
            )
            
            # Store results in session state
            st.session_state['results'] = results
            st.session_state['params'] = {
                'groups': groups,
                'cost_per_hour': cost_per_hour,
                'shift_starts': sorted(shift_starts),
                'shift_length': shift_length,
                'use_night_batch': current_use_night_batch,
            }
            
            st.success("✅ Optimalizace dokončena! Přejděte na stránku **Výsledky** pro zobrazení.")
            
        except Exception as e:
            st.error(f"Chyba při optimalizaci: {str(e)}")
