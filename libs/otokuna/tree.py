"""
NOTE: This is an experimental module.
Its dependencies are not included in the package.
aaa
"""

import numpy as np
from sklearn.tree import DecisionTreeRegressor


class DecisionTreeRegressorWithQuantiles(DecisionTreeRegressor):
    """Decision Tree Regressor that estimates (roughly) quantiles.

    It estimates the quantiles from the training samples that fall within
    each of the learned hyper-rectangles.

    Note that the tree does not directly optimize a quantile loss, and thus the
    training task is used as a proxy to partition the space in hyper-rectangles
    where hopefully the partitioned samples can be used to calculate non-parametric
    estimates of the quantile from the given features.

    Parameters
    ----------
    quantiles : float or array-like
        Quantile or sequence of quantiles to compute, which must be between
        0 and 1 inclusive.

    Other parameters are the same as DecisionTreeRegressor.

    Attributes
    ----------
    quantiles_by_leaf_ : dict[int, list[float]]
        The quantiles at each leaf node of the learned tree.

    Other attributes are the same as DecisionTreeRegressor.
    """

    def __init__(
            self, *, quantiles,
            criterion="mse", splitter="best", max_depth=None,
            min_samples_split=2, min_samples_leaf=1, min_weight_fraction_leaf=0.,
            max_features=None, random_state=None, max_leaf_nodes=None,
            min_impurity_decrease=0., min_impurity_split=None, ccp_alpha=0.0
    ):
        super().__init__(
            criterion=criterion, splitter=splitter, max_depth=max_depth,
            min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf, min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features, random_state=random_state, max_leaf_nodes=max_leaf_nodes,
            min_impurity_decrease=min_impurity_decrease, min_impurity_split=min_impurity_split, ccp_alpha=ccp_alpha)
        self.quantiles = quantiles

    def fit(self, X, y, sample_weight=None, check_input=True, X_idx_sorted="deprecated"):
        """Refer to `DecisionTreeRegressor.fit`"""
        super().fit(X, y, sample_weight, check_input, X_idx_sorted)
        try:
            quantiles = list(self.quantiles)
        except TypeError:
            quantiles = list([self.quantiles])

        leaf_idx_pred = self.apply(X)
        leaf_idxs, *_ = np.where(self.tree_.children_left == -1)

        # Sanity check
        assert np.all(np.sort(leaf_idxs) == np.unique(leaf_idx_pred))

        self.quantiles_by_leaf_idx_ = {}
        for leaf in leaf_idxs:
            self.quantiles_by_leaf_idx_[leaf] = list(np.quantile(y[leaf_idx_pred == leaf], quantiles))
        return self

    def predict_quantile(self, X, check_input=True):
        """Predict quantile values for X.

        For each sample in X it returns the (precomputed) quantile. The quantiles
        are estimated from the training samples that fall in the same leaf as the
        given sample.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The input samples. Internally, it will be converted to
            ``dtype=np.float32`` and if a sparse matrix is provided
            to a sparse ``csr_matrix``.

        check_input : bool, default=True
            Allow to bypass several input checking.
            Don't use this parameter unless you know what you do.

        Returns
        -------
        y : array-like of shape (n_samples, n_quantiles)
            The predicted quantiles.
        """
        leaf_idx_pred = self.apply(X, check_input)
        return np.stack([np.asarray(self.quantiles_by_leaf_idx_[li]) for li in leaf_idx_pred])
