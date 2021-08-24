"""This module is responsible for the automated updating of the COVID and vaccination
data from Public Health Wales, and fetching groups from Police Coders.
When run as main it will execute both scrapers daily at 3pm, and update the JSON 5
minutes later at 3.05pm. If a task raises an exception, it will
send a notification to the lab Slack group to notify us to check the logs."""

import time
import functools
import traceback
import logging
import datetime
from traceback import format_exc
from slack import WebClient
from schedule import Scheduler
from argparse import ArgumentParser

from slack_tokens import SLACK_TOKEN, SLACK_CHANNEL
from datasets import LIVE_DATA_FOLDER, LIVE_RAW_DATA_FOLDER, GEO_DATA_FOLDER
from data_collection.police_coders_groups.run_scraper import run_police_coders_scraper
from data_collection.phw_data import PHWDownload, COVID_CASES, VAX_RATES

# NB Necessary to set up the logging config before running the local imports
logging.basicConfig(
    filename="scheduler.log",
    filemode="a",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ------
# Set up
# ------
# Initialise logger
logger = logging.getLogger("scheduler")
# Slack connection set up
client = WebClient(token=SLACK_TOKEN)


# Source https://gist.github.com/mplewis/8483f1c24f2d6259aef6
class SafeScheduler(Scheduler):
    """
    An implementation of Scheduler that catches jobs that fail, logs their
    exception tracebacks as errors, optionally reschedules the jobs for their
    next run time, and keeps going.

    Use this to run jobs that may or may not crash without worrying about
    whether other jobs will run or if they'll crash the entire script.
    """

    def __init__(self, reschedule_on_failure=True):
        """
        If reschedule_on_failure is True, jobs will be rescheduled for their
        next run as if they had completed successfully. If False, they'll run
        on the next run_pending() tick.
        """
        self.reschedule_on_failure = reschedule_on_failure
        super().__init__()

    def _run_job(self, job):
        try:
            super()._run_job(job)
        except Exception:
            logger.error(format_exc())
            job.last_run = datetime.datetime.now()
            job._schedule_next_run()


# ---------------------
# Logging wrap function
# ---------------------
# Note: logging wrapper taken from docs https://schedule.readthedocs.io/en/stable/faq.html
def with_logging(func):
    """This is a wrapper that logs the start and end of a function,
    and sends exceptions to Slack"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info('Running job "%s"' % func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            message = (
                "Hello from ErrorBot! :tada: An exception "
                "has been raised by the scheduling system, inside SafeScheduler. "
                "I'll run again tomorrow."
            )

            client.chat_postMessage(
                channel=SLACK_CHANNEL, text=message,
            )
            raise e
        finally:
            logger.info('Job "%s" completed' % func.__name__)

        return result

    return wrapper


# ----------------
# Functions to run
# ----------------
@with_logging
def run_data_collection():
    # Get latest covid case data from PHW
    PHWDownload(COVID_CASES, LIVE_RAW_DATA_FOLDER).save_data()
    # Get the latest vaccination data from PHW
    PHWDownload(VAX_RATES, LIVE_RAW_DATA_FOLDER).save_data()
    # Run the Police Coders community group scraper
    run_police_coders_scraper(LIVE_RAW_DATA_FOLDER, LIVE_DATA_FOLDER, GEO_DATA_FOLDER)


@with_logging
def update_json(output_path: str):
    # Re-run the import each time to ensure the imported DATA object is not saved in memory
    from generate_json import DATA

    DATA.write(filepath=output_path)


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument(
        "-st", "--run-scrapers-at", dest="scrapers_time", type=str, default="15:00"
    )
    parser.add_argument(
        "-ut", "--run-updates-at", dest="update_time", type=str, default="15:05"
    )
    parser.add_argument("-o", "--output", type=str, default="", dest="json_output")

    args = parser.parse_args()

    try:
        client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="Thanks, the scheduler is up and running again. :raised_hands:",
        )

        # Run safe scheduler every day at 4pm and 4.15pm BST
        scheduler = SafeScheduler()

        scheduler.every().day.at(args.scrapers_time).do(run_data_collection)
        scheduler.every().day.at(args.update_time).do(
            update_json, output_path=args.json_output
        )

        # Sleep function
        while True:
            scheduler.run_pending()
            time.sleep(60)

    except KeyboardInterrupt:
        message = (
            ":octagonal_sign: Hello there, the scheduler has been successfully stopped."
        )
        client.chat_postMessage(channel=SLACK_CHANNEL, text=message)

    except Exception:
        message = (
            ":skull: It's a me, ErrorBot! Unfortunately the scheduler script has stopped running. Here is the trackback: \n"
            "{}".format(traceback.format_exc())
        )

        client.chat_postMessage(channel=SLACK_CHANNEL, text=message)

        logger.critical(
            "Running script terminated. Message sent to Slack. Traceback was {}".format(
                traceback.format_exc()
            )
        )
