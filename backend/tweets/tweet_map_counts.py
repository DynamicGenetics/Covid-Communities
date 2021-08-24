"""Function for generating user_counts data"""
import pandas as pd
import numpy as np
import os
from pipelines import TwitterPipeline
from datasets import load_tweets, load_annotated_tweets


# Create the full dataset of annotated tweets and get +ve ones
def generate_map_counts():
    """Writes out percentage of positive user tweets to file"""
    # Now load the full tweet dataset and find unique users per LA
    tweets = load_tweets()
    tweets = TwitterPipeline().apply(tweets.data, verbosity=2)
    annotations = load_annotated_tweets()

    tweets_annotated = pd.merge(annotations, tweets, on="id_str", how="left")
    tweets_yes = tweets_annotated[tweets_annotated["support_ND"] == "1"]
    tweets_yes = tweets_yes[["user.id_str", "lad19cd"]]

    # Get only unique users and create a table of counts by LA
    unique = tweets_yes.drop_duplicates(subset=["user.id_str", "lad19cd"])
    table = pd.pivot_table(
        unique, values="user.id_str", index="lad19cd", aggfunc=np.count_nonzero
    )

    tweets = tweets[["user.id_str", "lad19cd"]]
    unique_all = tweets.drop_duplicates(subset=["user.id_str", "lad19cd"])
    table_all = pd.pivot_table(
        unique_all, values="user.id_str", index="lad19cd", aggfunc=np.count_nonzero
    )

    # Now merge the two counts and create the overall percentage
    user_counts = pd.merge(table, table_all, on="lad19cd")
    user_counts["tweets_percent"] = (
        user_counts["user.id_str_x"] / user_counts["user.id_str_y"]
    ) * 100
    user_counts = user_counts[["tweets_percent"]]
    user_counts.to_csv(
        os.path.join(
            "..", "datasets", "data", "live", "cleaned", "community_tweets.csv"
        )
    )
    return user_counts
