"""Portable data-only workspace packages; never execute uploaded SQL or pickle."""
from datetime import datetime, timezone
from io import BytesIO
import json
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED
import pandas as pd
from .schemas import SCHEMAS

MAX_BYTES = 64 * 1024 * 1024
FORMAT = 'bosch-brm-workspace-v1'


def export_workspace(store):
    # One consistent SQLite snapshot, including the provenance of original imports.
    with store.connect() as conn:
        conn.execute('BEGIN')
        datasets = {}
        for key in SCHEMAS:
            rows = conn.execute(f'SELECT payload FROM {key} ORDER BY business_key').fetchall()
            if rows:
                datasets[key] = [json.loads(row[0]) for row in rows]
        conn.row_factory = __import__('sqlite3').Row
        history = [dict(row) for row in conn.execute(
            'SELECT created,filename,category,status,rows,detail FROM imports ORDER BY id')]
    payload = dict(format=FORMAT, created=datetime.now(timezone.utc).isoformat(),
                   datasets=datasets, source_history=history)
    raw = json.dumps(payload, allow_nan=False, ensure_ascii=False).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('Workspace exceeds the 64 MB transfer limit.')
    out = BytesIO()
    with ZipFile(out, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('workspace.json', raw)
    return out.getvalue()


def read_workspace(raw):
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError('Transfer file exceeds the 20 MB upload limit.')
    try:
        with ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != 'workspace.json':
                raise ValueError('Expected a Bosch workspace package containing workspace.json only.')
            if entries[0].file_size > MAX_BYTES:
                raise ValueError('Expanded workspace exceeds the 64 MB limit.')
            with archive.open(entries[0]) as member:
                content = member.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError('Expanded workspace exceeds the 64 MB limit.')
        payload = json.loads(content)
    except (BadZipFile, UnicodeError, json.JSONDecodeError, RuntimeError, EOFError) as exc:
        raise ValueError('Invalid workspace package.') from exc
    if not isinstance(payload, dict) or payload.get('format') != FORMAT:
        raise ValueError('Unsupported workspace format.')
    datasets = payload.get('datasets')
    if not isinstance(datasets, dict) or not datasets or set(datasets) - set(SCHEMAS):
        raise ValueError('Workspace contains missing or unknown datasets.')
    frames = {}
    # Approved master must be visible to product validation in the same transaction.
    for key in sorted(datasets, key=lambda key: key != 'sku_master'):
        rows = datasets[key]
        if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f'{key}: expected a nonempty list of data records.')
        frames[key] = pd.DataFrame(rows)
    history = payload.get('source_history', [])
    if not isinstance(history, list) or any(not isinstance(row, dict) for row in history):
        raise ValueError('Invalid source import history.')
    return frames, history


def import_workspace(store, raw, filename, replace=False):
    frames, history = read_workspace(raw)
    return store.ingest_bundle(frames, filename, replace=replace,
                               notes={'original_import_history': history})
