import numpy as np
import pytest

from otokuna.tree import DecisionTreeRegressorWithQuantiles


@pytest.fixture
def dummy_data():
    """Dummy data that is perfectly separable at x=0 by a binary tree of depth 1"""
    X = np.concatenate([-np.ones(101), np.ones(101)]).reshape(-1, 1)
    y = np.concatenate([np.arange(0, 101), np.arange(1000, 1101)])
    yield X, y


class TestDecisionTreeRegressorWithQuantiles:
    def test_fit(self, dummy_data):
        X, y = dummy_data
        expected = {1: [25, 50], 2: [1025, 1050]}
        model = DecisionTreeRegressorWithQuantiles(max_depth=1, random_state=123, quantiles=[0.25, 0.50])
        model.fit(X, y)
        assert model.quantiles_by_leaf_idx_ == expected

    def test_predict_quantile(self, dummy_data):
        X, y = dummy_data
        model = DecisionTreeRegressorWithQuantiles(max_depth=1, random_state=123, quantiles=[0.25, 0.50])
        model.fit(X, y)
        expected = np.column_stack([
            np.concatenate([25 * np.ones(101), 1025 * np.ones(101)]),
            np.concatenate([50 * np.ones(101), 1050 * np.ones(101)]),
        ])
        np.testing.assert_equal(model.predict_quantile(X), expected)
