# services/tesseramenti_service.py

def get_abilitazioni_tesseramento(cur, socio_id, associazione_id, anno):
    return cur.execute(
        """
        SELECT enti_tesseramento
        FROM soci_abilitazioni_storico
        WHERE socio_id = ?
          AND associazione_id = ?
          AND anno = ?
        """,
        (socio_id, associazione_id, anno)
    ).fetchone()