"""
Společný helper pro všechny stránky aplikace.

Streamlit v multipage režimu maže klíče v session_state, které jsou navázané
na widget (přes key=), jakmile se widget přestane renderovat (tj. při odchodu
ze stránky). Funkce `persist_state()` tomu brání tím, že všechny existující
klíče přepíše samy na sebe – Streamlit je poté považuje za "user-owned" state
a nezahodí je při přepnutí stránek.

Volej na začátku každé stránky, ještě PŘED renderováním jakéhokoli widgetu.
"""
import streamlit as st


def _is_file_upload_value(value) -> bool:
    """
    Vrátí True pokud hodnota pochází z file_uploader widgetu.

    Streamlit ukládá UploadedFile objekty s atributy 'file_id' a 'read'.
    Takové klíče nesmíme přiřazovat zpět do session_state – Streamlit
    nevyhodí chybu při samotném přiřazení, ale při následném renderování
    widgetu (proto try/except na přiřazení nestačí).
    """
    if hasattr(value, 'file_id') and callable(getattr(value, 'read', None)):
        return True
    # file_uploader s accept_multiple_files=True vrací list
    if isinstance(value, list) and value:
        first = value[0]
        if hasattr(first, 'file_id') and callable(getattr(first, 'read', None)):
            return True
    return False


def persist_state() -> None:
    """
    Ochraň všechny klíče v session_state před garbage collection při
    navigaci mezi stránkami Streamlit multipage appky.

    Přeskočíme hodnoty z file_uploader – ty nelze programaticky nastavit
    a jejich obsah je ze své podstaty dočasný (uživatel soubor znovu nahraje).
    Výsledek zpracování (generated_df) se ukládá zvlášť a přežije navigaci.
    """
    for key in list(st.session_state.keys()):
        value = st.session_state[key]
        if _is_file_upload_value(value):
            continue
        st.session_state[key] = value
