"""Identifica o achado de cada story e procura o link oficial (Claude com visão + pesquisa web)."""
import base64
import json
import os
import re
import subprocess
import tempfile

import anthropic
from PIL import Image

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

PROMPT = """És a editora da CarolContents, uma página de curadoria com olhar de revista (Vogue, Elle).
Recebes uma story do Instagram partilhada pela Carol. Decide se mostra um "achado" concreto
que alguém possa querer encontrar: um produto, uma peça de roupa, um perfume, um livro, um disco,
um restaurante, um hotel, um lugar, uma exposição, uma marca.

Regras:
- Lê todo o texto visível (etiquetas, menções @, autocolantes, embalagens, menus) para identificar o achado.
- Se for um momento pessoal sem achado identificável (selfie, paisagem genérica, texto pessoal), devolve is_finding=false.
- Usa a pesquisa web para encontrar o link OFICIAL: site da marca, página do produto, site do restaurante ou do lugar.
  Evita revendedores, agregadores e páginas de imprensa, exceto se não existir alternativa oficial.
- Confirma que o link corresponde exatamente ao achado (mesmo produto, mesma cor ou edição, quando visível).
- Se não tiveres a certeza da identificação, baixa a confiança em vez de adivinhar.

Responde APENAS com um objeto JSON, sem texto à volta:
{
  "is_finding": true,
  "name": "nome curto do achado",
  "brand": "marca, restaurante ou lugar",
  "category": "moda | beleza | perfumaria | casa | livros | musica | restaurantes | viagens | arte | outros",
  "description": "uma frase elegante em português europeu, máximo 110 caracteres, sem clichés",
  "url": "https://...",
  "confidence": 0.0
}"""


def _to_jpeg(path, max_side=1400):
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
    img.save(out, "JPEG", quality=88)
    return out


def frames_for(path, is_video):
    """Imagens a enviar ao Claude: a própria imagem, ou 2 fotogramas do vídeo."""
    if not is_video:
        return [_to_jpeg(path)]
    frames = []
    for t in ("0.6", "2.5"):
        out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", t, "-i", path,
                            "-frames:v", "1", "-q:v", "3", out])
        if r.returncode == 0 and os.path.getsize(out) > 0:
            frames.append(_to_jpeg(out))
    return frames


def _b64(p):
    with open(p, "rb") as fh:
        return base64.standard_b64encode(fh.read()).decode()


def _parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def identify(path, is_video, model):
    client = anthropic.Anthropic()
    images = frames_for(path, is_video)
    if not images:
        return {"is_finding": False, "error": "sem imagem utilizável"}
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": _b64(i)}} for i in images]
    content.append({"type": "text", "text": PROMPT})
    messages = [{"role": "user", "content": content}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]

    for _ in range(4):  # a pesquisa web pode pedir continuação (pause_turn)
        resp = client.messages.create(model=model, max_tokens=1500,
                                      messages=messages, tools=tools)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        text = "".join(b.text for b in resp.content if b.type == "text")
        data = _parse(text) or {"is_finding": False, "error": "resposta sem JSON"}
        data["confidence"] = float(data.get("confidence") or 0)
        return data
    return {"is_finding": False, "error": "pesquisa não terminou"}


def thumbnail(path, is_video, dest, width=480):
    """Miniatura para a página de links."""
    src = frames_for(path, is_video)
    if not src:
        return None
    img = Image.open(src[0]).convert("RGB")
    img.thumbnail((width, width * 2))
    img.save(dest, "JPEG", quality=82)
    return dest
