"""Invented names for people, clubs and venues (docs/DATA_AND_METRICS.md §1).

Surnames and place names are assembled from syllables in several naming traditions, so the
league feels global without borrowing anyone's real name. Given names come from per-tradition
lists of common first names (a first name alone identifies nobody). Every candidate is checked
against the hashed real-name blocklist and against names already taken in the league.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from regista_sim.blocklist import is_blocked


@dataclass(frozen=True)
class Tradition:
    """Syllable inventory for one naming tradition."""

    first_names: tuple[str, ...]
    heads: tuple[str, ...]
    tails: tuple[str, ...]


TRADITIONS: dict[str, Tradition] = {
    "anglo": Tradition(
        (
            "Callum",
            "Rhys",
            "Owen",
            "Liam",
            "Connor",
            "Jamie",
            "Aiden",
            "Harvey",
            "Lewis",
            "Ethan",
            "Cian",
            "Niall",
            "Ross",
            "Tyler",
            "Kieran",
            "Finn",
            "Kian",
            "Alfie",
            "Reece",
            "Toby",
        ),
        (
            "Brack",
            "Corr",
            "Dorn",
            "Elm",
            "Fen",
            "Gark",
            "Hollin",
            "Lark",
            "Merr",
            "Penn",
            "Quar",
            "Rook",
            "Stell",
            "Thorn",
            "Wend",
            "Yarr",
            "Ashen",
            "Bram",
        ),
        (
            "mere",
            "wick",
            "ridge",
            "combe",
            "hollow",
            "stead",
            "brook",
            "fell",
            "gate",
            "holt",
            "lowe",
            "haven",
        ),
    ),
    "iberian": Tradition(
        (
            "Iker",
            "Mateo",
            "Álvaro",
            "Unai",
            "Pablo",
            "Marcos",
            "Rubén",
            "Sergio",
            "Javier",
            "Adrián",
            "Hugo",
            "Gonzalo",
            "Íñigo",
            "Raúl",
            "Martín",
            "Nico",
            "Asier",
            "Aitor",
        ),
        (
            "Val",
            "Gar",
            "Sol",
            "Ber",
            "Cas",
            "Ol",
            "Ur",
            "Ver",
            "Mon",
            "Esc",
            "Lar",
            "Ib",
            "Zal",
            "Orv",
            "Taz",
            "Ald",
        ),
        (
            "dorra",
            "daño",
            "rosa",
            "dezo",
            "rabe",
            "illo",
            "eda",
            "ena",
            "ano",
            "eros",
            "uga",
            "ive",
        ),
    ),
    "franco": Tradition(
        (
            "Mattis",
            "Théo",
            "Bastien",
            "Louis",
            "Antoine",
            "Mathéo",
            "Enzo",
            "Clément",
            "Noé",
            "Malo",
            "Gaël",
            "Corentin",
            "Florian",
            "Damien",
            "Jules",
            "Sacha",
            "Lilian",
            "Maël",
        ),
        (
            "Bel",
            "Dur",
            "Lan",
            "Fon",
            "Char",
            "Gau",
            "Dum",
            "Mor",
            "Lec",
            "Pel",
            "Bou",
            "Tess",
            "Dau",
            "Arm",
            "Viel",
            "Roch",
        ),
        ("ville", "court", "mont", "ard", "elin", "ot", "eau", "ier", "oux", "elle", "ac", "aine"),
    ),
    "maghrebi": Tradition(
        (
            "Yanis",
            "Rayan",
            "Ilyes",
            "Sofiane",
            "Amine",
            "Nassim",
            "Bilal",
            "Walid",
            "Zakaria",
            "Anis",
            "Mehdi",
            "Hakim",
            "Samir",
            "Yassine",
            "Ayoub",
            "Othmane",
            "Idriss",
            "Adel",
        ),
        (
            "Bel",
            "Ben",
            "Am",
            "Kad",
            "Zer",
            "Haj",
            "Ait",
            "Mes",
            "Ou",
            "Sa",
            "Ta",
            "Bou",
            "Lah",
            "Med",
        ),
        (
            "kari",
            "rani",
            "mari",
            "ouri",
            "ladi",
            "dani",
            "hari",
            "sali",
            "mezi",
            "kadi",
            "rachi",
            "tani",
        ),
    ),
    "slavic": Tradition(
        (
            "Luka",
            "Marko",
            "Ivan",
            "Petar",
            "Filip",
            "Matej",
            "Nikola",
            "Dario",
            "Tomas",
            "Jakub",
            "Bogdan",
            "Milan",
            "Stefan",
            "Viktor",
            "Dominik",
            "Borna",
            "Lovro",
            "Ognjen",
        ),
        (
            "Kral",
            "Dvor",
            "Zel",
            "Hor",
            "Vol",
            "Brod",
            "Kos",
            "Lis",
            "Rad",
            "Yar",
            "Mrav",
            "Plet",
            "Sver",
            "Grab",
        ),
        ("ak", "ič", "ovan", "enko", "ski", "ek", "uk", "ar", "in", "ko", "ota", "ec"),
    ),
    "west_african": Tradition(
        (
            "Kwame",
            "Ibrahim",
            "Moussa",
            "Seydou",
            "Kofi",
            "Chidi",
            "Emeka",
            "Yaw",
            "Ousmane",
            "Lamine",
            "Tunde",
            "Ikenna",
            "Mamadou",
            "Kelechi",
            "Samuel",
            "Kojo",
            "Sekou",
            "Femi",
        ),
        ("Ade", "Oko", "Nda", "Asa", "Ama", "Tou", "Kwa", "Ola", "Emi", "Diba", "Sow", "Fofa"),
        (
            "yori",
            "romu",
            "mbata",
            "ssiko",
            "wunmi",
            "nkiri",
            "fola",
            "bari",
            "ndeye",
            "tey",
            "dugo",
            "lade",
        ),
    ),
    "italian": Tradition(
        (
            "Matteo",
            "Lorenzo",
            "Davide",
            "Federico",
            "Andrea",
            "Simone",
            "Riccardo",
            "Tommaso",
            "Alessio",
            "Niccolò",
            "Pietro",
            "Emanuele",
            "Filippo",
            "Samuele",
            "Edoardo",
            "Mattia",
        ),
        (
            "Cor",
            "Fer",
            "Gal",
            "Lom",
            "Mar",
            "Pa",
            "Ros",
            "San",
            "Ter",
            "Vin",
            "Zan",
            "Bru",
            "Cim",
            "Dol",
        ),
        (
            "etti",
            "inaro",
            "ucci",
            "ardi",
            "ato",
            "elli",
            "oni",
            "esi",
            "aro",
            "isio",
            "anza",
            "edda",
        ),
    ),
    "nordic": Tradition(
        (
            "Oskar",
            "Elias",
            "Magnus",
            "Sander",
            "Emil",
            "Henrik",
            "Tobias",
            "Jonas",
            "Aksel",
            "Vetle",
            "Mikkel",
            "Eskil",
            "Torben",
            "Rasmus",
            "Nils",
            "Viggo",
            "Halvar",
            "Linus",
        ),
        (
            "Vel",
            "Ost",
            "Hal",
            "Sto",
            "Ny",
            "Sund",
            "Fjell",
            "Hag",
            "Brann",
            "Skog",
            "Hed",
            "Kvist",
            "Rønn",
            "Gran",
        ),
        (
            "holm",
            "vik",
            "strand",
            "dal",
            "gard",
            "lund",
            "stad",
            "by",
            "ness",
            "heim",
            "rud",
            "ang",
        ),
    ),
    "finnic": Tradition(
        (
            "Eetu",
            "Aleksi",
            "Joonas",
            "Lauri",
            "Onni",
            "Veeti",
            "Eemil",
            "Topias",
            "Niklas",
            "Ville",
            "Sami",
            "Kalle",
            "Arttu",
            "Juho",
        ),
        ("Hyv", "Kor", "Lah", "Mäk", "Vir", "Hei", "Tal", "Rau", "Kul", "Nie", "Pel", "Saar"),
        ("vala", "inen", "ala", "onen", "maa", "luoto", "harju", "koski", "vuo", "niemi"),
    ),
    "lusophone": Tradition(
        (
            "João",
            "Rafael",
            "Gonçalo",
            "Tiago",
            "Rodrigo",
            "Vitor",
            "Caio",
            "Renan",
            "Igor",
            "Luan",
            "Davi",
            "Breno",
            "Otávio",
            "Duarte",
        ),
        ("Bra", "Fal", "Gou", "Lav", "Mir", "Quin", "Tor", "Zam", "Cor", "Ama"),
        ("eiro", "alhão", "ança", "oso", "inho", "edo", "ares", "ota"),
    ),
}

# Relative frequency of each tradition among invented players.
TRADITION_WEIGHTS: dict[str, float] = {
    "anglo": 0.24,
    "iberian": 0.10,
    "franco": 0.11,
    "maghrebi": 0.07,
    "slavic": 0.08,
    "west_african": 0.12,
    "italian": 0.07,
    "nordic": 0.09,
    "finnic": 0.04,
    "lusophone": 0.08,
}

_PLACE_HEADS = (
    "Ash",
    "Brack",
    "Corr",
    "Dray",
    "Elmer",
    "Fal",
    "Garr",
    "Ives",
    "Lark",
    "Marl",
    "Nethe",
    "Orm",
    "Pell",
    "Quen",
    "Rav",
    "Sel",
    "Tarr",
    "Ulm",
    "Vel",
    "Wyn",
    "Yar",
    "Cold",
    "Bryn",
    "Hob",
)
_PLACE_TAILS = (
    "mere",
    "wick",
    "haven",
    "combe",
    "moor",
    "holt",
    "brook",
    "stead",
    "gate",
    "fell",
    "ridge",
    "water",
    " Vale",
    " Heath",
    " Cross",
    " Bay",
)
CLUB_SUFFIXES = (
    "FC",
    "Athletic",
    "Rovers",
    "Town",
    "Albion",
    "Wanderers",
    "City",
    "United",
    "Harriers",
    "County",
    "Borough",
)
_VENUE_HEADS = (
    "Copper",
    "Lantern",
    "Foundry",
    "Orchard",
    "Beacon",
    "Weaver",
    "Signal",
    "Granary",
    "Quarry",
    "Ferry",
    "Tannery",
    "Kiln",
    "Harbour",
    "Cooper",
    "Saltmarsh",
    "Ropewalk",
    "Mariner",
    "Willowbank",
    "Heron",
    "Larch",
)
_VENUE_TAILS = ("Park", "Road", "Lane", "Ground", "Stadium", "Meadow", "Yard", "Field")

_MAX_TRIES = 200


def _pick(rng: np.random.Generator, options: tuple[str, ...]) -> str:
    return options[int(rng.integers(len(options)))]


def _join(head: str, tail: str) -> str:
    """Join two syllables, dropping a doubled letter at the seam ("Elm" + "mere" → "Elmere")."""
    if tail[:1].isalpha() and head[-1:].lower() == tail[:1].lower():
        tail = tail[1:]
    return head + tail


def _unique(make: Callable[[], str], taken: set[str]) -> str:
    for _ in range(_MAX_TRIES):
        candidate = make()
        if candidate not in taken and not is_blocked(candidate):
            taken.add(candidate)
            return candidate
    msg = "name space exhausted; widen the syllable lists"
    raise RuntimeError(msg)


def person_name(
    rng: np.random.Generator, taken: set[str], tradition: str | None = None
) -> tuple[str, str]:
    """Return an invented ``(first, last)`` name; neither the surname nor the full name is taken.

    Both are added to ``taken``, so surnames stay unique across the league ("Valdane" names one
    player). Both must also pass the real-name blocklist.
    """
    keys = tuple(TRADITION_WEIGHTS)
    weights = np.array([TRADITION_WEIGHTS[k] for k in keys])
    for _ in range(_MAX_TRIES):
        key = tradition or keys[int(rng.choice(len(keys), p=weights / weights.sum()))]
        style = TRADITIONS[key]
        first = _pick(rng, style.first_names)
        last = _join(_pick(rng, style.heads), _pick(rng, style.tails))
        full = f"{first} {last}"
        if last in taken or full in taken or is_blocked(full) or is_blocked(last):
            continue
        taken.update((full, last))
        return first, last
    msg = "person name space exhausted"
    raise RuntimeError(msg)


def place_name(rng: np.random.Generator, taken: set[str], used_heads: set[str]) -> str:
    """Return an invented place name (a club's stem) whose first syllable is not yet used."""
    heads = tuple(h for h in _PLACE_HEADS if h not in used_heads)
    head = _pick(rng, heads)
    used_heads.add(head)
    return _unique(lambda: _join(head, _pick(rng, _PLACE_TAILS)), taken)


def venue_name(rng: np.random.Generator, taken: set[str]) -> str:
    """Return an invented stadium name such as "Lantern Road", unique within ``taken``."""
    return _unique(lambda: f"{_pick(rng, _VENUE_HEADS)} {_pick(rng, _VENUE_TAILS)}", taken)
