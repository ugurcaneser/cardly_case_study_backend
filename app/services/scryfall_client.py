from dataclasses import dataclass

import httpx

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH_API_URL = "https://api.scryfall.com/cards/search"
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


def search_by_name_and_number(name: str, collector_number: str) -> ScryfallCard | None:
    """Looks up the exact printing matching both a name and its printed
    collector number (e.g. "101" parsed from a scanned "101/249").

    `search_by_name`'s fuzzy lookup ignores set/printing and Scryfall
    defaults to returning the card's *most recent* printing — for a
    frequently-reprinted card that's often a different collector number
    than the one actually photographed. This targets the specific printing
    instead, using Scryfall's search syntax (exact name + `cn:` filter).
    Same None-vs-raise contract as `search_by_name`.
    """
    query = f'!"{name}" cn:{collector_number}'
    try:
        response = httpx.get(
            SCRYFALL_SEARCH_API_URL,
            params={"q": query},
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
        results = response.json().get("data") or []
    except ValueError as exc:
        raise ScryfallError(f"Unexpected Scryfall response shape: {exc}") from exc

    if not results:
        return None

    try:
        return _parse_card(results[0])
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
