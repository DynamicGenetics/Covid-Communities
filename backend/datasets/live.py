"""Handles live data from reading to master dataset generation.

This module reads, standardises and defines the master dataset for data sources
from the data/live folder.

Notes
-----
This module imports classes from the `dataset` module.
The `LA_LIVE` master dataset definition has `from_csv=False`. This means that the
live dataset master will always be regenerated from the source files given here,
rather than read from the existing master csv.

To add a new live datasource, follow the existing examples for a `SOURCE_` constant
that is read from file, passed to a `Dataset` definition, and then the Dataset
definition defined in the `LA_LIVE` datasets list to ensure it is included.

"""

import pandas as pd
import os
from functools import partial
import sqlite3

from datasets import LIVE_DATA_FOLDER, LIVE_RAW_DATA_FOLDER

from datasets.dataset import DataResolution, DataFrequency, Dataset, MasterDataset

p_live = partial(os.path.join, LIVE_DATA_FOLDER)
p_raw = partial(os.path.join, LIVE_RAW_DATA_FOLDER)

# Get, and do some tidying, of the PHW data
SOURCE_COVID_COUNT_LA = pd.read_excel(
    p_raw("Rapid-COVID-19-surveillance-data.xlsx"),
    sheet_name="Tests by specimen date",
    usecols="A, B, E",
)  # LA, date, cumulative cases per 100,000
SOURCE_COVID_COUNT_LA["Specimen date"] = pd.to_datetime(
    SOURCE_COVID_COUNT_LA["Specimen date"]
)
latest_date = SOURCE_COVID_COUNT_LA["Specimen date"].max()
# Filter data by the latest date
SOURCE_COVID_COUNT_LA = SOURCE_COVID_COUNT_LA[
    SOURCE_COVID_COUNT_LA["Specimen date"] == latest_date
]

SOURCE_VAX_PCT_LA = pd.read_excel(
    p_raw("COVID19-vaccination-downloadable-data-.xlsx"),
    sheet_name="HealthBoard_LocalAuthority",
    usecols="A, B, E, G",
    skiprows=1,
)
SOURCE_VAX_PCT_LA = SOURCE_VAX_PCT_LA[
    SOURCE_VAX_PCT_LA["Risk group"] == "Wales residents aged 18 years and older"
]

SOURCE_GROUP_COUNTS_LA = pd.read_csv(p_live("groupCount_LA.csv"))

SOURCE_WCVA_ONLINE_LA = pd.read_csv(p_live("la_wcva_2020-05-18.csv"), usecols=[0, 1, 2])

SOURCE_TWEETS_LA = pd.read_csv(p_live("community_tweets.csv"))

SOURCE_ZOE_SUPPORT_LA = pd.read_csv(p_live("help_need20200531.csv"), nrows=3).T
SOURCE_ZOE_SUPPORT_LA.reset_index(level=0, inplace=True)

# This query gets the average sentiment for the past seven days, linked to local authority areas.
# This is then queried from the twitter data collection database.
VADER_QUERY = """SELECT AVG(vader_comp_avg),lsoa,lsoa_name from
(
SELECT AVG(tweets.vader_comp) as vader_comp_avg, tweets.author_id, matchedplaces.lsoa, matchedplaces.lsoa_name
FROM tweets
JOIN places ON tweets.place_id = places.id
JOIN matchedplaces ON matchedplaces.place_id = places.id
WHERE strftime("%Y-%m-%d %H:%M:%S", tweets.created_at) > date('now','start of day','-7 days')
GROUP BY tweets.author_id,matchedplaces.lsoa
) as lastweek_tweets
GROUP BY lsoa;
"""

SOURCE_TWEET_SENTIMENT_LA = pd.read_sql(
    VADER_QUERY,
    con=sqlite3.connect(os.path.join(LIVE_RAW_DATA_FOLDER, "phw_tweets.db")),
)

# Labelling this as a pct, it's not really but ensures it doesn't get changed.
LA_VADER = Dataset(
    data=SOURCE_TWEET_SENTIMENT_LA,
    res=DataResolution.LA,
    key_col="lsoa",
    key_is_code=True,
    csv_name="vader_pct",
    rename={"AVG(vader_comp_avg)": "vader_comp", "lsoa": "lad19cd"},
    keep_cols=["lad19cd", "vader_comp"],
)

LA_COVID = Dataset(
    data=SOURCE_COVID_COUNT_LA,
    res=DataResolution.LA,
    key_col="Local Authority",
    key_is_code=False,
    csv_name="covid_count",
    rename={
        "Cumulative incidence per 100,000 population": "covidIncidence_100k",
        "Local Authority": "lad19nm",
    },
    keep_cols=["lad19nm", "covidIncidence_100k"],
)

LA_VAX_1 = Dataset(
    data=SOURCE_VAX_PCT_LA,
    res=DataResolution.LA,
    key_col="Area of residence",
    key_is_code=False,
    csv_name="vax1_pct",
    rename={"Area of residence": "lad19nm", "Uptake(%) - Dose1": "vax1_pct"},
    keep_cols=["lad19nm", "vax1_pct"],
)

LA_VAX_2 = Dataset(
    data=SOURCE_VAX_PCT_LA,
    res=DataResolution.LA,
    key_col="Area of residence",
    key_is_code=False,
    csv_name="vax2_pct",
    rename={"Area of residence": "lad19nm", "Uptake(%) - Dose2": "vax2_pct"},
    keep_cols=["lad19nm", "vax2_pct"],
)

LA_GROUP_COUNTS = Dataset(
    data=SOURCE_GROUP_COUNTS_LA,
    res=DataResolution.LA,
    key_col="area_code",
    key_is_code=True,
    rename={"groupCount": "groups_count"},
    csv_name="group_counts",
)

LA_WCVA = Dataset(
    data=SOURCE_WCVA_ONLINE_LA,
    res=DataResolution.LA,
    key_col="AREA",
    key_is_code=False,
    csv_name="wcva_count",
)

LA_TWEETS = Dataset(
    data=SOURCE_TWEETS_LA,
    res=DataResolution.LA,
    key_col="lad19cd",
    key_is_code=True,
    csv_name="tweets_percentage",
)

LA_ZOE_SUPPORT = Dataset(
    data=SOURCE_ZOE_SUPPORT_LA,
    res=DataResolution.LA,
    key_col="index",
    key_is_code=False,
    rename={2: "has_someone_close"},
    keep_cols=["lad19nm", "has_someone_close"],
    bracketed_data_cols=["has_someone_close"],
    csv_name="zoe_support",
)

LA_LIVE = MasterDataset(
    datasets=[
        LA_COVID,
        LA_GROUP_COUNTS,
        LA_WCVA,
        LA_TWEETS,
        LA_ZOE_SUPPORT,
        LA_VAX_1,
        LA_VAX_2,
        LA_VADER,
    ],
    res=DataResolution.LA,
    freq=DataFrequency.LIVE,
    from_csv=False,
)
