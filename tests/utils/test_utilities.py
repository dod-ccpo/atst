from atat.utils.utilities import sort_nested


def test_sort_nested_with_2d_matrix():
    validate_sorting([["a", "c"], ["r", "e"]], [["a", "c"], ["e", "r"]])


def test_three_level_depth():
    nested_arr = [
        [["c", "a", "b"], ["x", "v", "u"], ["i", "p", "l"]],
        [["b", "m", "k"]],
        [["q", "w", "e"], ["f", "d", "s"]],
    ]
    sorted_arr = [
        [["b", "k", "m"]],
        [["a", "b", "c"], ["i", "l", "p"], ["u", "v", "x"]],
        [["d", "f", "s"], ["e", "q", "w"]],
    ]

    validate_sorting(nested_arr, sorted_arr)


def validate_sorting(arr_to_be_sorted, valid_sorted_arr):
    sort_nested(arr_to_be_sorted)
    assert arr_to_be_sorted == valid_sorted_arr
