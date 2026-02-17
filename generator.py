import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generuj_provoz(pocet_hovoru=500):
    # 1. Log-normální rozdělení pro délku (AHT)
    # mu a sigma nastaveny tak, aby průměr byl cca 15 min (900s)
    # a objevovaly se i dlouhé hovory (chvost distribuce)
    mu, sigma = 6.6, 0.5 
    durations = np.random.lognormal(mu, sigma, pocet_hovoru)
    
    # 2. Časy začátků (náhodně v pracovní době 8:00 - 17:00)
    start_dne = datetime(2026, 3, 2, 8, 0, 0)
    vterin_v_pracovni_dobe = 12 * 3600 # 12 hodin provozu
    

    # Vygenerujeme náhodné časy pro všech N hovorů
    timestamps = [start_dne + timedelta(seconds=np.random.randint(0, vterin_v_pracovni_dobe)) 
                  for _ in range(pocet_hovoru)]
    
    # 3. Složení do tabulky
    df = pd.DataFrame({
        'timestamp': sorted(timestamps),
        'duration_s': durations.astype(int)
    })
    
    # Uložení
    df.to_csv('data_hovory.csv', index=False)
    print(f"Generování hotovo! Vytvořeno {pocet_hovoru} hovorů v souboru data_hovory.csv")

if __name__ == "__main__":
    generuj_provoz()