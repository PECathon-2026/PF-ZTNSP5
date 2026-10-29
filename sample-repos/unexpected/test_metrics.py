from metrics import average


def test_average():
    assert average([2, 4]) == 3


def test_empty():
    assert average([]) == 0
