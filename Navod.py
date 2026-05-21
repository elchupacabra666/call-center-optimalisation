import streamlit as st
from state_utils import persist_state

st.set_page_config(page_title="Call Center Optimalizace", layout="wide")
persist_state()  # Ochrana session_state klíčů před GC při navigaci mezi stránkami

st.title("Optimalizace personálu call centra")

st.markdown("""
Tato aplikace slouží k nalezení nejlevnějšího a nejefektivnějšího rozvržení směn operátorů v call centru pomocí matematické optimalizace (lineárního programování). 

Aplikace balancuje dostupnou kapacitu agentů s poptávkou po odbavení hovorů tak, aby byly splněny všechny požadavky a zároveň se minimalizovaly mzdové náklady.
""")

st.markdown("---")

st.header("Průvodce parametry a funkcemi")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Skupiny agentů (G1, G2, G3)")
    st.markdown("""
    Práce i agenti jsou rozděleni do 3 úrovní obtížnosti (skills). Každá skupina má jinou hodinovou sazbu a maximální dostupnou kapacitu:
    * **G1 (Easy)**: Nejnižší sazba, řeší nejjednodušší hovory.
    * **G2 (Medium)**: Střední sazba, řeší standardní hovory.
    * **G3 (Hard)**: Nejvyšší sazba, zkušení agenti pro nejcennější zákazníky.
    """)

    st.subheader("Směny a jejich začátky")
    st.markdown("""
    Můžete definovat libovolný počet směn, jejich začátky (např. 9:00, 13:00) a jednotnou délku (např. 8 hodin).
    * Optimalizátor **sám rozhodne**, kolik agentů z jaké skupiny na jakou směnu přiřadí.
    * Pokud se daná směna finančně nebo kapacitně nevyplatí, optimalizátor na ni nemusí přiřadit nikoho (počet = 0).

    **Provozní okno je pevně nastavené na 9:00–21:00.** Každá směna se musí do tohoto okna vejít celou svou délkou – tj. platí `začátek + délka ≤ 21`. Například při délce směny 8 hodin jsou dovolené začátky 9:00 až 13:00; při délce 4 hodiny 9:00 až 17:00. Toto odpovídá běžnému provozu call centra, pro které aplikace vznikla. Pokud by bylo potřeba plánovat mimo toto okno (ranní nebo noční provoz), musela by se aplikace na tuto možnost rozšířit.

    Častá chyba: Směny nepokrývají celou pracovní dobu. Například při začátku poslední směny v 11:00 a délce 8 hodin nebude pokryta hodina provozu 20:00–20:59, což může vést k neproveditelnému řešení, pokud v danou hodinu existuje poptávka.
    """)

    st.subheader("Occupancy (Využití agenta)")
    st.markdown("""
    Vyjadřuje reálný čas, který agent stráví čistou prací (např. hovorem se zákazníkem) během jedné hodiny. 
    * Například **50 % occupancy** znamená, že agent efektivně odbavuje hovory **30 minut** z každé hodiny (zbytek tvoří pauzy, administrativa, čekání na hovor).
    """)

with col2:
    st.subheader("Night Batch vs. Stream")
    st.markdown("""
    Provoz se dělí na dva typy práce:
    * **Stream (Real-time)**: Hovory, které přicházejí v reálném čase. Musí být odbaveny přesně v tu hodinu, kdy přijdou (zákazník čeká na lince).
    * **Night Batch (Odložená práce)**: Kontakty na zákazníky z kontaktního formuláře, které se nahromadily přes noc. Nemají konkrétní časový otisk, ale musí být zpracovány do nastaveného času (tzv. **Batch deadline**, např. do 14:00).
    * *Výhoda batche:* Optimalizátor touto prací "vycpává" hluchá místa, kdy agenti zrovna nemají stream hovory. Pokud Night batch vypnete, veškerý provoz bude brán jako okamžitý stream.
    """)

st.markdown("---")

st.header("Jak funguje Generátor dat")
st.markdown("""
Pokud nemáte vlastní data, aplikace umí vygenerovat syntetický, avšak vysoce realistický provoz:
1. **Délka hovorů**: Používá *logaritmicko-normální distribuci*. To znamená, že většina hovorů má průměrnou délku (cca 15 minut), ale občas se objeví extrémně dlouhé hovory, což odpovídá realitě.
2. **Časová známka**: *Stream* hovorům je náhodně přidělen čas mezi 9:00 a 21:00. *Batch* úkoly časovou známku nemají (jsou přiděleny hned na ráno s úkolem je splnit do deadline).
3. **Rozdělení skupin a poměrů**: Sami si pomocí posuvníků v konfiguraci určíte, jaké procento z celkového počtu mají tvořit G1/G2/G3 úkoly a kolik procent má tvořit odložený Batch.
""")

st.markdown("---")

st.header("Formát pro vlastní data (CSV)")
st.info("Chcete-li optimalizovat na vlastních reálných datech, nahrajte v záložce **Konfigurace** vlastní CSV soubor.")

st.markdown("""
Váš CSV soubor musí mít oddělovač čárku (`,`) a obsahovat přesně tyto **4 sloupce**:

* `timestamp` – Čas hovoru ve formátu `YYYY-MM-DD HH:MM:SS` (např. *2026-03-02 10:15:30*). Pro 'batch' úkoly můžete nechat prázdné nebo vložit jakoukoliv hodnotu (generátor používá prázdnou hodnotu).
* `duration_s` – Délka trvání požadavku v **sekundách** (celé číslo, např. *450*).
* `source` – Původ práce. Povolené hodnoty jsou pouze texty `stream` nebo `batch`.
* `group` – Úroveň obtížnosti. Povolené hodnoty jsou pouze `G1`, `G2`, nebo `G3`.

**Příklad struktury vlastního CSV:**
```csv
timestamp,duration_s,source,group
2026-03-02 09:14:22,850,stream,G2
2026-03-02 09:45:10,120,stream,G1
,400,batch,G3
,520,batch,G2
2026-03-02 11:05:00,1050,stream,G3
```
""")