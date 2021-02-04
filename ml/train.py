#!/usr/bin/env python3
"""
Train regression model to predict median average price of properties.
TODO: Move parameters to a params.yaml file.
"""

import pandas as pd
from catboost import CatBoostRegressor

from otokuna.analysis import (
    add_address_coords, add_target_variable, clean_df,
    train_val_test_split, df2Xy
)

# Read and preprocess data
df = pd.read_pickle("data/2021-01-16T20:40:36+09:00/東京都.pickle")
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

model.save_model("models/regressor.cbm", format="cbm")
model.save_model("models/regressor.onnx", format="onnx")
