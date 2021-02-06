#!/usr/bin/env python3
"""Check that predictions are similar between the native format and ONNX"""
import json

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from onnxruntime import InferenceSession

from otokuna.analysis import (
    add_address_coords, add_target_variable, df2Xy
)

# Read and preprocess data
df = pd.read_pickle("data/2021-01-16T20:40:36+09:00/東京都.pickle")
df = df.sample(frac=0.1, random_state=123)
df = add_address_coords(df)
df.dropna(inplace=True)
df = add_target_variable(df)
X, y = df2Xy(df)

# Check
model = CatBoostRegressor()
model.load_model("models/regressor.cbm")
y_pred_cbm = model.predict(X)

sess = InferenceSession("models/regressor.onnx")
onnx_out = sess.run(["predictions"], {"features": X.values.astype(np.float32)})
y_pred_onnx = onnx_out[0].squeeze()

np.testing.assert_allclose(y_pred_onnx, y_pred_cbm, rtol=1e-5)
max_ape = np.max(np.abs((y_pred_cbm - y_pred_onnx) / y_pred_cbm))
with open("check_onnx.json", "w") as file:
    json.dump({"maxAPE_cbm_onnx": max_ape}, file)
