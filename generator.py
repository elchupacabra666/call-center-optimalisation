import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generuj_provoz(
    pocet_hovoru=500,
    batch_ratio: float = 0.70,
    output_path: str = "data_hovory.csv",
    seed: int | None = None,
    split: dict = None,
    use_night_batch: bool = True,
):
    """
    Generate synthetic call center data with batch/stream and difficulty group assignment.
    
    Args:
        pocet_hovoru: Total number of calls to generate
        batch_ratio: Fraction of calls that are batch (0.0-1.0)
        output_path: Path to save CSV file
        seed: Random seed for reproducibility
        split: Dict with difficulty split {'G3_Hard': 0.25, 'G2_Med': 0.50, 'G1_Easy': 0.25}
        use_night_batch: If False, all calls are generated as stream (no batch backlog)
    """
    if split is None:
        split = {'G3_Hard': 0.25, 'G2_Med': 0.50, 'G1_Easy': 0.25}
    
    # Set random seed if provided
    if seed is not None:
        np.random.seed(seed)
    
    # 1. Log-normální rozdělení pro délku (AHT)
    # mu a sigma nastaveny tak, aby průměr byl cca 15 min (900s)
    # a objevovaly se i dlouhé hovory (chvost distribuce)
    mu, sigma = 6.6, 0.5 
    durations = np.random.lognormal(mu, sigma, pocet_hovoru)
    durations_list = list(durations.astype(int))
    
    # 2. Split into batch and stream calls
    if use_night_batch:
        num_batch = round(pocet_hovoru * batch_ratio)
        num_stream = pocet_hovoru - num_batch
        sources = ['batch'] * num_batch + ['stream'] * num_stream
    else:
        num_batch = 0
        num_stream = pocet_hovoru
        sources = ['stream'] * num_stream
    
    # 3. Assign difficulty groups (G1, G2, G3) to all calls
    n_g3 = round(pocet_hovoru * split['G3_Hard'])
    n_g2 = round(pocet_hovoru * split['G2_Med'])
    n_g1 = pocet_hovoru - n_g3 - n_g2
    
    groups = ['G3'] * n_g3 + ['G2'] * n_g2 + ['G1'] * n_g1
    np.random.shuffle(groups)  # Shuffle groups so they're not systematically ordered
    
    # 4. Timestamps
    start_dne = datetime(2026, 3, 2, 9, 0, 0)
    vterin_v_pracovni_dobe = 12 * 3600  # 12 hodin provozu (8:00 - 20:00)
    
    # Batch calls get NaT, stream calls get timestamps
    timestamps = []
    for source in sources:
        if source == 'batch':
            timestamps.append(pd.NaT)
        else:
            timestamps.append(start_dne + timedelta(seconds=np.random.randint(0, vterin_v_pracovni_dobe)))
    
    # 5. Sort by timestamp (NaT values will be at the end)
    combined = list(zip(timestamps, durations_list, sources, groups))
    combined_stream = [(ts, dur, src, grp) for ts, dur, src, grp in combined if src == 'stream']
    combined_batch = [(ts, dur, src, grp) for ts, dur, src, grp in combined if src == 'batch']
    
    combined_stream.sort(key=lambda x: x[0])
    combined = combined_stream + combined_batch
    
    timestamps, durations_list, sources, groups = zip(*combined)
    
    # 6. Create DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'duration_s': durations_list,
        'source': sources,
        'group': groups
    })
    
    # Save to CSV
    if output_path:
        df.to_csv(output_path, index=False)
        print(f"Generování hotovo! Vytvořeno {pocet_hovoru} hovorů ({num_batch} batch, {num_stream} stream) v souboru {output_path}")
    else:
        print(f"Generování hotovo! Vytvořeno {pocet_hovoru} hovorů ({num_batch} batch, {num_stream} stream).")
    
    return df

if __name__ == "__main__":
    generuj_provoz()