from importlib.metadata import version


def test_scholarly_uses_compatible_bibtexparser_major_version():
    assert version("bibtexparser").split(".", 1)[0] == "1"
