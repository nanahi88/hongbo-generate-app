"""매장 사진을 인스타그램용으로 바꾸고, 인스타그램 홍보 문구도 함께 만드는 프로그램.

1) 사진: '자료' 폴더의 jpg, png 사진을 읽기만 한다 (원본은 절대 바꾸지 않는다)
   - 사진 가운데를 기준으로 정사각형으로 자른 뒤 1080x1080으로 맞춘다 (찌그러지지 않음)
   - 오른쪽 아래에 로고를 넣는다
   - 결과는 실행할 때마다 '완성' 폴더 안에 새로 만든 폴더(예: 2026-10-21_1513)에
     '오늘날짜_01.jpg' 형식으로 저장한다
2) 문구: '가게 정보.txt'를 읽어 인스타그램/네이버 블로그/카카오톡 문구와 해시태그를 만들고
   같은 새 폴더에 '홍보문구.txt'로 저장한다
"""

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

# 한글이 깨지지 않게 출력 설정
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ----- 설정 -----
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "자료"
OUTPUT_DIR = BASE_DIR / "완성"

SIZE = 1080                  # 결과 사진 크기 (가로, 세로)
LOGO_WIDTH_RATIO = 0.15      # 로고 가로 길이 = 사진 가로의 15%
EDGE_MARGIN = 40             # 사진 가장자리에서 안쪽으로 띄울 거리(픽셀)
CARD_PADDING = 12            # 흰 바탕 상자 안쪽 여백(픽셀)
CARD_RADIUS = 14             # 상자 모서리 둥글기
CARD_OPACITY = 120           # 흰 바탕 진하기 (255가 완전 불투명, 120은 약 47%로 사진이 비침)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}
LOGO_NAME = "로고"
LOGO_CANDIDATES = ["로고.jpg", "로고.jpeg", "로고.png"]


def find_logo_file():
    """로고 파일 찾기: 로고.jpg → 로고.png 순서로 '자료' 폴더와 현재 폴더를 확인."""
    for name in LOGO_CANDIDATES:
        for folder in (INPUT_DIR, BASE_DIR):
            path = folder / name
            if path.is_file():
                return path
    return None


def trim_logo_margin(logo):
    """로고 둘레의 빈 배경을 잘라내고 그림 부분만 남긴다."""
    w, h = logo.size
    # 네 모서리 색을 배경색으로 보고, 배경과 많이 다른 부분만 찾는다
    corners = [logo.getpixel(p) for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]]
    bg = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))
    diff = ImageChops.difference(logo, Image.new("RGB", logo.size, bg)).convert("L")
    mask = diff.point(lambda v: 255 if v > 45 else 0)
    box = mask.getbbox()
    if not box:
        return logo
    # 여유를 조금 두고 자른다
    pad = int(min(w, h) * 0.02)
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
           min(box[2] + pad, w), min(box[3] + pad, h))
    # 잘라낸 부분이 너무 작으면(잘못 찾은 것) 원본을 그대로 쓴다
    if (box[2] - box[0]) < w * 0.15 or (box[3] - box[1]) < h * 0.15:
        return logo
    return logo.crop(box)


def prepare_logo_card(logo_path):
    """로고를 작게 줄이고, 흰 바탕 둥근 상자와 은은한 그림자를 붙여 '로고 카드'를 만든다."""
    with Image.open(logo_path) as raw:
        logo = ImageOps.exif_transpose(raw)
        if logo.mode in ("RGBA", "LA", "P"):
            logo = logo.convert("RGBA")
            white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
            logo = Image.alpha_composite(white, logo)
        logo = logo.convert("RGB")

    logo = trim_logo_margin(logo)

    # 로고 가로 길이를 사진 가로의 15%로 맞춘다 (가로세로 비율 유지)
    logo_w = round(SIZE * LOGO_WIDTH_RATIO)
    logo_h = round(logo.height * logo_w / logo.width)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # 로고 모서리도 살짝 둥글게
    inner_mask = Image.new("L", logo.size, 0)
    ImageDraw.Draw(inner_mask).rounded_rectangle(
        (0, 0, logo_w - 1, logo_h - 1), radius=CARD_RADIUS - 5, fill=255)

    card_w = logo_w + CARD_PADDING * 2
    card_h = logo_h + CARD_PADDING * 2

    # 그림자가 번질 공간(blur)을 포함해 카드 이미지를 만든다
    blur = 10
    canvas_w, canvas_h = card_w + blur * 4, card_h + blur * 4
    origin = (blur * 2, blur * 2)

    # 1) 은은한 그림자
    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (origin[0], origin[1] + 4, origin[0] + card_w, origin[1] + 4 + card_h),
        radius=CARD_RADIUS, fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur / 2))

    # 2) 흰 바탕 둥근 상자
    ImageDraw.Draw(shadow).rounded_rectangle(
        (origin[0], origin[1], origin[0] + card_w, origin[1] + card_h),
        radius=CARD_RADIUS, fill=(255, 255, 255, CARD_OPACITY))

    # 3) 상자 안에 로고 붙이기
    shadow.paste(logo, (origin[0] + CARD_PADDING, origin[1] + CARD_PADDING), inner_mask)

    # 호출하는 쪽에서 위치를 계산할 수 있게 '상자 자체 크기'와 '그림자 여백'을 함께 돌려준다
    return shadow, origin, (card_w, card_h)


def make_square(photo_path):
    """사진을 가운데 기준 정사각형으로 자르고 1080x1080으로 맞춘다."""
    with Image.open(photo_path) as raw:
        img = ImageOps.exif_transpose(raw)   # 스마트폰 사진의 회전 정보 반영
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            white = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(white, img)
        img = img.convert("RGB")

    # 짧은 쪽에 맞춰 가운데를 기준으로 정사각형 자르기 (늘리지 않으므로 찌그러지지 않음)
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def add_logo(photo, card):
    """사진 오른쪽 아래에서 40픽셀 안쪽에 로고 카드를 올린다."""
    card_img, origin, (card_w, card_h) = card
    x = SIZE - EDGE_MARGIN - card_w - origin[0]
    y = SIZE - EDGE_MARGIN - card_h - origin[1]
    base = photo.convert("RGBA")
    base.alpha_composite(card_img, (x, y))
    return base.convert("RGB")


# 이번 실행의 결과를 담는 폴더 (실행할 때마다 새로 만들어진다)
RUN_DIR = None


def get_run_dir():
    """이번 실행 결과를 담을 새 폴더를 만든다. 예: 완성/2026-10-21_1513
    사진 저장과 문구 저장이 같은 폴더를 쓰도록, 처음 필요할 때 한 번만 만든다."""
    global RUN_DIR
    if RUN_DIR is None:
        name = datetime.now().strftime("%Y-%m-%d_%H%M")
        folder = OUTPUT_DIR / name
        n = 2
        while folder.exists():           # 같은 분에 또 실행하면 _2, _3을 붙인다
            folder = OUTPUT_DIR / f"{name}_{n}"
            n += 1
        folder.mkdir(parents=True)
        RUN_DIR = folder
    return RUN_DIR


def process_photos():
    """1단계: 사진을 인스타용으로 변환해서 '완성' 폴더에 저장한다."""
    if not INPUT_DIR.is_dir():
        print("'자료' 폴더를 찾을 수 없어요. 이 프로그램과 같은 폴더에 '자료' 폴더가 있는지 확인해 주세요.")
        return

    # 사진 목록 (로고 파일은 사진 변환 대상에서 제외)
    photos = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS and p.stem != LOGO_NAME
    )
    if not photos:
        print("'자료' 폴더에 변환할 사진(jpg, png)이 없어요.")
        return

    run_dir = get_run_dir()

    # 로고 준비 (파일이 없거나 열 수 없으면 로고 단계는 건너뜀)
    card = None
    logo_path = find_logo_file()
    if logo_path is None:
        print("로고 파일이 없어서 로고 넣기는 건너뜁니다.")
    else:
        try:
            card = prepare_logo_card(logo_path)
            print(f"로고 사용: {logo_path.name}")
        except Exception as e:
            print(f"로고를 열 수 없어서 로고 넣기는 건너뜁니다. ({e})")

    today = date.today().strftime("%Y%m%d")
    number = 1     # 새 폴더라서 항상 01번부터 시작
    done = 0

    for photo_path in photos:
        try:
            result = make_square(photo_path)
            if card is not None:
                result = add_logo(result, card)
            out_path = run_dir / f"{today}_{number:02d}.jpg"
            result.save(out_path, "JPEG", quality=95)
            print(f"완료: {photo_path.name} -> {out_path.name}")
            number += 1
            done += 1
        except Exception as e:
            print(f"실패: {photo_path.name} (건너뜀) - {e}")

    print(f"\n총 {done}장을 '{run_dir.name}' 폴더에 저장했어요.")


# ======================================================================
# 인스타그램 홍보 문구 만들기
# ======================================================================

INFO_CANDIDATES = ["가게 정보.txt", "가게정보.txt"]
COPY_FILE_NAME = "홍보문구.txt"


def read_text(path):
    """텍스트 파일 읽기 (UTF-8, 안 되면 윈도우 기본 한글 인코딩으로 다시 시도)."""
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("글자 모양을 읽을 수 없어요.")


def find_info_file():
    """'가게 정보.txt'를 '자료' 폴더와 현재 폴더에서 찾는다."""
    for name in INFO_CANDIDATES:
        for folder in (INPUT_DIR, BASE_DIR):
            path = folder / name
            if path.is_file():
                return path
    return None


def parse_shop_info(text):
    """'가게 정보.txt' 내용을 항목별로 나눈다."""
    info = {"shop": "", "place": "", "features": [], "customers": "",
            "menu": "", "price": "", "menu_desc": [], "discount": None,
            "promos": []}
    in_promo = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("가게 이름:"):
            info["shop"] = line.split(":", 1)[1].strip()
        elif line.startswith("위치:"):
            info["place"] = line.split(":", 1)[1].strip()
        elif line.startswith("가게 특징:"):
            value = line.split(":", 1)[1]
            info["features"] = [f.strip() for f in value.split(",") if f.strip()]
        elif line.startswith("주 고객층:"):
            info["customers"] = line.split(":", 1)[1].strip()
        elif line.startswith("이번 주 홍보할 것"):
            in_promo = True
        elif line.startswith("말투 느낌:"):
            in_promo = False
        elif in_promo and line.startswith("-"):
            info["promos"].append(line.lstrip("- ").strip())

    for promo in info["promos"]:
        # 할인 안내: "오전 11시 이전 방문 시 아메리카노 500원 할인"
        if "할인" in promo and info["discount"] is None:
            m = re.search(r"((?:오전|오후)\s*\d+시)\s*이전.*?(\S+)\s+([\d,]+원)\s*할인", promo)
            info["discount"] = (
                {"time": m.group(1), "drink": m.group(2), "amount": m.group(3)} if m
                else {"raw": promo}
            )
        # 신메뉴: "신메뉴 '흑임자 라떼' 5,500원, 설명, 설명"
        elif not info["menu"]:
            m = re.search(r"['‘“\"](.+?)['’”\"]", promo)
            if m:
                info["menu"] = m.group(1).strip()
                p = re.search(r"([\d,]+원)", promo)
                info["price"] = p.group(1) if p else ""
                # 쉼표로 나누되 '5,500원'처럼 숫자 사이의 쉼표는 나누지 않는다
                parts = [s.strip() for s in re.split(r"(?<!\d),|,(?!\d)", promo)]
                info["menu_desc"] = parts[1:]
    return info


def has_batchim(word):
    """마지막 글자에 받침이 있는지 (조사 '이/가' 선택용)."""
    ch = word[-1]
    return "가" <= ch <= "힣" and (ord(ch) - ord("가")) % 28 != 0


def josa(word, with_batchim, without_batchim):
    """받침 유무에 따라 알맞은 조사를 붙인다. 예: josa('커피', '을', '를') -> '커피를'"""
    return word + (with_batchim if has_batchim(word) else without_batchim)


def polite(phrase):
    """'넣음', '않음' 같은 메모체를 '넣었습니다', '않습니다'로 바꾼다."""
    phrase = phrase.strip().rstrip(".")
    m = re.match(r"(.*\S)\s+많음$", phrase)
    if m:
        word = m.group(1)
        return f"{word}{'이' if has_batchim(word) else '가'} 많습니다"
    for old, new in (("넣음", "넣었습니다"), ("않음", "않습니다"),
                     ("있음", "있습니다"), ("많음", "많습니다")):
        if phrase.endswith(old):
            return phrase[: -len(old)] + new
    return phrase


def make_hashtags(info):
    """지역명 + 업종 + 메뉴를 섞어 해시태그 10개를 만든다."""
    squeeze = lambda s: re.sub(r"\s+", "", s)

    # 지역명: '비엔날레 지구'의 '지구'처럼 뒤에 붙는 말은 뺀다
    regions = [w for w in info["place"].split() if w not in ("지구", "일대", "근처")]
    shop = squeeze(info["shop"])
    features = " ".join(info["features"])

    industry = "카페" if shop.endswith(("커피", "카페")) else "맛집"

    tags = [shop]
    tags += [f"{r}{industry}" for r in regions[:3]]                 # 지역 + 업종
    if "스페셜티" in features:
        tags.append("스페셜티커피")                                   # 업종
    if info["menu"]:
        tags += [squeeze(info["menu"]), f"{industry}신메뉴"]          # 메뉴
    if info["discount"] and info["discount"].get("drink"):
        tags.append(squeeze(info["discount"]["drink"]))             # 메뉴
    if "로스팅" in features:
        tags.append(f"로스팅{industry}")
    if "1인" in features:
        tags.append("혼카페" if industry == "카페" else "혼밥")
    if "직장인" in info["customers"]:
        tags.append(f"직장인{industry}")
    if regions:
        tags.append(f"{regions[0]}맛집")

    unique = []
    for t in tags:
        if t and t not in unique:
            unique.append(t)
    return ["#" + t for t in unique[:10]]


# ----- 내 말투 반영 -----
# '내 말투.txt'(직접 쓰신 글)를 읽어 이모지를 쓰시는지 확인한다.
# 쓰신 글에 이모지가 없으면 만드는 문구에도 이모지를 넣지 않는다.
STYLE_FILE = "내 말투.txt"
EMOJI_PATTERN = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆↔-↪⌀-⏿]")
USE_EMOJI = False


def detect_emoji_use():
    """'내 말투.txt'에 이모지가 있으면 True. 파일이 없거나 이모지가 없으면 False."""
    path = INPUT_DIR / STYLE_FILE
    if not path.is_file():
        return False
    return bool(EMOJI_PATTERN.search(read_text(path)))


def emoji(symbol):
    """이모지를 쓰는 말투일 때만 이모지를 붙인다 (앞에 띄어쓰기 포함)."""
    return f" {symbol}" if USE_EMOJI else ""


def make_copies(info):
    """감성형 / 정보형 / 이벤트형 문구를 만든다."""
    shop, place = info["shop"], info["place"]
    menu, price = info["menu"], info["price"]
    desc = [polite(d) for d in info["menu_desc"]]
    dc = info["discount"]
    features = info["features"]

    if dc and "time" in dc:
        discount_line = f"{dc['time']} 이전 방문 시 {dc['drink']} {dc['amount']} 할인"
    elif dc:
        discount_line = dc["raw"]
    else:
        discount_line = ""

    # 말투: 인사 없이 바로 본론, 한 줄에 한 사실, "~습니다" 체, 꾸밈과 감탄 없이 담백하게
    # (빈 줄은 짧은 덩어리를 나누는 용도)

    # --- 감성형 ---
    block1, block2, block3 = [], [], []
    if menu:
        block1.append(f"이번 주부터 '{menu}'를 시작합니다." + emoji("☕"))
        block1 += [f"{d}." for d in desc]
        if price:
            block1.append(f"가격은 {price}입니다.")
    if any("로스팅" in f for f in features):
        block2.append("커피는 평소대로 직접 볶은 원두로 내립니다.")
    if any("1인" in f for f in features):
        block2.append("조용한 자리도 그대로 있습니다.")
    block3.append(f"{place} {shop}에서 기다리겠습니다.")
    emotional = "\n\n".join("\n".join(b) for b in (block1, block2, block3) if b)

    # --- 정보형 ---
    block1 = [f"{shop} 이번 주 소식입니다." + emoji("☕")]
    block2, block3, block4 = [], [], []
    if menu:
        block2.append(f"신메뉴 '{menu}' {price}".rstrip())
        block2 += [f"{d}." for d in desc]
    if discount_line:
        block3.append(f"{discount_line}합니다.")
    block4.append(f"위치는 {place}입니다.")
    if features:
        block4.append(f"{josa(features[0], '을', '를')} 냅니다.")
    if len(features) > 1:
        block4.append(f"{polite(features[1])}.")
    informative = "\n\n".join("\n".join(b) for b in (block1, block2, block3, block4) if b)

    # --- 이벤트형 ---
    block1, block2, block3 = [], [], []
    if dc and "time" in dc:
        block1.append(f"{dc['time']} 이전에 오시면 {josa(dc['drink'], '을', '를')} {dc['amount']} 할인해 드립니다." + emoji("☕"))
    elif discount_line:
        block1.append(f"{discount_line}합니다.")
    if "직장인" in info["customers"]:
        block1.append("출근길이나 점심 전에 들러 주세요.")
    if menu:
        block2.append(f"신메뉴 '{menu}'({price})도 시작했습니다.".replace("()", ""))
    if any("로스팅" in f for f in features):
        block2.append("직접 로스팅한 원두로 내립니다.")
    block3.append(f"{place} {shop}입니다.")
    event = "\n\n".join("\n".join(b) for b in (block1, block2, block3) if b)

    return [("감성형", emotional), ("정보형", informative), ("이벤트형", event)]


def discount_sentence(info):
    """할인 안내 문장 (정보가 없으면 빈 글자)."""
    dc = info["discount"]
    if not dc:
        return ""
    if "time" in dc:
        return f"{dc['time']} 이전에 방문하시면 {josa(dc['drink'], '을', '를')} {dc['amount']} 할인해 드립니다."
    return dc["raw"]


def make_blog_post(info, hashtags):
    """네이버 블로그용 긴 글(약 1000자, 해시태그 포함)을 만든다. 정보에 없는 내용은 지어내지 않는다."""
    shop, place = info["shop"], info["place"]
    menu, price = info["menu"], info["price"]
    desc = [polite(d) for d in info["menu_desc"]]
    features = info["features"]
    dc = info["discount"]
    discount = discount_sentence(info)

    # 제목
    if menu and dc and "time" in dc:
        title = f"[{shop}] 이번 주 신메뉴 '{menu}' 출시, {dc['time']} 이전 {dc['drink']} {dc['amount']} 할인"
    elif menu:
        title = f"[{shop}] 이번 주 신메뉴 '{menu}'를 소개합니다"
    else:
        title = f"[{shop}] 이번 주 소식을 전합니다"

    paragraphs = []

    # 1) 인사와 가게 소개
    # 말투: 인사 없이 바로 본론, 한 줄에 한 문장, 짧게 끊어 쓰는 "~습니다" 체
    intro = [f"{place}의 {shop}입니다.", "이번 주 소식을 전합니다."]
    about_lines = []
    if features:
        about_lines.append(f"{josa(features[0], '을', '를')} 냅니다.")
        if "로스팅" in features[0]:
            about_lines.append("원두는 제가 직접 볶습니다.")
    if len(features) > 1:
        about_lines.append(f"가게 안에는 {polite(features[1])}.")
        if "1인" in features[1]:
            about_lines.append("혼자 오셔도 어색하지 않은 자리입니다.")
            about_lines.append("점심 뒤나 퇴근 전에 잠깐 앉았다 가셔도 좋습니다.")
    if info["customers"]:
        about_lines.append(f"주로 {josa(info['customers'], '이', '가')} 오십니다.")
        about_lines.append("바쁜 하루 중에 잠깐 쉬어 갈 수 있는 곳이 되고 싶습니다.")
    paragraphs.append("\n".join(intro))
    paragraphs.append("\n".join([f"■ {josa(shop, '은', '는')} 이런 곳입니다"] + about_lines))

    # 2) 신메뉴
    if menu:
        lines = [f"■ 이번 주 신메뉴, '{menu}'",
                 f"이번 주부터 '{menu}'를 시작합니다.",
                 f"가격은 {price}입니다."]
        lines += [f"{d}." for d in desc]
        if any("갈아" in d for d in info["menu_desc"]):
            lines.append("직접 갈아 넣기 때문에 본연의 고소함이 살아 있습니다.")
        if any("달지 않" in d for d in info["menu_desc"]):
            lines.append("단맛이 부담스러우셨던 분도 편하게 드실 수 있습니다.")
            lines.append("커피 대신 다른 음료를 찾으셨다면 한 번 드셔 보세요.")
        lines.append("이번 주에 들르시면 천천히 한 잔 드시고 가세요.")
        paragraphs.append("\n".join(lines))

    # 3) 할인
    if discount:
        lines = [f"■ 오전 방문 할인 안내" if dc and "time" in dc else "■ 할인 안내", discount]
        if dc and "drink" in dc and any("로스팅" in f for f in features):
            lines.append(f"{josa(dc['drink'], '은', '는')} 직접 로스팅한 원두의 맛이 가장 잘 느껴지는 메뉴입니다.")
        if info["customers"] and "직장인" in info["customers"]:
            lines.append("출근길이나 점심 전에 잠깐 들러 가셔도 됩니다.")
        paragraphs.append("\n".join(lines))

    # 4) 이런 날 오시면 좋습니다 (주 고객층과 좌석 정보가 있을 때만)
    wishes = []
    if "직장인" in info["customers"]:
        wishes += ["출근길에 커피 한 잔이 필요한 날.", "점심 전에 잠깐 쉬고 싶은 날."]
    if any("1인" in f for f in features):
        wishes.append("혼자 조용히 앉아 있고 싶은 날.")
    if wishes:
        paragraphs.append("\n".join(["■ 이런 날 들러 주세요"] + wishes + ["그런 날 들러 주시면 됩니다."]))

    # 5) 한눈에 보기
    summary = ["■ 이번 주 소식 한눈에 보기"]
    if menu:
        summary.append(f"- 신메뉴: {menu} {price}".rstrip())
    if dc and "time" in dc:
        summary.append(f"- 할인: {dc['time']} 이전 방문 시 {dc['drink']} {dc['amount']} 할인")
    elif discount:
        summary.append(f"- {discount}")
    summary.append(f"- 위치: {place}")
    if features:
        summary.append(f"- 특징: {', '.join(features)}")
    paragraphs.append("\n".join(summary))

    # 6) 찾아오시는 길과 마무리
    paragraphs.append("\n".join([
        "■ 찾아오시는 길",
        f"{josa(shop, '은', '는')} {place}에 있습니다.",
        "근처에 오실 일이 있으시면 편하게 들러 주세요.",
        "",
        "읽어 주셔서 감사합니다.",
        "기다리겠습니다.",
    ]))

    body = "\n\n".join(paragraphs)
    return title, body, " ".join(hashtags)


def make_kakao_notice(info):
    """카카오톡 단골 공지용 3줄 이내 존댓말 문구."""
    # 말투: 인사 없이 바로 본론
    lines = [f"{info['shop']}입니다."]
    if info["menu"]:
        price = f"({info['price']})" if info["price"] else ""
        lines.append(f"이번 주 신메뉴 '{info['menu']}'{price}를 시작합니다.")
    discount = discount_sentence(info)
    if discount:
        lines.append(discount)
    return "\n".join(lines[:3])


def make_copy_file():
    """2단계: '가게 정보.txt'를 읽어 인스타 문구를 만들고 '완성' 폴더에 저장한다."""
    info_path = find_info_file()
    if info_path is None:
        print("'가게 정보.txt' 파일이 없어서 홍보 문구 만들기는 건너뜁니다.")
        return

    # '내 말투.txt'를 보고 이모지를 쓸지 정한다
    global USE_EMOJI
    USE_EMOJI = detect_emoji_use()

    info = parse_shop_info(read_text(info_path))
    if not info["shop"]:
        print("'가게 정보.txt'에서 '가게 이름:' 항목을 찾지 못해 홍보 문구 만들기는 건너뜁니다.")
        return

    copies = make_copies(info)
    hashtags = make_hashtags(info)

    blog_title, blog_body, blog_tags = make_blog_post(info, hashtags)
    kakao = make_kakao_notice(info)

    line = "=" * 44
    out = [f"{info['shop']} 홍보 문구", f"({date.today().strftime('%Y-%m-%d')} 만듦)", ""]

    # 인스타그램
    out += [line, "[인스타그램]", line, ""]
    for i, (name, text) in enumerate(copies, 1):
        out += [f"[{i}] {name}  (글자 수: {len(text)}자)", "-" * 40, text, ""]
    out += ["[해시태그 10개]", "-" * 40, " ".join(hashtags), ""]

    # 네이버 블로그
    out += ["", line, "[네이버 블로그]", line, ""]
    out += [f"제목: {blog_title}", f"(본문 글자 수: {len(blog_body)}자, 해시태그 제외)", "-" * 40,
            blog_body, "", blog_tags, ""]

    # 카카오톡 단골 공지
    out += ["", line, "[카카오톡 단골 공지]", line, "", kakao, ""]

    # 실행할 때마다 새 폴더에 저장하므로 이전 결과와 섞이거나 덮어쓰지 않는다
    run_dir = get_run_dir()
    (run_dir / COPY_FILE_NAME).write_text("\n".join(out), encoding="utf-8")

    print(f"\n홍보 문구 저장: {run_dir.name}\\{COPY_FILE_NAME} (인스타그램 3종 + 네이버 블로그 + 카카오톡 공지)")


def main():
    # 사진 처리와 문구 만들기를 차례로 실행 (한쪽이 실패해도 다른 쪽은 진행)
    for step in (process_photos, make_copy_file):
        try:
            step()
        except Exception as e:
            print(f"'{step.__name__}' 단계에서 문제가 생겼어요: {e}")

    # 방금 만든 폴더 알려주기 ('--open'을 붙여 실행하면 폴더를 바로 열어 준다)
    if RUN_DIR is not None:
        print(f"\n결과 폴더: {RUN_DIR}")
        if "--open" in sys.argv:
            try:
                os.startfile(RUN_DIR)
            except Exception:
                pass


if __name__ == "__main__":
    main()
