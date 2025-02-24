import os.path

import pandas as pd
import geopandas as gpd
import numpy as np
import dill
import base64

from sqlalchemy import create_engine, exc, text
import datetime
from AIHABs_wrappers import measure_execution_time
from warnings import warn


def get_wq_db_last_date(osm_id, feature, db_name, user, db_table, model_id=None):
    """
    Get last date db table for particular OSM id and water quality feature

    :param osm_id: OSM object id
    :param feature: Water quality feature (e.g. ChlA, PC, TSS...)
    :param db_name: Database name
    :param user: Database user
    :param db_table: Database table
    :return: Last date in the database table for particular OSM id
    """

    # Connect to PostGIS
    engine = create_engine('postgresql://{}@/{}'.format(user, db_name))


    # Test the table existence in the DB
    query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tab_name}')".format(tab_name=db_table))
    with engine.connect() as connection:
        result = connection.execute(query)
        table_exists = result.scalar()

    if not table_exists:
        sql_query = text("CREATE TABLE IF NOT EXISTS {db_table} (osm_id text, date date, feature_value double "
                         "precision, feature varchar(50), model_id varchar(50), {PID} integer)".format(
            db_table=db_table, PID='"PID"'))

        srid = 4326
        sql_query2 = text(f"SELECT AddGeometryColumn('{db_table}', 'geometry', {srid}, 'POINT', 2)")

        with engine.connect() as connection:
            connection.execute(sql_query)
            connection.execute(sql_query2)
            connection.commit()

        last_date = None
        warn(f"The table does not exist in the database. The table {db_table} will be created. The default value of "
             f"the date will be set.", stacklevel=2)

    # Get last date if DB exists
    else:
        connection = engine.connect()
        # Define SQL query
        sql_query = text("SELECT MAX(date) FROM {db_table} WHERE osm_id = '{osm_id}' and feature = '{"
                         "feature}' and model_id = '{model_id}'".format(osm_id=str(osm_id), feature=feature, db_table=db_table, model_id=model_id))

        # Running SQL query, conversion to DataFrame
        df = pd.read_sql(sql_query, connection)
        last_date = df.iloc[0,0]

    connection.close()
    engine.dispose()

    return last_date


def execute_query(connection, query):
    """
    Function for SQL query execution.

    :param connection: connection to Postgres engine
    :param query: SQL query
    :return:
    """

    result = connection.execute(query)

    return result.scalar()


def get_model_query(db_table, feature, variable=None, osm_id=None, model_name=None, is_default=False):
    """
    The set of SQL queries for choosing the requested model for a WQ feature calculation.

    :param db_table: Name of the db table wth AI models
    :param feature: Water quality feature (e.g. ChlA, PC, TSS...)
    :param variable: Variable name in the table for data selection
    :param osm_id: OSM object id
    :param model_name: Name of the model
    :param is_default: Is the model default
    :return:
    """

    if is_default:
        return text(f"SELECT {variable} FROM {db_table} WHERE is_default = true AND feature = '{feature}' ORDER BY id "
                    f"DESC LIMIT 1")
    elif osm_id and model_name:
        return text(f"SELECT {variable} FROM {db_table} WHERE osm_id = '{osm_id}' AND model_name = '{model_name}' AND "
                    f"feature = '{feature}' ORDER BY id DESC LIMIT 1")
    elif osm_id:
        return text(f"SELECT {variable} FROM {db_table} WHERE osm_id = '{osm_id}' AND feature = '{feature}' ORDER BY id DESC LIMIT 1")
    elif model_name:
        return text(f"SELECT {variable} FROM {db_table} WHERE model_name = '{model_name}' AND feature = '{feature}' "
                    f"ORDER BY id DESC LIMIT 1")
    else:
        return text(f"SELECT {variable} FROM {db_table} WHERE feature = '{feature}' ORDER BY id DESC LIMIT 1")


def select_model(db_name, user, db_models, feature='ChlA', osm_id=None, model_name=None, default=True):
    """
    Function for selecting model for a particular feature from the database.

    :param db_name: Database name
    :param user: Database user
    :param db_models: Database table with AI models
    :param feature: Water quality feature
    :param osm_id: OSM object id
    :param model_name: Name of the model
    :param default: Is the model default
    :return:
    """

    engine = create_engine(f'postgresql://{user}@/{db_name}')
    connection = engine.connect()

    # 1. test if the model for particular feature is available
    test_feature_query = text(f"SELECT 1 FROM {db_models} WHERE feature = '{feature}' LIMIT 1")
    feature_exists = execute_query(connection, test_feature_query)

    if not feature_exists:
        warn(f"The water quality feature {feature} does not exist in the database. The analysis will be stopped.", stacklevel=2)
        return None

    # 2. select by default, osm_id and name
    model_query = None
    model_id = None

    if default:
        test_default_query = text(f"SELECT 1 FROM {db_models} WHERE is_default = true AND feature = '{feature}' LIMIT 1")
        if execute_query(connection, test_default_query):
            model_query = get_model_query(db_models, feature, variable='pkl_file', is_default=True)
            model_id = get_model_query(db_models, feature, variable='model_id', is_default=True)

    if model_query is None and osm_id and model_name:
        test_osmid_name_query = text(f"SELECT 1 FROM {db_models} WHERE osm_id = '{osm_id}' AND model_name = '{model_name}' AND feature = '{feature}' LIMIT 1")
        if execute_query(connection, test_osmid_name_query):
            model_query = get_model_query(db_models, feature, variable='pkl_file', osm_id=osm_id, model_name=model_name)
            model_id = get_model_query(db_models, feature, variable='model_id', osm_id=osm_id, model_name=model_name)

    if model_query is None and model_name:
        test_model_name_query = text(f"SELECT 1 FROM {db_models} WHERE model_name = '{model_name}' AND feature = '{feature}' LIMIT 1")
        if execute_query(connection, test_model_name_query):
            model_query = get_model_query(db_models, feature, variable='pkl_file', model_name=model_name)
            model_id = get_model_query(db_models, feature, variable='model_id', model_name=model_name)

    if model_query is None and osm_id:
        test_osmid_query = text(f"SELECT 1 FROM {db_models} WHERE osm_id = '{osm_id}' AND feature = '{feature}' LIMIT 1")
        if execute_query(connection, test_osmid_query):
            model_query = get_model_query(db_models, feature, variable='pkl_file', osm_id=osm_id)
            model_id = get_model_query(db_models, feature, variable='model_id', osm_id=osm_id)

    if model_query is None:
        # In that case select default model
        test_default_query = text(
            f"SELECT 1 FROM {db_models} WHERE is_default = true AND feature = '{feature}' LIMIT 1")
        if execute_query(connection, test_default_query):
            warn(f"The requested model does not exist in the database. The default model will be used.",
                 stacklevel=2)
            model_query = get_model_query(db_models, feature, variable='pkl_file', is_default=True)
            model_id = get_model_query(db_models, feature, variable='model_id', is_default=True)
        else:
            # Select the last model if default does not exist
            warn(f"The requested model does not exist in the database. The last available model will be used.",
                 stacklevel=2)
            model_query = get_model_query(db_models, feature, variable='pkl_file')
            model_id = get_model_query(db_models, feature, variable='model_id')

    # Get prediction model from DB and model ID
    result = execute_query(connection, model_query)
    m_id = execute_query(connection, model_id)
    connection.close()
    engine.dispose()

    if result:
        result = base64.b64decode(result)
        return dill.loads(result), m_id

    return None

@measure_execution_time
def calculate_feature(feature, osm_id, db_name, user, db_bands_table, db_features_table, db_models, model_name=None,
                      default_model=False, **kwargs):
    """
    Function for calculating water quality feature for a particular OSM object from the Sentinel 2 L2A bands.

    :param feature: Water quality feature
    :param osm_id: OSM object id
    :param db_name: Database name
    :param user: Database user
    :param db_bands_table: DB table with Sentinel 2 L2A bands data
    :param db_features_table: DB table with water quality features where the calculated data will be stored
    :param db_models: DB table with AI models (stored as Pickle object)
    :param model_name: Name of the model
    :param default_model: Is the model default
    :param kwargs: Additional parameters
    :return: Output water quality dataset; Model ID
    """

    # Connect to PostGIS
    engine = create_engine('postgresql://{}@/{}'.format(user, db_name))
    connection = engine.connect()

    ## Get Pickle model and its ID from the database
    prediction_model, model_id = select_model(db_name, user, db_models, feature, osm_id, model_name, default_model)

    print("Model ID: ", model_id)
    print("Model: ", prediction_model)

    # Getting starting and ending dates for WQ feature calculations:
    try:
        start_date = get_wq_db_last_date(osm_id, feature, db_name, user, db_features_table, model_id)

        if start_date is None:
            warn("The date does not exist in the database. The default value will be set.", stacklevel=2)
            start_date = '2015-06-01'
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)

    except TypeError:
        warn("The date does not exist in the database. The default value will be set.", stacklevel=2)
        start_date = '2015-06-01'
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)

    # Get data for calculation from the bands DB table
    sql_query = text("SELECT * FROM {db_bands_table} WHERE osm_id = '{osm_id}' and date > '{start_date}'".format(
        osm_id=str(osm_id), start_date=start_date, db_bands_table=db_bands_table))
    gdf_data = gpd.read_postgis(sql_query, connection, geom_col='geometry')

    # Calculate the wq feature
    if gdf_data.empty:
        warn("The data are not available in the database. The result is None.", stacklevel=2)

        connection.close()
        engine.dispose()

        return None, model_id

    else:
        # Define input parameters for the model
        B01 = np.nan_to_num(gdf_data['B01'].values * 0.0001, nan=1.0)
        B02 = np.nan_to_num(gdf_data['B02'].values * 0.0001, nan=1.0)
        B03 = np.nan_to_num(gdf_data['B03'].values * 0.0001, nan=1.0)
        B04 = np.nan_to_num(gdf_data['B04'].values * 0.0001, nan=1.0)
        B05 = np.nan_to_num(gdf_data['B05'].values * 0.0001, nan=1.0)
        B06 = np.nan_to_num(gdf_data['B06'].values * 0.0001, nan=1.0)
        B07 = np.nan_to_num(gdf_data['B07'].values * 0.0001, nan=1.0)
        B08 = np.nan_to_num(gdf_data['B08'].values * 0.0001, nan=1.0)
        B8A = np.nan_to_num(gdf_data['B8A'].values * 0.0001, nan=1.0)
        B09 = np.nan_to_num(gdf_data['B09'].values * 0.0001, nan=1.0)
        B11 = np.nan_to_num(gdf_data['B11'].values * 0.0001, nan=1.0)
        B12 = np.nan_to_num(gdf_data['B12'].values * 0.0001, nan=1.0)

        input_data = [B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12]

        # Run the prediction model
        if prediction_model is None:
            return None, None

        # Calculate WQ feature values
        wq_values = prediction_model.predict(input_data)

        # Save the results to the database
        selected_columns = ['osm_id', 'date', 'PID', 'geometry']
        gdf_out = gdf_data[selected_columns].copy()
        gdf_out['feature_value'] = wq_values
        gdf_out['feature'] = feature
        gdf_out['model_id'] = model_id

        # Set CRS of the output GeoDataFrame geometry
        gdf_out.set_crs("EPSG:4326")

        # Save the results to the database
        gdf_out.to_postgis(db_features_table, con=engine, if_exists='append', index=False)

        connection.close()
        engine.dispose()

        return gdf_out, model_id
