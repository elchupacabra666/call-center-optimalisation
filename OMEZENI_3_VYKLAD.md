# Omezení 3: Detailní vysvětlení

## Aktuální kód (Co ti teď chybí):

```python
# Omezení 3: Jsou hodiny kde nechceme stream ale máme batch práci
for t in range(8, 24):
    if t not in all_hours and t <= batch_deadline:
        # ... constraints pro batch
```

**Problem:** Komentář je zavádějící! Říká "hodiny kde nechceme stream" - ale to není pravda o tvém call centru.

---

## Realita tvého call centra:

Tvůj call center funguje takto:

```
┌─────────────────────────────────────────────────────────┐
│ TYP HOVORŮ                                              │
├─────────────────────────────────────────────────────────┤
│ STREAM (prodejní hovory)                                │
│  - Přijdou náhodně v čase 8:00-20:00                   │
│  - Musíš je zpracovat HNED (zákazník čeká)             │
│  - Je to část pracovní doby agenta                      │
│                                                         │
│ BATCH (administrativa, emaily, vyřizování objednávek)   │
│  - Nemají konkrétní čas příchodu                        │
│  - Můžeš si je naplánovat kdy chceš (do deadline!)      │
│  - Je to další část pracovní doby agenta                │
└─────────────────────────────────────────────────────────┘
```

### Pracovní doba agenta (8-16 je 8 hodin):
```
┌──────────────────────────────────────────────────┐
│ Pracovní doba agenta                             │
├──────────────────────────────────────────────────┤
│ 50% času: Stream hovory (zákazník volá)          │
│ 50% času: Batch práce (administrativa)           │
│                                                  │
│ Příklad: Agent pracuje 8 hodin                   │
│ - 4 hodiny = stream (prodejní hovory)            │
│ - 4 hodiny = batch (administrativa)              │
└──────────────────────────────────────────────────┘
```

---

## Kde se stává problém s Omezením 3:

Vezmi příklad:
- Call center je otevřeno 8:00-20:00
- Ale ve skutečnosti máš stream hovory pouze 8:00-18:00 (prodej se uzavírá)
- Deadline pro batch je 14:00

**Hodinový harmonogram:**
```
Hodina | Stream poptávka | Batch ?
-------|-----------------|--------
8:00   | 35 min          | ANO (můžeš dělat batch)
9:00   | 42 min          | ANO
10:00  | 38 min          | ANO
...
14:00  | 45 min          | ANO (poslední možnost dělat batch - deadline!)
15:00  | 52 min          | ANO (ale už NOVÝ deadline - batch už musí být hotov)
16:00  | 48 min          | NE (po 15:00 se batch dělat nemůže, už je hotov!)
17:00  | 60 min          | NE (po 15:00 se batch dělat nemůže, už je hotov!)
18:00  | 55 min          | NE (po 15:00 se batch dělat nemůže, už je hotov!)
19:00  | 0 min (zavřeno) | NE (stream končí)
20:00  | 0 min (zavřeno) | NE (stream končí)
```

---

## Správný kontext Omezení 3:

Omezení 3 existuje kvůli těmto hodinám:

```
Hodina | Stream | Batch work  | Příklad
-------|--------|-------------|------------------------
8:00   | 35 min | Možno       | Dopoledne - agenti dělají stream + batch
9:00   | 42 min | Možno       |
10:00  | 38 min | Možno       |
...
14:00  | 45 min | Poslední!   | Deadline - poslední šance na batch
15:00  | 52 min | NE          | PROBLÉM: Chceš dělat batch,
16:00  | 48 min | NE          | ale deadline už prošel!
...
```

**NENÍ to "hodiny kde nechceme stream"**

**JE to "hodiny kde se NESMÍ dělat batch, protože deadline už prošel"**

---

## Správné vysvětlení Omezení 3:

```python
# Omezení 3: Zajistit kapacitu pro batch V TĚCH HODINÁCH 
# kde je stream prázdný nebo slabý, ale ještě máme čas na batch
# NEBO: V hodinách kde streams nejsou, ale ještě můžeme dělat batch
for t in range(8, 24):
    if t not in all_hours and t <= batch_deadline:
        # t = hodina kde NENÍ žádný stream demand
        # MŮŽE TO BÝT:
        # - Ráno když se call center chystá (7:00-8:00)
        # - Mezi špičkami
        # - Později, když se stream zpomaluje
        #
        # POKUD je to PŘED deadline (t <= batch_deadline),
        # musíme mít kapacitu pro batch
```

---

## Vizualizace co se děje:

```
Čas  │ Stream │ Batch │ Agenti   │ Co se dělá
─────┼────────┼───────┼──────────┼─────────────────────────
8:00 │   35   │  XX   │ 2 agenti │ 35 min stream + XX batch
9:00 │   42   │  XX   │ 2 agenti │ 42 min stream + XX batch
10:00│   38   │  XX   │ 2 agenti │ 38 min stream + XX batch
     │        │       │          │
     │        │ DEADLINE 14:00   │ ← Poslední šance!
     │        │       │          │
14:00│   45   │  XX   │ 2 agenti │ 45 min stream + XX batch
15:00│   52   │ ---   │ 2 agenti │ 52 min stream (batch hotov!)
16:00│   48   │ ---   │ 2 agenti │ 48 min stream (žádný batch)
17:00│   60   │ ---   │ 2 agenti │ 60 min stream (žádný batch)
18:00│   55   │ ---   │ 2 agenti │ 55 min stream (žádný batch)
19:00│    0   │ ---   │ ? agenti │ Call center zavřeno
20:00│    0   │ ---   │ ? agenti │ Call center zavřeno
```

---

## Co Omezení 3 vlastně řeší:

```python
for t in range(8, 24):
    if t not in all_hours and t <= batch_deadline:
        # Pro hodiny kde NENÍ stream demand
        # ALE JE JEŠTĚ ČAS NA BATCH (t <= deadline)
        # 
        # Musím zajistit: Máme dost agentů na batch?
        
        prob += staff_g3 * capacity >= batch_assigned[(t, 'G3')]
        # Anglicky: "Kapacita G3 agentů >= batch práce kterou jsme naplánovali"
```

**Výklad:** Pokud jsem si řekl "v 10:00 budu dělat 25 minut G3 batch práce", pak v 10:00 musím mít dost agentů, aby to zvládli. I když v 10:00 není žádný stream demand!

---

## Správný komentář by měl být:

```python
# Omezení 3: Pro hodiny bez stream demand - zajistit kapacitu na batch
# Jsou hodiny (před deadline) kde se stream hovory neočekávají,
# ale chceme v nich dělat batch práci. Musíme zajistit, že máme dost agentů.
# Příklad: Ráno než se stream hovory začnou, nebo v mezidobí.
for t in range(8, 24):
    if t not in all_hours and t <= batch_deadline:
        # Tato hodina: NEMÁ stream, ALE má batch práci naplánovanou
        # Musíme mít kapacitu na tuto batch práci
        ...
```

---

## Praktický příklad:

```
Tvůj call center: Otevřeno 8:00-20:00
Stream hovory: 10:00-18:00 (dopoledne se chystáš, nepřijímáš hovory)
Deadline: 14:00

Harmonogram:
─────────────────────────────────────────────────────────
8:00-10:00: NÉ stream, ALE batch - Omezení 3 to hlídá!
            (Ráno se administrativa, potom začnou hovory)

10:00-14:00: Stream + Batch - Omezení 2 to hlídá
            (Normální provoz, zákazníci volají)

14:00-18:00: Stream, žádný batch
            (Už není čas na batch, deadline prošel)

18:00-20:00: NÉ stream, NÉ batch
            (Call center uzavírá, agenti odcházejí)
```

**Omezení 3 se aktivuje v:**
- **8:00-10:00** - Když není stream, ale dělají se batch úkoly
- Jakékoli jiné části dne, kde by byla "díra" v stream, ale stále je čas na batch

---

## Závěr:

Omezení 3 **NENÍ** o tom že "nechceš stream" - je to o tom, že:

> **V hodinách kde se stream hovory neobjevují ALE stále máš čas na batch (před deadline), musíš zajistit kapacitu pro tuto batch práci.**

Bez tohoto omezení by se stalo:
- Plánuješ si batch práci na 8:00 (kdy je zavřeno)
- Ale nemáš dost agentů, aby ji zvládli
- Řešitel by selhal, protože porušil by deadline omezení
