from typing import List
from operator import itemgetter


def sort_nested(lst: List[list]):
    """
    This method is for sorting a list of lists. This as it is will only work with one depth or rather a matrix
    The contents must be a list of a list
    """

    # First sort the content of the array first
    lst.sort(key=itemgetter(0))
    for item in lst:
        if isinstance(item, list):
            # If they are a list, then sort it
            item.sort()

    return lst
