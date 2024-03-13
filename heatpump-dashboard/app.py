import pandas as pd
import plotnine as p9
import numpy as np
from shiny import App, Inputs, Outputs, Session, reactive, render, req, ui
import openmeteo_requests
import requests_cache
from retry_requests import retry
from mizani.breaks import date_breaks
from mizani.formatters import date_format
from ipyleaflet import Map, Marker
from shinywidgets import output_widget, render_widget

cache_session = requests_cache.CachedSession('.cache', expire_after = -1)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Load the data
data = pd.read_csv('data/cities.csv')

us_cities = data['city_state']
us_cities = us_cities.tolist()


# setup ui
app_ui = ui.page_fluid(
    ui.page_fixed(
        ui.panel_title(title="Daily Heat Pump Efficiency Counter", window_title="Heat Pump Efficiency"),
    ),
    ui.layout_sidebar(
        ui.panel_sidebar(
            ui.input_selectize("us_city", "City", us_cities, selected="Champaign, Illinois"),
            ui.output_ui("city_coords"),
            ui.input_date_range("date_range","Date range", start="2020-01-01", end="2024-01-01", min="2020-01-01", max="2024-01-01"), 
            ui.input_radio_buttons("temperature_unit", "Temperature Unit", choices=["Fahrenheit", "Celsius"], selected="Fahrenheit"), 
            ui.output_ui("render_temp_slider"),
            ui.input_checkbox_group("plot_avg", "Plot Options",{'w': 'Weekly Rolling Average', 'm': 'Monthly Rolling Average'}),
            ui.output_ui("render_table_slider"),
            ui.HTML("<hr>"),
            output_widget("show_map"),
        ),
        ui.panel_main(
            ui.page_navbar(
                ui.nav_panel("Historical",
                    ui.output_plot("plot"),
                    ui.output_data_frame("heat_table"),

                ),
                ui.nav_panel("About", 
                    ui.markdown(
                        """
                        # Daily Heat Pump Efficiency Counter

                        This dashboard aims at providing you with the information need to help you determine the efficacy of installing a heat pump depending on the weather in a particular location in the United States. This dashboard contains all cities with a population greater than 10,000 and which were in the Simple Maps data set. 

                        ### ✨How To Use✨
                        - Changing the **City** will affect that graph to display the weather for that city
                        - The **Date Range** is limited to 01-01-2020 to 01-01-2024, however changing the date range affect the graph to display the selected date range
                        - The **Temperature Unit** allows you to switch from Farenheit to Celscius, this change will also be displayed in the graph
                        - Changing the **Plot Temperature** will modify the graph to help indicate what days the weather was below that given temperature
                        - The **Plot Options** let you display a line on the graph showing the weekly rolling average or the monthly rolling average depending on what you check. Feel free to press one, both or neither :)
                        - The **Table Temperature** changes the teperature range that is then used for the table to let you know how many days was weather in your location below the selected temperature.

                        ### Citations
                        ##### Open-Mateo API
                        - Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649
                        - Hersbach, H., Bell, B., Berrisford, P., Biavati, G., Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N. (2023). ERA5 hourly data on single levels from 1940 to present [Data set]. ECMWF. https://doi.org/10.24381/cds.adbb2d47
                        - Muñoz Sabater, J. (2019). ERA5-Land hourly data from 2001 to present [Data set]. ECMWF. https://doi.org/10.24381/CDS.E2161BAC
                        - Schimanke S., Ridal M., Le Moigne P., Berggren L., Undén P., Randriamampianina R., Andrea U., Bazile E., Bertelsen A., Brousseau P., Dahlgren P., Edvinsson L., El Said A., Glinton M., Hopsch S., Isaksson L., Mladek R., Olsson E., Verrelle A., Wang Z.Q. (2021). CERRA sub-daily regional reanalysis data for Europe on single levels from 1984 to present [Data set]. ECMWF. https://doi.org/10.24381/CDS.622A565A

                        ##### Simple Maps
                        - https://simplemaps.com/data/us-cities

                        """
                    )
                )
            ),
        )
    ),
    
)

def server(input, output, session):
    @render.ui
    @reactive.event(input.temperature_unit)
    def render_temp_slider():
        if input.temperature_unit() == "Fahrenheit":
            min_temp,max_temp,default_temp = -15,50,5
        else:
            min_temp,max_temp,default_temp = -25,10,-15
        return ui.input_slider("plot_temp","Plot Temperature", min=min_temp, max=max_temp, value=default_temp, step=1)

    @render.ui
    @reactive.event(input.temperature_unit)
    def render_table_slider():
        if input.temperature_unit() == "Fahrenheit":
            min_temp,max_temp,default_temp = -25,60,[0,15]
        else:
            min_temp,max_temp,default_temp = -30,15,[-20,-10]
        return ui.input_slider("table_temp","Table Temperature", min=min_temp, max=max_temp, value=default_temp)

    @render_widget
    @reactive.event(input.us_city)
    def show_map():
        city = chosen_city()
        city_lat = city['lat'].iloc[0]
        city_lng = city['lng'].iloc[0]
        city_center = (city_lat, city_lng)
        print(city_center)
        city_map = Map(center=city_center, zoom=12)
        city_marker = Marker(location=city_center, draggable=False)
        city_map.add(city_marker);
        return city_map


    @reactive.Calc
    def chosen_city() -> pd.DataFrame:
        url = "https://archive-api.open-meteo.com/v1/archive"
        # print(input.us_city())
        params = {
            "latitude": data[data['city_state'] == input.us_city()]['lat'],# input
            "longitude": data[data['city_state'] == input.us_city()]['lng'], #input
            "start_date": input.date_range()[0],      # input
            "end_date": input.date_range()[1],        # input
            "daily": "temperature_2m_min",   # fixed
            "temperature_unit": input.temperature_unit().lower() # input
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        daily = response.Daily()
        daily_temperature_2m = daily.Variables(0).ValuesAsNumpy()

        city_lat = response.Latitude()
        city_lng = response.Longitude()
        print(f"Coordinates {city_lat}°N {city_lng}°E")

        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        )}
        daily_data["temperature_2m"] = daily_temperature_2m
        daily_dataframe = pd.DataFrame(data = daily_data)
        daily_dataframe['lat'] = city_lat
        daily_dataframe['lng'] = city_lng
        return daily_dataframe

    @render.plot
    def plot():
        city = chosen_city()
        temperature_threshold = input.plot_temp()
        city["plot_temp"] = city["temperature_2m"] > temperature_threshold
        if 'w' in input.plot_avg():
            window_size = 7  # Approximation of days in a month
            city['w_rolling_avg'] = city['temperature_2m'].rolling(window=window_size).mean()
        if 'm' in input.plot_avg():
            window_size = 30 # Approximation of days in a month
            city['m_rolling_avg'] = city['temperature_2m'].rolling(window=window_size).mean()

        plot = (p9.ggplot(city, p9.aes(x='date', y='temperature_2m', color='plot_temp'))
            + p9.geom_point()  # Adds scatter plot points
            + p9.scale_color_manual(values={True: 'cadetblue', False: 'indianred'})
            + p9.geom_hline(yintercept=temperature_threshold, color="indianred", linetype="dashed", size=1) 
            + p9.labs(title='Temperature Over Time', x='Date', y='Temperature')
            + p9.theme(axis_text_x=p9.element_text(rotation=45, hjust=1),legend_position="none")  # Rotate x-axis labels
            + p9.scale_x_datetime(date_breaks='3 month', date_labels='%b %Y')  # Customize date breaks and labels
        )
        if 'w' in input.plot_avg():
            plot += p9.geom_line(p9.aes( y='w_rolling_avg'), color="slateblue", size=1)
        if 'm' in input.plot_avg():
            plot += p9.geom_line(p9.aes( y='m_rolling_avg'), color="gold", size=1)
        return plot
     
    @render.data_frame
    def heat_table():
        city = chosen_city()
        temp_range = np.arange(input.table_temp()[1], input.table_temp()[0]-1,-1)
        
        city_table = {
            'Temperature': temp_range,
            'Days_Below': [len(city[city['temperature_2m'] < temp]) for temp in temp_range],
            }
        city_table = pd.DataFrame(city_table)
        city_table['Proportion_Below'] = round(city_table['Days_Below'] / len(city),3)
        return render.DataGrid(city_table, width="100%",height="100%", row_selection_mode="none",)

    @render.ui
    @reactive.event(input.us_city)
    def city_coords():
        city = chosen_city()
        city_lat = city['lat'].iloc[0]
        city_lng = city['lng'].iloc[0]
        return ui.markdown(f"<p style='text-align: center;'>{round(city_lat,4)}°N, {round(city_lng,4)}°E</p>")


# run app
app = App(app_ui, server)