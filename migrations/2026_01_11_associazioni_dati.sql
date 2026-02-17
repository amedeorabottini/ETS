BEGIN TRANSACTION;

ALTER TABLE associazioni RENAME TO associazioni_old;

CREATE TABLE associazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    denominazione TEXT NOT NULL,
    codice_fiscale TEXT NOT NULL,

    indirizzo TEXT NOT NULL,
    civico TEXT NOT NULL,
    cap TEXT NOT NULL,
    citta TEXT NOT NULL,
    provincia TEXT NOT NULL,

    pec TEXT,
    partita_iva TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

INSERT INTO associazioni (
    id,
    denominazione,
    codice_fiscale,
    indirizzo,
    civico,
    cap,
    citta,
    provincia,
    pec,
    partita_iva,
    created_at,
    updated_at
)
SELECT
    id,
    denominazione,
    codice_fiscale,
    'DA COMPLETARE',
    '—',
    '00000',
    'DA COMPLETARE',
    '—',
    NULL,
    NULL,
    CURRENT_TIMESTAMP,
    NULL
FROM associazioni_old;

DROP TABLE associazioni_old;

COMMIT;