"""The ci.cog manifest parser: every rule with a positive and a negative
control.

A stability manifest exists precisely because nobody can eyeball the numbers
in it (a brass stalk's grams, a density, a placement), so a line that
half-parses is a verdict built on unaudited input — every malformed shape
fails loudly with file and line, and these tests pin that it stays that way.
"""

import pytest

from cogcheck.conf import ManifestError, parse


def test_full_manifest_parses():
    m = parse(
        "# designs/ovodyo/ci.cog\n"
        "margin: 2.0\n"
        "part: ovodyo-base.stl | density: 1.24\n"
        "part: ovodyo-head.stl | density: 1.24 | translate: 0,0,86 | rotate: 0,0,15\n"
        "mass: stalk | grams: 42 | at: 0,0,43\n",
        path="ci.cog",
    )
    assert m.margin == 2.0
    assert len(m.parts) == 2
    base, head = m.parts
    assert base.stl == "ovodyo-base.stl"
    assert base.density == 1.24
    assert base.translate == (0.0, 0.0, 0.0)
    assert base.rotate == (0.0, 0.0, 0.0)
    assert head.translate == (0.0, 0.0, 86.0)
    assert head.rotate == (0.0, 0.0, 15.0)
    (stalk,) = m.masses
    assert stalk.label == "stalk"
    assert stalk.grams == 42.0
    assert stalk.at == (0.0, 0.0, 43.0)


def test_margin_defaults_to_zero():
    m = parse("part: a.stl | density: 1.24\n")
    assert m.margin == 0.0


def test_negative_margin_refused():
    with pytest.raises(ManifestError, match="margin"):
        parse("margin: -1\npart: a.stl | density: 1.24\n")


def test_no_parts_refused():
    with pytest.raises(ManifestError, match="no 'part:'"):
        parse("margin: 1\nmass: stalk | grams: 5 | at: 0,0,10\n")


def test_part_without_density_refused():
    with pytest.raises(ManifestError, match="density"):
        parse("part: a.stl | translate: 1,2,3\n")


def test_part_with_defaulted_density_is_not_a_thing():
    """No default exists: a part line with density omitted must name that
    fact in its error, never silently assume PLA."""
    with pytest.raises(ManifestError, match="no density"):
        parse("part: a.stl\n")


def test_non_positive_density_refused():
    with pytest.raises(ManifestError, match="density"):
        parse("part: a.stl | density: 0\n")


def test_malformed_translate_refused():
    with pytest.raises(ManifestError, match="translate"):
        parse("part: a.stl | density: 1.24 | translate: 1,2\n")


def test_malformed_rotate_refused():
    with pytest.raises(ManifestError, match="rotate"):
        parse("part: a.stl | density: 1.24 | rotate: 1,2,three\n")


def test_unknown_part_field_refused():
    with pytest.raises(ManifestError, match="unknown part field 'colour'"):
        parse("part: a.stl | density: 1.24 | colour: red\n")


def test_unknown_mass_field_refused():
    with pytest.raises(ManifestError, match="unknown mass field"):
        parse("part: a.stl | density: 1.24\nmass: x | grams: 5 | at: 0,0,0 | colour: red\n")


def test_mass_without_position_refused():
    with pytest.raises(ManifestError, match="no at"):
        parse("part: a.stl | density: 1.24\nmass: stalk | grams: 42\n")


def test_mass_without_grams_refused():
    with pytest.raises(ManifestError, match="no grams"):
        parse("part: a.stl | density: 1.24\nmass: stalk | at: 0,0,43\n")


def test_unknown_top_level_key_refused():
    with pytest.raises(ManifestError, match="unknown key 'friction'"):
        parse("friction: 0.5\npart: a.stl | density: 1.24\n")


def test_not_a_kv_line_refused():
    with pytest.raises(ManifestError, match="not a 'key: value' line"):
        parse("just some words\npart: a.stl | density: 1.24\n")


def test_duplicate_part_refused():
    with pytest.raises(ManifestError, match="twice"):
        parse(
            "part: a.stl | density: 1.24\n"
            "part: a.stl | density: 1.24\n"
        )


def test_duplicate_part_field_refused():
    with pytest.raises(ManifestError, match="density.*twice|field 'density'"):
        parse("part: a.stl | density: 1.24 | density: 20\n")


def test_duplicate_mass_field_refused():
    with pytest.raises(ManifestError, match="grams.*twice|field 'grams'"):
        parse(
            "part: a.stl | density: 1.24\n"
            "mass: stalk | grams: 5 | grams: 10 | at: 0,0,1\n"
        )


def test_non_finite_density_refused():
    with pytest.raises(ManifestError, match="finite"):
        parse("part: a.stl | density: nan\n")


def test_non_finite_margin_refused():
    with pytest.raises(ManifestError, match="finite"):
        parse("margin: inf\npart: a.stl | density: 1.24\n")


def test_non_finite_translate_refused():
    with pytest.raises(ManifestError, match="finite"):
        parse("part: a.stl | density: 1.24 | translate: 0,nan,0\n")


def test_path_traversal_stl_refused():
    with pytest.raises(ManifestError, match="basename"):
        parse("part: ../secret.stl | density: 1.24\n")


def test_slash_in_stl_refused():
    with pytest.raises(ManifestError, match="basename"):
        parse("part: sub/dir.stl | density: 1.24\n")


def test_backslash_in_stl_refused():
    with pytest.raises(ManifestError, match="basename"):
        parse("part: sub\\dir.stl | density: 1.24\n")


def test_dotdot_basename_refused():
    with pytest.raises(ManifestError, match="basename"):
        parse("part: .. | density: 1.24\n")


def test_duplicate_margin_refused():
    with pytest.raises(ManifestError, match="margin declared twice"):
        parse("margin: 1\nmargin: 2\npart: a.stl | density: 1.24\n")


def test_error_carries_file_and_line():
    with pytest.raises(Exception) as excinfo:
        parse(
            "part: a.stl | density: 1.24\n"
            "part: b.stl | density: one\n",
            path="ci.cog",
        )
    assert "ci.cog:2" in str(excinfo.value)


def test_comments_and_blanks_ignored():
    m = parse(
        "\n"
        "# a comment with 'part:' in it that must not parse\n"
        "   \n"
        "part: a.stl | density: 1.24  # trailing comment\n",
    )
    assert len(m.parts) == 1
    assert m.parts[0].density == 1.24
