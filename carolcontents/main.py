"""CarolContents: stories do Drive → achados com link → reel semanal + página de links.

Uso:
  python -m carolcontents.main recolher    # procura stories novas no Drive e identifica os achados
  python -m carolcontents.main edicao      # monta a edição da semana (reel, legenda, página)
  python -m carolcontents.main tudo        # recolher + edicao
  python -m carolcontents.main publicar    # publica no Instagram a última edição (modo automático)
"""
import datetime as dt
import json
import os
import sys
import tempfile

import yaml

from . import drive, findings, reel, site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "state.json")
MEDIA = os.path.join(ROOT, "docs", "media")
REELS = os.path.join(ROOT, "docs", "reels")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def load_cfg():
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return {"stories": {}, "editions": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def date_label(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def recolher(cfg, state, svc):
    start = (cfg["drive"].get("start_month") or "").strip()
    found = drive.find_story_files(svc, cfg)
    novas = [(k, v) for k, v in found.items()
             if k not in state["stories"] and (not start or v["month"] >= start)]
    print(f"{len(found)} stories no Drive, {len(novas)} novas.")
    os.makedirs(MEDIA, exist_ok=True)
    tmp = tempfile.mkdtemp()
    for media_id, info in sorted(novas, key=lambda kv: (kv[1]["month"], kv[0])):
        local = drive.download(svc, info["drive_id"], os.path.join(tmp, info["name"]))
        try:
            f = findings.identify(local, info["is_video"], cfg["claude"]["model"])
        except Exception as e:  # uma story com problemas não pára as outras
            print(f"  {media_id}: erro ({e}); fica para a próxima recolha")
            continue
        entry = {**info, "finding": f}
        if not f.get("is_finding") or not f.get("url"):
            entry["status"] = "ignorada"
        elif f["confidence"] < cfg["edition"]["min_confidence"]:
            entry["status"] = "por_rever"
        else:
            entry["status"] = "pendente"
            thumb = os.path.join(MEDIA, f"{media_id}.jpg")
            if findings.thumbnail(local, info["is_video"], thumb):
                entry["thumb"] = f"media/{media_id}.jpg"
        state["stories"][media_id] = entry
        save_state(state)
        print(f"  {media_id}: {entry['status']} {f.get('name', '')}")
        os.remove(local)


def caption(items, number, cfg):
    linhas = [f"Edição Nº {number}. O que me prendeu o olhar.", ""]
    for n, it in enumerate(items, 1):
        brand = it["finding"].get("brand", "")
        nome = it["finding"]["name"]
        linhas.append(f"{n:02d} {nome}" + (f", {brand}" if brand and brand.lower() not in nome.lower() else ""))
    linhas += ["", "Todos os links na bio.", "", " ".join(cfg["edition"]["hashtags"])]
    return "\n".join(linhas)


def edicao(cfg, state, svc, force=False):
    e = cfg["edition"]
    pend = sorted(((k, v) for k, v in state["stories"].items() if v["status"] == "pendente"),
                  key=lambda kv: (kv[1]["month"], kv[0]))
    if len(pend) < e["min_items"] and not (force and pend):
        print(f"Só {len(pend)} achados prontos; a edição espera por mais.")
        return None
    escolhidos = pend[: e["max_items"]]
    number = len(state["editions"]) + 1
    hoje = dt.date.today()
    tmp = tempfile.mkdtemp()

    items_reel = []
    for media_id, info in escolhidos:
        local = drive.download(svc, info["drive_id"], os.path.join(tmp, info["name"]))
        items_reel.append({"path": local, "is_video": info["is_video"],
                           "name": info["finding"]["name"], "brand": info["finding"].get("brand", "")})

    os.makedirs(REELS, exist_ok=True)
    reel_path = os.path.join(REELS, f"edicao-{number}.mp4")
    reel.build(items_reel, number, date_label(hoje), reel_path, cfg)
    legenda = caption([v for _, v in escolhidos], number, cfg)

    # pasta da edição no Drive: reel, legenda e lista do que ficou por rever
    root = cfg["drive"]["root_folder_id"]
    pasta = drive.ensure_folder(svc, drive.ensure_folder(svc, root, cfg["drive"]["editions_folder_name"]),
                                f"Edição Nº {number}")
    drive.upload(svc, reel_path, pasta, "video/mp4")
    leg_path = os.path.join(tmp, "legenda.txt")
    with open(leg_path, "w", encoding="utf-8") as fh:
        fh.write(legenda)
    drive.upload(svc, leg_path, pasta, "text/plain")
    rever = [v for v in state["stories"].values() if v["status"] == "por_rever" and not v.get("reportada")]
    if rever:
        txt = os.path.join(tmp, "por-rever.txt")
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write("Stories em que a identificação não foi segura. Para incluir uma, corrige o link\n"
                     "em data/state.json e muda o estado para \"pendente\".\n\n")
            for v in rever:
                f = v["finding"]
                fh.write(f"{v['name']}: {f.get('name', '?')} ({f.get('brand', '')}) {f.get('url', '')} "
                         f"confiança {f['confidence']:.2f}\n")
                v["reportada"] = True
        drive.upload(svc, txt, pasta, "text/plain")

    edition = {"number": number, "date": hoje.isoformat(), "date_label": date_label(hoje),
               "reel": f"reels/edicao-{number}.mp4", "caption": legenda, "published": False,
               "items": [{"media_id": k, "name": v["finding"]["name"], "brand": v["finding"].get("brand", ""),
                          "description": v["finding"].get("description", ""), "url": v["finding"]["url"],
                          "thumb": v.get("thumb")} for k, v in escolhidos]}
    for k, _ in escolhidos:
        state["stories"][k]["status"] = "usada"
        state["stories"][k]["edition"] = number
    state["editions"].append(edition)
    save_state(state)
    site.render(state["editions"], cfg)
    print(f"Edição Nº {number} pronta com {len(escolhidos)} achados.")
    return edition


def publicar(cfg, state):
    if cfg["instagram"]["publish_mode"] != "automatico":
        print("Modo rascunho: o reel e a legenda estão no Drive para publicares.")
        return
    from . import instagram
    for ed in state["editions"]:
        if not ed["published"]:
            url = cfg["site"]["public_url"].rstrip("/") + "/" + ed["reel"]
            ed["ig_media_id"] = instagram.publish_reel(url, ed["caption"])
            ed["published"] = True
            save_state(state)
            print(f"Edição Nº {ed['number']} publicada no Instagram.")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tudo"
    cfg, state = load_cfg(), load_state()
    if cmd == "publicar":
        return publicar(cfg, state)
    if cmd == "pagina":
        return site.render(state["editions"], cfg)
    svc = drive.service()
    if cmd in ("recolher", "tudo"):
        recolher(cfg, state, svc)
    if cmd in ("edicao", "tudo", "forcar"):
        edicao(cfg, state, svc, force=(cmd == "forcar"))
    site.render(state["editions"], cfg)


if __name__ == "__main__":
    main()
