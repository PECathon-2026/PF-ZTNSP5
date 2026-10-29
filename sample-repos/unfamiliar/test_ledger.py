import pytest

from ledger import debit


def test_negative_amount():
    with pytest.raises(ValueError):
        debit(10, -2)


def test_nonnegative_amounts():
    assert debit(10, 2) == 8
    assert debit(10, 0) == 10
