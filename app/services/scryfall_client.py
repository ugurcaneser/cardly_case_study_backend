from dataclasses import dataclass

import httpx

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
_REQUEST_TIMEOUT_SECONDS = 10.0
# Scryfall's API guidelines ask for a descriptive User-Agent + Accept header
# to avoid being rate-limited as an anonymous/unidentified client.
_REQUEST_HEADERS = {"User-Agent": "Cardly/1.0", "Accept": "application/json"}


@dataclass(frozen=True)
class ScryfallCard:
    scryfall_id: str
    name: str
    set_name: str
    set_code: str
    collector_number: str
    rarity: str
    mana_cost: str | None
    type_line: str
    oracle_text: str | None
    image_url: str | None
    prices: dict[str, str | None]


class ScryfallError(Exception):
    """Raised for a genuine Scryfall failure (network, unexpected status, malformed response).

    Not raised when Scryfall simply has no match for the given name —
    `search_by_name` returns `None` for that, a legitimate result.
    """


def search_by_name(name: str) -> ScryfallCard | None:
    try:
        response = httpx.get(
            SCRYFALL_API_URL,
            params={"fuzzy": name},
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers=_REQUEST_HEADERS,
        )
    except httpx.HTTPError as exc:
        raise ScryfallError(f"Scryfall request failed: {exc}") from exc

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise ScryfallError(f"Scryfall returned status {response.status_code}: {response.text}")

    try:
        return _parse_card(response.json())
    except (KeyError, TypeError, ValueError) as exc:
        raise ScryfallError(f"Unexpected Scryfall response shape: {exc}") from exc


def _parse_card(data: dict) -> ScryfallCard:
    image_uris = data.get("image_uris") or {}
    return ScryfallCard(
        scryfall_id=data["id"],
        name=data["name"],
        set_name=data["set_name"],
        set_code=data["set"],
        collector_number=data["collector_number"],
        rarity=data["rarity"],
        mana_cost=data.get("mana_cost"),
        type_line=data["type_line"],
        oracle_text=data.get("oracle_text"),
        image_url=image_uris.get("normal"),
        prices=data.get("prices") or {},
    )
