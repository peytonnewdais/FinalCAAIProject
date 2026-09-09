"""Tests for the pure text-scoring and XBRL transforms in services/edgar.py.

None of these touch the network: they exercise the regexes and dict-shaping logic
directly against small hand-built inputs.
"""
from services import edgar


def test_ai_any_counts_each_distinct_term_once():
    text = "The company uses AI and machine learning. It also invests in generative AI and neural networks."
    assert len(edgar.AI_ANY.findall(text)) == 4


def test_ai_any_is_case_sensitive_for_the_bare_letters_ai():
    # "ai" inside ordinary prose (e.g. "certain", "maintain") must not count.
    text = "We maintain a certain amount of contingency capital."
    assert edgar.AI_ANY.findall(text) == []


def test_snippets_keeps_only_ai_bearing_sentences_in_range():
    short = "Hi."
    on_topic = ("This filing discusses artificial intelligence and machine learning "
                "as a growing part of our product roadmap and R&D spend this year.")
    off_topic = ("Our facilities lease in Austin, Texas expires in 2027 and we do not "
                "expect a material change in our real estate footprint.")
    text = f"{short} {on_topic} {off_topic}"

    snippets = edgar._snippets(text)

    assert len(snippets) == 1
    assert "artificial intelligence" in snippets[0].lower()


def test_annual_values_keeps_full_year_10k_entries_and_skips_quarters():
    facts = {
        "facts": {
            "us-gaap": {
                "ResearchAndDevelopmentExpense": {
                    "units": {
                        "USD": [
                            {"start": "2022-01-01", "end": "2022-12-31", "val": 1000,
                             "form": "10-K", "filed": "2023-02-01"},
                            {"start": "2022-06-01", "end": "2022-09-01", "val": 250,
                             "form": "10-Q", "filed": "2022-10-01"},
                        ]
                    }
                }
            }
        }
    }

    values, unit = edgar._annual_values(facts, edgar.RD_CONCEPTS)

    assert values == {2022: 1000.0}
    assert unit == "USD"


def test_annual_values_returns_empty_when_concept_is_missing():
    values, unit = edgar._annual_values({"facts": {}}, edgar.RD_CONCEPTS)
    assert values == {}
    assert unit is None
