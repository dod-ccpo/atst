from operator import itemgetter
from typing import List


def sort_nested(lst: List[list]):
    """
    This method is for sorting a list of lists. This as it is will only work with one depth or rather a matrix
    The contents must be a list of a list
    """

    # First sort the content of the array first
    lst.sort(key=itemgetter(0))
    for item in lst:
        # Sort the list of items
        item.sort()

    return lst
