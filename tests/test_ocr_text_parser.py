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
