#####################################
# USEFUL TWEET PROCESSING FUNCTIONS #
#####################################

from geojson import Feature, MultiPolygon, FeatureCollection
import json

##############################
# Textual Analysis Functions #
##############################


def analyse_sentiment(data, col="text"):
    """Given a Pandas dataframe with col 'tweet_text', this will apply the vaderSentiment dictionary
    in a new column called 'vader'."""

    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    # define the sentiment analyser object
    analyser = SentimentIntensityAnalyzer()

    # Apply sentiment analysis to the data frame (new col for each)
    data["vader_comp"] = data[col].apply(
        lambda x: analyser.polarity_scores(x)["compound"]
    )
    data["vader_pos"] = data[col].apply(lambda x: analyser.polarity_scores(x)["pos"])
    data["vader_neg"] = data[col].apply(lambda x: analyser.polarity_scores(x)["neg"])
    data["vader_neu"] = data[col].apply(lambda x: analyser.polarity_scores(x)["neu"])

    return data


################################
# Geodata Processing Functions #
################################


def split_coords(data, col="geo.coordinates"):
    """Takes a Pandas dataframe with a column geo.coordinates (col) and adds the lat and long to their own columns
    for easy conversion to geojson."""

    # Split the string on the comma
    data["long"], data["lat"] = data[col].str.split(",", 1).str

    # Remove the left over square brackets
    data["lat"] = data["lat"].str[:-1]
    data["long"] = data["long"].str[1:]

    return data


def write_bbox_geojson(data, col="bbox_geojson"):
    """Given a correctly formatted column of bbox polygons, this will convert them to
    a geojson object, and write it out to a file."""

    # Make a Mutlipolygon from the values.
    features = Feature(geometry=MultiPolygon(data[col].tolist()))

    # All the other columns used as properties
    # properties = df.drop(['lat', 'lng'], axis=1).to_dict('records')
    # Add properties to the geo_json
    # feature_collection = FeatureCollection(features=features, properties=properties)

    feature_collection = FeatureCollection(features=features)

    print("Geojson object generated.")

    with open("tweets_bboxes.geojson", "w", encoding="utf-8") as f:
        json.dump(feature_collection, f, ensure_ascii=False)

    print("Written object to 'tweets_bboxes.geojson'")


# In progress - how to define how certain the match is
def class_uncertainty(laoi):
    """Roughly calculate how certain the classification is based on distances between
    the likelihood of the potentially overlapping LA boundaries."""

    # Sort dataframe by highest to lowest
    laoi = laoi.sort_values(by="likelihood", ascending=False)
    # Get the list of values
    a = laoi["likelihood"]
    a.reset_index().drop()
    del laoi["index"]

    # If there was only one, the
    if len(a) == 1:
        return 1
    elif len(a) == 2:
        return "only two"  # decide penalty function
    else:
        # Get the difference between each sequential number
        b = a.diff(periods=-1)
        # Divide the distance between the first and second number by the
        b["likelihood"][0] / b[1:].mean()
