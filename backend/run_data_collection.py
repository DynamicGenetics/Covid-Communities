"""When run as `__main__` this module will run the police coders scraper, and the PHW scraper.
"""

from datasets import LIVE_DATA_FOLDER, LIVE_RAW_DATA_FOLDER, GEO_DATA_FOLDER

from data_collection.police_coders_groups.run_scraper import run_police_coders_scraper
from data_collection.phw_data import PHWDownload, COVID_CASES, VAX_RATES

if __name__ == "__main__":
    # Get latest covid case data from PHW
    PHWDownload(COVID_CASES, LIVE_RAW_DATA_FOLDER).save_data()
    # Get the latest vaccination data from PHW
    PHWDownload(VAX_RATES, LIVE_RAW_DATA_FOLDER).save_data()
    # Run the Police Coders community group scraper
    run_police_coders_scraper(LIVE_RAW_DATA_FOLDER, LIVE_DATA_FOLDER, GEO_DATA_FOLDER)
