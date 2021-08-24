"""This module is used to write and define the content and structure of the final
`data.json` file that is used to plot the data on the frontend.

Notes
-------
    Running this module as `__main__` will generate the .json file and write it to the
    data folder in the frontend.

    If you are adding new variables, you must first define it as a Variable instance,
    and then
    add the name of the varible instance to either the `LA_VARBS` or `LSOA_VARBS` list,
    depending on whether it is an LA or LSOA variable.
    Prior to doing this you must also have added the data source to the `live`
    or `static`
    modules in the `datasets` package, so that they appear in the corresponding
    `MasterDataset` object.

    The pd.Series provided to the Variable class instances are columns from the
    instances of `MasterDataset` that are imported from the `datasets` package.
    These are:
        `LA_STATIC_MASTER` (from `datasets.static`)
        `LSOA_STATIC_MASTER` (from `datasets.static`)
        `LA_LIVE_MASTER` (from `datasets.live`)
"""


import pandas as pd
from dataclasses import dataclass
from typing import Sequence
from warnings import warn
from datetime import datetime
import os
import json

# Local imports
from datasets.live import LA_LIVE
from datasets.static import LA_STATIC, LSOA_STATIC

from datasets import BASE_FOLDER

LA_STATIC_MASTER = LA_STATIC.master_dataset
LSOA_STATIC_MASTER = LSOA_STATIC.master_dataset
LA_LIVE_MASTER = LA_LIVE.master_dataset


@dataclass
class Variable:
    """This class defines the metadata and transformations needed for
    a variable. It will generate the transformed variable, and will also
    generate and object with the variable's associated metadata.

    Notes
    -------
    Not all transformations can be applied to all data types. For instance,
    data of type `rank` cannot be transformed to a percentage. In these cases,
    the variable data is returned as itself.

    Attributes
    -------
    data: pd.Series
        The variable data. Index should be set as area name and area code.
    label: str
        Human readable label to be presented on the map.
    data_class: str
        Accepts options 'support' or 'challenge'
    invert: bool
        Does the direction of the data need to be inverted before mapping?
    data_type: str
        Is the data a percentage, a count or a rank?
    la_and_lsoa: bool
        Is it available at both LA and LSOA resolution? By default, True.
    data_transformed_: pd.Series
        Set by calling the `transform` method. By default, None.
    """

    data: pd.Series
    label: str
    data_class: str
    invert: bool
    data_type: str
    la_and_lsoa: bool = True
    data_transformed_: pd.Series = None

    @property
    def res(self):
        """Guess and set the resolution of the data depending on no. of rows."""
        if self.data.shape[0] == 22:
            return "LA"
        elif self.data.shape[0] == 1909:
            return "LSOA"
        else:
            warn(
                "Series length of {} does not match LA or LSOA".format(
                    self.data.shape[0]
                )
            )

    def transform(self):
        """Applies transformation methods to the variable and sets
        the data_transformed_ attribute.

        Returns
        -------
        Variable
            Returns self
        """
        self.data_transformed_ = self.data
        self.data_transformed_ = self.transform_per100()
        if self.invert:
            self.data_transformed_ = self.invert_data()

        # Rename without the _ string section defining data type
        self.data_transformed_.name = self.new_name()

        return self

    @property
    def transformed_data(self):
        """Returns transformed data. Will return `None` if `transform` method
        has not been applied."""
        if self.data_transformed_ is None:
            self.transform()
        return self.data_transformed_

    def new_name(self):
        """Assuming all variables are originally named `name_datatype` this method
        removes the `_datatype` and returns just `name` as str."""
        name_to_change = self.data.name
        new_name = "_".join(name_to_change.split("_")[:-1])
        return new_name

    def transform_per100(self):
        """Based on variable type, perform transforms to percentage if possible, and
        sets self.data_transformed_ as the output.

        Notes
        -------
        The percentage for `count` type data will be as a percentage of the population
        variable at that geography.
        For `per100k` this will just be divided by 1000.
        All other data types (`percentage`, `density`, `rank`)
        they will be returned as given.

        Raises
        -------
        Exception
            When a data type is defined that is not yet supported.
        """
        if self.data_type == "percentage":
            return self.data_transformed_
        elif self.data_type == "count":
            if self.res == "LA":
                return (self.data_transformed_ / LA_POPULATION) * 100
            elif self.res == "LSOA":
                return (self.data_transformed_ / LSOA_POPULATION) * 100
        elif self.data_type == "density":
            return self.data_transformed_
        elif self.data_type == "rank":
            return self.data_transformed_
        elif self.data_type == "per100k":
            return self.data_transformed_ / 1000
        else:
            raise Exception(
                "Transformation of data type: {} are not suppored".format(
                    self.data_type
                )
            )

    def invert_data(self):
        """Invert data direction AFTER transformation and set self.data_transformed_
        as the output.

        Notes
        -------
        Data of type `percentage`, `count` and `per100k` are all inverted by subtracting
        them from 100. This only holds if inversion is applied *after* transform_per100.
        Data of type `rank` has the rank order reversed.

        Raises
        -------
        Exception
            When a data type is defined that is not yet supported.
        """
        if self.data_type in ["percentage", "count", "per100k"]:
            return 100 - self.data_transformed_
        elif self.data_type == "rank":
            return (self.data_transformed_.max() + 1) - self.data_transformed_
        else:
            raise Exception(
                "Inversion of data type: {} are not suppored".format(self.data_type)
            )

    def meta_to_json(self):
        """Creates a dict of the metadata, containing `name`, `label`, `class`, and
        `lsoa`. This is used in the `variables` section of the .json file.

        Returns
        -------
        dict
            Dictionary with keys `name`, `label`, `class` and `lsoa`.
        """
        return {
            "name": self.new_name(),
            "label": self.label,
            "class": self.data_class,
            "lsoa": self.la_and_lsoa,
        }


@dataclass
class Variables:
    """This dataclass turns a list of variables into one overall dictionary object of
    all the variable data attached to each geographic area.

    Attributes
    -------
    variables: Sequence[Variable]
        A sequence of the variables of the same geographic resolution to be transformed
        into a level in the json file.
    """

    variables: Sequence[Variable]

    @property
    def is_valid(self):
        """Returns True if all the variables are the same geographic resolution"""
        # Check resolutions are same for all variables
        resolutions = map(lambda v: v.res, self.variables)
        if len(set(resolutions)) < 2:
            return True
        else:
            return False

    def metadata_to_json(self):
        """Returns a list of metadata dictionaries for each variable"""
        return [var.meta_to_json() for var in self.variables]

    def data_to_json(self):
        """Transforms the variables, merges them to one df, rounds them to 3dp,
        then generates a list of dicts that represent each row (i.e. geographic area).

        Returns
        -------
        list
            List of dicts, where the keys in each dict are variable names and the
            values are the values of each varb. This includes the area name
            and code as keys.
        """
        vars = map(lambda v: v.transform(), self.variables)
        vars = map(lambda v: v.transformed_data, vars)

        data = pd.concat(vars, axis=1)
        # Reset index the dataframe first, because we want the index values in json
        data = data.round(3)
        data = data.reset_index()

        return data.to_dict(orient="records")


@dataclass
class DataDashboard:
    """Transforms existing Variables objects into one object that can be
    written to .json.

    Attributes
    -------
    la_data: Variables
        A Variables object of all the LA Variables to be included.
    lsoa_data: Variables
        A Variables object of all the LSOA Variables to be included.
    """

    la_data: Variables
    lsoa_data: Variables

    def to_json(self):
        """Creates the final dict object to write to json.

        Notes
        -------
        The metadata written to json here is only the LA metadata. This is because
        we assume that any LA level data is also available at LSOA level, and so the
        LA metadata will cover all the variables available.

        Returns
        -------
        dict
            Dictionary with three keys: `variables`, `LAs`, `LSOAs`. The values
            are lists of dictionaries containing the data as defined in Variables.
        """
        # Currently only returning LA level meta data as it encompasses both
        return {
            "variables": self.la_data.metadata_to_json(),
            "LAs": self.la_data.data_to_json(),
            "LSOAs": self.lsoa_data.data_to_json(),
            "updated": datetime.today().strftime("%Y-%m-%d"),
        }

    def write(self, filepath: str = None):
        """Writes out the variables in the required json format to the frontend.

        Notes
        -------
        The frontend data folder is assumed to be: `frontend/map/data/data.json`
        """
        if not filepath:
            filepath = os.path.join(
                BASE_FOLDER, "..", "..", "frontend", "map", "data", "data.json",
            )

        with open(filepath, "w") as outfile:
            json.dump(self.to_json(), outfile)


LA_POPULATION = LA_STATIC_MASTER["population_count"]
LSOA_POPULATION = LSOA_STATIC_MASTER["population_count"]

LA_POPDENSITY = Variable(
    data=LA_STATIC_MASTER["pop_density_persqkm"],
    label="Population Density (per sq. km)",
    data_class="challenge",
    la_and_lsoa=True,
    invert=False,
    data_type="density",
)

LSOA_POPDENSITY = Variable(
    data=LSOA_STATIC_MASTER["pop_density_persqkm"],
    label="Population Density (per sq. km)",
    data_class="challenge",
    invert=False,
    data_type="density",
)

LA_OVER_65 = Variable(
    data=LA_STATIC_MASTER["over_65_count"],
    label="Over Age 65 (per 100 ppl)",
    data_class="challenge",
    la_and_lsoa=True,
    invert=False,
    data_type="count",
)

LSOA_OVER_65 = Variable(
    data=LSOA_STATIC_MASTER["over_65_count"],
    label="Over Age 65 (per 100 pop)",
    data_class="challenge",
    invert=False,
    data_type="count",
)

LA_WIMD = Variable(
    data=LA_STATIC_MASTER["wimd_2019"],
    label="Most Deprived (% areas in lowest quintile of deprivation)",
    data_class="challenge",
    la_and_lsoa=True,
    invert=False,
    data_type="percentage",
)

LSOA_WIMD = Variable(
    data=LSOA_STATIC_MASTER["wimd_2019"],
    label="Index of Multiple Deprivation (rank)",
    data_class="challenge",
    invert=True,
    data_type="rank",
)

HAS_INTERNET = Variable(
    data=LA_STATIC_MASTER["has_internet_percent"],
    label="Digital Exclusion: No Internet Access (per 100 pop)",
    data_class="challenge",
    la_and_lsoa=False,
    invert=True,  # originally percent WITH internet but we need inverse for map
    data_type="percentage",
)

VULNERABLE = Variable(
    data=LA_STATIC_MASTER["vulnerable_pct"],
    label="Moderate Risk of COVID-19 (estimated per 100 pop)",
    data_class="challenge",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

BELONGING = Variable(
    data=LA_STATIC_MASTER["belong_percent"],
    label="Sense of Community Belonging (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

COVID_CASES = Variable(
    data=LA_LIVE_MASTER["covidIncidence_100k"],
    label="Cumulative COVID-19 Cases (per 100 pop)",
    data_class="challenge",
    la_and_lsoa=False,
    invert=False,
    data_type="per100k",
)

VAX_DOSE1 = Variable(
    data=LA_LIVE_MASTER["vax1_pct"],
    label="Vaccine Uptake Dose 1 (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

VAX_DOSE2 = Variable(
    data=LA_LIVE_MASTER["vax2_pct"],
    label="Vaccine Update Dose 2 (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

GROUPS = Variable(
    data=LA_LIVE_MASTER["groups_count"],
    label="Community Support Groups (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="count",
)

SHIELDING = Variable(
    data=LA_STATIC_MASTER["shielded_count"],
    label="High Risk of COVID-19 (per 100 pop)",
    data_class="challenge",
    la_and_lsoa=False,
    invert=False,
    data_type="count",
)

VOLS_TOTAL = Variable(
    data=LA_LIVE_MASTER["total_vol_count"],
    label="WCVA Registered Volunteers (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="count",
)

VOLS_INCREASE = Variable(
    data=LA_LIVE_MASTER["vol_increase_pct"],
    label="WCVA Increase in Volunteers (since March 2020, %)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)


GP_DIGITAL = Variable(
    data=LA_STATIC_MASTER["MHOL_pct"],
    label="Digital Exclusion: Not Registered with Online GP Services "
    + "(per 100 patients)",
    data_class="challenge",
    la_and_lsoa=False,
    invert=True,
    data_type="percentage",
)

TWEETS = Variable(
    data=LA_LIVE_MASTER["tweets_percent"],
    label="Twitter Community Support (estimated per 100 users)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

ZOE_SUPPORT = Variable(
    data=LA_LIVE_MASTER["has_someone_close_pct"],
    label="Symptom Tracker: Can Count On Someone Close (per 100 pop)",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)

VADER_SENTIMENT = Variable(
    data=LA_LIVE_MASTER["vader_comp"],
    label="Avg Twitter Sentiment Past 7 Days",
    data_class="support",
    la_and_lsoa=False,
    invert=False,
    data_type="percentage",
)


LA_VARBS = Variables(
    (
        VOLS_TOTAL,
        VOLS_INCREASE,
        VAX_DOSE1,
        VAX_DOSE2,
        GROUPS,
        TWEETS,
        BELONGING,
        COVID_CASES,
        SHIELDING,
        VULNERABLE,
        LA_OVER_65,
        LA_POPDENSITY,
        LA_WIMD,
        GP_DIGITAL,
        HAS_INTERNET,
        ZOE_SUPPORT,
        VADER_SENTIMENT,
    )
)

LSOA_VARBS = Variables((LSOA_WIMD, LSOA_OVER_65, LSOA_POPDENSITY,))

# Finally, create the data with the json function!
DATA = DataDashboard(la_data=LA_VARBS, lsoa_data=LSOA_VARBS)


if __name__ == "__main__":
    DATA.write()
    print("Successfully executed!")
