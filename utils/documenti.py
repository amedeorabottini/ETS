def attach_documento(
    associazione_id,
    entita,
    entita_id,
    file_storage
):
    """
    Salva un file e lo collega a un'entità del gestionale
    """

    if not file_storage or file_storage.filename == "":
        return None

    filename = secure_filename(file_storage.filename)

    upload_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        str(associazione_id),
        entita
    )
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    file_storage.save(filepath)

    cur.execute("""
        INSERT INTO documenti_file (
            associazione_id,
            entita,
            entita_id,
            nome_originale,
            file_path,
            mime_type,
            dimensione
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        associazione_id,
        entita,
        entita_id,
        file_storage.filename,
        filepath,
        file_storage.mimetype,
        os.path.getsize(filepath)
    ))

    return cur.lastrowid