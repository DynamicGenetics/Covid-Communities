"""Module containing class for creating custom transformation pipelines, a series of
functions used for transforming Twitter data, and a Twitter transformation pipeline."""

import pandas as pd
import numpy as np
import json
from typing import Tuple, Callable, List
from typing import Sequence, Union
from abc import ABC, abstractmethod
from functools import partial
from shapely.geometry import Polygon, Point
from datetime import datetime

# -------------------------------
# Type Hints (Custom Definitions)
# -------------------------------
# Pipeline
Pipe = Tuple[str, Callable[[pd.DataFrame], pd.DataFrame]]

# Types for (Geo) functions
Lat = float
Long = float
BoundingBox = Sequence[Tuple[Long, Lat]]
MatchingLA = Union[Tuple[str, str, str], pd.DataFrame]
# -------------------------------


class Pipeline(ABC):
    """ABC implementing the general template of a
    Dynamic Pipeline to process the Twitter dataset.

    The pipeline is composed by a sequence of
    (name, function) pairs.
    Valid (Pipe) functions must comply to the following signature:
        Callable[[pd.DataFrame], pd.DataFrame]
    Therefore, only one parameter is expected, i.e. the dataset
    in the form of a pandas.DataFrame, and a DataFrame is returned
    (to be fed as input for the next step).

    (Concrete) pipeline definitions are obtained via subclassing:
    steps are hard-coded so to have pre-defined and controllable
    behaviours. However, it is always possible to register
    extra steps into a pipeline via the `register` method.
    """

    def __init__(self):
        self._steps = self.create_pipeline()

    @abstractmethod
    def create_pipeline(self) -> List[Pipe]:
        pass

    def register(self, op: Pipe):
        self._steps.append(op)

    def apply(self, data: pd.DataFrame, verbosity: int = 0) -> pd.DataFrame:
        """Executes the pipeline on input data

        Parameters
        ----------
        data : pd.DataFrame
            Input data to initialise the pipeline
        verbosity : int, optional
            Controls the verbosity of the execution of the pipeline,
            by default 0 (no verbosity)

        Returns
        -------
        pd.DataFrame
            New copy of the data after the execution of all the steps
            of the pipeline.
        """
        data_df = data.copy()
        for name, step in self._steps:
            if verbosity:
                print(f"{name}...", end="")
            # Timing
            start = datetime.now()
            data_df = step(data_df)
            end = datetime.now()

            if verbosity:
                if verbosity > 1:
                    print(f"..completed in {(end-start)}")
                else:
                    print("..complete.")
        return data_df


# ---------------------------------
# Pipeline Step (utility) Functions
# ---------------------------------


def _get_welsh_tweets(data: pd.DataFrame, col: str = "place.full_name"):
    """Filters dataframe to only include tweets from Wales,
    by querying on column with place.full_name ('col')."""
    # Filter out non-Wales tweets
    data = data[data[col].str.contains("Wales", regex=False, na=False)]
    # filter out tweets referencing the whole Wales
    # removed as we cannot match any of those to any LA later on.
    return data[~data[col].str.contains("Wales, ")]


def _create_datetime_index(data: pd.DataFrame) -> pd.DataFrame:
    """Using the 'created_at' column from a Twitter export,
    makes this the index column in a pandas datetime format."""

    # Parse 'created at' to pandas datetime - requires 'from datetime import datetime'
    data["created_at"] = pd.to_datetime(data["created_at"])
    # Set the datetime of tweet creation as the dataframe index
    data.set_index("created_at", inplace=True)
    return data


def _tidy_text_cols(
    data: pd.DataFrame, col: str = "extended_tweet.full_text"
) -> pd.DataFrame:
    """Uses values from the short ('text') and extended
    ('extended_tweet.full_text') columns to make a
    single 'text' column with the full version of every tweet."""

    # Keep the data for where 'tweet_full' is not used
    keep = pd.isnull(data[col])
    # Where tweet_full is used, make tweet_full as the text
    data_valid = data[~keep]
    data.loc[~keep, "text"] = data_valid[col]
    # Drop the (extra) text column
    data.drop(col, axis=1, inplace=True)
    return data


def _bbox_geojson(data: pd.DataFrame, col: str = "place.bounding_box.coordinates"):
    """This function will reformat the bounding boxes from strings to lists of lists,
    and will append the first coordinate as the last one to allow for
    geojson conversion."""

    # Convert the lists from strings to json
    data[col] = data[col].apply(lambda x: json.loads(x))

    # Append the first list to the end of the LoL so
    # the coords make a connected shape
    def append_coords(bbox):
        bbox[0].append(bbox[0][0])
        return bbox

    data["bbox_geojson"] = data[col].apply(lambda x: append_coords(x))
    return data


def _bbox_tuple(data: pd.DataFrame) -> pd.DataFrame:
    """Creates a new column in the data with BoundingBoxes encoded as
    tuples of floats (with no repetition). This column is meant
    to ease the processing to match closest local authority.
    """
    data["bbox"] = data["place.bounding_box.coordinates"].apply(
        lambda c: tuple(map(tuple, c[0][:-1]))
    )
    return data


def convert_coordinates(data, col="geo.coordinates"):
    """Takes a Pandas dataframe with a column geo.coordinates (col)
    and adds the lat and long to their own columns
    for easy conversion to geojson."""

    def convert_coords(geo_coords):
        if not geo_coords:
            return np.nan, np.nan
        coords = tuple(map(float, geo_coords[1:-1].split(",")))
        return coords

    def set_geo_coords(geo_coords):
        coords = convert_coords(geo_coords)
        if np.isnan(coords[0]):
            return None
        return coords[::-1]

    # Substitute the nan with empty strings
    data[col].fillna("", inplace=True)

    data["lat"] = data[col].apply(lambda c: convert_coords(c)[0])
    data["long"] = data[col].apply(lambda c: convert_coords(c)[1])
    data["geo_coords"] = data[col].apply(lambda c: set_geo_coords(c))

    return data


# %%
def match_local_authorities(
    bbox: BoundingBox, la_df: pd.DataFrame, return_all: bool = False
) -> MatchingLA:
    """Get the Intersection Over Union for the the Local Authorities that
    overlap with the bounding box. Requires 'geometry' col in LA geopandas df.
    Returns df of local authorities of interest.

    Parameters
    ----------
    bbox: BoundingBox
        Bounding box coordinates of the tweet

    la_df: pd.DataFrame
        (pandas) DataFrame containing information of
        the Local Authorities (keys) to match

    return_all: bool
        Flag controlling whether to return only the top
        matching local authorities or all of them
        (ranked by likelihood). By default, False.

    Returns
    -------
    A tuple containing the name, the code, and the reference of
    the top matching LA, or all of them (in the form of
    a pd.DataFrame)
    """

    if len(bbox) == 1:
        # This is the case of using geo.coordinates
        # for tweets
        bbox = Point(bbox[0])
    else:
        polygon = Polygon(bbox)
        if not polygon.is_valid:  # Try matching a Point
            # Apply a slight correction to point coords
            # to allow for better matching
            bbox = np.asarray(bbox) - 0.01
            bbox = Point(bbox[0])
        else:
            bbox = polygon

    # Local Authorities of Interest are those that overlap with the bbox
    laoi = la_df[la_df["geometry"].intersects(bbox)].copy()

    if laoi.shape[0] == 0:  # no overlap found
        return None

    # Intersection over the union is a measure of how exactly the bounding box
    # and the la overlap
    laoi["iou"] = la_df["geometry"].apply(
        lambda g: g.intersection(bbox).area / g.union(bbox).area
    )
    # Pop weight is the proportion of the la population covered by the bounding box.
    laoi["pop_weight"] = (
        laoi["geometry"].apply(lambda g: (g.intersection(bbox).area / g.area))
        * laoi["pop"]
    )
    # The final likelihood is the IoU multiplied by the population weight
    laoi["likelihood"] = laoi["iou"] * laoi["pop_weight"]
    # Sort dataframe by highest to lowest
    laoi = laoi.sort_values(by="likelihood", ascending=False)

    if return_all:
        return laoi
    return laoi["lad18nm"].iat[0], laoi["lad18cd"].iat[0], laoi["lhb"].iat[0]


# %%
def match_reference_la(data):
    """ Choose LA with highest likelihood. Add LA and LHB to dataset. """

    # Get a list of the required values from the first row of sorted dataframe.
    def match_la(coords):
        if coords is None:
            return None
        laoi = match_local_authorities(coords, la)
        if laoi is None:
            return None
        return laoi

    from datasets import load_local_authorities

    la_ds = load_local_authorities()
    la = la_ds.data

    # Matching for Geo Coordinates - Those tweets having Geo-location info
    set_geo_coords = set(data[~data["geo_coords"].isna()]["geo_coords"].values)
    list_geo_coords = map(lambda c: [c], set_geo_coords)
    la_map_geo_coords = {
        c: l for c, l in zip(set_geo_coords, map(match_la, list_geo_coords))
    }

    data["la"] = data["geo_coords"].apply(
        lambda c: None
        if c is None or la_map_geo_coords[c] is None
        else la_map_geo_coords[c]
    )

    set_bbox_coords = set(data[data["la"].isna()]["bbox"].values)
    la_map_bbox_coords = {
        c: l for c, l in zip(set_bbox_coords, map(match_la, set_bbox_coords))
    }
    residual_matchings = data[data["la"].isna()]["bbox"].apply(
        lambda c: la_map_bbox_coords[c]
    )
    data["la"].fillna(residual_matchings, inplace=True)

    # Split values for LA in three cols
    data["lad18nm"] = data["la"].apply(lambda c: c[0])
    data["lad18cd"] = data["la"].apply(lambda c: c[1])
    data["lhb"] = data["la"].apply(lambda c: c[2])

    # Drop la column - not needed anymore
    data.drop("la", axis=1, inplace=True)

    return data


# %% Twitter Pipeline
class TwitterPipeline(Pipeline):
    """Implementation of the Pipeline class for reading and preparing tweets."""

    def create_pipeline(self) -> List[Pipe]:
        # define pipeline
        filter_welsh = partial(_get_welsh_tweets, col="place.full_name")
        combine_text = partial(_tidy_text_cols, col="extended_tweet.full_text")
        geojson_bbox = partial(_bbox_geojson, col="place.bounding_box.coordinates")
        convert_coords = partial(convert_coordinates, col="geo.coordinates")

        return [
            ("Filter Tweets from Wales", filter_welsh),
            ("Combine Text fields", combine_text),
            ("Convert Geo Coordinates (in Floating Point)", convert_coords),
            ("Collect BoundingBox Coordinates (GeoJSON)", geojson_bbox),
            ("Collect BoundingBox Coordinates (Tuples)", _bbox_tuple),
            ("Match Local Authorities", match_reference_la),
            ("Set DateTime Index", _create_datetime_index),
        ]
