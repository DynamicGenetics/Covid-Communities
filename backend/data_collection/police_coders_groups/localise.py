"""Functions required to locate groups in Wales."""
import json
import csv
import logging
from shapely.geometry import shape, Point

logger = logging.getLogger(__name__)


def filter_welsh_groups(input_path, polygon):
    """Return a csv list of groups which are located in Wales, as well
    as the last row which is used as a header.

    Parameters
    ----------
    input_path : str
        File path to raw data location
    polygon : shapely.Polygon
        Polygon object of Welsh country boundary
    """
    output = []

    with open(input_path, encoding="utf-8") as f:
        data = csv.DictReader(f)

        for row in data:
            point = Point([float(row["Lng"]), float(row["Lat"])])

            if polygon.contains(point):

                output.append(row)

    return (output, row)


def write_data_to_CSV(output, row, out_path):
    """Writes given data to .csv

    Parameters
    ----------
    output : str
        Data on each group
    row : str
        Row to be used as header
    out_path : str
        File path to write cleaned data
    """

    with open(out_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write csv header
        writer.writerow(row)

        # Write groups as rows
        for row in output:
            writer.writerow(row.values())

    logger.info(
        "Message (iterateGroups): Localised {} groups to Wales".format(len(output))
    )


# Import welsh boundary
def get_welsh_boundary(fileNm_Wales):
    """Given the .geojson file of the Welsh boundary, returns a polygon shape
    of the Welsh boundary."""

    with open(fileNm_Wales) as boundaries:
        boundaries_js = json.load(boundaries)

        features = boundaries_js["features"]
        for feature in features:
            properties = feature["properties"]

            if properties["ctry19cd"] == "W92000004":
                polygon = shape(feature["geometry"])

                return polygon
