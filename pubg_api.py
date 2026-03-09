import difflib
import random
import time

import requests

PUBG_ALL_URL = "https://raw.githubusercontent.com/pubgapi/v2/main/all"
PUBG_SINGLE_URL = "https://raw.githubusercontent.com/pubgapi/v2/main/single/{weapon_url}"
CACHE_TTL_SECONDS = 600

CATEGORY_RULES = [
    ("Штурмовые винтовки", [(1, 8), (44, 45)]),
    ("Болтовые винтовки", [(9, 12)]),
    ("ДМРки", [(13, 18)]),
    ("Пистолеты-пулемёты", [(19, 22), (51, 53)]),
    ("Дробовики", [(23, 25), (50, 50)]),
    ("Пулемёты", [(26, 27)]),
    ("Пистолеты", [(28, 32), (54, 55)]),
    ("Обрез", [(33, 33)]),
    ("Ракетница (Флаер)", [(34, 34)]),
    ("Арбалет", [(39, 39)]),
]

DETAIL_FIELDS = [
    "name",
    "image",
    "short_description",
    "bullet_type",
    "without_mag",
    "with_mag",
    "fire_modes",
    "damage",
    "bullet_speed",
    "impact",
    "pickup_delay",
    "ready_delay",
    "normal_reload",
    "quick_reload",
]

PISTOL_IDS = {28, 29, 30, 31, 32, 54, 55}
FLARE_ID = 34

_cache_payload = None
_cache_ts = 0.0


def _category_by_weapon_id(weapon_id):
    for category, ranges in CATEGORY_RULES:
        for start, end in ranges:
            if start <= weapon_id <= end:
                return category
    return None


def _fetch_all_weapons():
    response = requests.get(PUBG_ALL_URL, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("Некорректный формат PUBG API: ожидался список.")
    return data


def get_all_weapons_cached():
    global _cache_payload, _cache_ts
    now = time.time()
    if _cache_payload is not None and (now - _cache_ts) < CACHE_TTL_SECONDS:
        return _cache_payload
    _cache_payload = _fetch_all_weapons()
    _cache_ts = now
    return _cache_payload


def build_gun_list_text_and_aliases():
    items = get_all_weapons_cached()
    grouped = {name: [] for name, _ in CATEGORY_RULES}
    aliases = []

    for item in items:
        try:
            weapon_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        category = _category_by_weapon_id(weapon_id)
        if not category:
            continue

        weapon_name = (item.get("name") or "").strip()
        weapon_url = (item.get("url") or "").strip()
        if weapon_name:
            grouped[category].append((weapon_id, weapon_name))
            if weapon_url:
                aliases.append((weapon_name, weapon_url))

    blocks = []
    for category, _ in CATEGORY_RULES:
        weapons = sorted(grouped[category], key=lambda x: x[0])
        if not weapons:
            continue
        lines = [f"{category}:"] + [name for _, name in weapons]
        blocks.append("\n".join(lines))

    if not blocks:
        return "Не удалось получить список оружия.", aliases
    return "\n\n".join(blocks), aliases


def _normalize(text):
    return (text or "").strip().strip('"').strip("'").lower()


def resolve_weapon_url(gun_query, db):
    text = (gun_query or "").strip().strip('"').strip("'")
    if not text:
        return None, []

    aliases = db.get_all_weapon_aliases()
    if not aliases:
        return None, []

    normalized_query = _normalize(text)
    query_tail = normalized_query.rsplit("/", 1)[-1]

    for weapon_name, weapon_url in aliases:
        if _normalize(weapon_name) == normalized_query:
            return weapon_url.lower(), []

    for _, weapon_url in aliases:
        url_norm = _normalize(weapon_url)
        if url_norm == normalized_query or url_norm == query_tail:
            return weapon_url.lower(), []

    name_matches = []
    url_matches = []
    for weapon_name, weapon_url in aliases:
        name_norm = _normalize(weapon_name)
        url_norm = _normalize(weapon_url)
        if normalized_query in name_norm:
            name_matches.append((weapon_name, weapon_url))
        elif normalized_query in url_norm:
            url_matches.append((weapon_name, weapon_url))

    if name_matches:
        name_matches.sort(key=lambda x: len(x[0]))
        suggestions = [name for name, _ in name_matches[:5]]
        return name_matches[0][1].lower(), suggestions

    if url_matches:
        url_matches.sort(key=lambda x: len(x[1]))
        suggestions = [name for name, _ in url_matches[:5]]
        return url_matches[0][1].lower(), suggestions

    scored = []
    for weapon_name, weapon_url in aliases:
        name_norm = _normalize(weapon_name)
        url_norm = _normalize(weapon_url)
        ratio = max(
            difflib.SequenceMatcher(None, normalized_query, name_norm).ratio(),
            difflib.SequenceMatcher(None, normalized_query, url_norm).ratio(),
        )
        scored.append((ratio, weapon_name, weapon_url))

    scored.sort(key=lambda x: x[0], reverse=True)
    suggestions = [name for _, name, _ in scored[:5]]
    if scored and scored[0][0] >= 0.72:
        return scored[0][2].lower(), suggestions

    return None, suggestions


def format_suggestions_text(suggestions):
    if not suggestions:
        return ""
    return "\nВозможно, ты имел в виду:\n" + "\n".join(suggestions[:5])


def build_random_loadout():
    items = get_all_weapons_cached()

    primary_pool = []
    pistol_pool = []

    for item in items:
        try:
            weapon_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue

        name = (item.get("name") or "").strip()
        image = (item.get("image") or "").replace("\\/", "/").strip()
        if not name or not image:
            continue

        if weapon_id in PISTOL_IDS:
            pistol_pool.append({"id": weapon_id, "name": name, "image": image})
        elif weapon_id != FLARE_ID:
            primary_pool.append({"id": weapon_id, "name": name, "image": image})

    if len(primary_pool) < 2:
        raise ValueError("Недостаточно оружия для случайной выборки.")
    if not pistol_pool:
        raise ValueError("Не удалось найти пистолеты для опционального слота.")

    main_weapons = random.sample(primary_pool, 2)
    optional_pistol = random.choice(pistol_pool)
    return main_weapons, optional_pistol


def get_weapon_details_by_url(weapon_url):
    response = requests.get(PUBG_SINGLE_URL.format(weapon_url=weapon_url), timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Некорректный формат PUBG API: ожидался объект.")

    result = {field: data.get(field, "") for field in DETAIL_FIELDS}
    return result


def format_weapon_details_text(details):
    labels = {
        "name": "Название",
        "short_description": "Описание",
        "bullet_type": "Тип патрона",
        "without_mag": "Магазин без обвеса",
        "with_mag": "Магазин с обвесом",
        "fire_modes": "Режимы огня",
        "damage": "Урон",
        "bullet_speed": "Скорость пули",
        "impact": "Impact",
        "pickup_delay": "Pickup Delay",
        "ready_delay": "Ready Delay",
        "normal_reload": "Обычная перезарядка",
        "quick_reload": "Быстрая перезарядка",
    }

    lines = []
    ordered = [f for f in DETAIL_FIELDS if f != "image"]
    for key in ordered:
        value = details.get(key)
        if value:
            lines.append(f"{labels[key]}: {value}")

    return "\n".join(lines) if lines else "Данные по оружию не найдены."
