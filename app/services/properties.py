from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROPERTIES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "properties.json"

LISTING_ALIASES = {
    "rent": ["rent", "rental", "lease", "for rent", "إيجار", "للإيجار", "ايجار"],
    "sale": ["sale", "buy", "purchase", "for sale", "بيع", "للبيع", "شراء"],
}

PROPERTY_TYPE_ALIASES = {
    "apartment": ["apartment", "flat", "شقة", "شقق"],
    "villa": ["villa", "فilla", "فيلا", "فillas"],
    "duplex": ["duplex", "دوبlex", "دوبلكس"],
    "townhouse": ["townhouse", "تاون هاوس"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def load_properties() -> list[dict[str, Any]]:
    with PROPERTIES_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [unit for unit in data.get("units", []) if unit.get("available", True)]


def get_unit(unit_id: str) -> dict[str, Any] | None:
    normalized_id = unit_id.strip().upper()
    for unit in load_properties():
        if unit["id"].upper() == normalized_id:
            return unit
    return None


def format_unit_summary(unit: dict[str, Any], language: str = "en") -> str:
    title = unit.get(f"title_{language}") or unit.get("title_en")
    price = unit.get(f"price_label_{language}") or unit.get("price_label_en")
    listing = unit.get("listing_type", "").upper()
    return (
        f"{unit['id']} — {title}\n"
        f"{price} | {unit.get('bedrooms')}BR | {unit.get('area_sqm')} sqm | {listing}\n"
        f"{unit.get('city')} — {unit.get(f'district_{language}') or unit.get('district_en')}"
    )


def _detect_listing_type(message: str) -> str | None:
    normalized = _normalize(message)
    for listing_type, aliases in LISTING_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return listing_type
    return None


def _detect_property_type(message: str) -> str | None:
    normalized = _normalize(message)
    for property_type, aliases in PROPERTY_TYPE_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return property_type
    return None


def _detect_city(message: str) -> str | None:
    normalized = _normalize(message)
    cities = {
        "riyadh": ["riyadh", "الرياض"],
        "jeddah": ["jeddah", "jiddah", "جدة", "جده"],
    }
    for city, aliases in cities.items():
        if any(alias in normalized for alias in aliases):
            return city.title()
    return None


def _detect_bedrooms(message: str) -> int | None:
    text = _normalize(message)

    # Arabic bedroom expressions
    arabic_numbers = {
        "غرفة": 1,
        "غرفة واحدة": 1,
        "غرفتين": 2,
        "غرفتان": 2,
        "ثلاث غرف": 3,
        "ثلاثة غرف": 3,
        "أربع غرف": 4,
        "أربعة غرف": 4,
        "خمس غرف": 5,
        "خمسة غرف": 5,
    }

    for phrase, count in arabic_numbers.items():
        if phrase in text:
            return count

    # Arabic digits: ١، ٢، ٣...
    arabic_digit_match = re.search(
        r"([0-9]+)\s*(?:غرف|غرفة|غرفه)",
        text,
    )
    if arabic_digit_match:
        arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        return int(arabic_digit_match.group(1).translate(arabic_digits))

    # English / normal numeric format
    match = re.search(
        r"(\d+)\s*(?:br|bed|bedroom|bedrooms|غرف|غرفة|غرفه)",
        text,
    )

    if match:
        return int(match.group(1))

    normalized = _normalize(message)

    # الأرقام: 2 غرف، 2 غرفة، 2 bedroom، 2 bedrooms، 2 br
    match = re.search(
        r"(\d+)\s*(?:br|bed|bedroom|غرف|غرفة|غرفه|غرفتين|غرفتان)",
        normalized
    )
    if match:
        return int(match.group(1))

    # الكلمات العربية
    arabic_numbers = {
        "غرفة واحدة": 1,
        "غرفه واحدة": 1,
        "غرفة": 1,
        "غرفتين": 2,
        "غرفتان": 2,
        "ثلاث غرف": 3,
        "ثلاثة غرف": 3,
        "اربع غرف": 4,
        "أربع غرف": 4,
        "أربعة غرف": 4,
        "خمس غرف": 5,
        "خمسة غرف": 5,
    }

    for phrase, bedrooms in arabic_numbers.items():
        if phrase in normalized:
            return bedrooms

    return None
    match = re.search(r"(\d+)\s*(?:br|bed|bedroom|غرف|غرفة)", _normalize(message))
    if match:
        return int(match.group(1))
    return None

def _detect_max_price(message: str) -> int | None:
    text = _normalize(message)

    # Arabic digits → English digits
    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    text = text.translate(arabic_digits)

    # Maximum price / under / less than
    patterns = [
        r"(?:اقل من|أقل من|تحت|حد اقصى|حد أقصى|بحد اقصى|بحد أقصى)\s*([\d,]+)",
        r"(?:under|below|max|maximum)\s*([\d,]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))

    return None

def _unit_matches_query(unit: dict[str, Any], message: str) -> bool:
    normalized = _normalize(message)
    tokens = [
        _normalize(unit["id"]),
        _normalize(unit.get("title_en", "")),
        _normalize(unit.get("title_ar", "")),
        _normalize(unit.get("district_en", "")),
        _normalize(unit.get("district_ar", "")),
        _normalize(unit.get("project_id", "").replace("-", " ")),
    ]
    return any(token and token in normalized for token in tokens)


@dataclass
class PropertySearchResult:
    units: list[dict[str, Any]] = field(default_factory=list)
    matched_unit: dict[str, Any] | None = None


def search_properties(message: str) -> PropertySearchResult:
    units = load_properties()
    listing_type = _detect_listing_type(message)
    property_type = _detect_property_type(message)
    city = _detect_city(message)
    bedrooms = _detect_bedrooms(message)
    max_price = _detect_max_price(message)

    for unit in units:
        if _normalize(unit["id"]) in _normalize(message) or _unit_matches_query(unit, message):
            return PropertySearchResult(units=[unit], matched_unit=unit)

    filtered = []

    for unit in units:
        if listing_type and unit.get("listing_type") != listing_type:
            continue

        if property_type and unit.get("property_type") != property_type:
            continue

        if city and unit.get("city", "").lower() != city.lower():
            continue

        if bedrooms is not None and unit.get("bedrooms") != bedrooms:
            continue

        if max_price is not None and unit.get("price", 0) > max_price:
            continue

        filtered.append(unit)

    if filtered:
        return PropertySearchResult(units=filtered[:5])

    if listing_type or property_type or city or bedrooms is not None or max_price is not None:
        return PropertySearchResult(units=[])

    return PropertySearchResult(units=[])


def wants_photos(message: str) -> bool:
    normalized = _normalize(message)
    keywords = ["photo", "photos", "picture", "pictures", "image", "images", "صور", "صورة", "صوره"]
    return any(keyword in normalized for keyword in keywords)


def list_units_for_menu(language: str = "en") -> str:
    lines = []
    for unit in load_properties():
        lines.append(format_unit_summary(unit, language))
    header = "Available units:" if language == "en" else "الوحدات المتاحة:"
    return header + "\n\n" + "\n\n".join(lines)
