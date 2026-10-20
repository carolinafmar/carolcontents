"""Monta o reel vertical (1080x1920) de uma edição com ffmpeg."""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "fonts")

PISTACHE = (207, 224, 210)
ROSA = (196, 128, 142)
PRETO = (0, 0, 0)
CINZA = (94, 94, 94)


def _font(file, size, **axes):
    f = ImageFont.truetype(os.path.join(FONTS, file), size)
    if axes:
        try:
            names = [a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
                     for a in f.get_variation_axes()]
            current = {"Optical size": 11, "Weight": 400}
            current.update({{"opsz": "Optical size", "wght": "Weight"}[k]: v for k, v in axes.items()})
            f.set_variation_by_axes([current.get(n, 400) for n in names])
        except Exception:
            pass
    return f


def didone(size, italic=False, wght=400):
    return _font("BodoniModa-Italic.ttf" if italic else "BodoniModa.ttf", size,
                 opsz=min(96, max(6, size // 2)), wght=wght)


def sans(size, wght=400):
    return _font("Jost.ttf", size, wght=wght)


def _center(draw, y, text, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)


def _wrap(draw, text, font, max_w):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def cover_card(path, edition_no, date_label, title):
    img = Image.new("RGB", (W, H), PISTACHE)
    d = ImageDraw.Draw(img)
    big = didone(150)
    while d.textlength(title, font=big) > W - 120:
        big = didone(big.size - 6)
    _center(d, 760, title, big, PRETO)
    _center(d, 960, f"Edição Nº {edition_no}", didone(64, italic=True), PRETO)
    _center(d, 1070, date_label, sans(34), CINZA)
    img.save(path)
    return path


def end_card(path, link_text, url_label):
    img = Image.new("RGB", (W, H), PISTACHE)
    d = ImageDraw.Draw(img)
    _center(d, 840, link_text, didone(76, italic=True), PRETO)
    _center(d, 960, url_label, sans(34), CINZA)
    img.save(path)
    return path


def overlay(path, number, name, brand):
    """Faixa inferior com o número (que corresponde à página de links), nome e marca."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    nf, bf, numf = didone(58), sans(32, wght=400), didone(46, italic=True)
    lines = _wrap(d, name, nf, W - 190 - 170)[:2]  # deixa livre a coluna de botões do Instagram
    band_h = 90 + 70 * len(lines) + 60
    top = H - band_h - 430  # acima da zona da legenda do Instagram
    d.rectangle([0, top, W, top + band_h], fill=(255, 255, 255, 236))
    d.text((70, top + 48), f"{number:02d}", font=numf, fill=ROSA)
    y = top + 40
    for ln in lines:
        d.text((190, y), ln, font=nf, fill=PRETO)
        y += 70
    if brand and brand.lower() not in name.lower():
        d.text((192, y + 6), brand, font=bf, fill=CINZA)
    img.save(path)
    return path


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
       "-shortest", "-movflags", "+faststart"]
FILL = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
WHITE = "0xFFFFFF"


def _fades(dur):
    return f"fade=t=in:st=0:d=0.25:color={WHITE},fade=t=out:st={dur - 0.3:.2f}:d=0.3:color={WHITE}"


def _run(args):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])


def _silence(dur):
    return ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=44100:cl=stereo"]


def segment_card(png, dur, out):
    _run(["-loop", "1", "-t", f"{dur}", "-i", png, *_silence(dur),
          "-vf", f"{FILL},{_fades(dur)}", "-map", "0:v", "-map", "1:a", *ENC, out])
    return out


def segment_image(src, ov, dur, out):
    frames = int(dur * FPS)
    zoom = (f"scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
            f"zoompan=z='min(zoom+0.0007,1.06)':d={frames}:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=1080x1920:fps={FPS}")
    _run(["-i", src, "-i", ov, *_silence(dur), "-filter_complex",
          f"[0:v]{zoom}[b];[b][1:v]overlay=0:0,{_fades(dur)},setsar=1[v]",
          "-map", "[v]", "-map", "2:a", "-t", f"{dur}", *ENC, out])
    return out


def segment_video(src, ov, dur, out):
    # o áudio original das stories fica de fora (muitas vezes é música com direitos)
    _run(["-ss", "0.3", "-t", f"{dur}", "-i", src, "-i", ov, *_silence(dur), "-filter_complex",
          f"[0:v]{FILL},fps={FPS}[b];[b][1:v]overlay=0:0,{_fades(dur)},setsar=1[v]",
          "-map", "[v]", "-map", "2:a", "-t", f"{dur}", *ENC, out])
    return out


def build(items, edition_no, date_label, out_path, cfg):
    """items: lista de dicts com 'path', 'is_video', 'name', 'brand' (já pela ordem final)."""
    rc = cfg["reel"]
    tmp = tempfile.mkdtemp()
    parts = [segment_card(cover_card(f"{tmp}/cover.png", edition_no, date_label, cfg["site"]["title"]),
                          rc["cover_seconds"], f"{tmp}/00.mp4")]
    for n, it in enumerate(items, 1):
        ov = overlay(f"{tmp}/ov{n}.png", n, it["name"], it.get("brand", ""))
        seg = f"{tmp}/{n:02d}.mp4"
        src = it["path"]
        if it["is_video"]:
            segment_video(src, ov, rc["video_seconds"], seg)
        else:
            if not src.lower().endswith((".jpg", ".jpeg", ".png")):
                conv = f"{tmp}/src{n}.jpg"
                Image.open(src).convert("RGB").save(conv, quality=95)
                src = conv
            segment_image(src, ov, rc["image_seconds"], seg)
        parts.append(seg)
    url_label = cfg["site"]["public_url"].replace("https://", "")
    parts.append(segment_card(end_card(f"{tmp}/end.png", rc["link_text"], url_label),
                              rc["end_seconds"], f"{tmp}/99.mp4"))
    listing = f"{tmp}/list.txt"
    with open(listing, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    _run(["-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", "-movflags", "+faststart", out_path])
    return out_path
