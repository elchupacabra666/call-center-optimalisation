import streamlit as st

st.set_page_config(page_title="Call Center Optimalizace", layout="wide")

st.title("🎯 Optimalizace personálu call centra")

st.markdown("""
Aplikace pro optimalizaci personálního obsazení v call centru s využitím lineárního programování.

### 📋 Jak použít aplikaci

1. **Konfigurace** ← Začněte zde
   - Nastavte parametry agentů (hodinová sazba, limity)
   - Definujte pracovní směny
   - Vygenerujte nebo nahrajte data hovorů
   - Spusťte optimalizaci

2. **Výsledky**
   - Prohlédněte si optimální rozvrh agentů
   - Analyzujte grafické výstupy
   - Zjistěte náklady a vytížení

### 🔑 Klíčové funkce

- **Skupiny agentů**: G1 (snadné), G2 (střední), G3 (obtížné)
- **Dělení práce**: Stream (realtime) vs Batch (odložená práce)
- **Generátor dat**: Vytvoř syntetické data s realistickou distribucí
- **Optimalizace**: Minimalizace nákladů s respektem ke všem omezením

### 🚀 Začněte nyní

Klikněte na **Konfigurace** v levém menu a začněte!
""")

st.markdown("---")

st.info("""
💡 **Tip**: Nejprve si vyzkoušejte aplikaci s vygenerovanými daty. 
Klikněte na "Generátor dat" v Konfiguraci a vytvořte testovací dataset.
""")
