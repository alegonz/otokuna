from setuptools import setup

setup(
    name="otokuna_dump_svc",
    description="Minimal package to make service modules importable in tests.",
    py_modules=[
        "build_search_url",
        "generate_base_path",
        "dump_property_data",
        "zip_property_data",
        "scrape_property_data",
        "predict",
        "save_job_info"
    ]
)
