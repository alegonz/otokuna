from setuptools import setup, find_packages

PACKAGE_NAME = "otokuna"
DESCRIPTION = "Library for scraping and analyzing rental real estate data from Suumo"
PROJECT_URL = "https://github.com/alegonz/otokuna"
AUTHOR = "Alejandro González Tineo"
AUTHOR_EMAIL = "alejandrojgt@gmail.com"
PYTHON_REQUIRES = ">=3.5"
# TODO: Split package into a namespace package with at least 3 packages:
#  commons, dumper, scraper
#  This will allow to package only the necessary dependency for each app service
INSTALL_REQUIRES = [
    "attrs",
    "beautifulsoup4",
    "joblib",
    "kanjize",
    "pandas",
    "requests"
]
EXTRAS_REQUIRE = {"dev": ["pytest"]}
ENTRY_POINTS = {
    "console_scripts": [
        "dump-properties=otokuna.dumping:_main",
        "scrape-properties=otokuna.scraping:scrape_properties",
    ]
}
LICENSE = "MIT"
CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: MIT License"
]

# Execute _version.py to get __version__ variable in context
exec(open("otokuna/_version.py", encoding="utf-8").read())

setup(
    name=PACKAGE_NAME,
    version=__version__,
    description=DESCRIPTION,
    url=PROJECT_URL,
    license=LICENSE,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    python_requires=PYTHON_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points=ENTRY_POINTS,
    include_package_data=True,
    classifiers=CLASSIFIERS,
    packages=find_packages(exclude=["tests"]),
)
