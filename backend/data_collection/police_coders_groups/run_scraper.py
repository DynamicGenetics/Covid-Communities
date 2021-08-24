"""This module executes the police coders scraper.

    Notes
    ----------
    Intended purpose of this script:
    1. Get updated data using googleScrape ()
    2. Save scraping data archived by date (csv)
    3. Overwrite most recent data (csv)
    4. Produce groupCount layer as a count of groups per area
"""

import logging
import os

from .police_scraper import police_coders_scrape
from .localise import (
    get_welsh_boundary,
    filter_welsh_groups,
    write_data_to_CSV,
)
from .group_count import (
    count_groups,
    get_boundaries_LA,
    get_boundaries_LSOA,
    locate_group,
)

logger = logging.getLogger(__name__)


def run_police_coders_scraper(LIVE_RAW_DATA_FOLDER, LIVE_DATA_FOLDER, GEO_DATA_FOLDER):
    """Executes the tasks required to run the Police Coders data collector.

    Parameters
    ----------
    LIVE_RAW_DATA_FOLDER : str
        Path to the live raw data folder.
    LIVE_DATA_FOLDER : str
        Path to the live cleaned data folder.
    GEO_DATA_FOLDER : str
        Path to the geoboundaries data folder.
    """
    # Define file output paths
    fn_groups_raw = os.path.join(LIVE_RAW_DATA_FOLDER, "groups_raw.csv")
    fn_groups_cleaned = os.path.join(LIVE_DATA_FOLDER, "groups.csv")

    # Get latest community group data
    groups = police_coders_scrape(fn_groups_raw)
    logger.info("Message (googleScrape): Scraped group count: {} ".format(groups))

    # Get welsh border as polygon Shape object
    welsh_border_polygon = get_welsh_boundary(
        os.path.join(GEO_DATA_FOLDER, "boundaries_Wales.geojson")
    )

    # Search if group coordinates are located within welsh border Shape object
    welsh_groups = filter_welsh_groups(fn_groups_raw, welsh_border_polygon)

    # Write list of welsh groups to csv
    write_data_to_CSV(welsh_groups[0], welsh_groups[1], fn_groups_cleaned)

    # Count the number of groups per area to produce the groupCount layer

    # Get boundary shapes and names for la and lsoa levels
    boundary_info_LA = get_boundaries_LA(
        os.path.join(GEO_DATA_FOLDER, "boundaries_LA.geojson")
    )
    boundary_info_LSOA = get_boundaries_LSOA(
        os.path.join(GEO_DATA_FOLDER, "boundaries_LSOA.geojson")
    )

    # Make seperate counts of groups per la and lsoa
    count_LA = count_groups(fn_groups_cleaned, boundary_info_LA, "lad18cd")
    count_LSOA = count_groups(fn_groups_cleaned, boundary_info_LSOA, "LSOA11CD")

    logger.info(
        "Message (groupCount): Performed count of groups per area, {} groups localised to LAs and {} to LSOAs".format(
            count_LA["groupCount"].sum(), count_LSOA["groupCount"].sum()
        )
    )

    # Save counts of groups by areas to seperate csvs
    count_LA.to_csv(os.path.join(LIVE_DATA_FOLDER, "groupCount_LA.csv"), index=False)
    count_LSOA.to_csv(
        os.path.join(LIVE_DATA_FOLDER, "groupCount_LSOA.csv"), index=False
    )
