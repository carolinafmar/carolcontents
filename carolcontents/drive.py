"""Leitura das stories no Google Drive e envio das edições de volta para lá."""
import io
import json
import os
import re

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER = "application/vnd.google-apps.folder"
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".mp4", ".mov"}
MONTH_RE = re.compile(r"^(20\d{2})(0[1-9]|1[0-2])$")


def service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _children(svc, folder_id):
    token = None
    while True:
        res = svc.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
            pageSize=1000,
            pageToken=token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        yield from res.get("files", [])
        token = res.get("nextPageToken")
        if not token:
            return


def find_story_files(svc, cfg):
    """Devolve {media_id: info} com todas as stories encontradas, sem duplicados.

    As exportações do Instagram repetem as mesmas stories em cada download;
    o nome do ficheiro é o ID da story no Instagram, por isso serve de chave única.
    """
    d = cfg["drive"]
    prefix = d["export_prefix"].lower()
    story_names = {n.lower() for n in d["stories_folder_names"]}
    flat = d.get("flat", False)
    found = {}

    def walk(folder_id, in_stories, month):
        for f in _children(svc, folder_id):
            name = f["name"]
            low = name.lower()
            if f["mimeType"] == FOLDER:
                # exportações de outras contas ficam de fora
                if low.startswith("instagram-") and not low.startswith(prefix):
                    continue
                m = MONTH_RE.match(name)
                walk(f["id"], in_stories or low in story_names, (m.group(0) if m else month))
                continue
            ext = os.path.splitext(low)[1]
            if ext in MEDIA_EXT and (in_stories or flat):
                media_id = os.path.splitext(name)[0]
                found.setdefault(media_id, {
                    "drive_id": f["id"],
                    "name": name,
                    "ext": ext,
                    "month": month or f["modifiedTime"][:7].replace("-", ""),
                    "is_video": ext in {".mp4", ".mov"},
                })

    walk(d["root_folder_id"], False, None)
    return found


def download(svc, drive_id, dest):
    req = svc.files().get_media(fileId=drive_id, supportsAllDrives=True)
    with io.FileIO(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest


def ensure_folder(svc, parent_id, name):
    safe = name.replace("'", "\\'")
    res = svc.files().list(
        q=f"'{parent_id}' in parents and name = '{safe}' and mimeType = '{FOLDER}' and trashed = false",
        fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    meta = {"name": name, "mimeType": FOLDER, "parents": [parent_id]}
    return svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()["id"]


def upload(svc, path, parent_id, mime):
    meta = {"name": os.path.basename(path), "parents": [parent_id]}
    media = MediaFileUpload(path, mimetype=mime, resumable=True)
    f = svc.files().create(body=meta, media_body=media, fields="id,webViewLink",
                           supportsAllDrives=True).execute()
    return f.get("webViewLink")
