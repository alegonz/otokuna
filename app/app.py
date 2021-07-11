#!/usr/bin/env python3
import datetime
import io
import json
import os
import re
import secrets
import uuid
from typing import Dict, List
from dataclasses import dataclass
from pathlib import Path

import boto3
import dtale.global_state
import pandas as pd
import yaml
from dtale.app import build_app
from dtale.views import startup
from flask import abort, flash, render_template, redirect, request, url_for, send_from_directory
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired

from state import AppRedis


@dataclass
class JobInfo:
    job_id: str
    user_id: str
    timestamp: float
    search_url: str
    search_conditions: str
    raw_data_key: str
    scraped_data_key: str
    prediction_data_key: str

    _JST = datetime.timezone(datetime.timedelta(seconds=32400), 'JST')

    @classmethod
    def json_loads(cls, bytes_or_str):
        return cls(**json.loads(bytes_or_str))

    @property
    def datetime_jst_formatted(self):
        d = datetime.datetime.fromtimestamp(self.timestamp, tz=self._JST)
        return d.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Config:
    """Parameters from configuration file"""
    # Flask app
    secret_key: str
    users: List[Dict[str, str]]
    dtale_state_dir: str
    app_db_file: str
    bucket_name: str
    sfn_region_name: str
    sfn_arn: str
    scraped_data_key_prefix: str
    scraped_data_key_template: str
    predictions_key_prefix: str
    prediction_key_template: str
    prediction_key_pattern: str

    @classmethod
    def load_from_yaml(cls, filename=None):
        filename = filename or os.getenv("OTOKUNA_CONFIG_FILE") or "/etc/otokuna-web-server/config/config.yml"
        with open(filename) as file:
            config_dict = yaml.safe_load(file)
        return cls(**config_dict)


CONFIG = Config.load_from_yaml()
BASE_PATH = Path(__file__).parent
TEMPLATES_PATH = BASE_PATH / "templates"
BUCKET = boto3.resource("s3").Bucket(CONFIG.bucket_name)
ISO_DATETIMES_KEY = "iso_datetimes"
DATAFRAMES_KEY = "dataframes"
JOB_INFO_KEYS_KEY = "job_info_keys"
JOB_INFO_KEY = "job_info"

app = build_app(reaper_on=False, additional_templates=TEMPLATES_PATH)

# Set up redis data stores
# There are two instances of redis:
# The first is internal to Dtale and the second is an extra instance
# we provision to handle additional app state. We don't reuse the Dtale
# internal instance because it has modifications specific to Dtale
# internals which make it difficult for general usage.
os.makedirs(CONFIG.dtale_state_dir, exist_ok=True)
dtale.global_state.use_redis_store(CONFIG.dtale_state_dir)
REDIS_DB = AppRedis(CONFIG.app_db_file)

app.secret_key = CONFIG.secret_key
login_manager = LoginManager()
login_manager.init_app(app)


class CustomRequestForm(FlaskForm):
    # TODO: "begins with" validator to constrain to suumo URLs
    #   e.g. begins with 'https://suumo.jp/jj/chintai/ichiran/FR301FC001/'
    search_url = StringField("Search URL", validators=[InputRequired()])


class LoginForm(FlaskForm):
    user_id = StringField("User ID", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    remember_me = BooleanField("Remember me")


@dataclass
class User(UserMixin):
    id: str
    password_hash: str
    alternative_id: str

    def get_id(self):
        return self.alternative_id


def generate_users(config: Config):
    """
    We use the user id to authenticate the login, but from there on
    we use an alternative id that it is re-generated everytime the app
    is restarted. Thus the user sessions will be invalidated everytime
    the app is restarted. This is a rough way to invalidate sessions
    when we change the password (because we restart the app to do so).
    """
    users_by_id = {}
    users_by_alternative_id = {}
    for user_data in config.users:
        alternative_id = secrets.token_hex()
        user = User(user_data["user_id"], user_data["password_hash"], alternative_id)
        users_by_id[user.id] = user
        users_by_alternative_id[user.alternative_id] = user
    return users_by_id, users_by_alternative_id


USERS_BY_ID, USERS_BY_ALTERNATIVE_ID = generate_users(CONFIG)


def download_dataframe(key):
    with io.BytesIO() as stream:
        BUCKET.download_fileobj(Key=key, Fileobj=stream)
        stream.seek(0)
        df = pd.read_pickle(stream)
    return df


def join_dataframes(scraped_df, prediction_df):
    # Add score column
    prediction_df = prediction_df.assign(otokuna_score=lambda df_: df_.y_pred / df_.y)
    # Join data
    df = prediction_df.join(scraped_df)
    df.sort_values(by="otokuna_score", ascending=False, inplace=True)
    # Rename columns to more readable names
    df.rename(
        inplace=True,
        columns={"y": "monthly_cost", "y_pred": "monthly_cost_predicted"}
    )
    return df


# TODO: Retire this method once that daily jobs are
#   handled the same way as user requested jobs
def load_data_daily(date):
    if not REDIS_DB.hexists(ISO_DATETIMES_KEY, date):
        abort(404)
    if REDIS_DB.hexists(DATAFRAMES_KEY, date):
        return REDIS_DB.hget(DATAFRAMES_KEY, date)
    # Get scraped data
    iso_datetime = REDIS_DB.hget(ISO_DATETIMES_KEY, date)
    key = os.path.join(CONFIG.scraped_data_key_prefix, CONFIG.scraped_data_key_template).format(iso_datetime)
    scraped_df = download_dataframe(key)
    # Get prediction data
    key = os.path.join(CONFIG.predictions_key_prefix, CONFIG.prediction_key_template).format(iso_datetime)
    prediction_df = download_dataframe(key.format(iso_datetime))
    df = join_dataframes(scraped_df, prediction_df)
    REDIS_DB.hset(DATAFRAMES_KEY, date, df)
    return df


def load_data(job_id):
    if REDIS_DB.hexists(DATAFRAMES_KEY, job_id):
        return REDIS_DB.hget(DATAFRAMES_KEY, job_id)
    job_info = REDIS_DB.hget(JOB_INFO_KEY, job_id)
    scraped_df = download_dataframe(job_info.scraped_data_key)
    prediction_df = download_dataframe(job_info.prediction_data_key)
    df = join_dataframes(scraped_df, prediction_df)
    REDIS_DB.hset(DATAFRAMES_KEY, job_id, df)
    return df


def iso2date(iso: str) -> str:
    # e.g. 2021-02-11T12:00:15+00:00 -> 2021-02-11
    return datetime.datetime.fromisoformat(iso).strftime("%Y-%m-%d")


def date2dataid(date: str) -> int:
    # e.g. 2021-02-08 --> 1612710000
    datetime_ = datetime.datetime.combine(datetime.date.fromisoformat(date), datetime.time())
    data_id = int(datetime_.timestamp())
    return data_id


def iso2dataid(iso: str) -> int:
    return date2dataid(iso2date(iso))


@login_manager.user_loader
def load_user_by_alternative_id(user_alternative_id):
    return USERS_BY_ALTERNATIVE_ID.get(user_alternative_id)


def load_user_by_id(user_id):
    return USERS_BY_ID.get(user_id)


def public_endpoint(function):
    function.is_public = True
    return function


@app.route("/login", methods=("GET", "POST"))
@public_endpoint
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = load_user_by_id(form.user_id.data)
        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash("Please check your login details and try again.")
            return redirect(url_for("login"))

        login_user(user, remember=form.remember_me.data)
        return redirect(url_for("index"))

    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You just logged out.")
    return redirect(url_for("login"))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for("login"))


@app.before_request
def check_valid_login():
    # From https://stackoverflow.com/a/52572337
    if (
        request.endpoint is None  # e.g. from "Refresh list" button
        or request.endpoint.startswith('static/')
        or current_user.is_authenticated
        or getattr(app.view_functions[request.endpoint], "is_public", False)
    ):
        return  # Access granted
    return render_template("login.html", form=LoginForm())


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/daily", methods=("GET", "POST"))
@login_required
def index_daily():
    prediction_objects = BUCKET.objects.iterator(Prefix=CONFIG.predictions_key_prefix)
    pattern = os.path.join(CONFIG.predictions_key_prefix, CONFIG.prediction_key_pattern)
    prediction_iso_datetimes = sorted(re.match(pattern, obj.key).group(1)
                                      for obj in prediction_objects)
    prediction_dates = []
    for iso in prediction_iso_datetimes:
        date = iso2date(iso)
        # NOTE: we assume there is exactly one datetime for each date.
        # If two or more datetimes for the same date the latest will be kept.
        REDIS_DB.hset(ISO_DATETIMES_KEY, date, iso)
        prediction_dates.append(date)
    return render_template("index_daily.html", prediction_dates=prediction_dates)


# TODO: Retire this method once that daily jobs are
#   handled the same way as user requested jobs
@app.route("/daily/prediction/<date>")
def load_daily_prediction(date):
    df = load_data_daily(date)
    data_id = uuid.uuid4().int
    _ = startup(data_id=data_id,
                data=df,
                name=date,
                ignore_duplicate=True,
                allow_cell_edits=False,
                inplace=True)
    return redirect(url_for("dtale.view_iframe", data_id=data_id))


@app.route("/custom_request", methods=("GET", "POST"))
@login_required
def index_custom_request():
    # TODO: the job info should be in a DB an the app should query that DB
    for obj in BUCKET.objects.iterator(Prefix="jobs"):
        if not obj.key.endswith("job_info.json") or REDIS_DB.sismember(JOB_INFO_KEYS_KEY, obj.key):
            continue
        job_info = JobInfo.json_loads(obj.get()["Body"].read())
        REDIS_DB.sadd(JOB_INFO_KEYS_KEY, obj.key)
        REDIS_DB.hset(JOB_INFO_KEY, job_info.job_id, job_info)
    jobs = sorted(REDIS_DB.hvals(JOB_INFO_KEY), key=lambda job: (job.timestamp, job.user_id))
    return render_template("index_custom_request.html", jobs=jobs, form=CustomRequestForm())


@app.route("/prediction/<job_id>")
def load_prediction(job_id):
    job_info = REDIS_DB.hget(JOB_INFO_KEY, job_id)
    data_id = uuid.UUID(job_id).int
    _ = startup(data_id=data_id,
                data=load_data(job_id),
                name=job_info.search_conditions,
                ignore_duplicate=True,
                allow_cell_edits=False,
                inplace=True)
    return redirect(url_for("dtale.view_iframe", data_id=data_id))


@app.route("/custom_request/submit", methods=("POST",))
def submit_custom_request():
    form = CustomRequestForm()
    assert form.validate_on_submit()
    input_data = {
        "user_id": current_user.id,
        "search_url": form.search_url.data
    }
    boto3.client("stepfunctions", region_name=CONFIG.sfn_region_name).start_execution(
        stateMachineArn=CONFIG.sfn_arn,
        input=json.dumps(input_data),
    )
    return render_template("request_submitted.html")


# dtale already takes the default static path for its assets,
# so we define a new one for the this app's vendored assets.
@app.route('/static/vendor/<path:filename>')
def static_vendor(filename):
    return send_from_directory((BASE_PATH / "static" / "vendor").resolve(), secure_filename(filename))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, processes=4, threaded=False)
