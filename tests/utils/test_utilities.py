from atat.utils.utilities import sort_nested


def test_sort_nested():
    nested_arr = [["a", "c"], ["r", "e"]]
    sorted_nested_arr = sort_nested(nested_arr)
    assert sorted_nested_arr == [["a", "c"], ["e", "r"]]
