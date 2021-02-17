from atat.routes.dev import _DEV_USERS


def test_users():
    """
    Validates users in _DEV_USERS
    """
    names = [user["first_name"] for user in _DEV_USERS.values()]
    for user in _DEV_USERS.values():
        assert user["citizenship"] == "United States"
        assert user["first_name"] in names
