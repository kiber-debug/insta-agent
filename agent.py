"""
Instagram цитата-блог агенти.
Занжир: ғоя+цитата -> текшириш (fact-check) -> расм дизайни -> (Telegram'га кўрсатиш) -> Instagram'га чиқариш.
MODE=preview  -> фақат тайёрлайди ва Telegram'га юборади (хавфсиз режим)
MODE=publish  -> Instagram'га ҳам чиқаради
"""
import os, io, re, json, time, base64, datetime, textwrap, random
import requests
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------- Созламалар ----------
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
LANGUAGE = os.environ.get("POST_LANGUAGE", "ўзбек тили (лотин ёзуви)")
NICHE = os.environ.get("BLOG_NICHE", "буюк одамларнинг ҳикматли цитаталари")
HANDLE = os.environ.get("BLOG_HANDLE", "")
MODE = os.environ.get("MODE", "preview").strip().lower()

IMGBB_KEY = os.environ.get("IMGBB_KEY", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "").strip().lower()   # gemini | openai | none
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
SUBJECT = os.environ.get("SUBJECT", "person").strip().lower()   # person (олим қиёфаси) | symbolic (қиёфасиз манзара)
LAYOUT = os.environ.get("LAYOUT", "portrait").strip().lower()   # portrait (4:5) | landscape (16:9)

HISTORY_FILE = "history.json"
OUT_DIR = "out"
GRAPH = "https://graph.facebook.com/v21.0"


# ---------- Claude ----------
def claude(prompt, system="", search=False, max_tokens=2000):
    body = {"model": MODEL, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    if search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json=body, timeout=180)
    if r.status_code != 200:
        if search:  # қидирув ишламаса, қидирувсиз уриниб кўрамиз
            return claude(prompt, system, False, max_tokens)
        raise RuntimeError(f"Claude хатоси: {r.status_code} {r.text}")
    return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")


def parse_json(text):
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])


# ---------- Тарих (такрорланмаслик учун) ----------
def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h[-300:], f, ensure_ascii=False, indent=1)


# ---------- 1-2. Ғоя + текшириш ----------
def create_quote(history):
    used = "; ".join(f'{x["author"]}: {x["quote"][:50]}' for x in history[-40:]) or "йўқ"
    system = (f"Сен Instagram блоги муҳаррири ва тадқиқотчисан. Блог мавзуси: {NICHE}. "
              "Фақат ишончли манбада ТАСДИҚЛАНГАН цитаталарни танла. "
              "Интернетда нотўғри муаллифга берилган машҳур 'фейк' цитаталардан сақлан.")
    prompt = f"""Битта янги пост учун цитата танла.
Аллақачон ишлатилганлар (такрорлама): {used}

Қоида:
- цитата қисқа бўлсин (25 сўздан ошмасин), кучли ва мазмунли
- муаллифи ва манбаси (китоб/нутқ/хат) аниқ маълум бўлсин
- 'quote' майдони: {LANGUAGE}да, табиий ва чиройли таржима
- 'caption': {LANGUAGE}да: 1-сатр — диққатни тортувчи қисқа сарлавҳа; кейин 2-3 жумла (цитата ҳаётда нимани англатиши); охирида қисқа чорлов («сақлаб қўйинг» ёки фикрингизни ёзинг). Хэштегсиз, эмодзи 1-2 тадан ошмасин.
- 'hashtags': 8-12 та, # белгисиз

- 'highlights': 1-2 та ибора (2-4 сўздан), 'quote' ичидан АЙНАН нусхаланган, энг муҳим сўзлар (расмда олтин рангда чиқади)
- 'tagline': муаллифнинг касби ва мартабаси, 3 та қисқа сўз нуқталар билан, {LANGUAGE}да (масалан «Физик. Олим. Daho.» услубида)
- 'scene_person': ИНГЛИЗ тилида расм тавсифи: муаллифнинг таниқли қиёфаси (ёши, сочи, мўйлови, кийими), ўйчан поза, унинг соҳасига оид фон ва 4-5 буюм (кутубхона, глобус, доска, китоблар, асбоблар). Расмда ёзув бўлмасин.
- 'scene_symbolic': ИНГЛИЗ тилида цитата маъносига мос РАМЗИЙ манзара (тонгги тоғ, маёқ, кўчат ва ҳ.к.), ОДАМСИЗ, 3-4 деталь, ёзувсиз.

Фақат JSON қайтар:
{{"quote": "...", "original": "...", "author": "...", "source": "...", "caption": "...", "hashtags": ["..."], "highlights": ["..."], "tagline": "...", "scene_person": "...", "scene_symbolic": "..."}}"""
    return parse_json(claude(prompt, system))


def verify_quote(item):
    prompt = f"""Фактчекер сифатида текшир. Қуйидаги цитата ростдан шу муаллифга тегишлими?
Цитата (асл): {item.get('original')}
Муаллиф: {item['author']}
Манба: {item.get('source')}

Агар ишончли манбада тасдиқланмаса, ёки кўпинча нотўғри нисбат берилган цитата бўлса — "doubtful".
Фақат JSON: {{"verdict": "ok" ёки "doubtful", "reason": "қисқа сабаб"}}"""
    return parse_json(claude(prompt, search=True))


def get_good_quote(history, attempts=4):
    for i in range(attempts):
        item = create_quote(history)
        check = verify_quote(item)
        print(f"[{i+1}] {item['author']} -> {check.get('verdict')} ({check.get('reason')})")
        if check.get("verdict") == "ok":
            return item
    raise RuntimeError("Ишончли цитата топилмади, кейинроқ қайта уриниб кўринг.")


# ---------- 3. Расм (замонавий, содда дизайн) ----------
BASE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(BASE, "fonts")
FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf",
]
THEMES = [
    dict(bg=(15, 15, 16), fg=(245, 245, 245), accent=(255, 197, 61), muted=(150, 150, 156)),   # қора + олтин
    dict(bg=(244, 241, 234), fg=(18, 18, 20), accent=(228, 87, 46), muted=(120, 115, 105)),    # оч + тўқ сариқ
    dict(bg=(20, 33, 92), fg=(255, 255, 255), accent=(124, 240, 200), muted=(170, 180, 222)),  # кўк + мента
    dict(bg=(16, 48, 44), fg=(240, 248, 244), accent=(255, 170, 90), muted=(150, 190, 180)),   # яшил + шафақ
]


def has_cyrillic(s):
    return any("\u0400" <= ch <= "\u04FF" for ch in s)


def norm_latin(text):
    # Poppins'да oʻ/gʻ белгиси (ʻ) йўқ, шунинг учун бир хил апострофга келтирамиз
    for ch in ("ʻ", "ʼ", "’", "`", "´", "'"):
        text = text.replace(ch, "\u2018")
    return text


def get_font(kind, size, cyr):
    try:
        if cyr:  # кирилл ёзуви: Lora (кирилл ҳарфларни тўлиқ қўллайди)
            f = ImageFont.truetype(os.path.join(FONTS, "Lora-Variable.ttf"), size)
            try:
                f.set_variation_by_axes([{"bold": 700, "medium": 500, "regular": 400}[kind]])
            except Exception:
                pass
            return f
        name = {"bold": "Poppins-Bold.ttf", "medium": "Poppins-Medium.ttf",
                "regular": "Poppins-Regular.ttf"}[kind]
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except Exception:
        for p in FALLBACKS:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_image(quote, author, source, path, theme_idx=0):
    W, H, M = 1080, 1350, 96
    th = THEMES[theme_idx % len(THEMES)]
    cyr = has_cyrillic(quote)
    if not cyr:
        quote, author, source = norm_latin(quote), norm_latin(author), norm_latin(source or "")

    img = Image.new("RGB", (W, H), th["bg"])
    d = ImageDraw.Draw(img)

    # юқори чизиқ: акцент + блог номи
    d.rounded_rectangle([M, 96, M + 64, 106], radius=5, fill=th["accent"])
    if HANDLE:
        d.text((M + 90, 84), HANDLE, font=get_font("medium", 32, False), fill=th["muted"])

    # катта тирноқ белгиси
    d.text((M - 6, 150), "\u201c", font=get_font("bold", 260, False), fill=th["accent"])

    # цитата: ҳарф ўлчами автоматик мосланади
    box_w, box_h = W - 2 * M, 640
    size = 84
    while size > 38:
        f = get_font("bold", size, cyr)
        lh = int(size * 1.3)
        lines = wrap(d, quote, f, box_w)
        if len(lines) * lh <= box_h:
            break
        size -= 4
    f = get_font("bold", size, cyr)
    y = 430
    for ln in lines:
        d.text((M, y), ln, font=f, fill=th["fg"])
        y += lh

    # пастки қисм: муаллиф ва манба
    base = H - 250
    d.line([(M, base), (M + 90, base)], fill=th["accent"], width=6)
    d.text((M, base + 28), author, font=get_font("medium", 46, cyr), fill=th["fg"])
    if source:
        s = source if len(source) <= 60 else source[:57] + "..."
        d.text((M, base + 92), s, font=get_font("regular", 30, cyr), fill=th["muted"])

    img.save(path, "PNG")


# ---------- Процедур манзара: расм калити бўлмаса шу ишлатилади ----------
SCENES = [
    dict(top=(22, 26, 58), mid=(122, 70, 84), hor=(255, 172, 84), sun=(255, 228, 160), stars=False),   # тонг
    dict(top=(5, 9, 28), mid=(20, 42, 92), hor=(76, 116, 176), sun=(236, 242, 255), stars=True),       # тунги осмон
    dict(top=(8, 30, 38), mid=(28, 88, 90), hor=(240, 162, 104), sun=(255, 214, 150), stars=False),    # яшил-шафақ
    dict(top=(24, 14, 48), mid=(102, 52, 112), hor=(255, 142, 112), sun=(255, 204, 156), stars=True),  # бинафша шафақ
]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scenic_background(layout="portrait", idx=0):
    W, H = (1920, 1080) if layout == "landscape" else (1080, 1350)
    sc = SCENES[idx % len(SCENES)]
    rnd = random.Random(idx * 11 + 5)
    hz = 0.60                                             # уфқ чизиғи
    sx, sy = 0.27 * W, hz * H - 0.07 * H

    # осмон градиенти
    strip = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (hz * H)
        col = _lerp(sc["top"], sc["mid"], min(t / 0.55, 1)) if t < 0.55 else _lerp(sc["mid"], sc["hor"], min((t - 0.55) / 0.45, 1))
        strip.putpixel((0, y), col if t <= 1 else sc["hor"])
    img = strip.resize((W, H)).convert("RGBA")

    # юлдузлар
    if sc["stars"]:
        st = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        for _ in range(260):
            x, y = rnd.randint(0, W), rnd.randint(0, int(hz * H * 0.8))
            r = rnd.choice([1, 1, 1, 2])
            sd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(90, 220)))
        img = Image.alpha_composite(img, st)

    # қуёш/ой ва ёруғлик ҳосиласи (маска орқали, ҳошиясиз)
    R = int(0.055 * min(W, H) * (1.2 if layout == "landscape" else 1.5))
    gm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gm).ellipse([sx - R * 4, sy - R * 4, sx + R * 4, sy + R * 4], fill=150)
    gm = gm.filter(ImageFilter.GaussianBlur(R * 2.2))
    img = Image.composite(Image.new("RGBA", (W, H), (*sc["hor"], 255)), img, gm)
    sm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sm).ellipse([sx - R, sy - R, sx + R, sy + R], fill=255)
    sm = sm.filter(ImageFilter.GaussianBlur(3))
    img = Image.composite(Image.new("RGBA", (W, H), (*sc["sun"], 255)), img, sm)

    # тоғ қаторлари (узоқдан яқинга)
    n = 5
    near = (8, 10, 15)
    far = _lerp(_lerp(sc["hor"], sc["mid"], 0.45), (0, 0, 0), 0.30)
    for i in range(n):
        t = i / (n - 1)
        col = _lerp(far, near, t ** 0.75)
        base = (hz + 0.02 + 0.045 * i) * H
        amp = (0.10 - 0.012 * i) * H
        freqs = [(2 ** k) * (1.6 + rnd.random()) for k in range(5)]
        phs = [rnd.random() * 6.283 for _ in range(5)]
        pts = []
        for x in range(0, W + 6, 6):
            yv = 0
            for k in range(5):
                w = math.sin(2 * math.pi * freqs[k] * x / W + phs[k])
                w = (1 - abs(w)) * 1.2 - 0.6 if k == 0 else w   # биринчи гармоника: ўткир чўққилар
                yv += (amp / (1.75 ** k)) * w
            pts.append((x, base - yv))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon(pts + [(W, H), (0, H)], fill=(*col, 255))
        img = Image.alpha_composite(img, layer)
        if i < n - 1:  # қатлар орасида енгил туман
            fm = Image.new("L", (W, H), 0)
            fy = int(base + amp * 0.1)
            ImageDraw.Draw(fm).rectangle([0, fy, W, fy + int(0.05 * H)], fill=45)
            fm = fm.filter(ImageFilter.GaussianBlur(0.03 * H))
            img = Image.composite(Image.new("RGBA", (W, H), (*sc["hor"], 255)), img, fm)

    out = img.convert("RGB")
    noise = Image.effect_noise((W, H), 18).convert("RGB")
    return Image.blend(out, noise, 0.035)


# ---------- 3б. Олим расми + цитата (эталон услуби) ----------
GOLD = (240, 186, 48)
WHITE = (250, 250, 250)
SOFT = (196, 190, 172)


def resolve_provider():
    if IMAGE_PROVIDER in ("gemini", "openai", "none"):
        return IMAGE_PROVIDER
    if GEMINI_KEY:
        return "gemini"
    if OPENAI_KEY:
        return "openai"
    return "none"


def compose_prompt(scene, layout, subject="person"):
    if layout == "landscape":
        comp = ("Wide cinematic 16:9 composition. The main subject sits on the LEFT side of the frame (left 45%). "
                "The RIGHT 50% of the frame is a dark, calm, mostly empty area (dark chalkboard, shadow) "
                "reserved for text overlay.")
    else:
        comp = ("Vertical 4:5 composition. The main subject is large and occupies the LEFT 58% of the frame "
                "(from head down to the waist and desk). The RIGHT 40% of the frame is a dark, calm, mostly empty area "
                "(dark chalkboard, shadow) reserved for text overlay.")
    if subject == "person":
        tail = ("Photorealistic cinematic portrait, warm golden lighting, moody dark tones, shallow depth of field, "
                "high detail. Absolutely no text, letters, numbers, captions, logos or watermarks anywhere, "
                "including on books and chalkboards.")
    else:
        tail = ("Epic cinematic landscape, dramatic golden light, moody dark tones, high detail. "
                "No people, no human figures, no faces, no hands. Absolutely no text, letters, numbers, "
                "captions, logos or watermarks.")
    return f"{scene}. {comp} {tail}"


def gen_gemini(prompt, aspect):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    r = requests.post(url, params={"key": GEMINI_KEY}, json=body, timeout=240)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini: {r.status_code} {r.text[:300]}")
    for cand in r.json().get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            data = part.get("inlineData") or part.get("inline_data")
            if data and data.get("data"):
                return Image.open(io.BytesIO(base64.b64decode(data["data"]))).convert("RGB")
    raise RuntimeError("Gemini расм қайтармади: " + r.text[:300])


def gen_openai(prompt, layout):
    size = "1536x1024" if layout == "landscape" else "1024x1536"
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                      json={"model": OPENAI_IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1},
                      timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI: {r.status_code} {r.text[:300]}")
    d = r.json()["data"][0]
    if d.get("b64_json"):
        return Image.open(io.BytesIO(base64.b64decode(d["b64_json"]))).convert("RGB")
    return Image.open(io.BytesIO(requests.get(d["url"], timeout=120).content)).convert("RGB")


def generate_background(scene, layout, provider, subject="person"):
    prompt = compose_prompt(scene, layout, subject)
    if provider == "gemini":
        return gen_gemini(prompt, "16:9" if layout == "landscape" else "4:5")
    return gen_openai(prompt, layout)


def cover_fit(img, W, H, ay=0.25):
    s = max(W / img.width, H / img.height)
    nw, nh = int(img.width * s) + 1, int(img.height * s) + 1
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - W) // 2, int((nh - H) * ay)
    return img.crop((x, y, x + W, y + H))


def darken(img, strength=0.7, start=0.36, ramp=0.30):
    W, H = img.size
    strip = Image.new("L", (W, 1))
    for x in range(W):
        t = min(max((x - start * W) / (ramp * W), 0), 1)
        strip.putpixel((x, 0), int(255 * strength * t * t * (3 - 2 * t)))
    mask = strip.resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, mask)


def serif(kind, size, italic=False):
    try:
        f = ImageFont.truetype(os.path.join(FONTS, "Lora-Italic-Variable.ttf" if italic else "Lora-Variable.ttf"), size)
        try:
            f.set_variation_by_axes([{"bold": 700, "medium": 500, "regular": 400}[kind]])
        except Exception:
            pass
        return f
    except Exception:
        return get_font("bold", size, True)


def tok_norm(t):
    return re.sub(r"[\W_]+", "", t.lower())


def highlight_flags(words, phrases):
    norms = [tok_norm(w) for w in words]
    flags = [False] * len(words)
    for ph in phrases or []:
        p = [tok_norm(x) for x in ph.split() if tok_norm(x)]
        if not p:
            continue
        for i in range(len(norms) - len(p) + 1):
            if norms[i:i + len(p)] == p:
                for j in range(i, i + len(p)):
                    flags[j] = True
                break
    if not any(flags):  # топилмаса, охирги 2-3 сўзни ажратамиз
        for j in range(max(0, len(words) - 3), len(words)):
            flags[j] = True
    return flags


def wrap_pairs(d, pairs, font, max_w):
    lines, cur = [], []
    for w, fl in pairs:
        t = " ".join(x[0] for x in cur + [(w, fl)])
        if cur and d.textlength(t, font=font) > max_w:
            lines.append(cur)
            cur = [(w, fl)]
        else:
            cur.append((w, fl))
    if cur:
        lines.append(cur)
    return lines


def draw_spaced(d, cx, y, text, font, fill, spacing):
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill)
        x += w + spacing


def make_photo_post(raw, item, path, layout="portrait", dim=0.7):
    if layout == "landscape":
        W, H = 1920, 1080
        cx, bw = int(0.715 * W), int(0.50 * W)
        mark_y, q_top, q_bot = int(0.20 * H), int(0.30 * H), int(0.70 * H)
        a_y, t_y, max_size, a_size, t_size, ay = int(0.775 * H), int(0.875 * H), 92, 62, 34, 0.5
        ds, dr = 0.36, 0.30
    else:  # 4:5: сурат чапда, ёзув ўнг устунда
        W, H = 1080, 1350
        cx, bw = int(0.755 * W), int(0.44 * W)
        mark_y, q_top, q_bot = int(0.285 * H), int(0.33 * H), int(0.665 * H)
        a_y, t_y, max_size, a_size, t_size, ay = int(0.695 * H), int(0.775 * H), 60, 50, 24, 0.3
        ds, dr = 0.40, 0.18

    img = darken(cover_fit(raw, W, H, ay), dim, ds, dr)
    d = ImageDraw.Draw(img)
    x0, x1 = cx - bw // 2, cx + bw // 2

    # тирноқ белгиси ва ён чизиқлар
    mf = serif("bold", int(max_size * 2.4))
    bb = d.textbbox((0, 0), "\u201c", font=mf)
    gw, gh = bb[2] - bb[0], bb[3] - bb[1]
    d.text((cx - gw // 2 - bb[0], mark_y - gh // 2 - bb[1]), "\u201c", font=mf, fill=GOLD)
    lw = max(2, W // 640)
    d.line([(x0, mark_y), (cx - gw // 2 - 24, mark_y)], fill=GOLD, width=lw)
    d.line([(cx + gw // 2 + 24, mark_y), (x1, mark_y)], fill=GOLD, width=lw)

    # цитата: марказда, калит сўзлар олтин рангда
    words = item["quote"].split()
    pairs = list(zip(words, highlight_flags(words, item.get("highlights"))))
    box_h = q_bot - q_top
    size = max_size
    while size > 28:
        f = serif("bold", size)
        lh = int(size * 1.22)
        lines = wrap_pairs(d, pairs, f, bw)
        if len(lines) * lh <= box_h and all(d.textlength(w, font=f) <= bw for w, _ in pairs):
            break
        size -= 2
    f = serif("bold", size)
    y = q_top + (box_h - len(lines) * lh) // 2
    space = d.textlength(" ", font=f)
    for ln in lines:
        total = d.textlength(" ".join(w for w, _ in ln), font=f)
        x = cx - total / 2
        for w, fl in ln:
            d.text((x, y), w, font=f, fill=GOLD if fl else WHITE)
            x += d.textlength(w, font=f) + space
        y += lh

    # муаллиф (курсив): узун исм сиғмаса, ҳарфи кичраяди
    aw_max = bw * (0.78 if layout == "landscape" else 0.92)
    while True:
        af = serif("medium", a_size, italic=True)
        aw = d.textlength(item["author"], font=af)
        if aw <= aw_max or a_size <= 24:
            break
        a_size -= 2
    d.text((cx - aw / 2, a_y), item["author"], font=af, fill=GOLD)
    if layout == "landscape":
        my = a_y + int(a_size * 0.72)
        gap, ln_len = 26, int(bw * 0.14)
        d.line([(cx - aw / 2 - gap - ln_len, my), (cx - aw / 2 - gap, my)], fill=GOLD, width=lw)
        d.line([(cx + aw / 2 + gap, my), (cx + aw / 2 + gap + ln_len, my)], fill=GOLD, width=lw)
    else:
        uy = a_y + int(a_size * 1.45)
        d.line([(cx - aw * 0.42, uy), (cx + aw * 0.42, uy)], fill=GOLD, width=lw)

    # касби: ҳарфлар орасида масофа билан, сиғмаса кичраяди
    tag = (item.get("tagline") or "").upper()
    ts = t_size
    if tag:
        while ts > 14:
            tf = serif("regular", ts)
            sp = ts * 0.28
            total = sum(d.textlength(c, font=tf) for c in tag) + sp * (len(tag) - 1)
            if total <= bw:
                break
            ts -= 1
        draw_spaced(d, cx, t_y, tag, tf, SOFT, sp)

    if HANDLE:
        hf = serif("regular", int(t_size * 0.8))
        hw = d.textlength(HANDLE, font=hf)
        hy = min(H - int(t_size * 1.9), t_y + int(t_size * 2.8))
        d.text((cx - hw / 2, hy), HANDLE, font=hf, fill=(150, 146, 135))

    img.save(path, "PNG")


def build_image(item, history, img_path):
    provider = resolve_provider()
    subject = SUBJECT if SUBJECT in ("person", "symbolic") else "person"
    raw, dim = None, 0.85
    if provider != "none":
        try:
            key = "scene_person" if subject == "person" else "scene_symbolic"
            scene = (item.get(key) or item.get("scene")
                     or (f"Portrait of {item['author']}" if subject == "person"
                         else "A lone mountain peak above the clouds at sunrise"))
            raw = generate_background(scene, LAYOUT, provider, subject)
            raw.save(img_path.replace(".png", "_fon.jpg"), quality=92)
            dim = 0.62
        except Exception as e:
            print("Расм генерацияси ишламади, процедур манзарага ўтилди:", e)
            raw = None
    if raw is None:
        raw = scenic_background(LAYOUT, len(history))
    make_photo_post(raw, item, img_path, LAYOUT, dim)


# ---------- Telegram ----------
def tg_send(path, caption):
    if not (TG_TOKEN and TG_CHAT):
        return
    with open(path, "rb") as f:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                      data={"chat_id": TG_CHAT, "caption": caption[:1000]},
                      files={"photo": f}, timeout=60)


# ---------- Instagram ----------
def upload_public(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    r = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_KEY},
                      data={"image": b64}, timeout=120)
    r.raise_for_status()
    return r.json()["data"]["url"]


def publish_instagram(image_url, caption):
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media",
                      data={"image_url": image_url, "caption": caption, "access_token": IG_TOKEN},
                      timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Instagram (container): {r.text}")
    cid = r.json()["id"]
    time.sleep(8)
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish",
                      data={"creation_id": cid, "access_token": IG_TOKEN}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Instagram (publish): {r.text}")
    return r.json()["id"]


# ---------- Асосий ----------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    history = load_history()
    item = get_good_quote(history)

    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in item["hashtags"])
    caption = f'{item["caption"]}\n\n— {item["author"]}\n\n{tags}'
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    img_path = os.path.join(OUT_DIR, f"post_{stamp}.png")
    build_image(item, history, img_path)
    with open(img_path.replace(".png", ".txt"), "w", encoding="utf-8") as f:
        f.write(caption)
    print("Расм тайёр:", img_path)

    if MODE == "publish":
        if not (IMGBB_KEY and IG_USER_ID and IG_TOKEN):
            raise RuntimeError("Instagram калитлари тўлиқ эмас (IMGBB_KEY, IG_USER_ID, IG_ACCESS_TOKEN).")
        url = upload_public(img_path)
        post_id = publish_instagram(url, caption)
        print("Instagram'га чиқарилди:", post_id)
        tg_send(img_path, "✅ Чиқарилди\n\n" + caption)
    else:
        print("PREVIEW режим: Instagram'га чиқарилмади.")
        tg_send(img_path, "👀 Кўриб чиқиш учун (чиқарилмаган)\n\n" + caption)

    history.append({"date": stamp, "author": item["author"], "quote": item["quote"]})
    save_history(history)


if __name__ == "__main__":
    main()
