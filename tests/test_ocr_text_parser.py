from app.services.ocr_text_parser import parse_ocr_text


def test_empty_input_returns_none_for_both_fields():
    result = parse_ocr_text("")
    assert result.parsed_name is None
    assert result.parsed_number is None


def test_none_input_returns_none_for_both_fields():
    result = parse_ocr_text(None)
    assert result.parsed_name is None
    assert result.parsed_number is None


def test_whitespace_only_input_returns_none():
    result = parse_ocr_text("   \n  \n")
    assert result.parsed_name is None
    assert result.parsed_number is None


def test_parses_name_from_first_line():
    result = parse_ocr_text("Lightning Bolt\nInstant\nDeals 3 damage to any target.")
    assert result.parsed_name == "Lightning Bolt"


def test_skips_leading_non_alphabetic_lines_for_name():
    result = parse_ocr_text("133\nLightning Bolt\nInstant")
    assert result.parsed_name == "Lightning Bolt"


def test_parses_collector_number():
    result = parse_ocr_text("Lightning Bolt\nInstant\n133/264")
    assert result.parsed_number == "133/264"


def test_no_number_present_returns_none():
    result = parse_ocr_text("Lightning Bolt\nInstant\nDeals 3 damage to any target.")
    assert result.parsed_number is None


def test_extracts_number_from_noisy_copyright_line():
    raw = "Lightning Bolt\nInstant\n™ & © 2023 Wizards of the Coast LLC 133/264 C"
    result = parse_ocr_text(raw)
    assert result.parsed_number == "133/264"


def test_multiple_slash_patterns_picks_the_first_match():
    raw = "Lightning Bolt\n133/264\nReprinted from 45/86"
    result = parse_ocr_text(raw)
    assert result.parsed_number == "133/264"


def test_ignores_a_bare_year_without_a_slash():
    raw = "Lightning Bolt\n© 2023 Wizards of the Coast"
    result = parse_ocr_text(raw)
    assert result.parsed_number is None


def test_handles_extra_whitespace_around_the_slash():
    raw = "Lightning Bolt\n133 / 264"
    result = parse_ocr_text(raw)
    assert result.parsed_number == "133/264"


def test_power_toughness_is_not_mistaken_for_a_collector_number():
    # A real report: a creature's "7/5" P/T box was the only digit/digit
    # pattern OCR picked up (the actual "0059" collector line had no visible
    # "/total" suffix), and it was wrongly treated as the collector number.
    raw = "Dreamtide Whale\nCreature - Whale\n7/5\nR 0059\nMH3 - EN"
    result = parse_ocr_text(raw)
    assert result.parsed_number is None


def test_a_genuine_collector_number_is_still_found_alongside_power_toughness():
    raw = "Lightning Bolt\nCreature - Elemental\n7/5\n133/264"
    result = parse_ocr_text(raw)
    assert result.parsed_number == "133/264"


def test_single_clean_line_produces_one_candidate():
    result = parse_ocr_text("Lightning Bolt")
    assert result.name_candidates == ("Lightning Bolt",)


def test_short_junk_tokens_are_excluded_from_candidates():
    # "ms" (2 alpha chars) falls below the minimum and is skipped entirely,
    # rather than being promoted to parsed_name the way the old
    # first-alphabetic-line heuristic would have.
    result = parse_ocr_text("19\n14\n)\nms\nLightning Bolt")
    assert "ms" not in result.name_candidates
    assert result.parsed_name == "Lightning Bolt"


def test_truncated_filename_artifact_is_excluded_from_candidates():
    result = parse_ocr_text("mh3-59-dreamt...\nDreamtide Whale")
    assert result.name_candidates == ("Dreamtide Whale",)


def test_duplicate_lines_are_deduped_case_insensitively():
    result = parse_ocr_text("Lightning Bolt\nLIGHTNING BOLT")
    assert result.name_candidates == ("Lightning Bolt",)


def test_candidates_are_capped_at_six():
    lines = [f"Candidate Line {i}" for i in range(10)]
    result = parse_ocr_text("\n".join(lines))
    assert len(result.name_candidates) == 6
    assert result.name_candidates[0] == "Candidate Line 0"


def test_reproduces_the_screenshot_chrome_scenario():
    # A real report: photographing a screenshot of a card (in a browser/
    # Preview window) OCR's the window chrome above the actual card name.
    # The old single-guess heuristic picked "ms" and never found the card.
    raw = "\n".join(
        [
            "19",
            "14",
            ")",
            "ms",
            "/ 4",
            "AIL",
            "1S)",
            "mh3-59-dreamt...",
            'Locked"',
            "»",
            "Dreamtide Whale",
            "+",
            "2",
            "Creature - Whale",
        ]
    )
    result = parse_ocr_text(raw)
    assert "Dreamtide Whale" in result.name_candidates
    assert "ms" not in result.name_candidates
    assert "mh3-59-dreamt..." not in result.name_candidates
