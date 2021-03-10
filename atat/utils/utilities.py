def sort_nested(lst):
    """
    This method is for sorting a list of lists. As of now, this will work as long as
    the inner lists are the same depth and all of the typings are the same.
    The contents must be a list of a list

    sort_nested(["a, "b", c"]) -> Valid
    sort_nested([["a", "b", "c"], ["d", "e", "f"]]) -> Valid
    sort_nested( [
        [["c", "a", "b"], ["x", "v", "u"], ["i", "p", "l"]],
        [["b", "m", "k"]],
        [["q", "w", "e"], ["f", "d", "s"]],
    ]) -> Valid
    sort_nested([["a"], "b"]) -> Invalid
    sort_nested([["a", "b", "c"], [["a"], ["b", "c"]]) -> Invalid
    """

    # First sort the content of the array first

    for item in lst:
        # Sort the list of items
        if isinstance(item, list):
            sort_nested(item)

    lst.sort()
