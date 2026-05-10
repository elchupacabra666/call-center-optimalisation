from pulp import LpProblem, LpVariable, LpMinimize, LpStatus, value, lpSum
import pandas as pd


def load_demand_data(data_source, batch_deadline: int = 14, use_night_batch: bool = True):
    """
    Load and aggregate call data from CSV file or DataFrame, split by source and group.
    Groups are assigned during generation in generator.py.
    
    Args:
        data_source: Path to CSV file or pandas DataFrame
        batch_deadline: Hour by which all batch calls must be completed
        use_night_batch: If False, batch part is ignored and set to zero
    
    Returns:
        Tuple of (stream_demand_by_group, batch_total_by_group, batch_deadline)
        - stream_demand_by_group: Dict with keys 'G3', 'G2', 'G1', each with Series of hourly demand
        - batch_total_by_group: Dict with keys 'G3', 'G2', 'G1', each with total minutes of batch calls
        - batch_deadline: int, deadline hour for batch processing
    """
    # Načteme soubor - buď CSV cestu nebo DataFrame, který už máme v paměti
    if isinstance(data_source, pd.DataFrame):
        df = data_source
    else:
        df = pd.read_csv(data_source)
    
    # Převedeme text z CSV na správný datetime formát, aby Pandas věděl, jak s ním manipulovat
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Oddělíme hovory na dva druhy: ty co se dělají hned (stream) a ty co si můžeme odložit (batch)
    df_stream = df[df['source'] == 'stream']
    if use_night_batch:
        df_batch = df[df['source'] == 'batch']
    else:
        df_batch = df.iloc[0:0].copy()
    
    # Pro každou skupinu (jednoduší, střední, těžcí agenti) sečteme kolik minut práce mají za každou hodinu
    stream_demand_by_group = {}
    for group in ['G1', 'G2', 'G3']:
        # .copy() abychom nemanipulovali s view a nedostali SettingWithCopyWarning
        df_stream_group = df_stream[df_stream['group'] == group].copy()
        if len(df_stream_group) > 0:
            df_stream_group['hour'] = df_stream_group['timestamp'].dt.hour
            stream_demand_by_group[group] = df_stream_group.groupby('hour')['duration_s'].sum() / 60
        else:
            stream_demand_by_group[group] = pd.Series(dtype=float)
    
    # Stejné jako nahoře, ale pro batch hovory - ty nemají čas, takže jen sečteme celkem za skupinu
    batch_total_by_group = {}
    for group in ['G1', 'G2', 'G3']:
        df_batch_group = df_batch[df_batch['group'] == group]
        if len(df_batch_group) > 0:
            batch_total_by_group[group] = df_batch_group['duration_s'].sum() / 60
        else:
            batch_total_by_group[group] = 0.0
    
    return stream_demand_by_group, batch_total_by_group, batch_deadline


def optimize_schedule(
    data_source,
    groups=['G1', 'G2', 'G3'],
    cost_per_hour={'G1': 150, 'G2': 220, 'G3': 350},
    limit={'G1': 10, 'G2': 50, 'G3': 50},
    shift_starts=[8, 10, 12, 14, 16],
    shift_length=8,
    occupancy=0.50,
    batch_deadline: int = 14,
    use_night_batch: bool = True
):
    """
    Optimize call center staff scheduling to minimize costs while meeting demand.
    
    Args:
        data_source: Path to CSV file or pandas DataFrame with columns 'timestamp', 'duration_s', 'source', 'group'
        groups: List of agent groups (e.g., ['G1', 'G2', 'G3'])
        cost_per_hour: Dictionary with hourly cost for each group
        limit: Dictionary with maximum total agents per group across all shifts
        shift_starts: List of shift start hours (e.g., [8, 10, 12, 14, 16])
        shift_length: Length of each shift in hours
        occupancy: Fraction of time agents spend on calls (0.0-1.0)
        batch_deadline: Hour by which all batch calls must be completed
        use_night_batch: If False, batch backlog is disabled
    
    Returns:
        Dictionary with optimization results:
            - status: Optimization status ('Optimal', 'Infeasible', etc.)
            - total_cost: Total cost in currency units
            - shifts: Dict of (start_hour, group) -> number of agents
            - agents_by_group: Dict of group -> (total_agents, total_cost)
            - hourly_coverage: List of dicts with hourly staffing details
            - stream_demand_by_group: Stream call demand by group
            - batch_total_by_group: Total batch work by group
            - batch_deadline: Deadline hour for batch processing
    """
    
    # Pomocná funkce - spočítá kolik agentů je aktuálně v práci v konkrétní hodinu
    def get_active_workers(shifts_var, hour, group):
        count = 0
        for start in shift_starts:
            if start <= hour < start + shift_length:
                count += shifts_var[(start, group)]
        return count
    
    # Načteme data - stream a batch hovory rozdělené po skupinách
    stream_demand_by_group, batch_total_by_group, batch_deadline = load_demand_data(
        data_source,
        batch_deadline,
        use_night_batch=use_night_batch,
    )
    
    # Vytvoříme optimalizační problém - říkáme: chceme minimalizovat náklady
    prob = LpProblem("Shift_Scheduling_Cascade", LpMinimize)
    
    # Rozhodovací proměnné: Kolik agentů (z které skupiny) přijmeme na jakou směnu?
    # Příklad: shifts[(9, 'G3')] = 5 znamená "5 agentů skupiny G3 na směnu od 9:00"
    shifts = LpVariable.dicts("Nabor", 
                               ((h, g) for h in shift_starts for g in groups), 
                               lowBound=0, cat='Integer')
    
    # Rozhodovací proměnné: Kolik minut batch práce budeme dělat v každé hodině (pro každou skupinu)?
    # Příklad: batch_by_group[(10, 'G1')] = 30 znamená "30 minut batch práce pro G1 v 10:00"
    batch_by_group = LpVariable.dicts("BatchByGroup",
                                               ((h, g) for h in range(9, batch_deadline) for g in groups),
                                               lowBound=0, cat='Continuous')
    
    # Omezení 1: Všechna batch práce musí být hotová do deadline
    # Pokud má G1 100 minut batch práce, musíme ji rozvrhnout mezi 9:00 a deadline tak, aby se sečetla na 100
    for g in groups:
        prob += lpSum([batch_by_group[(h, g)] for h in range(9, batch_deadline)]) == batch_total_by_group[g], f"Batch_Deadline_{g}"
    
    # Pokrýváme všechny provozní hodiny 9:00-20:59 bez ohledu na to,
    # zda v nich zrovna stream obsahuje záznam
    all_hours = range(9, 21)
    
    # Omezení 2: V každé hodině musíme mít dost kapacity na stream hovory + batch práci kterou jsme naplánovali
    # Stream hovory jsou naléhavé (zákazník čeká), batch si můžeme vybrat kdy dělat
    #
    # SKILL CASCADE (kumulativní pokrytí):
    # - G3 práci umí jen G3 agenti
    # - G2 práci umí G3 nebo G2 agenti
    # - G1 práci umí kdokoli (G3, G2, G1)
    # Constrainty formulujeme kumulativně: kapacita na dané úrovni a výš
    # musí pokrýt součet práce na dané úrovni a výš.
    for t in all_hours:
        # Spočítáme kolik agentů máme v každé skupině v tuto hodinu
        staff_g3 = get_active_workers(shifts, t, 'G3')
        staff_g2 = get_active_workers(shifts, t, 'G2')
        staff_g1 = get_active_workers(shifts, t, 'G1')

        # Každý agent zvládne 30 minut práce za hodinu (60 minut * 50% occupancy)
        capacity_per_agent = 60 * occupancy

        # Práce (stream + batch) po skupinách v této hodině
        work_g3 = stream_demand_by_group['G3'].get(t, 0) + (batch_by_group[(t, 'G3')] if t < batch_deadline else 0)
        work_g2 = stream_demand_by_group['G2'].get(t, 0) + (batch_by_group[(t, 'G2')] if t < batch_deadline else 0)
        work_g1 = stream_demand_by_group['G1'].get(t, 0) + (batch_by_group[(t, 'G1')] if t < batch_deadline else 0)

        # G3 práci zvládnou jen G3 agenti
        prob += staff_g3 * capacity_per_agent >= work_g3, f"G3_Coverage_Hour_{t}"

        # G2 + G3 práci zvládnou G2 a G3 agenti dohromady
        prob += (staff_g3 + staff_g2) * capacity_per_agent >= work_g3 + work_g2, f"G2_Coverage_Hour_{t}"

        # Celou práci (G1 + G2 + G3) zvládnou všichni agenti dohromady
        prob += (staff_g3 + staff_g2 + staff_g1) * capacity_per_agent >= work_g3 + work_g2 + work_g1, f"G1_Coverage_Hour_{t}"
    
    # Omezení 3: Nemůžeme najmout unlimited agentů - máme limit na každou skupinu
    # (Poznámka: Omezení 2 už zajišťuje, že máme dost kapacity na stream+batch v každé hodině.
    #  Batch se automaticky rozvrháže do hodin s volnou kapacitou.)
    for g in groups:
        total_agents = sum(shifts[(start, g)] for start in shift_starts)
        prob += total_agents <= limit[g], f"Max_Agents_{g}"
    
    # Cíl: Minimalizujeme celkové náklady na mzdy
    # (počet agentů × délka směny × hodinová sazba)
    total_cost = 0
    for start in shift_starts:
        for g in groups:
            total_cost += shifts[(start, g)] * shift_length * cost_per_hour[g]
    
    prob += total_cost
    
    # Spustíme solver - najde nejlevnější řešení které splňuje všechna omezení
    prob.solve()
    
    # Vyextrahujeme výsledky z optimalizace
    results = {
        'status': LpStatus[prob.status],
        'total_cost': value(prob.objective) if prob.status == 1 else None,
        'shifts': {},
        'agents_by_group': {},
        'hourly_coverage': [],
        'stream_demand_by_group': stream_demand_by_group,
        'batch_total_by_group': batch_total_by_group,
        'batch_deadline': batch_deadline,
        'use_night_batch': use_night_batch,
    }
    
    # Pokud se podařilo najít optimální řešení, rozpracujeme výsledky
    if prob.status == 1:  # 1 = Optimal solution found
        # Zjistíme kolik agentů má být na každé směně
        for start in shift_starts:
            for g in groups:
                results['shifts'][(start, g)] = int(value(shifts[(start, g)]))
        
        # Spočítáme celkem agentů a náklady pro každou skupinu
        for g in groups:
            total_agents = sum(results['shifts'][(start, g)] for start in shift_starts)
            group_cost = sum(results['shifts'][(start, g)] * shift_length * cost_per_hour[g] 
                           for start in shift_starts)
            results['agents_by_group'][g] = {
                'total_agents': total_agents,
                'total_cost': group_cost
            }
        
        # Pro každou hodinu vypočítáme detaily: kolik agentů, kolik práce, jaká obsazenost
        for t in range(9, 21):
            # Spočítáme kolik agentů které skupiny je teď v práci
            staff_by_group = {}
            for g in groups:
                staff_by_group[g] = sum(
                    results['shifts'][(start, g)]
                    for start in shift_starts
                    if start <= t < start + shift_length
                )
            
            # Kapacita = součet všech agentů × čas kterou zvládnou za hodinu
            total_agents = sum(staff_by_group.values())
            total_capacity = total_agents * 60 * occupancy
            
            # Jaké máme požadavky na práci v tuto hodinu (stream + batch)
            stream_demand_g1 = stream_demand_by_group['G1'].get(t, 0)
            stream_demand_g2 = stream_demand_by_group['G2'].get(t, 0)
            stream_demand_g3 = stream_demand_by_group['G3'].get(t, 0)
            total_stream = stream_demand_g1 + stream_demand_g2 + stream_demand_g3
            
            # Jak jsme si naplánovali zpracovat batch (z řešení optimalizace)
            batch_g1 = value(batch_by_group[(t, 'G1')]) if t < batch_deadline else 0
            batch_g2 = value(batch_by_group[(t, 'G2')]) if t < batch_deadline else 0
            batch_g3 = value(batch_by_group[(t, 'G3')]) if t < batch_deadline else 0
            total_batch = batch_g1 + batch_g2 + batch_g3
            
            # Celková práce a jak moc jsme vytížení
            total_work = total_stream + total_batch
            utilization = (total_work / total_capacity * 100) if total_capacity > 0 else 0
            
            # Uložíme všechny detaily pro tuto hodinu
            results['hourly_coverage'].append({
                'hour': t,
                'stream_demand_g1': stream_demand_g1,
                'stream_demand_g2': stream_demand_g2,
                'stream_demand_g3': stream_demand_g3,
                'stream_demand_total': total_stream,
                'batch_assigned_g1': batch_g1,
                'batch_assigned_g2': batch_g2,
                'batch_assigned_g3': batch_g3,
                'batch_assigned_total': total_batch,
                'total_demand': total_work,
                'capacity': total_capacity,
                'G1': staff_by_group.get('G1', 0),
                'G2': staff_by_group.get('G2', 0),
                'G3': staff_by_group.get('G3', 0),
                'total_agents': total_agents,
                'utilization': utilization
            })
    
    return results


def print_results(results, shift_starts, shift_length, groups, cost_per_hour):
    """
    Print optimization results in a formatted way.
    
    Args:
        results: Results dictionary from optimize_schedule()
        shift_starts: List of shift start hours
        shift_length: Length of each shift
        groups: List of agent groups
        cost_per_hour: Cost per hour for each group
    """
    # Řekneme jestli se to vyřešilo nebo ne
    print(f"\nStatus: {results['status']}")
    
    if results['total_cost'] is not None:
        # Základní informace o celkových nákladech a batch práci
        print(f"Celkové náklady na mzdy: {results['total_cost']:,.0f} Kč")
        print(f"\nBatch work po skupinách:")
        for g in groups:
            total = results['batch_total_by_group'][g]
            print(f"  {g}: {total:.1f} minut")
        print(f"Deadline: {results['batch_deadline']}:00\n")
        
        # Detailní přehled - jaký je náš optimální plán směn
        print("=" * 60)
        print("OPTIMÁLNÍ ROZLOŽENÍ SMĚN:")
        print("=" * 60)
        
        for start in shift_starts:
            print(f"\nSměna začínající v {start}:00 (trvá {shift_length}h):")
            for g in groups:
                count = results['shifts'][(start, g)]
                cost = count * shift_length * cost_per_hour[g]
                print(f"  {g}: {count} agentů (náklady: {cost:,} Kč)")
        
        # Kolik máme dohromady agentů v každé skupině
        print("\n" + "=" * 60)
        print("CELKOVÝ POČET AGENTŮ PO SKUPINÁCH:")
        print("=" * 60)
        
        for g in groups:
            info = results['agents_by_group'][g]
            print(f"{g}: {info['total_agents']} agentů celkem (náklady: {info['total_cost']:,.0f} Kč)")
        
        # Hodinový rozpis - kde jsme vytížení, kde máme kapacitu
        print("\n" + "=" * 60)
        print("POKRYTÍ POPTÁVKY PO HODINÁCH:")
        print("=" * 60)
        
        for row in results['hourly_coverage']:
            print(f"Hodina {row['hour']}:00 | Stream: G1={row['stream_demand_g1']:5.1f} G2={row['stream_demand_g2']:5.1f} G3={row['stream_demand_g3']:5.1f} | "
                  f"Batch: G1={row['batch_assigned_g1']:5.1f} G2={row['batch_assigned_g2']:5.1f} G3={row['batch_assigned_g3']:5.1f} | "
                  f"Kapacita: {row['capacity']:4.0f} min | "
                  f"Agenti: G3={row['G3']}, G2={row['G2']}, G1={row['G1']} | "
                  f"Využití: {row['utilization']:.1f}%")
    else:
        # Pokud se nepodařilo najít řešení
        print("Řešení nebylo nalezeno!")


# Main execution - only runs when script is called directly
if __name__ == "__main__":
    # Nastavení: kolik maximálně agentů, jaké mzdy, jak dlouhé směny, apod.
    DATA = 'data_hovory.csv'
    GROUPS = ['G1', 'G2', 'G3']
    COST_PER_HOUR = {'G1': 150, 'G2': 220, 'G3': 350}
    LIMIT = {'G1': 10, 'G2': 50, 'G3': 50}
    SHIFT_STARTS = [8, 10, 12, 14, 16]
    SHIFT_LENGTH = 8
    OCCUPANCY = 0.50
    BATCH_DEADLINE = 14
    
    # Krok 1: Načteme data a uvidíme co máme za práci
    print("Načítám data...")
    stream_demand_by_group, batch_total_by_group, batch_deadline = load_demand_data(DATA, BATCH_DEADLINE)
    print(f"Poptávka stream hovorů v minutách pro jednotlivé hodiny (G1):")
    print(stream_demand_by_group['G1'])
    print(f"\nPoptávka stream hovorů v minutách pro jednotlivé hodiny (G2):")
    print(stream_demand_by_group['G2'])
    print(f"\nPoptávka stream hovorů v minutách pro jednotlivé hodiny (G3):")
    print(stream_demand_by_group['G3'])
    print(f"\nCelkem batch práce po skupinách:")
    for g in GROUPS:
        print(f"  {g}: {batch_total_by_group[g]:.1f} minut")
    print(f"Deadline: {batch_deadline}:00")
    
    # Krok 2: Spustíme optimalizaci
    print("\nOptimalizuji rozvrh...")
    results = optimize_schedule(
        data_source=DATA,
        groups=GROUPS,
        cost_per_hour=COST_PER_HOUR,
        limit=LIMIT,
        shift_starts=SHIFT_STARTS,
        shift_length=SHIFT_LENGTH,
        occupancy=OCCUPANCY,
        batch_deadline=BATCH_DEADLINE
    )
    
    # Krok 3: Vypíšeme výsledky
    print_results(results, SHIFT_STARTS, SHIFT_LENGTH, GROUPS, COST_PER_HOUR)
