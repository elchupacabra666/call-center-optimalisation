"""
PŘÍKLAD: Co vrací funkce load_demand_data()
=========================================

load_demand_data() vrací TUPLE se třemi věcmi:
1. stream_demand_by_group - Dict skupin s hodinovou poptávkou
2. batch_total_by_group - Dict skupin s celkovým batch workload
3. batch_deadline - Číslo (hodina)
"""

import pandas as pd

# ============================================================
# PŘÍKLAD 1: Jak vypadá vrácená data
# ============================================================

# Když zavoláš:
# stream_demand_by_group, batch_total_by_group, batch_deadline = load_demand_data('data_hovory.csv', batch_deadline=14)

# Dostaneš:

# 1. stream_demand_by_group - DICT se skupinami
#    Klíče jsou: 'G1', 'G2', 'G3'
#    Hodnoty jsou: pandas Series (index = hodina, value = minuty)

stream_demand_by_group = {
    'G1': pd.Series({
        8: 35.5,   # V 8:00 má G1 35.5 minut stream hovorů
        9: 42.1,   # V 9:00 má G1 42.1 minut stream hovorů
        10: 38.9,  # V 10:00 má G1 38.9 minut stream hovorů
        11: 45.2,  # V 11:00 má G1 45.2 minut stream hovorů
        12: 52.0,  # V 12:00 má G1 52.0 minut stream hovorů
        # ... do 20:00
    }),
    'G2': pd.Series({
        8: 48.3,   # V 8:00 má G2 48.3 minut stream hovorů
        9: 55.7,   # V 9:00 má G2 55.7 minut stream hovorů
        10: 62.1,  # V 10:00 má G2 62.1 minut stream hovorů
        # ... 
    }),
    'G3': pd.Series({
        8: 25.6,   # V 8:00 má G3 25.6 minut stream hovorů (těžké hovory, méně jich je)
        9: 28.3,   # V 9:00 má G3 28.3 minut stream hovorů
        10: 31.9,  # V 10:00 má G3 31.9 minut stream hovorů
        # ...
    })
}

# 2. batch_total_by_group - DICT se skupinami
#    Klíče jsou: 'G1', 'G2', 'G3'
#    Hodnoty jsou: FLOAT (celkem minut batch práce)

batch_total_by_group = {
    'G1': 150.5,   # G1 má celkem 150.5 minut batch práce (bez času, jen suma)
    'G2': 200.3,   # G2 má celkem 200.3 minut batch práce
    'G3': 95.8     # G3 má celkem 95.8 minut batch práce
}

# 3. batch_deadline - INT
#    Deadline = hodina, do které musí být všechna batch práce hotová

batch_deadline = 14  # Do 14:00 musí být všechny batch hovory zpracovány


# ============================================================
# PŘÍKLAD 2: Jak se to používá dál v kódu
# ============================================================

print("=" * 60)
print("PRAKTICKÝ PŘÍKLAD - Jak se to používá v optimize_schedule()")
print("=" * 60)

# Když máš vrácená data:
print("\n1. Stream demand pro G1 (hodinově):")
print(stream_demand_by_group['G1'])
print("   ^ To je pandas Series - můžeš s ním pracovat jako s tabulkou")

print("\n2. Stream demand pro G2 (hodinově):")
print(stream_demand_by_group['G2'])

print("\n3. Batch celkem po skupinách:")
for group in ['G1', 'G2', 'G3']:
    print(f"   {group}: {batch_total_by_group[group]:.1f} minut")

print("\n4. Deadline:")
print(f"   {batch_deadline}:00")
print("   ^ Do této hodiny musí být všechna batch práce hotová")

print("\n" + "=" * 60)
print("V OPTIMIZE_SCHEDULE() SE POUŽÍVÁ TAKTO:")
print("=" * 60)

# V optimize_schedule() to pak používáš v constraints:
# 
# for g in groups:  # Pro každou skupinu
#     prob += lpSum([
#         batch_assigned_by_group[(h, g)] 
#         for h in range(8, batch_deadline + 1)
#     ]) == batch_total_by_group[g]
#
# To znamená:
# "Součet všech batch minut co přiřadíme skupině G1 v hodinách 8-14
#  MUSÍ ROVNAT batch_total_by_group['G1'] = 150.5 minut"
#
# Řešení pak říká: OK, rozpracuji těch 150.5 minut G1 batch práce
# takto:
#   - Hodina 8: 20 minut
#   - Hodina 9: 25 minut
#   - Hodina 10: 30 minut
#   - Hodina 11: 35 minut
#   - Hodina 12: 25 minut
#   - Hodina 13: 15.5 minut
#   - Hodina 14: 0 minut
#   SUMA = 150.5 ✓


# ============================================================
# PŘÍKLAD 3: Vizualizace dat
# ============================================================

print("\n" + "=" * 60)
print("CO SE DĚJE V load_demand_data():")
print("=" * 60)

print("""
1. Načteme CSV soubor se sloupci:
   timestamp | duration_s | source | group
   ----------|-----------|--------|-------
   2026-03-02 08:15:00 | 180 | stream | G1
   2026-03-02 08:32:00 | 240 | stream | G2
   2026-03-02 08:45:00 | 120 | stream | G1
   (nema) | 300 | batch | G3
   (nema) | 450 | batch | G1
   ...

2. Oddělíme na stream a batch:
   STREAM: ty s timestampem (zákazník volá a čeká)
   BATCH: ty bez timestampu (administrativa, lze odložit)

3. Sečteme stream po hodinách a skupinách:
   G1 v 8:00 = 180 + 120 = 300 sekund = 5 minut
   G2 v 8:00 = 240 sekund = 4 minut
   
4. Sečteme batch po skupinách (bez rozlišení času):
   G1 batch = 300 + 450 = 750 sekund = 12.5 minut
   G3 batch = 300 sekund = 5 minut

5. Vrátíme všechna data zorganizovaná:
   stream_demand_by_group = {'G1': Series(...), 'G2': Series(...), 'G3': Series(...)}
   batch_total_by_group = {'G1': 12.5, 'G2': 0.0, 'G3': 5.0}
   batch_deadline = 14
""")
