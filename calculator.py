from pulp import *
import pandas as pd


def load_demand_data(data_source):
    """
    Load and aggregate call data from CSV file or DataFrame.
    
    Args:
        data_source: Path to CSV file or pandas DataFrame
    
    Returns:
        pandas Series with hourly demand in minutes, indexed by hour
    """
    if isinstance(data_source, pd.DataFrame):
        df = data_source
    else:
        df = pd.read_csv(data_source)
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    demand_hour = df.groupby('hour')['duration_s'].sum() / 60
    
    return demand_hour


def optimize_schedule(
    data_source,
    groups=['G1', 'G2', 'G3'],
    cost_per_hour={'G1': 150, 'G2': 220, 'G3': 350},
    limit={'G1': 10, 'G2': 50, 'G3': 50},
    shift_starts=[8, 10, 12, 14, 16],
    shift_length=8,
    occupancy=0.50,
    split={'G3_Hard': 0.25, 'G2_Med': 0.50, 'G1_Easy': 0.25}
):
    """
    Optimize call center staff scheduling to minimize costs while meeting demand.
    
    Args:
        data_source: Path to CSV file or pandas DataFrame with columns 'timestamp' and 'duration_s'
        groups: List of agent groups (e.g., ['G1', 'G2', 'G3'])
        cost_per_hour: Dictionary with hourly cost for each group
        limit: Dictionary with maximum total agents per group across all shifts
        shift_starts: List of shift start hours (e.g., [8, 10, 12, 14, 16])
        shift_length: Length of each shift in hours
        occupancy: Fraction of time agents spend on calls (0.0-1.0)
        split: Dictionary with call difficulty split (G3_Hard, G2_Med, G1_Easy)
    
    Returns:
        Dictionary with optimization results:
            - status: Optimization status ('Optimal', 'Infeasible', etc.)
            - total_cost: Total cost in currency units
            - shifts: Dict of (start_hour, group) -> number of agents
            - agents_by_group: Dict of group -> (total_agents, total_cost)
            - hourly_coverage: List of dicts with hourly staffing details
            - demand_hours: Original demand data (pandas Series)
    """
    
    # Helper function to count active workers at a given hour
    def get_active_workers(shifts_var, hour, group):
        count = 0
        for start in shift_starts:
            if start <= hour < start + shift_length:
                count += shifts_var[(start, group)]
        return count
    
    # Load data
    demand_hours = load_demand_data(data_source)
    
    # Create optimization model
    prob = LpProblem("Shift_Scheduling_Cascade", LpMinimize)
    
    # Decision variables: number of agents for each (shift_start, group)
    shifts = LpVariable.dicts("Nabor", 
                               ((h, g) for h in shift_starts for g in groups), 
                               lowBound=0, cat='Integer')
    
    # Demand coverage constraints for each hour
    for t in demand_hours.index:
        # Calculate demand for each difficulty level
        total_req = demand_hours[t]
        req_hard = total_req * split['G3_Hard']
        req_med  = total_req * split['G2_Med']
        req_easy = total_req * split['G1_Easy']
        
        # Count active staff by group
        staff_g3 = get_active_workers(shifts, t, 'G3')
        staff_g2 = get_active_workers(shifts, t, 'G2')
        staff_g1 = get_active_workers(shifts, t, 'G1')
        
        # Each agent has capacity of 60 min * occupancy per hour
        capacity_per_agent = 60 * occupancy
        
        # G3 agents handle hard calls
        prob += staff_g3 * capacity_per_agent >= req_hard, f"Hard_Coverage_Hour_{t}"
        
        # G3 + G2 agents handle hard + medium calls
        prob += (staff_g3 + staff_g2) * capacity_per_agent >= req_hard + req_med, f"Med_Coverage_Hour_{t}"
        
        # All agents handle all calls
        prob += (staff_g3 + staff_g2 + staff_g1) * capacity_per_agent >= total_req, f"Total_Coverage_Hour_{t}"
    
    # Limit constraints: maximum total agents per group
    for g in groups:
        total_agents = sum(shifts[(start, g)] for start in shift_starts)
        prob += total_agents <= limit[g], f"Max_Agents_{g}"
    
    # Objective function: minimize total cost
    total_cost = 0
    for start in shift_starts:
        for g in groups:
            total_cost += shifts[(start, g)] * shift_length * cost_per_hour[g]
    
    prob += total_cost
    
    # Solve the optimization problem
    prob.solve()
    
    # Extract results
    results = {
        'status': LpStatus[prob.status],
        'total_cost': value(prob.objective) if prob.status == 1 else None,
        'shifts': {},
        'agents_by_group': {},
        'hourly_coverage': [],
        'demand_hours': demand_hours
    }
    
    if prob.status == 1:  # Optimal solution found
        # Extract shift assignments
        for start in shift_starts:
            for g in groups:
                results['shifts'][(start, g)] = int(value(shifts[(start, g)]))
        
        # Calculate totals by group
        for g in groups:
            total_agents = sum(results['shifts'][(start, g)] for start in shift_starts)
            group_cost = sum(results['shifts'][(start, g)] * shift_length * cost_per_hour[g] 
                           for start in shift_starts)
            results['agents_by_group'][g] = {
                'total_agents': total_agents,
                'total_cost': group_cost
            }
        
        # Calculate hourly coverage
        for t in demand_hours.index:
            staff_by_group = {}
            for g in groups:
                staff_by_group[g] = sum(
                    results['shifts'][(start, g)]
                    for start in shift_starts
                    if start <= t < start + shift_length
                )
            
            total_agents = sum(staff_by_group.values())
            total_capacity = total_agents * 60 * occupancy
            demand = demand_hours[t]
            utilization = (demand / total_capacity * 100) if total_capacity > 0 else 0
            
            results['hourly_coverage'].append({
                'hour': t,
                'demand': demand,
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
    print(f"\nStatus: {results['status']}")
    
    if results['total_cost'] is not None:
        print(f"Celkové náklady na mzdy: {results['total_cost']:,.0f} Kč\n")
        
        print("=" * 60)
        print("OPTIMÁLNÍ ROZLOŽENÍ SMĚN:")
        print("=" * 60)
        
        for start in shift_starts:
            print(f"\nSměna začínající v {start}:00 (trvá {shift_length}h):")
            for g in groups:
                count = results['shifts'][(start, g)]
                cost = count * shift_length * cost_per_hour[g]
                print(f"  {g}: {count} agentů (náklady: {cost:,} Kč)")
        
        print("\n" + "=" * 60)
        print("CELKOVÝ POČET AGENTŮ PO SKUPINÁCH:")
        print("=" * 60)
        
        for g in groups:
            info = results['agents_by_group'][g]
            print(f"{g}: {info['total_agents']} agentů celkem (náklady: {info['total_cost']:,.0f} Kč)")
        
        print("\n" + "=" * 60)
        print("POKRYTÍ POPTÁVKY PO HODINÁCH:")
        print("=" * 60)
        
        for row in results['hourly_coverage']:
            print(f"Hodina {row['hour']}:00 | Poptávka: {row['demand']:6.1f} min | "
                  f"Kapacita: {row['capacity']:4.0f} min | "
                  f"Agenti: G3={row['G3']}, G2={row['G2']}, G1={row['G1']} | "
                  f"Využití: {row['utilization']:.1f}%")
    else:
        print("Řešení nebylo nalezeno!")


# Main execution - only runs when script is called directly
if __name__ == "__main__":
    # Default configuration
    DATA = 'data_hovory.csv'
    GROUPS = ['G1', 'G2', 'G3']
    COST_PER_HOUR = {'G1': 150, 'G2': 220, 'G3': 350}
    LIMIT = {'G1': 10, 'G2': 50, 'G3': 50}
    SHIFT_STARTS = [8, 10, 12, 14, 16]
    SHIFT_LENGTH = 8
    OCCUPANCY = 0.50
    SPLIT = {'G3_Hard': 0.25, 'G2_Med': 0.50, 'G1_Easy': 0.25}
    
    print("Načítám data...")
    demand_hours = load_demand_data(DATA)
    print("Poptávka v minutách pro jednotlivé hodiny:")
    print(demand_hours)
    
    print("\nOptimalizuji rozvrh...")
    results = optimize_schedule(
        data_source=DATA,
        groups=GROUPS,
        cost_per_hour=COST_PER_HOUR,
        limit=LIMIT,
        shift_starts=SHIFT_STARTS,
        shift_length=SHIFT_LENGTH,
        occupancy=OCCUPANCY,
        split=SPLIT
    )
    
    print_results(results, SHIFT_STARTS, SHIFT_LENGTH, GROUPS, COST_PER_HOUR)
