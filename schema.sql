PRAGMA foreign_keys = ON;

-- =================================================
-- ASSOCIAZIONI
-- =================================================
CREATE TABLE associazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    denominazione TEXT NOT NULL,
    codice_fiscale TEXT NOT NULL,

    indirizzo TEXT,
    civico TEXT,
    cap TEXT,
    citta TEXT,
    provincia TEXT,

    pec TEXT,
    partita_iva TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

-- =================================================
-- ENTI DI AFFILIAZIONE
-- =================================================
CREATE TABLE IF NOT EXISTS enti_affiliazione (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,

    codice TEXT NOT NULL,          -- es. CSEN, ENDAS, FIWUK
    nome TEXT NOT NULL,            -- nome esteso ente
    descrizione TEXT,

    attivo INTEGER NOT NULL DEFAULT 1,
    creato_il DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (associazione_id, codice),

    FOREIGN KEY (associazione_id)
        REFERENCES associazioni(id)
        ON DELETE CASCADE
);

-- =================================================
-- IMPOSTAZIONI ASSOCIAZIONE
-- =================================================
CREATE TABLE IF NOT EXISTS impostazioni (
    associazione_id INTEGER PRIMARY KEY,
    conto_default INTEGER,
    strumento_default TEXT,
    FOREIGN KEY (associazione_id) REFERENCES associazioni(id)
);

-- =================================================
-- ESERCIZI
-- =================================================
CREATE TABLE esercizi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    anno INTEGER NOT NULL,
    UNIQUE (associazione_id, anno),
    FOREIGN KEY (associazione_id) REFERENCES associazioni(id)
);

-- =================================================
-- IMPOSTE DI ESERCIZIO (INSERIMENTO MANUALE)
-- =================================================
CREATE TABLE IF NOT EXISTS bilancio_imposte (
    associazione_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,
    importo REAL NOT NULL DEFAULT 0,

    PRIMARY KEY (associazione_id, esercizio_id),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (esercizio_id) REFERENCES esercizi(id)
);

-- =================================================
-- IMPOSTE SU INVESTIMENTI E FINANZIAMENTI (IMP2)
-- =================================================
CREATE TABLE IF NOT EXISTS bilancio_imposte_i (
    associazione_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,
    importo REAL NOT NULL DEFAULT 0,

    PRIMARY KEY (associazione_id, esercizio_id),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (esercizio_id) REFERENCES esercizi(id)
);

-- =================================================
-- CONTI CORRENTI
-- =================================================
CREATE TABLE conti_correnti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    codice INTEGER NOT NULL CHECK (codice BETWEEN 1 AND 9),
    nome TEXT NOT NULL,
    iban TEXT,
    colore TEXT,
    attivo INTEGER NOT NULL DEFAULT 1,
    UNIQUE (associazione_id, codice),
    FOREIGN KEY (associazione_id) REFERENCES associazioni(id)
);

-- =================================================
-- PIANO DEI CONTI – RENDICONTO MODELLO D ETS
-- =================================================
DROP TABLE IF EXISTS piano_conti_md;

CREATE TABLE piano_conti_md (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codice TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    sezione TEXT NOT NULL,
    tipo TEXT NOT NULL,          -- USCITA | ENTRATA | TOTALE | RISULTATO | MANUALE
    ordine INTEGER NOT NULL,
    segno INTEGER                -- -1 uscite, +1 entrate, 0 neutro
);

-- =================================================
-- A) ATTIVITÀ DI INTERESSE GENERALE
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UA1','Materie prime, sussidiarie, di consumo e merci','A','USCITA',1,-1),
(NULL,'UA2','Servizi','A','USCITA',2,-1),
(NULL,'UA3','Godimento beni di terzi','A','USCITA',3,-1),
(NULL,'UA4','Personale','A','USCITA',4,-1),
(NULL,'UA5','Uscite diverse di gestione','A','USCITA',5,-1),
(NULL,'UA_TOT','Totale uscite attività di interesse generale','A','TOTALE',6,0),

(NULL,'EA1','Entrate da quote associative e apporti dei fondatori','A','ENTRATA',7,1),
(NULL,'EA2','Entrate dagli associati per attività mutuali','A','ENTRATA',8,1),
(NULL,'EA3','Entrate per prestazioni e cessioni ad associati e fondatori','A','ENTRATA',9,1),
(NULL,'EA4','Erogazioni liberali','A','ENTRATA',10,1),
(NULL,'EA5','Entrate del 5 per mille','A','ENTRATA',11,1),
(NULL,'EA6','Contributi da soggetti privati','A','ENTRATA',12,1),
(NULL,'EA7','Entrate per prestazioni e cessioni a terzi','A','ENTRATA',13,1),
(NULL,'EA8','Contributi da enti pubblici','A','ENTRATA',14,1),
(NULL,'EA9','Entrate da contratti con Enti pubblici','A','ENTRATA',15,1),
(NULL,'EA10','Altre entrate','A','ENTRATA',16,1),
(NULL,'EA_TOT','Totale entrate attività di interesse generale','A','TOTALE',17,0),

(NULL,'RA','Avanzo / Disavanzo attività di interesse generale','A','RISULTATO',18,0);

-- =================================================
-- B) ATTIVITÀ DIVERSE
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UB1','Materie prime, sussidiarie, di consumo e merci','B','USCITA',21,-1),
(NULL,'UB2','Servizi','B','USCITA',22,-1),
(NULL,'UB3','Godimento beni di terzi','B','USCITA',23,-1),
(NULL,'UB4','Personale','B','USCITA',24,-1),
(NULL,'UB5','Uscite diverse di gestione','B','USCITA',25,-1),
(NULL,'UB_TOT','Totale uscite attività diverse','B','TOTALE',26,0),

(NULL,'EB1','Entrate per prestazioni e cessioni ad associati e fondatori','B','ENTRATA',27,1),
(NULL,'EB2','Contributi da soggetti privati','B','ENTRATA',28,1),
(NULL,'EB3','Entrate per prestazioni e cessioni a terzi','B','ENTRATA',29,1),
(NULL,'EB4','Contributi da enti pubblici','B','ENTRATA',30,1),
(NULL,'EB5','Entrate da contratti con Enti pubblici','B','ENTRATA',31,1),
(NULL,'EB6','Altre entrate','B','ENTRATA',32,1),
(NULL,'EB_TOT','Totale entrate attività diverse','B','TOTALE',33,0),

(NULL,'RB','Avanzo / Disavanzo attività diverse','B','RISULTATO',34,0);

-- =================================================
-- C) RACCOLTA FONDI
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UC1','Uscite per raccolte fondi abituali','C','USCITA',41,-1),
(NULL,'UC2','Uscite per raccolte fondi occasionali','C','USCITA',42,-1),
(NULL,'UC3','Altre uscite','C','USCITA',43,-1),
(NULL,'UC_TOT','Totale uscite per raccolta fondi','C','TOTALE',44,0),

(NULL,'EC1','Entrate da raccolte fondi abituali','C','ENTRATA',45,1),
(NULL,'EC2','Entrate da raccolte fondi occasionali','C','ENTRATA',46,1),
(NULL,'EC3','Altre entrate','C','ENTRATA',47,1),
(NULL,'EC_TOT','Totale entrate per raccolta fondi','C','TOTALE',48,0),

(NULL,'RC','Avanzo / Disavanzo da raccolta fondi','C','RISULTATO',49,0);

-- =================================================
-- D) ATTIVITÀ FINANZIARIE E PATRIMONIALI
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UD1','Su rapporti bancari','D','USCITA',51,-1),
(NULL,'UD2','Su investimenti finanziari','D','USCITA',52,-1),
(NULL,'UD3','Su patrimonio edilizio','D','USCITA',53,-1),
(NULL,'UD4','Su altri beni patrimoniali','D','USCITA',54,-1),
(NULL,'UD5','Altre uscite','D','USCITA',55,-1),
(NULL,'UD_TOT','Totale uscite finanziarie e patrimoniali','D','TOTALE',56,0),

(NULL,'ED1','Da rapporti bancari','D','ENTRATA',57,1),
(NULL,'ED2','Da altri investimenti finanziari','D','ENTRATA',58,1),
(NULL,'ED3','Da patrimonio edilizio','D','ENTRATA',59,1),
(NULL,'ED4','Da altri beni patrimoniali','D','ENTRATA',60,1),
(NULL,'ED5','Altre entrate','D','ENTRATA',61,1),
(NULL,'ED_TOT','Totale entrate finanziarie e patrimoniali','D','TOTALE',62,0),

(NULL,'RD','Avanzo / Disavanzo attività finanziarie e patrimoniali','D','RISULTATO',63,0);

-- =================================================
-- E) ATTIVITÀ DI SUPPORTO GENERALE
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UE1','Materie prime, sussidiarie, di consumo e merci','E','USCITA',71,-1),
(NULL,'UE2','Servizi','E','USCITA',72,-1),
(NULL,'UE3','Godimento beni di terzi','E','USCITA',73,-1),
(NULL,'UE4','Personale','E','USCITA',74,-1),
(NULL,'UE5','Altre uscite','E','USCITA',75,-1),
(NULL,'UE_TOT','Totale uscite di supporto generale','E','TOTALE',76,0),

(NULL,'EE1','Da distacco del personale','E','ENTRATA',77,1),
(NULL,'EE2','Altre entrate di supporto generale','E','ENTRATA',78,1),
(NULL,'EE_TOT','Totale entrate di supporto generale','E','TOTALE',79,0),

(NULL,'RE','Avanzo / Disavanzo di supporto generale','E','RISULTATO',80,0);

-- =================================================
-- RISULTATI COMPLESSIVI E IMPOSTE
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'IMP1','Imposte','R','MANUALE',90,0),
(NULL,'R_PRE','Avanzo / Disavanzo d’esercizio prima di investimenti','R','RISULTATO',91,0);

-- =================================================
-- INVESTIMENTI, DISINVESTIMENTI E FINANZIAMENTI
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'UI1','Investimenti in immobilizzazioni attività di interesse generale','I','USCITA',200,-1),
(NULL,'UI2','Investimenti in immobilizzazioni attività diverse','I','USCITA',201,-1),
(NULL,'UI3','Investimenti in attività finanziarie e patrimoniali','I','USCITA',202,-1),
(NULL,'UI4','Rimborso di finanziamenti e prestiti','I','USCITA',203,-1),
(NULL,'UI_TOT','Totale uscite da investimenti','I','TOTALE',204,0),

(NULL,'EI1','Disinvestimenti attività di interesse generale','I','ENTRATA',205,1),
(NULL,'EI2','Disinvestimenti attività diverse','I','ENTRATA',206,1),
(NULL,'EI3','Disinvestimenti finanziari e patrimoniali','I','ENTRATA',207,1),
(NULL,'EI4','Ricevimento di finanziamenti e prestiti','I','ENTRATA',208,1),
(NULL,'EI_TOT','Totale entrate da disinvestimenti','I','TOTALE',209,0),

(NULL,'IMP2','Imposte (investimenti)','I','MANUALE',210,0),
(NULL,'RI','Avanzo / Disavanzo da investimenti e finanziamenti','I','RISULTATO',211,0),

(NULL,'R_FIN1','Avanzo / Disavanzo complessivo','R','RISULTATO',214,0);

-- =================================================
-- CASSA E BANCA (MANUALE)
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'CB1','Cassa','CB','MANUALE',300,0),
(NULL,'CB2','Depositi bancari e postali','CB','MANUALE',301,0);

-- =================================================
-- COSTI E PROVENTI FIGURATIVI (MANUALI)
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'CF1','Costi figurativi attività di interesse generale','F','MANUALE',310,0),
(NULL,'CF2','Costi figurativi attività diverse','F','MANUALE',311,0),
(NULL,'PF1','Proventi figurativi attività di interesse generale','F','MANUALE',312,0),
(NULL,'PF2','Proventi figurativi attività diverse','F','MANUALE',313,0);

-- =================================================
-- NOTA FINALE
-- =================================================
INSERT INTO piano_conti_md VALUES
(NULL,'NF','Nota attestante il carattere secondario e strumentale delle attività diverse','N','MANUALE',400,0);

-- =================================================
-- OPERAZIONI DI PRIMA NOTA
-- =================================================
CREATE TABLE operazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,
    data TEXT NOT NULL,
    descrizione TEXT NOT NULL,

    operazione TEXT,

    importo REAL NOT NULL,

    tipo TEXT NOT NULL CHECK (tipo IN ('U','E')),

    piano_conti_id INTEGER,
    conto_id INTEGER,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (esercizio_id) REFERENCES esercizi(id),
    FOREIGN KEY (piano_conti_id) REFERENCES piano_conti_md(id),
    FOREIGN KEY (conto_id) REFERENCES conti_correnti(id)
);

-- =================================================
-- VALORI FIGURATIVI (INSERIMENTO MANUALE)
-- =================================================
CREATE TABLE IF NOT EXISTS valori_figurativi (
    associazione_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,
    codice TEXT NOT NULL,
    importo REAL NOT NULL DEFAULT 0,

    PRIMARY KEY (associazione_id, esercizio_id, codice),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (esercizio_id) REFERENCES esercizi(id)
);

-- =================================================
-- WIZARD PRIMA NOTA (SUGGERIMENTI AUTOMATICI)
-- =================================================

DROP TABLE IF EXISTS wizard_mapping;

CREATE TABLE wizard_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,

    parola_chiave TEXT NOT NULL,
    operazione TEXT NOT NULL,
    piano_conti_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('U','E')),
    priorita INTEGER DEFAULT 100,
    attiva INTEGER DEFAULT 1,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id) ON DELETE CASCADE,
    FOREIGN KEY (piano_conti_id) REFERENCES piano_conti_md(id),

    UNIQUE (associazione_id, parola_chiave, tipo)
);

-- 🔍 INDICE PER PERFORMANCE WIZARD
CREATE INDEX idx_wizard_assoc_attiva
ON wizard_mapping (associazione_id, attiva, priorita);

-- =========================================================
-- MODULO SOCI
-- =========================================================
CREATE TABLE IF NOT EXISTS soci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,

    -- ✅ NUMERO MATRICOLA SOCIO (PERSISTENTE)
    matricola INTEGER NOT NULL,

    nome TEXT NOT NULL,
    cognome TEXT NOT NULL,
    codice_fiscale TEXT,

    data_nascita DATE,
    luogo_nascita TEXT,

    indirizzo TEXT,
    cap TEXT,
    comune TEXT,
    provincia TEXT,

    email TEXT,
    telefono TEXT,

    data_ingresso DATE NOT NULL,
    data_uscita DATE,

    note TEXT,

    -- ✅ ABILITAZIONI MODULI SOCIO (0/1)
    gestione_tesseramento INTEGER NOT NULL DEFAULT 0,
    gestione_certificati_medici INTEGER NOT NULL DEFAULT 0,
    is_volontario INTEGER NOT NULL DEFAULT 0,
    abilita_rimborso_spese INTEGER NOT NULL DEFAULT 0,

    -- ✅ matricola unica per associazione
    UNIQUE (associazione_id, matricola),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id)
);

-- =================================================
-- STATO SOCIO PER ESERCIZIO
-- =================================================
CREATE TABLE IF NOT EXISTS soci_stato_anno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,

    stato TEXT NOT NULL
        CHECK (stato IN ('ATTIVO','NON_ATTIVO','SOSPESO','USCITO')),

    data_inizio DATE,
    data_fine DATE,

    UNIQUE (associazione_id, socio_id, esercizio_id),

    FOREIGN KEY (associazione_id)
        REFERENCES associazioni(id)
        ON DELETE CASCADE,

    FOREIGN KEY (socio_id)
        REFERENCES soci(id)
        ON DELETE CASCADE,

    FOREIGN KEY (esercizio_id)
        REFERENCES esercizi(id)
        ON DELETE CASCADE
);

-- =================================================
-- MODULISTICA SOCIO PER ESERCIZIO
-- =================================================
CREATE TABLE IF NOT EXISTS soci_modulistica_anno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,

    stato TEXT NOT NULL
        CHECK (stato IN ('VALIDA','NON_VALIDA','VALIDATA_MANUALMENTE')),

    file_path TEXT,
    validata_il DATE,
    note TEXT,

    UNIQUE (associazione_id, socio_id, esercizio_id),

    FOREIGN KEY (associazione_id)
        REFERENCES associazioni(id)
        ON DELETE CASCADE,

    FOREIGN KEY (socio_id)
        REFERENCES soci(id)
        ON DELETE CASCADE,

    FOREIGN KEY (esercizio_id)
        REFERENCES esercizi(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_soci_modulistica_esercizio
ON soci_modulistica_anno (associazione_id, esercizio_id);

-- =================================================
-- STORICO TESSERAMENTI SOCI
-- =================================================

CREATE TABLE IF NOT EXISTS soci_tesseramenti (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  associazione_id INTEGER NOT NULL,
  socio_id INTEGER NOT NULL,
  ente_id INTEGER NOT NULL,

  numero_tessera TEXT,
  data_inizio TEXT NOT NULL,      -- YYYY-MM-DD
  data_scadenza TEXT NOT NULL,    -- YYYY-MM-DD

  validato_manualmente INTEGER NOT NULL DEFAULT 0,
  file_path TEXT,                 -- path/filename upload (se lo gestisci)
  note TEXT,

  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
  FOREIGN KEY (socio_id) REFERENCES soci(id),
  FOREIGN KEY (ente_id) REFERENCES enti_affiliazione(id)
);

CREATE INDEX IF NOT EXISTS ix_tess_assoc_socio
ON soci_tesseramenti(associazione_id, socio_id);

CREATE INDEX IF NOT EXISTS ix_tess_assoc_ente
ON soci_tesseramenti(associazione_id, ente_id);

-- =================================================
-- ABILITAZIONE TESSERAMENTO (serve per GRIGIO/non abilitato)
-- =================================================
CREATE TABLE IF NOT EXISTS soci_tesseramenti_abilitazioni (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  associazione_id INTEGER NOT NULL,
  socio_id INTEGER NOT NULL,
  ente_id INTEGER NOT NULL,

  data_inizio TEXT NOT NULL,   -- YYYY-MM-DD (da quando è abilitato)
  data_fine TEXT,              -- YYYY-MM-DD (NULL = ancora abilitato)

  FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
  FOREIGN KEY (socio_id) REFERENCES soci(id),
  FOREIGN KEY (ente_id) REFERENCES enti_affiliazione(id)
);

CREATE INDEX IF NOT EXISTS ix_tessabil_assoc_socio
ON soci_tesseramenti_abilitazioni(associazione_id, socio_id);

-- =================================================
-- CERTIFICATI MEDICI SOCI
-- =================================================
CREATE TABLE soci_certificati_medici (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,

    tipo TEXT NOT NULL
        CHECK (tipo IN ('AGONISTICO','NON_AGONISTICO')),

    data_rilascio DATE NOT NULL,
    data_scadenza DATE NOT NULL,

    medico TEXT,
    struttura TEXT,

    annullato INTEGER NOT NULL DEFAULT 0,
    note TEXT,

    creato_il DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id) ON DELETE CASCADE,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE CASCADE
);

-- =================================================
-- STORICO ABILITAZIONI SOCIO (PER ANNO)
-- =================================================
CREATE TABLE IF NOT EXISTS soci_abilitazioni_storico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,

    anno INTEGER NOT NULL,

    -- ---- TESSERAMENTO ----
    gestione_tesseramento INTEGER NOT NULL DEFAULT 0,
    enti_tesseramento TEXT, -- es: "CSEN,FIWUK"

    -- ---- CERTIFICATI MEDICI ----
    certificato_agonistico INTEGER NOT NULL DEFAULT 0,
    certificato_non_agonistico INTEGER NOT NULL DEFAULT 0,

    -- ---- RUOLO / RIMBORSI ----
    is_volontario INTEGER NOT NULL DEFAULT 0,
    abilita_rimborso_spese INTEGER NOT NULL DEFAULT 0,

    note TEXT,
    creato_il DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (associazione_id, socio_id, anno),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id) ON DELETE CASCADE,
    FOREIGN KEY (socio_id) REFERENCES soci(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_soci_abilitazioni_anno
ON soci_abilitazioni_storico (associazione_id, anno);

-- =========================================================
-- MODULO SOCI – ANAGRAFICA QUOTE
-- =========================================================
CREATE TABLE IF NOT EXISTS quote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,

    nome TEXT NOT NULL,
    descrizione TEXT,

    importo REAL NOT NULL,
    periodicita TEXT NOT NULL,

    attiva INTEGER NOT NULL DEFAULT 1,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id)
);

-- =================================================
-- COLLEGAMENTO SOCI ↔ QUOTE
-- =================================================
CREATE TABLE IF NOT EXISTS soci_quote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,
    quota_id INTEGER NOT NULL,

    data_inizio DATE NOT NULL,
    data_fine DATE,

    -- VALIDITÀ MENSILE DELLA QUOTA
    mese_da INTEGER NOT NULL DEFAULT 1,
    mese_a  INTEGER NOT NULL DEFAULT 12,

    attiva INTEGER NOT NULL DEFAULT 1,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (socio_id) REFERENCES soci(id),
    FOREIGN KEY (quota_id) REFERENCES quote(id)
);

-- =================================================
-- TABELLA RICEVUTE TESTA DOCUMENTO  ✅ (UNICA)
-- =================================================
CREATE TABLE IF NOT EXISTS ricevute (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    socio_id INTEGER,
    sezionale_id INTEGER,

    numero_progressivo INTEGER NOT NULL,
    anno INTEGER NOT NULL,
    data_emissione DATE NOT NULL,

    totale REAL NOT NULL,

    metodo_pagamento TEXT,
    note TEXT,

    creata_il DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (socio_id) REFERENCES soci(id)
);

-- =================================================
-- TABELLA RICEVUTE RIGHE DOCUMENTO
-- =================================================
CREATE TABLE IF NOT EXISTS ricevute_righe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ricevuta_id INTEGER NOT NULL,

    tipo TEXT NOT NULL,           -- 'QUOTA' | 'MANUALE'
    quota_id INTEGER,             -- NULL se manuale
    mese TEXT,                    -- 'YYYY-MM'
    descrizione TEXT NOT NULL,
    importo REAL NOT NULL,

    FOREIGN KEY (ricevuta_id) REFERENCES ricevute(id),
    FOREIGN KEY (quota_id) REFERENCES quote(id)
);

-- =================================================
-- TABELLA RICEVUTE COLLEGAMENTO SCADENZE
-- (lasciata intatta per non omettere nulla)
-- =================================================
CREATE TABLE IF NOT EXISTS ricevute_mesi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    ricevuta_riga_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,
    quota_id INTEGER NOT NULL,

    anno INTEGER NOT NULL,
    mese INTEGER NOT NULL,

    FOREIGN KEY (ricevuta_riga_id) REFERENCES ricevute_righe(id),
    FOREIGN KEY (socio_id) REFERENCES soci(id),
    FOREIGN KEY (quota_id) REFERENCES quote(id)
);

-- =========================================================
-- QUOTE SOCI (SCADENZE / RATE / ANNUALI)
-- =========================================================
CREATE TABLE IF NOT EXISTS quote_soci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,
    socio_id INTEGER NOT NULL,
    esercizio_id INTEGER NOT NULL,
    quota_id INTEGER NOT NULL,

    anno INTEGER NOT NULL,
    mese INTEGER NOT NULL,     -- 0 = ANNUALE | 1..12 = MENSILE / UNA_TANTUM

    importo REAL NOT NULL,

    stato TEXT NOT NULL DEFAULT 'DA_PAGARE',
    -- DA_PAGARE | PAGATA | ANNULLATA

    data_scadenza DATE,
    data_pagamento DATE,

    ricevuta_id INTEGER,

    UNIQUE (socio_id, esercizio_id, quota_id, mese),

    FOREIGN KEY (associazione_id) REFERENCES associazioni(id),
    FOREIGN KEY (socio_id) REFERENCES soci(id),
    FOREIGN KEY (esercizio_id) REFERENCES esercizi(id),
    FOREIGN KEY (quota_id) REFERENCES quote(id),
    FOREIGN KEY (ricevuta_id) REFERENCES ricevute(id)
);



-- =================================================
-- SEZIONALI RICEVUTE
-- =================================================
CREATE TABLE IF NOT EXISTS ricevute_sezionali (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    associazione_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    codice TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    UNIQUE(associazione_id, codice),
    FOREIGN KEY (associazione_id) REFERENCES associazioni(id) ON DELETE CASCADE
);

-- crea automaticamente il sezionale di default quando si crea un'associazione
CREATE TRIGGER IF NOT EXISTS trg_associazioni_sezionale_default
AFTER INSERT ON associazioni
BEGIN
    INSERT INTO ricevute_sezionali (associazione_id, nome, codice, is_default)
    VALUES (NEW.id, 'Default', NULL, 1);
END;

-- =================================================
-- QUOTA ASSOCIATIVA ANNUALE (FLAG)
-- =================================================
ALTER TABLE quote
ADD COLUMN is_quota_associativa INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS ux_quota_associativa
ON quote(associazione_id)
WHERE is_quota_associativa = 1;

-- =================================================
-- FILE / DOCUMENTI (GENERICA, MULTI-USO)
-- =================================================
CREATE TABLE IF NOT EXISTS documenti_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    associazione_id INTEGER NOT NULL,

    -- riferimento logico
    entita TEXT NOT NULL,
    -- es: 'CERTIFICATO_MEDICO', 'MODULISTICA_SOCIO', 'VERBALE'

    entita_id INTEGER NOT NULL,
    -- id della riga collegata

    anno_riferimento INTEGER NOT NULL,
    -- ✅ ANNO A CUI SI RIFERISCE IL DOCUMENTO

    nome_originale TEXT NOT NULL,
    file_path TEXT NOT NULL,

    mime_type TEXT,
    dimensione INTEGER,

    caricato_il DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (associazione_id)
        REFERENCES associazioni(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documenti_assoc_entita_anno
ON documenti_file (associazione_id, entita, entita_id, anno_riferimento);