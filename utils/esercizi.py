# =================================================
# FUNZIONE DI UTILITA' CREAZIONE ESERCIZIO AUTOMATICO
# =================================================

def assicurati_esercizi(conn, associazione_id, anno_minimo):
    """
    Crea automaticamente gli esercizi mancanti
    dall'anno_minimo fino all'ultimo esercizio esistente.
    NON modifica l'esercizio attivo in sessione.
    """
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT anno
        FROM esercizi
        WHERE associazione_id = ?
        ORDER BY anno
        """,
        (associazione_id,)
    ).fetchall()

    if not rows:
        return  # caso patologico: nessun esercizio esistente

    anni_esistenti = {r["anno"] for r in rows}
    anno_max = max(anni_esistenti)

    for anno in range(anno_minimo, anno_max + 1):
        if anno not in anni_esistenti:
            cur.execute(
                """
                INSERT INTO esercizi (associazione_id, anno, chiuso)
                VALUES (?, ?, 0)
                """,
                (associazione_id, anno)
            )

