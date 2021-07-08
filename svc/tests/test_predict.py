import io
import os
from pathlib import Path

import boto3
import pandas as pd
from moto import mock_s3

import predict

DATA_DIR = Path(__file__).parent / "data"


@mock_s3
def test_main(set_environ):
    output_bucket = os.environ["OUTPUT_BUCKET"]
    root_key = "predictions/daily/2021-01-25T14:59:25+00:00"
    scraped_data_key = "dumped_data/daily/2021-01-25T14:59:25+00:00/東京都.pickle"
    model_filename = "../ml/models/regressor.onnx"
    os.environ["MODEL_PATH"] = model_filename

    expected_prediction_data_key = f"{root_key}/prediction.pickle"

    # Upload pickle file with scraped property data
    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=output_bucket)
    s3_client.upload_file(Bucket=output_bucket, Key=scraped_data_key, Filename=str(DATA_DIR / "scraped_data.pickle"))

    # run main (downloads scraped data, predicts, and uploads results pickle)
    event = {
        "root_key": root_key,
        "scraped_data_key": scraped_data_key,
        "model_filename": model_filename
    }
    event_out = predict.main(event, None)
    assert event_out is event
    assert event_out["prediction_data_key"] == expected_prediction_data_key

    # Download predicted data pickle
    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=expected_prediction_data_key, Fileobj=stream)
        stream.seek(0)
        prediction_df = pd.read_pickle(stream)

    assert tuple(prediction_df.columns) == ("y", "y_pred")
    scraped_df = pd.read_pickle(DATA_DIR / "scraped_data.pickle")
    pd.testing.assert_index_equal(prediction_df.index, scraped_df.index)
