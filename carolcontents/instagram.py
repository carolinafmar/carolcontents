"""Publicação opcional do reel no Instagram (Instagram Graph API)."""
import os
import time

import requests

API = os.environ.get("IG_GRAPH_HOST", "https://graph.facebook.com") + "/v21.0"


def publish_reel(video_url, caption):
    token, user = os.environ["IG_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    r = requests.post(f"{API}/{user}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true", "access_token": token}, timeout=60)
    r.raise_for_status()
    container = r.json()["id"]
    for _ in range(40):  # o Instagram processa o vídeo antes de deixar publicar
        st = requests.get(f"{API}/{container}", params={
            "fields": "status_code,status", "access_token": token}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram recusou o vídeo: {st.get('status')}")
        time.sleep(15)
    else:
        raise RuntimeError("O Instagram demorou demasiado a processar o vídeo.")
    r = requests.post(f"{API}/{user}/media_publish", data={
        "creation_id": container, "access_token": token}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]
