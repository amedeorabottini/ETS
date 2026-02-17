from types import SimpleNamespace


from types import SimpleNamespace

def stato_quota_socio(conn, associazione_id, socio_id, anno):
    """
    Stato quota per badge gestione soci:
    - verde: nessuna quota DA_PAGARE nell'anno
    - rosso: almeno una quota DA_PAGARE nell'anno
    - grigio: nessuna quota collegata / nessuna quota generata nell'anno
    """

    cur = conn.cursor()

    # 1) Quota collegata al socio? (soci_quote attive e valide nell'anno)
    rows = cur.execute(
        """
        SELECT qs.quota_id, qs.data_inizio, qs.data_fine
        FROM soci_quote qs
        WHERE qs.associazione_id = ?
          AND qs.socio_id = ?
          AND qs.attiva = 1
        """,
        (associazione_id, socio_id)
    ).fetchall()

    if not rows:
        return SimpleNamespace(colore="grigio", tooltip="Nessuna quota associata")

    # filtra quote valide per l'anno selezionato
    quota_ids_validi = []
    for r in rows:
        y_start = int(r["data_inizio"][:4])
        if y_start > anno:
            continue

        if r["data_fine"]:
            y_end = int(r["data_fine"][:4])
            if y_end < anno:
                continue

        quota_ids_validi.append(int(r["quota_id"]))

    if not quota_ids_validi:
        return SimpleNamespace(colore="grigio", tooltip="Non iscritto in questo anno")

    # 2) In quote_soci per quell'anno, c'è qualcosa DA_PAGARE?
    placeholders = ",".join(["?"] * len(quota_ids_validi))

    row = cur.execute(
        f"""
        SELECT 1
        FROM quote_soci
        WHERE associazione_id = ?
          AND socio_id = ?
          AND anno = ?
          AND quota_id IN ({placeholders})
          AND stato = 'DA_PAGARE'
        LIMIT 1
        """,
        (associazione_id, socio_id, anno, *quota_ids_validi)
    ).fetchone()

    if row:
        return SimpleNamespace(colore="rosso", tooltip="Quota da regolarizzare")

    # 3) Se non ci sono DA_PAGARE ma non esiste nemmeno una riga quote_soci → grigio (quote non generate)
    row_any = cur.execute(
        f"""
        SELECT 1
        FROM quote_soci
        WHERE associazione_id = ?
          AND socio_id = ?
          AND anno = ?
          AND quota_id IN ({placeholders})
        LIMIT 1
        """,
        (associazione_id, socio_id, anno, *quota_ids_validi)
    ).fetchone()

    if not row_any:
        return SimpleNamespace(colore="grigio", tooltip="Quote non generate per questo anno")

    return SimpleNamespace(colore="verde", tooltip="Quota in regola")