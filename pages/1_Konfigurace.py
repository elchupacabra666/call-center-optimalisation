import streamlit as st
import pandas as pd
from calculator import optimize_schedule, load_demand_data
from generator import generuj_provoz
from state_utils import persist_state

st.set_page_config(page_title="Konfigurace", layout="wide")
persist_state()  # Ochrana session_state klíčů před GC při navigaci mezi stránkami

# ── Provozní okno call centra ─────────────────────────────────────────────────
# Aplikace plánuje pouze v rámci 9:00–21:00. Všechny směny se musí celou délkou
# vejít do tohoto okna (start + shift_length <= 21).
OPERATING_START = 9
OPERATING_END = 21  # exclusive (poslední pracovní hodina je 20:00-21:00)
# ─────────────────────────────────────────────────────────────────────────────

# ── Initialize session_state defaults BEFORE any widget is rendered ───────────
_defaults = {
    "cost_g1": 150,
    "cost_g2": 220,
    "cost_g3": 350,
    "limit_g1": 50,
    "limit_g2": 50,
    "limit_g3": 50,
    "num_shifts": 2,
    "shift_length": 8,
    "occupancy_pct": 50,
    "batch_deadline": 14,
    "use_night_batch": True,
    "gen_pocet": 500,
    "gen_batch_ratio": 70,
    "gen_g1_pct": 25,
    "gen_g2_pct": 50,
    "gen_seed": 0,
    # Výchozí starty směn: pro default shift_length=8 je platný rozsah 9–13.
    "shift_0": 9,
    "shift_1": 11,
    "shift_2": 13,
    "shift_3": 10,
    "shift_4": 12,
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Clamp všech existujících shift_* hodnot do platného rozsahu pro aktuální
# shift_length. Když uživatel změní délku směny, uloženou hodnotu upravíme tak,
# aby nespadla mimo [OPERATING_START, OPERATING_END - shift_length], jinak by
# number_input spadl na chybu "value out of range".
_max_shift_start = OPERATING_END - st.session_state["shift_length"]
for _i in range(10):  # max_value num_shifts je 10
    _key = f"shift_{_i}"
    if _key in st.session_state:
        st.session_state[_key] = min(
            max(st.session_state[_key], OPERATING_START),
            _max_shift_start,
        )
# ─────────────────────────────────────────────────────────────────────────────

st.title("Konfigurace optimalizace")
st.markdown("Zde nastavte parametry a vygenerujte nebo nahrajte data hovorů.")

# Configuration section
st.subheader("Skupiny agentů")
col1, col2 = st.columns(2)
with col1:
    st.number_input("G1 - Kč/hod", step=10, key="cost_g1")
    st.number_input("G2 - Kč/hod", step=10, key="cost_g2")
    st.number_input("G3 - Kč/hod", step=10, key="cost_g3")
with col2:
    st.number_input("G1 - Max", step=5, key="limit_g1")
    st.number_input("G2 - Max", step=5, key="limit_g2")
    st.number_input("G3 - Max", step=5, key="limit_g3")

st.markdown("---")
st.subheader("Směny")

st.number_input("Počet směn", min_value=1, max_value=10, step=1, key="num_shifts")
num_shifts = st.session_state["num_shifts"]

# Dynamický strop podle aktuální délky směny – směna musí celá spadnout do 9–21.
max_shift_start = OPERATING_END - st.session_state["shift_length"]

shift_starts = []
cols = st.columns(2)
for i in range(num_shifts):
    # Ensure key exists for any newly added shift (např. při zvýšení num_shifts)
    if f"shift_{i}" not in st.session_state:
        _default_hours = [9, 11, 13, 10, 12]
        _candidate = _default_hours[i] if i < len(_default_hours) else OPERATING_START
        # Defaultní hodnota musí respektovat aktuální max_shift_start
        st.session_state[f"shift_{i}"] = min(max(_candidate, OPERATING_START), max_shift_start)
    with cols[i % 2]:
        st.number_input(
            f"Směna {i+1} začíná",
            min_value=OPERATING_START,
            max_value=max_shift_start,
            step=1,
            key=f"shift_{i}",
            help=f"Provozní okno je {OPERATING_START}:00–{OPERATING_END}:00, směna se musí vejít celá.",
        )
        shift_starts.append(st.session_state[f"shift_{i}"])

st.slider("Délka směny (hodiny)", min_value=4, max_value=12, step=1, key="shift_length")
shift_length = st.session_state["shift_length"]

st.markdown("---")
st.subheader("Parametry")
st.slider("Occupancy (%)", min_value=10, max_value=100, step=5, key="occupancy_pct")
occupancy = st.session_state["occupancy_pct"] / 100

st.markdown("---")
st.subheader("Batch parametry")
st.number_input("Batch deadline (hodina)", min_value=10, max_value=21, step=1, key="batch_deadline",
                help="Hodina, do které musí být všechna batch práce hotová. Minimum je 10 (tj. batch se může zpracovávat minimálně v hodině 9).")
batch_deadline = st.session_state["batch_deadline"]
st.checkbox("Použít night batch", key="use_night_batch")
use_night_batch = st.session_state["use_night_batch"]

st.markdown("---")
st.subheader("Generátor dat")

st.number_input("Počet hovorů", min_value=50, max_value=10000, step=50, key="gen_pocet")
gen_pocet = st.session_state["gen_pocet"]

st.slider(
    "Batch hovor (procenta)",
    min_value=0, max_value=100, step=5,
    key="gen_batch_ratio",
    disabled=not use_night_batch,
)
gen_batch_ratio_float = st.session_state["gen_batch_ratio"] / 100

if not use_night_batch:
    st.caption("Night batch je vypnutý: všechny hovory budou stream.")

st.markdown("**Rozdělení skupin hovorů**")
col_g1, col_g2 = st.columns(2)
with col_g1:
    st.number_input("G1 (%)", min_value=0, max_value=100, step=1, key="gen_g1_pct")
with col_g2:
    st.number_input("G2 (%)", min_value=0, max_value=100, step=1, key="gen_g2_pct")

gen_g1_pct = st.session_state["gen_g1_pct"]
gen_g2_pct = st.session_state["gen_g2_pct"]
gen_g3_pct = 100 - gen_g1_pct - gen_g2_pct
group_split_valid = gen_g3_pct >= 0

if group_split_valid:
    st.info(f"**Dopočet G3:** `100 - G1 - G2 = {gen_g3_pct} %`", icon="🧮")
else:
    st.error("Součet G1 + G2 nesmí být větší než 100 %.")

st.number_input("Seed (0 = náhodný)", min_value=0, max_value=99999, step=1, key="gen_seed")
seed = None if st.session_state["gen_seed"] == 0 else int(st.session_state["gen_seed"])

# Preview
batch_count = round(gen_pocet * gen_batch_ratio_float) if use_night_batch else 0
stream_count = gen_pocet - batch_count
g1_count = round(gen_pocet * (gen_g1_pct / 100)) if group_split_valid else 0
g2_count = round(gen_pocet * (gen_g2_pct / 100)) if group_split_valid else 0
g3_count = gen_pocet - g1_count - g2_count if group_split_valid else 0

st.caption(f"Batch hovorů: **{batch_count}**")
st.caption(f"Stream hovorů: **{stream_count}**")
st.caption(f"G1 hovorů: **{g1_count}**, G2 hovorů: **{g2_count}**, G3 hovorů: **{g3_count}**")

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
                f"Data vygenerována: {len(df)} hovorů ({batch_count} batch, {stream_count} stream, "
                f"G1 {g1_count}, G2 {g2_count}, G3 {g3_count})"
            )
        except Exception as e:
            st.error(f"Chyba při generování: {str(e)}")

st.markdown("---")

# Data loading section
st.subheader("Zdroj dat")

uploaded_file = st.file_uploader("Nahrajte CSV soubor s daty hovorů", type=['csv'])

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

if df is not None:
    required_cols = ['timestamp', 'duration_s', 'source', 'group']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Chybí: {', '.join([repr(c) for c in missing_cols])}")
        st.info("Pokud se soubor nedaří nahrát, podívejte se prosím do návodu.")
        df = None
    else:
        st.success(f"Zdroj: {data_source} ({len(df)} záznamů)")

        with st.expander("Náhled dat"):
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.write(f"Celkem záznamů: {len(df)}")
            if 'source' in df.columns:
                st.write(f"Stream: {len(df[df['source'] == 'stream'])}, Batch: {len(df[df['source'] == 'batch'])}")
            if 'group' in df.columns:
                st.write(f"G3: {len(df[df['group'] == 'G3'])}, G2: {len(df[df['group'] == 'G2'])}, G1: {len(df[df['group'] == 'G1'])}")
else:
    st.info("Nahrajte CSV soubor nebo vygenerujte data")
    st.stop()

st.markdown("---")

if st.button("Spustit optimalizaci", type="primary", use_container_width=True):
    # Validace: duplicitní začátky směn by vedly k tichému sloučení v LP modelu
    # (PuLP dict klíče (hour, group) se přepíší). Raději tvrdě odmítnout.
    duplicates = sorted({h for h in shift_starts if shift_starts.count(h) > 1})
    if duplicates:
        duplicates_str = ", ".join(f"{h}:00" for h in duplicates)
        st.error(
            f"Duplicitní začátky směn: {duplicates_str}. "
            f"Každá směna musí mít unikátní začátek – upravte konfiguraci výše."
        )
        st.stop()

    with st.spinner("Optimalizuji rozvrh..."):
        try:
            current_use_night_batch = st.session_state.get("use_night_batch", True)
            stream_demand_by_group, batch_total_by_group, batch_deadline_info = load_demand_data(
                df,
                batch_deadline,
                use_night_batch=current_use_night_batch,
            )

            groups = ['G1', 'G2', 'G3']
            cost_per_hour = {
                'G1': st.session_state["cost_g1"],
                'G2': st.session_state["cost_g2"],
                'G3': st.session_state["cost_g3"],
            }
            limit_map = {
                'G1': st.session_state["limit_g1"],
                'G2': st.session_state["limit_g2"],
                'G3': st.session_state["limit_g3"],
            }

            results = optimize_schedule(
                data_source=df,
                groups=groups,
                cost_per_hour=cost_per_hour,
                limit=limit_map,
                shift_starts=sorted(shift_starts),
                shift_length=shift_length,
                occupancy=occupancy,
                batch_deadline=batch_deadline,
                use_night_batch=current_use_night_batch,
            )

            st.session_state['results'] = results
            st.session_state['params'] = {
                'groups': groups,
                'cost_per_hour': cost_per_hour,
                'shift_starts': sorted(shift_starts),
                'shift_length': shift_length,
                'use_night_batch': current_use_night_batch,
            }

            st.success("Optimalizace dokončena! Přejděte na stránku **Výsledky** pro zobrazení.")

        except Exception as e:
            st.error(f"Chyba při optimalizaci: {str(e)}")
