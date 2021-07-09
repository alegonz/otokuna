#!/usr/bin/env python3
"""
Train regression model to predict median average price of properties.
TODO: Move parameters to a params.yaml file.
"""
import argparse
import json
from collections import defaultdict

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from otokuna.analysis import (
    add_address_coords, add_target_variable, clean_df,
    train_val_test_split, df2Xy
)


def mae(y_true, y_pred):
    """Mean absolute error"""
    assert y_true.shape == y_pred.shape, f"{y_true.shape} != {y_pred.shape}"
    return np.mean(np.abs(y_true - y_pred), axis=0)


def main(args):
    # Read and preprocess data
    df = pd.read_pickle(args.data_filename)
    df = add_address_coords(df)
    df = add_target_variable(df)
    df = clean_df(df)

    # Split datasets
    (df_train, df_val, df_test), *_ = train_val_test_split(
        [df], val_ratio=0.1875, test_ratio=0.25, seed=123
    )
    X_train, y_train = df2Xy(df_train)
    X_val, y_val = df2Xy(df_val)
    X_test, y_test = df2Xy(df_test)

    # Train model
    model = CatBoostRegressor(
        learning_rate=1e-2,
        iterations=10000,
        loss_function="MAE",
        random_seed=456
    )

    _ = model.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        use_best_model=True,
        early_stopping_rounds=10
    )

    # Evaluate model
    datasets = {"train": (X_train, y_train), "val": (X_val, y_val), "test": (X_test, y_test)}
    metrics = defaultdict(dict)
    for set_name, (X, y) in datasets.items():
        y_pred = model.predict(X)
        metrics[set_name]["MAE"] = mae(y, y_pred)

    with open(args.metrics_filename, "w") as file:
        json.dump(metrics, file)

    # Save model
    # We drop the model_guid and train_finish_time metadata to ensure that the
    # produced files are reproducible and result in the same hash always, which
    # is necessary to ensure correct tracking with DVC.
    for key in ("model_guid", "train_finish_time"):
        del model.get_metadata()[key]
    for format_ in ("cbm", "onnx"):
        model.save_model(f"{args.model_filename}.{format_}", format=format_)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train model")
    parser.add_argument("data_filename", help="Input data filename (pickle format)")
    parser.add_argument("model_filename", help="Output model filename (extension will be added automatically)")
    parser.add_argument("--metrics-filename", default="metrics.json", help="Output metrics filename")
    main(parser.parse_args())
