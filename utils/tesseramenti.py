from datetime import datetime, date
from typing import Optional

def stato_tesseramento(
    *,
    socio_attivo: bool,
    abilitato: bool,
    data_scadenza: Optional[str],
    oggi: date
):
    """
    Ritorna:
    - stato  : NON_ATTIVO | NON_ABILITATO | MANCANTE | SCADUTO | VALIDO
    - colore : grigio | rosso | verde
    - label  : gg/mm oppure None
    """

    # 1️⃣ socio non attivo
    if not socio_attivo:
        return "NON_ATTIVO", "grigio", None

    # 2️⃣ socio attivo ma non abilitato
    if not abilitato:
        return "NON_ABILITATO", "grigio", None

    # 3️⃣ abilitato ma senza tesseramento
    if not data_scadenza:
        return "MANCANTE", "rosso", None

    scadenza = datetime.strptime(data_scadenza, "%Y-%m-%d").date()
    label = scadenza.strftime("%d/%m")

    # 4️⃣ tesseramento scaduto
    if scadenza < oggi:
        return "SCADUTO", "rosso", label

    # 5️⃣ tesseramento valido
    return "VALIDO", "verde", label