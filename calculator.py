from pulp import *
import pandas as pd

DATA = 'data_hovory.csv'

# employee groups information
GROUPS = ['G1', 'G2', 'G3']
COST_PER_HOUR = {'G1': 150, 'G2': 220, 'G3': 350} # could be rewritten to fixed part + bonus from each call (if i get enough data)

#shift information
SHIFT_STARTS = [8, 10, 12, 14, 16]
SHIFT_LENGTH = 8  # Different shift lengths in hours

# could combine groups + shifts lengths for different types of employee (comes at whatever times and leaves even after few hours)

# occupancy - kolik % času agent skutečně vyřizuje hovory (zbytek = pauza, ACW, idle)
OCCUPANCY = 0.50  # 50% času na hovorech

#call split - defined number -> could be different based on reality (if i get enough data i can change it)
# note: group G3 can make calls for G3, G2 and G1
SPLIT = {'G3_Hard': 0.25, 'G2_Med': 0.50, 'G1_Easy': 0.25}


# load data  TODO: failed load
def read_data():

    df = pd.read_csv(DATA)

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    df['hour'] = df['timestamp'].dt.hour

    demand_hour = df.groupby('hour')['duration_s'].sum() / 60


    print("Poptávka v minutách pro jednotlivé hodiny:")
    print(demand_hour)

    return demand_hour


def get_active_workers(shifts, hour, group):
    count = 0
    for start in SHIFT_STARTS:
        if start <= hour < start + SHIFT_LENGTH:
            count += shifts[(start, group)]
    return count


#model
prob = LpProblem("Shift_Scheduling_Cascade", LpMinimize)

shifts = LpVariable.dicts("Nabor", 
                               ((h, g) for h in SHIFT_STARTS for g in GROUPS), 
                               lowBound=0, cat='Integer')


demand_hours = read_data()

#nastaveni podminek
for t in demand_hours.index:  # ← iteruj přes INDEX (hodiny 8, 9, 10...), ne hodnoty
    #vypocet poptavek
    total_req = demand_hours[t]
    req_hard = total_req * SPLIT['G3_Hard']
    req_med  = total_req * SPLIT['G2_Med']
    req_easy = total_req * SPLIT['G1_Easy']


    staff_g3 = get_active_workers(shifts, t, 'G3')
    staff_g2 = get_active_workers(shifts, t, 'G2')
    staff_g1 = get_active_workers(shifts, t, 'G1')
    
    # každý agent má kapacitu 60 min * OCCUPANCY za hodinu
    capacity_per_agent = 60 * OCCUPANCY

    # cally G3 jsou jen pro G3
    prob += staff_g3 * capacity_per_agent >= req_hard, f"Hard_Coverage_Hour_{t}"

    #cally pro G2 jsou pro G3 a G2
    prob += (staff_g3 + staff_g2) * capacity_per_agent >= req_hard + req_med, f"Med_Coverage_Hour_{t}"
    
    #g1
    prob += (staff_g3 + staff_g2 + staff_g1) * capacity_per_agent >= total_req, f"Total_Coverage_Hour_{t}"


#ucelova funkce

total_cost = 0
for start in SHIFT_STARTS:
    for g in GROUPS:
        total_cost += shifts[(start, g)] * SHIFT_LENGTH * COST_PER_HOUR[g]

prob += total_cost



#vypis

prob.solve()
print(f"\nStatus: {LpStatus[prob.status]}")
print(f"Celkové náklady na mzdy: {value(prob.objective):,.0f} Kč\n")



#zatim provizorni vypis co jsem si nechal vygenerovat
print("=" * 60)
print("OPTIMÁLNÍ ROZLOŽENÍ SMĚN:")
print("=" * 60)

for start in SHIFT_STARTS:
    print(f"\nSměna začínající v {start}:00 (trvá {SHIFT_LENGTH}h):")
    for g in GROUPS:
        count = int(value(shifts[(start, g)]))
        cost = count * SHIFT_LENGTH * COST_PER_HOUR[g]
        print(f"  {g}: {count} agentů (náklady: {cost:,} Kč)")

print("\n" + "=" * 60)
print("CELKOVÝ POČET AGENTŮ PO SKUPINÁCH:")
print("=" * 60)

for g in GROUPS:
    total_agents = sum(int(value(shifts[(start, g)])) for start in SHIFT_STARTS)
    total_cost = sum(int(value(shifts[(start, g)])) * SHIFT_LENGTH * COST_PER_HOUR[g] for start in SHIFT_STARTS)
    print(f"{g}: {total_agents} agentů celkem (náklady: {total_cost:,} Kč)")

print("\n" + "=" * 60)
print("POKRYTÍ POPTÁVKY PO HODINÁCH:")
print("=" * 60)

for t in demand_hours.index:
    staff_g3 = sum(int(value(shifts[(start, 'G3')])) for start in SHIFT_STARTS if start <= t < start + SHIFT_LENGTH)
    staff_g2 = sum(int(value(shifts[(start, 'G2')])) for start in SHIFT_STARTS if start <= t < start + SHIFT_LENGTH)
    staff_g1 = sum(int(value(shifts[(start, 'G1')])) for start in SHIFT_STARTS if start <= t < start + SHIFT_LENGTH)
    
    total_capacity = (staff_g3 + staff_g2 + staff_g1) * 60 * OCCUPANCY  # kapacita s occupancy
    demand = demand_hours[t]
    utilization = (demand / total_capacity * 100) if total_capacity > 0 else 0
    
    print(f"Hodina {t}:00 | Poptávka: {demand:6.1f} min | Kapacita: {total_capacity:4.0f} min | "
          f"Agenti: G3={staff_g3}, G2={staff_g2}, G1={staff_g1} | Využití: {utilization:.1f}%")
