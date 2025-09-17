import pandas as pd
import openmeteo_requests
import requests_cache
import geopandas as gpd

from retry_requests import retry
from sqlalchemy import create_engine, exc, text
from datetime import datetime, timedelta
import warnings


def getHistoricalMeteoData(osm_id, meteo_features, db_session, db_table, vect_db_table, time_zone='GMT'):
    """
    Get meteodata from Open-Meteo Historical Weather API and save it to PostGIS database for the particular OSM id and its location. The function fulfill the last data in the database. The time serries is daily from 2015-06-01 till one day before today.

    :param osm_id: ID of OSM object (water reservoir)
    :param meteo_features: List of meteo features
    :param user: Postgres DB user
    :param db_name: Postgres database name
    :param db_table: Postgres database table for meteo history
    :param vect_db_table: PostGIS database table with water reservoirs
    :param time_zone: Time zone. Default GMT
    :return:
    """

    # Connect to PostGIS
    engine = db_session.get_bind()

    # Get latitude and longitude
    lat, lon = getLatLon(osm_id, db_session, vect_db_table)

    # Getting the last date from database for particular OSM id.
    try:
        last_db_date = getLastDateInDB(osm_id, db_session, db_table)

        if last_db_date == None:
            datum = '2015-06-01'
            last_db_date = datetime.strptime(datum, "%Y-%m-%d").date()

        else:
            # Remove last date from database.
            sql_query = text(f"DELETE FROM {db_table} WHERE osm_id = :val1 AND date = :val2")

            db_session.execute(sql_query, {'val1': str(osm_id), 'val2': last_db_date})
            db_session.commit()

        start_date = last_db_date

    except:
        datum = "2015-06-01"
        start_date = datetime.strptime(datum, "%Y-%m-%d").date()

    end_date = datetime.now().date() - timedelta(days=1)

    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": meteo_features,
        "timezone": time_zone
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    # print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    # print(f"Elevation {response.Elevation()} m asl")
    # print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    # print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s"),

    daily = response.Daily()

    daily_data = {"date": pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left"
    )}

    # Process daily data. The order of variables needs to be the same as requested.
    for i in range(len(meteo_features)):
        daily_data[meteo_features[i]] = daily.Variables(i).ValuesAsNumpy()

    daily_meteo = pd.DataFrame(data=daily_data)

    # Handling date
    daily_meteo["date"] = daily_meteo["date"].dt.tz_localize(None).dt.date

    # Add OSM ID to dataframe
    daily_meteo["osm_id"] = str(osm_id)

    # Save data to PostGIS
    daily_meteo.to_sql(db_table, con=engine, if_exists='append', index=False)

    return

def getPredictedMeteoData(osm_id, meteo_features, db_session, db_table_forecast, db_table_reservoirs, forecast_days=10, time_zone='GMT'):
    """
    Get meteodata forecast from Open-Meteo Forecast API in daily step for particular OSM object id. The results are
    saved to database.

    :param osm_id: OSM object id (water reservoir)
    :param meteo_features: List of weather variables to get
    :param user: Database user
    :param db_name: Database name
    :param db_table_forecast: Database table with meteo forecast
    :param db_table_reservoirs: PostGIS database table with water reservoirs
    :param forecast_days: Number of days to forecast. Default = 10, max = 16
    :param time_zone: Time zone. Default = 'GMT'
    :return: Dataframe with meteo data forecast
    """

    if forecast_days > 16:
        warnings.warn("The maximum number of days to forecast is 16. The forecast will be set to 16 days", stacklevel=2)
        forecast_days = 16

    # Connect to PostGIS
    engine = db_session.get_bind()

    # Get latitude and longitude
    lat, lon = getLatLon(osm_id, db_session, db_table_reservoirs)

    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": meteo_features,
        "timezone": time_zone,
        "forecast_days": forecast_days
    }

    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    # print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    # print(f"Elevation {response.Elevation()} m asl")
    # print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    # print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s"),

    daily = response.Daily()

    daily_data = {"date": pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s", utc=True),
        end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=daily.Interval()),
        inclusive="left"
    )}

    # Process daily data. The order of variables needs to be the same as requested.
    for i in range(len(meteo_features)):
        daily_data[meteo_features[i]] = daily.Variables(i).ValuesAsNumpy()

    daily_forecast = pd.DataFrame(data=daily_data)
    daily_forecast["osm_id"] = str(osm_id)

    # Handling date
    daily_forecast["date"] = daily_forecast["date"].dt.tz_localize(None).dt.date

    # Remove the old data from Postgres
    # Check if table exists and create new one if not
    query = text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tab_name}')".format(
            tab_name=db_table_forecast))

    # Vykonání dotazu s parametrem
    # with engine.connect() as connection:
    #     result = connection.execute(query)
    #     exists = result.scalar()
    result = db_session.execute(query)
    exists = result.scalar()

    if exists:
        print("Table {} exists".format(db_table_forecast))
        db_session.execute(text("DELETE FROM {db_table} WHERE osm_id = '{osm_id}'".format(db_table=db_table_forecast, osm_id=str(osm_id))))
        db_session.commit()


    # Save new data to Postgres
    daily_forecast.to_sql(db_table_forecast, con=engine, if_exists='append', index=False)

    return daily_forecast

def getLatLon(osm_id, db_session, db_table):
    """
    Get latitude and longitude from OSM id

    :param osm_id: OSM object id
    :param db_name: Database name
    :param user: Database user
    :param db_table: Database table
    :return: Tuple of latitude and longitude
    """

    # Připojení k databázi PostGIS
    engine = db_session.get_bind()

    # Get geometry for polygon
    sql_query = text("SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(osm_id=str(osm_id), db_table=db_table))
    gdf = gpd.read_postgis(sql_query, engine, geom_col='geometry')
    gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs='epsg:4326')

    # Get latitude and longitude
    epsg_new = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(epsg_new)

    centroid_utm = gdf_utm['geometry'].centroid
    centroid_wgs = centroid_utm.to_crs(gdf.crs)

    lon = centroid_wgs.x.mean()
    lat = centroid_wgs.y.mean()

    return lat, lon

def getLastDateInDB(osm_id, db_session, db_table):
    """
    Get last date db table for particular OSM id

    :param osm_id: OSM object id
    :param db_name: Database name
    :param user: Database user
    :param db_table: Database table
    :return: Last date in the database table for particular OSM id
    """

    try:
        # Connect to PostGIS
        engine = db_session.get_bind()

        # Define SQL query
        sql_query = text("SELECT MAX(date) FROM {db_table} WHERE osm_id = '{osm_id}'".format(
            osm_id=str(osm_id), db_table=db_table))

        # Running SQL query, conversion to DataFrame
        df = pd.read_sql(sql_query, engine)

        last_date = df.iloc[0,0]

    except exc.NoSuchTableError:
        print("The date does not exist in the database. The default value will be set.")
        last_date = None

    return last_date


"""
@software{Zippenfenig_Open-Meteo,
  author = {Zippenfenig, Patrick},
  doi = {10.5281/zenodo.7970649},
  license = {CC-BY-4.0},
  title = {Open-Meteo.com Weather API},
  year = {2023},
  copyright = {Creative Commons Attribution 4.0 International},
  url = {https://open-meteo.com/}
}
@misc{Hersbach_ERA5,
  doi = {10.24381/cds.adbb2d47},
  url = {https://cds.climate.copernicus.eu/doi/10.24381/cds.adbb2d47},
  author = {Hersbach, H., Bell, B., Berrisford, P., Biavati, G., Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N.},
  title = {ERA5 hourly data on single levels from 1940 to present},
  publisher = {ECMWF},
  year = {2023}
}
@misc{Munoz_ERA5_LAND,
  doi = {10.24381/CDS.E2161BAC},
  url = {https://cds.climate.copernicus.eu/doi/10.24381/cds.e2161bac},
  author = {Muñoz Sabater, J.},
  title = {ERA5-Land hourly data from 2001 to present},
  publisher = {ECMWF},
  year = {2019}
}
@misc{Schimanke_CERRA,
  doi = {10.24381/CDS.622A565A},
  url = {https://cds.climate.copernicus.eu/doi/10.24381/cds.622a565a},
  author = {Schimanke S., Ridal M., Le Moigne P., Berggren L., Undén P., Randriamampianina R., Andrea U., Bazile E., Bertelsen A., Brousseau P., Dahlgren P., Edvinsson L., El Said A., Glinton M., Hopsch S., Isaksson L., Mladek R., Olsson E., Verrelle A., Wang Z.Q.},
  title = {CERRA sub-daily regional reanalysis data for Europe on single levels from 1984 to present},
  publisher = {ECMWF},
  year = {2021}
}
"""


