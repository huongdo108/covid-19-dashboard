import os

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_table

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np


external_stylesheets = [
    "https://codepen.io/chriddyp/pen/bWLwgP.css",
    dbc.themes.BOOTSTRAP,
]


app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server


# get raw data
rootpath = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/"
)
confirmed = pd.read_csv(f"{rootpath}time_series_covid19_confirmed_global.csv")
recovered = pd.read_csv(f"{rootpath}time_series_covid19_recovered_global.csv")
dead = pd.read_csv(f"{rootpath}time_series_covid19_deaths_global.csv")


def get_last_column(df):
    last_column = df.columns[-1]
    return last_column


# create main dataframe used in world map, data table and stacked chart
def create_main_dataframe():
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
def transform_data(df, type_of_data):
    # fill in missing Province/State
    df["Province/State"] = df["Province/State"].transform(lambda x: x.fillna(df["Country/Region"]))

    # pivot data
    df = df.melt(id_vars=["Province/State", "Country/Region", "Lat", "Long"], var_name="Date", value_name="Value",)

    # add new column type
    df = df.rename(columns={"Country/Region": "Country", "Province/State": "Country/Region"})
    df["type"] = type_of_data
    return df


# create new dataframe for charts
confirmed_f = transform_data(confirmed, "Confirmed Cases")
recovered_f = transform_data(recovered, "Recovered Cases")
dead_f = transform_data(dead, "Death Cases")
data_table = create_main_dataframe()


# world map
@app.callback(
    dash.dependencies.Output("world-map", "figure"), [dash.dependencies.Input("year", "value")],
)
def update_graph(year):
    px.set_mapbox_access_token(open(".mapbox_token").read())
    fig = px.scatter_mapbox(
        data_table,
        lat="Lat",
        lon="Long",
        size="Confirmed",
        color="Confirmed",
        size_max=70,
        hover_name="Country/Region",
        # hover_data=["Dead","Confirmed"],
        # custom_data=["Recovered", "Dead"],
        # text="Recovered",
        color_continuous_scale=px.colors.cyclical.IceFire,
        zoom=1,
    )

    fig.update_traces(customdata=data_table["Country/Region"])
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=5, r=5, t=5, b=5), height=350)

    fig.layout.autosize = True

    return fig


# time series for each country
def create_time_series(df, title):
    fig = px.line(df, x="Date", y="Value", color="type")
    fig.update_traces(mode="lines")
    fig.update_xaxes(showgrid=False)
    fig.add_annotation(
        x=0,
        y=0.85,
        xanchor="left",
        yanchor="bottom",
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        bgcolor="rgba(255, 255, 255, 0.5)",
        text=title,
    )
    fig.update_layout(height=185, margin=dict(l=20, r=5, t=0, b=20))
    fig.update_layout(legend=dict(x=0, y=0.5))
    return fig


@app.callback(
    dash.dependencies.Output("country-specific", "figure"), [dash.dependencies.Input("world-map", "hoverData")],
)
def update_timeseries(hoverData):
    country_name = hoverData["points"][0]["customdata"]
    df_confirmed = confirmed_f[confirmed_f["Country/Region"] == country_name]
    df_recovered = recovered_f[recovered_f["Country/Region"] == country_name]
    df_dead = dead_f[dead_f["Country/Region"] == country_name]
    df = pd.concat([df_confirmed, df_recovered, df_dead])
    title = "<b>{}</b>".format(country_name)
    return create_time_series(df, title)


#  data table
operators = [
    ["ge ", ">="],
    ["le ", "<="],
    ["lt ", "<"],
    ["gt ", ">"],
    ["ne ", "!="],
    ["eq ", "="],
    ["contains "],
    ["datestartswith "],
]


def split_filter_part(filter_part):
    for operator_type in operators:
        for operator in operator_type:
            if operator in filter_part:
                name_part, value_part = filter_part.split(operator, 1)
                name = name_part[name_part.find("{") + 1 : name_part.rfind("}")]

                value_part = value_part.strip()
                v0 = value_part[0]
                if v0 == value_part[-1] and v0 in ("'", '"', "`"):
                    value = value_part[1:-1].replace("\\" + v0, v0)
                else:
                    try:
                        value = float(value_part)
                    except ValueError:
                        value = value_part

                # word operators need spaces after them in the filter string,
                # but we don't want these later
                return name, operator_type[0].strip(), value

    return [None] * 3


@app.callback(
    dash.dependencies.Output("table-paging-with-graph", "data"),
    [
        dash.dependencies.Input("table-paging-with-graph", "page_current"),
        dash.dependencies.Input("table-paging-with-graph", "page_size"),
        dash.dependencies.Input("table-paging-with-graph", "sort_by"),
        dash.dependencies.Input("table-paging-with-graph", "filter_query"),
    ],
)
def update_table(page_current, page_size, sort_by, filter):
    filtering_expressions = filter.split(" && ")
    dff = data_table[["Country/Region", "Confirmed", "Recovered", "Dead", "Recovered/Confirmed", "Dead/Confirmed"]]
    for filter_part in filtering_expressions:
        col_name, operator, filter_value = split_filter_part(filter_part)

        if operator in ("eq", "ne", "lt", "le", "gt", "ge"):
            # these operators match pandas series operator method names
            dff = dff.loc[getattr(dff[col_name], operator)(filter_value)]
        elif operator == "contains":
            dff = dff.loc[dff[col_name].str.contains(filter_value)]
        elif operator == "datestartswith":
            # this is a simplification of the front-end filtering logic,
            # only works with complete fields in standard format
            dff = dff.loc[dff[col_name].str.startswith(filter_value)]

    if len(sort_by):
        dff = dff.sort_values(
            [col["column_id"] for col in sort_by],
            ascending=[col["direction"] == "asc" for col in sort_by],
            inplace=False,
        )

    return dff.iloc[page_current * page_size : (page_current + 1) * page_size].to_dict("records")


# stacked bar chart
@app.callback(
    dash.dependencies.Output("table-paging-with-graph-container", "children"),
    [dash.dependencies.Input("table-paging-with-graph", "data")],
)
def update_graph(rows):
    dff = pd.DataFrame(rows)
    fig = go.Figure(
        data=[
            go.Bar(name="Confirmed", x=dff["Country/Region"], y=dff["Confirmed"]),
            go.Bar(name="Recovered", x=dff["Country/Region"], y=dff["Recovered"]),
            go.Bar(name="Dead", x=dff["Country/Region"], y=dff["Dead"]),
        ]
    )
    fig.update_layout(barmode="stack", margin=dict(l=10, r=5, t=10, b=5), height=250, width=718)
    return html.Div([dcc.Graph(figure=fig)])


# cards
card_content1 = [
    dbc.CardHeader("WORLD CONFIRMED CASES", style={"fontSize": 12, "fontWeight": "bold"}),
    dbc.CardBody(
        [
            # html.H5("Card title", className="card-title"),
            html.P("%.2f" % int(data_table["Confirmed"].sum()), style={"fontSize": 15, "fontWeight": "bold"}),
        ]
    ),
]

card_content2 = [
    dbc.CardHeader("WORLD RECOVERED CASES", style={"fontSize": 12, "fontWeight": "bold"}),
    dbc.CardBody(
        [
            # html.H5("Card title", className="card-title"),
            html.P("%.2f" % round(data_table["Recovered"].sum()), style={"fontSize": 15, "fontWeight": "bold"}),
        ]
    ),
]

card_content3 = [
    dbc.CardHeader("WORLD DEAD CASES", style={"fontSize": 12, "fontWeight": "bold"}),
    dbc.CardBody(
        [
            # html.H5("Card title", className="card-title"),
            html.P("%.2f" % round(data_table["Dead"].sum()), style={"fontSize": 15, "fontWeight": "bold"}),
        ]
    ),
]

## LAYOUT

app.layout = html.Div(
    [
        dbc.Row(
            dbc.Col(
                html.Div([html.H1("Covid-19 Global Visualization")], style={"textAlign": "left", "marginLeft": 20},)
            )
        ),
        dbc.Row(
            [
                dbc.Col(dbc.Card(card_content1, color="info", inverse=True)),
                dbc.Col(dbc.Card(card_content2, color="success", inverse=True)),
                dbc.Col(dbc.Card(card_content3, color="secondary", inverse=True)),
            ],
            className="mb-4",
            style={"marginLeft": 5, "marginRight": 5, "marginTop": 5, "marginBottom": 0},
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Row(
                            dbc.Col(
                                html.Div([dcc.Graph(id="world-map", hoverData={"points": [{"customdata": "US"}]},)],)
                            )
                        ),
                        dbc.Row(dbc.Col(html.Div([dcc.Graph(id="country-specific")], style={},))),
                    ],
                    width=6,
                    style={"marginLeft": 20},
                ),
                dbc.Col(
                    [
                        dbc.Row(html.Div(id="table-paging-with-graph-container",)),
                        dbc.Row(
                            html.Div(
                                dash_table.DataTable(
                                    id="table-paging-with-graph",
                                    columns=[
                                        {"name": i, "id": i}
                                        for i in (
                                            [
                                                "Country/Region",
                                                "Confirmed",
                                                "Recovered",
                                                "Dead",
                                                "Recovered/Confirmed",
                                                "Dead/Confirmed",
                                            ]
                                        )
                                    ],
                                    page_current=0,
                                    page_size=7,
                                    page_action="custom",
                                    filter_action="custom",
                                    filter_query="",
                                    row_deletable=True,
                                    sort_action="custom",
                                    sort_mode="multi",
                                    sort_by=[],
                                    style_as_list_view=True,
                                    style_cell={"padding": "0px", "font_size": "10px"},
                                    style_header={
                                        "backgroundColor": "LightSlateGray",
                                        "fontWeight": "bold",
                                        "color": "White",
                                    },
                                    style_cell_conditional=[
                                        {"if": {"column_id": c}, "textAlign": "left"} for c in ["Country/Region"]
                                    ],
                                    style_data_conditional=[
                                        {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
                                    ],
                                ),
                                style={"width": "110%", "marginRight": -58, "marginTop": 10, "marginLeft": 15},
                            )
                        ),
                    ],
                    width=5,
                ),
            ]
        ),
        dbc.Row(
            dbc.Col(
                html.Div(
                    [dcc.Dropdown(id="year", options=[{"label": i, "value": i} for i in ["2020"]], value="2020",)],
                )
            )
        ),
    ],
    style={"backgroundColor": "Gainsboro"},
)


if __name__ == "__main__":
    app.run_server(debug=True)
