"""Backup diário do banco e limpeza dos backups antigos."""
import sqlite3
from datetime import datetime
from pathlib import Path


def fazer_backup(caminho_db: str, pasta: Path, manter: int = 7) -> tuple[Path, list[str]]:
    """
    Copia o banco para backups/precos-auto-AAAAMMDD-HHMM.db (pela API de backup do SQLite: pega o que
    ainda está no -wal, uma cópia simples do arquivo sairia velha) e apaga os backups mais antigos,
    ficando só os `manter` mais novos. Só apaga depois que o backup novo foi gravado.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"precos-auto-{datetime.now():%Y%m%d-%H%M}.db"
    tmp = destino.with_suffix(".tmp")
    origem = sqlite3.connect(caminho_db, timeout=30)
    try:
        copia = sqlite3.connect(tmp)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()
    tmp.replace(destino)

    apagados = []
    backups = sorted((f for f in pasta.glob("precos*.db") if f.is_file()),
                     key=lambda f: f.stat().st_mtime, reverse=True)
    for velho in backups[max(manter, 1):]:
        try:
            velho.unlink()
            apagados.append(velho.name)
        except OSError:
            pass                                    # aberto em outro programa: tenta de novo amanhã
    return destino, apagados
