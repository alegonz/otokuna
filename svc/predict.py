import io
import os
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from onnxruntime import InferenceSession

from otokuna.analysis import add_address_coords, add_target_variable, df2Xy
from otokuna.logging import setup_logger


def main(event, context):
    """Makes predictions from scraped data and stores the results in the bucket."""
    logger = setup_logger("predict", include_timestamp=False, propagate=False)

    output_bucket = os.environ["OUTPUT_BUCKET"]
    root_key = event["root_key"]
    scraped_data_key = event["scraped_data_key"]
    prediction_data_key = str(Path(root_key) / "prediction.pickle")
    model_filename = os.environ["MODEL_PATH"]

    s3_client = boto3.client("s3")
    # Get pickle from bucket and read dataframe from it
    logger.info(f"Getting scraped data from: {scraped_data_key}")
    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=scraped_data_key, Fileobj=stream)
        stream.seek(0)
        df = pd.read_pickle(stream)

    # Preprocess dataframe
    logger.info(f"Preprocessing dataframe")
    df = add_address_coords(df)
    df = add_target_variable(df)
    X, y = df2Xy(df.dropna())

    # Predict
    logger.info(f"Predicting")
    sess = InferenceSession(model_filename)
    onnx_out = sess.run(["predictions"], {"features": X.values.astype(np.float32)})
    y_pred = pd.Series(onnx_out[0].squeeze(), index=y.index).rename("y_pred")
    # Make dataframe with predictions and target from df **prior** to dropna
    prediction_df = df[["y"]].join(y_pred, how="left")

    # Upload result to bucket
    logger.info(f"Uploading results to: {prediction_data_key}")
    with io.BytesIO() as stream:
        prediction_df.to_pickle(stream, compression=None, protocol=5)
        stream.seek(0)
        s3_client.upload_fileobj(Fileobj=stream, Bucket=output_bucket, Key=prediction_data_key)

    event["prediction_data_key"] = prediction_data_key
    return event
