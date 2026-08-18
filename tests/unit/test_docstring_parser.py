from open_fox.core.custom_tools.schema_builder import (
    parse_docstring_args,
    parse_docstring_summary,
)


def test_google_style():
    doc = """
    Summary line.

    Args:
        x: the x param
        y: the y param

    Returns:
        result
    """
    assert parse_docstring_summary(doc) == "Summary line."
    args = parse_docstring_args(doc)
    assert args["x"] == "the x param"
    assert args["y"] == "the y param"


def test_numpy_style():
    doc = """
    Summary.

    Parameters
    ----------
    x : str
        the x param
    y : int
        the y param
    """
    args = parse_docstring_args(doc)
    assert args["x"] == "the x param"


def test_sphinx_style():
    doc = """
    Summary.

    :param x: the x param
    :param y: the y param
    """
    args = parse_docstring_args(doc)
    assert args["x"] == "the x param"


def test_empty_doc_returns_empty():
    assert parse_docstring_summary(None) == ""
    assert parse_docstring_args(None) == {}
