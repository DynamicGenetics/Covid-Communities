"""Module containing functions required for attaining and cleaning data
from the Public Health Wales public datasets.
"""

import requests
import os
import logging
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Dataset names to be used with run_phw_scraper
COVID_CASES = "Rapid COVID-19 surveillance data"
VAX_RATES = "COVID19 vaccination downloadable data "


class PHWDownload:
    """Get latest data from PHW, where dataset defines what is being scraped.

    This function will get the latest data, write it to the raw folder as a .xlsx.
    It will then clean it it, and write the cleaned data to the clean folder.

    Parameters
    ----------
    dataset : str
        The name of the file to be downloaded from the PHW website.
    folder : str
        File path to write the scraped data to.
    """

    def __init__(self, dataset, folder):
        """Setup the filenames and paths based on the folders provided."""

        self.dataset = dataset
        self.folder = folder
        self.filename = dataset.replace(" ", "-")
        self.path = os.path.join(folder, self.filename + ".xlsx")

    def get_url(self):
        """Get the URL of the latest dataset."""

        # Get the content from the webpage
        response = requests.get(
            "http://www2.nphs.wales.nhs.uk:8080/CommunitySurveillanceDocs.nsf/PublicPage?OpenPage&AutoFramed"
        )
        # Parse the content using Beautiful Soup
        soup = BeautifulSoup(response.content, "html.parser")

        try:
            # Find the element with the title that we need, and get the parent row (<tr>)
            element = soup.find(title=self.dataset).find_parent("tr")
            # Extract the URL from the row element (it is the first href in the row.)
            url = "http://www2.nphs.wales.nhs.uk:8080" + element.find("a").get("href")
        except AttributeError:
            # If the element can't be found then return url as None.
            url = None

        return url

    def save_data(self):
        """
        Downloads PHW dashboard data Excel file, saves as xlsx to given output path.
        Runs the function `get_url`.
        """

        # Get the data URL
        try:
            url = self.get_url()
        except Exception as e:
            raise e

        if url is not None:
            r = requests.get(url, allow_redirects=True)
            # Save in native xlsx format
            output = open(self.path, "wb")
            output.write(r.content)
            output.close()
            logger.info("Successfully saved {}".format(self.dataset))
        elif url is None:
            logger.error("Could not get URL to download {}".format(self.dataset))
