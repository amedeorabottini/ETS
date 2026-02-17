# services/quote_sync_service.py
# -*- coding: utf-8 -*-

from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class SyncResult:
    inserted: int

def _months_for_quota(
        anno: int,
        periodicita: str,
        data_inizio: str,
        data_fine: Optional[str]
    ):
    """
    Restituisce lista mesi (int) da generare per l'anno selezionato.
    - ANNUALE: mese attivo = mese di ingresso se anno==anno_inizio, altrimenti gennaio (1)
              mese salvato in quote_soci come 0 (annuale), NON 1..12
    - MENSILE / UNA_TANTUM (se la usi così): genera mesi compresi nel range
    """
    y_start, m_start, _ = map(int, data_inizio.split("-"))

    # quota futura rispetto all'anno selezionato
    if y_start > anno:
        return []

    # gestisci fine
    y_end = None
    m_end = None
    if data_fine:
        y_end, m_end, _ = map(int, data_fine.split("-"))
        if y_end < anno:
            return []

    if periodicita == "ANNUALE":
        # mese attivo per validità, ma in quote_soci salviamo mese=0
        mese_attivo = m_start if anno == y_start else 1

        # se nell'anno di fine il mese attivo è oltre m_end → niente
        if data_fine and y_end == anno and mese_attivo > m_end:
            return []

        return [0]  # 0 = annuale in quote_soci

    # NON annuale → mesi 1..12 entro range
    mese_start = 1
    if y_start == anno:
        mese_start = m_start

    mese_end = 12
    if data_fine and y_end == anno:
        mese_end = m_end

    return list(range(mese_start, mese_end + 1))

def sync_quote_soci(conn, associazione_id: int, esercizio_id: int, anno: int) -> SyncResult:
    """
    Popola quote_soci (DA_PAGARE) a partire da soci_quote + quote.
    Idempotente: inserisce solo combinazioni (socio_id, esercizio_id, quota_id, mese) mancanti.
    """
    cur = conn.cursor()

    # 1) recupera collegamenti soci_quote + quote attive
    rows = cur.execute(
        """
        SELECT
            qs.associazione_id,
            qs.socio_id,
            qs.quota_id,
            qs.data_inizio,
            qs.data_fine,
            q.importo,
            q.periodicita
        FROM soci_quote qs
        JOIN quote q
            ON q.id = qs.quota_id
           AND q.associazione_id = qs.associazione_id
        WHERE qs.associazione_id = ?
          AND qs.attiva = 1
          AND q.attiva = 1
        """,
        (associazione_id,)
    ).fetchall()

    inserted = 0

    # 2) prepara statement insert idempotente
    # UNIQUE(socio_id, esercizio_id, quota_id, mese) già presente nel tuo schema:
    # quindi usiamo INSERT OR IGNORE.
    insert_sql = """
        INSERT OR IGNORE INTO quote_soci (
            associazione_id, socio_id, esercizio_id, quota_id,
            anno, mese, importo, stato, data_scadenza, data_pagamento, ricevuta_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'DA_PAGARE', NULL, NULL, NULL)
    """

    for r in rows:
        mesi = _months_for_quota(
            anno=anno,
            periodicita=r["periodicita"],
            data_inizio=r["data_inizio"],
            data_fine=r["data_fine"]
        )

        for mese in mesi:
            cur.execute(
                insert_sql,
                (
                    associazione_id,
                    r["socio_id"],
                    esercizio_id,
                    r["quota_id"],
                    anno,
                    mese,
                    r["importo"],
                )
            )
            # rowcount = 1 se inserito, 0 se ignorato
            if cur.rowcount == 1:
                inserted += 1

    conn.commit()
    return SyncResult(inserted=inserted)