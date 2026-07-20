"""
WordNet + wordfreq grounded category expansion derivation.

Queries Princeton WordNet (via NLTK) to derive word lists for each ReVoice
concept category, then filters by real word frequency (wordfreq library,
sourced from Wikipedia, OpenSubtitles, Twitter, and web crawls).

For word-finding difficulty, the relevant words are those a person with anomia
would say INSTEAD of the target name — superordinates, coordinate terms,
and functional descriptions. The synsets are chosen to match these error types:

  - Kinship synsets (relative.n.01) → coordinate kinship errors
    "grandson" when meaning granddaughter; "aunt" when meaning a specific person
  - Role synsets (health_professional.n.01) → occupational stand-ins
    "nurse" or "doctor" when meaning a specific caregiver
  - Category synsets (beverage.n.01, medicine.n.02) → superordinate errors
    "drink" or "hot thing" when meaning black coffee

Frequency threshold: 1e-6 (1 per million words in the wordfreq corpus).
Words below this threshold are too obscure to appear in natural speech as
word-finding substitutes.

References
----------
Miller, G.A. (1995). WordNet: A lexical database for English.
  Communications of the ACM, 38(11), 39-41.

Fellbaum, C. (Ed.). (1998). WordNet: An electronic lexical database.
  MIT Press.

Speer, R. et al. (2018). wordfreq: v2.2 [software].
  Zenodo. https://doi.org/10.5281/zenodo.1443582
  (Combines Wikipedia, OpenSubtitles, Twitter, Leeds Web Corpus)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import nltk
nltk.download("wordnet", quiet=True)
nltk.download("omw-1.4", quiet=True)
from nltk.corpus import wordnet as wn
from wordfreq import word_frequency

# Minimum frequency for a word to be included.
# 1e-6 = 1 occurrence per million words in the wordfreq corpus.
# Below this words are too rare to appear as natural speech substitutes.
FREQ_THRESHOLD = 1e-6

# ── WordNet synset seeds ──────────────────────────────────────────────────────
# Synsets chosen to capture the actual STAND-IN words people with anomia use,
# not every possible hyponym of the category label.
#
# Format: {category: [(synset_name, hyponym_depth), ...]}
#   depth 0 = just the synset's own lemmas
#   depth 1 = synset + direct hyponyms
#   depth 2 = synset + grandchildren (use carefully — can explode)

CATEGORY_SEEDS: dict[str, list[tuple[str, int]]] = {
    "person": [
        ("relative.n.01", 2),          # kinship: cousin, sibling, grandchild, niece…
        ("health_professional.n.01", 1),# caregiver, nurse, pharmacist
        ("adult.n.01", 1),             # man, woman, adult
        ("child.n.01", 1),             # boy, girl, kid, baby
        ("friend.n.01", 0),            # friend
        ("neighbor.n.01", 0),          # neighbor/neighbour
        ("colleague.n.01", 0),         # colleague
    ],
    "document": [
        ("written_document.n.01", 1),  # form, letter, certificate, report, record
        ("legal_document.n.01", 1),    # contract, bill, deed, warrant
        ("record.n.05", 1),            # file, report, account
        ("receipt.n.02", 0),           # receipt
        ("bill.n.02", 0),              # bill (invoice sense)
        ("prescription.n.01", 0),      # prescription
        ("notice.n.06", 0),            # notice (written)
    ],
    "order": [
        ("beverage.n.01", 1),          # coffee, tea, juice, milk, smoothie, soda
        ("meal.n.01", 1),              # breakfast, lunch, dinner, brunch, snack
        ("appetizer.n.01", 1),         # starter, snack
        ("dish.n.02", 0),              # dish (generic food item)
    ],
    "place": [
        ("health_facility.n.01", 1),   # clinic, hospital, infirmary, pharmacy
        ("building.n.01", 0),          # building (generic)
        ("facility.n.03", 1),          # facility, center, hall
        ("area.n.01", 1),              # area, zone, region, district
        ("location.n.01", 0),          # location
        ("store.n.01", 0),             # store, shop
        ("office.n.01", 0),            # office
    ],
    "medication": [
        ("medicine.n.02", 1),          # medication, remedy, treatment, dose, prescription
        ("drug.n.01", 0),              # drug (generic)
        ("tablet.n.02", 0),            # tablet
        ("pill.n.01", 0),              # pill
        ("capsule.n.01", 0),           # capsule
        ("injection.n.01", 0),         # injection
        ("vitamin.n.01", 0),           # vitamin
        ("supplement.n.02", 0),        # supplement
    ],
    "event": [
        ("social_event.n.01", 1),      # occasion, function, affair, show
        ("celebration.n.01", 1),       # anniversary, birthday, jubilee
        ("meeting.n.02", 1),           # appointment, session, conference
        ("outing.n.01", 1),            # trip, excursion
        ("reunion.n.01", 0),           # reunion
        ("visit.n.01", 0),             # visit
        ("party.n.01", 0),             # party
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def collect_lemmas(synset_name: str, depth: int) -> set[str]:
    """Return single-token lemma names from synset + hyponyms up to depth."""
    result: set[str] = set()

    def walk(s, remaining):
        for lemma in s.lemmas():
            name = lemma.name().lower().replace("_", " ")
            if " " not in name:          # single-token words only
                result.add(name)
        if remaining > 0:
            for hypo in s.hyponyms():
                walk(hypo, remaining - 1)

    try:
        walk(wn.synset(synset_name), depth)
    except Exception:
        pass
    return result


def is_common(word: str) -> bool:
    """True if word meets the frequency threshold in the wordfreq corpus."""
    return word_frequency(word, "en") >= FREQ_THRESHOLD


# ── Main derivation ───────────────────────────────────────────────────────────

def derive_all() -> dict[str, dict]:
    results = {}

    for category, seeds in CATEGORY_SEEDS.items():
        all_lemmas: set[str] = set()
        synset_log = []

        for synset_name, depth in seeds:
            lemmas = collect_lemmas(synset_name, depth)
            freq_filtered = {w for w in lemmas if is_common(w)}
            all_lemmas.update(freq_filtered)

            synset = None
            try:
                synset = wn.synset(synset_name)
            except Exception:
                pass

            synset_log.append({
                "synset": synset_name,
                "definition": synset.definition() if synset else "N/A",
                "depth": depth,
                "raw_lemmas": len(lemmas),
                "after_freq_filter": len(freq_filtered),
                "words": sorted(freq_filtered),
            })

        results[category] = {
            "total_unique_words": len(all_lemmas),
            "all_words": sorted(all_lemmas),
            "synsets": synset_log,
        }

    return results


if __name__ == "__main__":
    print("Deriving category expansions from Princeton WordNet + wordfreq...")
    print(f"Frequency threshold: {FREQ_THRESHOLD:.0e} (per million words)")
    print("Sources: Miller (1995) WordNet; Speer et al. (2018) wordfreq\n")

    results = derive_all()

    out_path = Path(__file__).parent / "wordnet_expansions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"{'Category':<14} {'Total words':>12}")
    print("-" * 28)
    for cat, data in results.items():
        print(f"{cat:<14} {data['total_unique_words']:>12}")
        print(f"  {data['all_words']}")

    print(f"\nFull data saved to: {out_path}")
