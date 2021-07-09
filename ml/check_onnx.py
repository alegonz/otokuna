#!/usr/bin/env python3
"""Check that predictions are similar between the native format and ONNX"""
import argparse
import json

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from onnxruntime import InferenceSession

from otokuna.analysis import (
    add_address_coords, add_target_variable, df2Xy
)


def main(args):
    # Read and preprocess data
    df = pd.read_pickle(args.data_filename)
    df = df.sample(frac=0.1, random_state=123)
    df = add_address_coords(df)
    df.dropna(inplace=True)
    df = add_target_variable(df)
    X, y = df2Xy(df)

    # Check
    model = CatBoostRegressor()
    model.load_model(args.model_cbm_filename)
    y_pred_cbm = model.predict(X)

    sess = InferenceSession(args.model_onnx_filename)
    onnx_out = sess.run(["predictions"], {"features": X.values.astype(np.float32)})
    y_pred_onnx = onnx_out[0].squeeze()

    np.testing.assert_allclose(y_pred_onnx, y_pred_cbm, rtol=1e-5)
    max_ape = np.max(np.abs((y_pred_cbm - y_pred_onnx) / y_pred_cbm))
    with open(args.out_filename, "w") as file:
        json.dump({"maxAPE_cbm_onnx": max_ape}, file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check onnx model produces an output close "
                                                 "to that of its version in cbm format")
    parser.add_argument("data_filename", help="Input data filename (pickle format)")
    parser.add_argument("model_onnx_filename", help="Model filename in onnx format")
    parser.add_argument("model_cbm_filename", help="Model filename in cbm format")
    parser.add_argument("--out-filename", default="check_onnx.json", help="Output filename")
    main(parser.parse_args())
