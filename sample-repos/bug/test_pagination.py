from pagination import page


def test_full_pages():
    assert page([1, 2, 3, 4, 5], 0, 2) == [1, 2]
    assert page([1, 2, 3, 4, 5], 1, 2) == [3, 4]
    assert page([1, 2, 3, 4, 5], 2, 2) == [5]
