import pandas as pd



# get raw data
"""
Get daily data of confirmed cases, recovered cases and dead cases in every country/region
"""
rootpath = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/"
)
confirmed = pd.read_csv(f"{rootpath}time_series_covid19_confirmed_global.csv")
recovered = pd.read_csv(f"{rootpath}time_series_covid19_recovered_global.csv")
dead = pd.read_csv(f"{rootpath}time_series_covid19_deaths_global.csv")


def get_last_column(df):
    """
    Get the latest data of the most recent day
    """
    last_column = df.columns[-1]
    return last_column


# create main dataframe used in world map, data table and stacked chart
def create_main_dataframe():
    """
    Create main dataframe which is used in world map, data table and stacked chart
    """
    confirmed["Province/State"] = confirmed["Province/State"].transform(lambda x: x.fillna(confirmed["Country/Region"]))
    confirmed_cases = get_last_column(confirmed)
    recovered_cases = get_last_column(recovered)
    dead_cases = get_last_column(dead)
    ratio_recovered = round(recovered[recovered_cases] / confirmed[confirmed_cases], 2)
    ratio_dead = round(dead[dead_cases] / confirmed[confirmed_cases], 2)
    df = pd.DataFrame(
        {
            "Country/Region": confirmed["Province/State"],
            "Lat": confirmed["Lat"],
            "Long": confirmed["Long"],
            "Confirmed": confirmed[confirmed_cases],
            "Recovered": recovered[recovered_cases],
            "Dead": dead[dead_cases],
            "Recovered/Confirmed": ratio_recovered,
            "Dead/Confirmed": ratio_dead,
        }
    )
    return df


# transform data for time series charts
def transform_data_time_series(df, type_of_data):
    """
    Transform function which is applied on daily data to create time series charts
    """
    # fill in missing Province/State
    df["Province/State"] = df["Province/State"].transform(lambda x: x.fillna(df["Country/Region"]))

    # pivot data
    df = df.melt(id_vars=["Province/State", "Country/Region", "Lat", "Long"], var_name="Date", value_name="Value",)

    # add new column type
    df = df.rename(columns={"Country/Region": "Country", "Province/State": "Country/Region"})
    df["type"] = type_of_data
    return df

## DATA
confirmed_ts = transform_data_time_series(confirmed, "Confirmed Cases")
recovered_ts = transform_data_time_series(recovered, "Recovered Cases")
dead_ts = transform_data_time_series(dead, "Death Cases")
data_table = create_main_dataframe()