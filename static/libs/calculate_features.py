# -*- coding: utf-8 -*-

import os
import sys
import pandas as pd
import geopandas as gpd
import numpy as np
import subprocess
import json
import uuid
import time

from sqlalchemy import text
import datetime
from warnings import warn


def get_wq_db_last_date(osm_id, feature, db_session, db_table, model_id=None):
    """
    Get last date from db table for particular OSM id and water quality feature

    :param osm_id: OSM object id
    :param feature: Water quality feature (e.g. ChlA, PC, TSS...)
    :param db_sessin: Database session
    :param db_table: Database table
    :return: Last date in the database table for particular OSM id
    """

    # Get DB engine
    engine = db_session.get_bind()

    # Test the table existence in the DB
    query = text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{db_table}')")
    result = db_session.execute(query)
    table_exists = result.scalar()

    if not table_exists:
        sql_query = text("CREATE TABLE IF NOT EXISTS {db_table} (osm_id text, date date, feature_value double "
                         "precision, feature varchar(50), model_id varchar(50), {PID} integer)".format(db_table=db_table, PID='"PID"'))

        srid = 4326
        sql_query2 = text(f"SELECT AddGeometryColumn('{db_table}', 'geometry', {srid}, 'POINT', 2)")
        db_session.execute(sql_query)
        db_session.execute(sql_query2)
        db_session.commit()

        last_date = None
        print(f"The table does not exist in the database. The table {db_table} will be created. The default value of the date will be set.")

    # Get last date if DB exists
    else:
        # Define SQL query
        sql_query = text(f"SELECT MAX(date) FROM {db_table} WHERE osm_id = '{osm_id}' and feature = '{feature}' and model_id = '{model_id}'")

        # Running SQL query
        result = db_session.execute(sql_query)
        last_date = result.scalar()

    return last_date
    
def calculate_feature(feature, osm_id, db_session, db_bands_table, db_features_table, db_models, model_id=None, **kwargs):
    
    """
    Function for calculating water quality feature for a particular OSM object from the Sentinel 2 L2A bands.

    :param feature: Water quality feature
    :param osm_id: OSM object id
    :param db_session: Database session
    :param db_bands_table: DB table with Sentinel 2 L2A bands data
    :param db_features_table: DB table with water quality features where the calculated data will be stored
    :param db_models: DB table with AI models (stored as Pickle object)
    :param model_name: Name of the model
    :param default_model: Is the model default
    :param kwargs: Additional parameters
    :return: Output water quality dataset; Model ID
    """
    
    # Get DB engine
    engine = db_session.get_bind()
    
    # Test the table existence in the DB
    query = text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{db_features_table}')")
    result = db_session.execute(query)
    table_exists = result.scalar()

    if not table_exists:
        print(f"The table does not exist in the database. The table {db_features_table} will be created. The result is None.")
        
        create_db_table(db_session, db_features_table)
    
    # Getting starting and ending dates for WQ feature calculations:
    print("Getting the starting date for water quality feature calculation...")
    try:
        start_date = get_wq_db_last_date(osm_id, feature, db_session, db_features_table, model_id)

        if start_date is None:
            print("The date does not exist in the database. The default value will be set.")
            start_date = '2015-06-01'
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)

    except TypeError:
        print("The date does not exist in the database. The default value will be set.")
        start_date = '2015-06-01'
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)

    # Get data for calculation from the bands DB table
    sql_query = text(f"SELECT * FROM {db_bands_table} WHERE osm_id = '{osm_id}' and date > '{start_date}'")
    gdf_data = gpd.read_postgis(sql_query, engine, geom_col='geometry')

    # Calculate the wq feature
    if gdf_data.empty:
        print("The data are not available in the database. The result is None.")

        return None

    else:
        # Calculate WQ feature values
        try:
            wq_values = predict_feature_values(db_session, model_id, db_models, gdf_data)            
            print("Water quality feature values successfully calculated.")
            
        except Exception as e:
            warn(f"Error during the prediction: {e}", stacklevel=2)
            return None

        # Save the results to the database
        selected_columns = ['osm_id', 'date', 'pid', 'geometry']
        gdf_out = gdf_data[selected_columns].copy()        
        gdf_out['feature_value'] = wq_values['fvalues'].values        
        gdf_out['feature'] = feature
        gdf_out['model_id'] = model_id

        # Set CRS of the output GeoDataFrame geometry
        gdf_out.set_crs("EPSG:4326")
        
        # Save the results to the database
        # Check if the db table partition exists for the particular OSM id
        query = text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{db_features_table}_{osm_id}')")
        result = db_session.execute(query)
        table_exists = result.scalar()
        
        if not table_exists:
            create_part_query = text(f"CREATE TABLE {db_features_table}_{osm_id} PARTITION OF {db_features_table} FOR VALUES IN ('{osm_id}');")
            db_session.execute(create_part_query)
            db_session.commit()

        # Save the results to the database
        gdf_out.to_postgis(db_features_table, con=engine, if_exists='append', index=False)

        return gdf_out

def predict_feature_values(db_session, model_id, db_models, gdf_s2data):
    
    # Convert gdf to geojson
    # Set path to temp
    csv_name = f"{uuid.uuid4()}.csv"
    csv_path = os.path.join(os.getcwd(), 'cache', csv_name)
    
    gdf_s2data.to_csv(csv_path) 
    
    # Check if the file is available
    print("Waiting for data to be available...")
    t0 = time.time()
    while not os.path.exists(csv_path):
        if time.time() - t0 > 360:                  # up to 6 minutes
            print(f"Data are not available.")
        time.sleep(0.1) 
    
    # Set env paths
    # Get model env name
    query = text(f"SELECT env_name FROM {db_models} WHERE model_id = '{model_id}'")
    env_name = db_session.execute(query).scalar()    
    # Create path to service env
    
    cur_env_path = sys.prefix
    envs_path = os.path.split(cur_env_path)[0]
    service_env_path = os.path.join(envs_path, env_name, "bin", "python")
    
    # Get service path
    models_service_path = os.path.join(os.getcwd(), 'RWQForecast', 'static', 'services', 'pred_models_service.py')
    
    # Run the service using subprocess
    try:
        result = subprocess.run([service_env_path, models_service_path, str(model_id), str(db_models), str(csv_path)],
            capture_output=True,
            text=True,
            check=True)
        
        # Get results
        out_path = result.stdout.strip()
        in_df = pd.read_csv(out_path)
        
        return in_df
    
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr} 

def create_db_table(db_session, db_features_table):
    create_table_query = text(f"""
    CREATE TABLE IF NOT EXISTS {db_features_table} (        
        osm_id	VARCHAR(50),
        date DATE,
        pid	bigint,
        geometry geometry(Point, 4326),
        feature_value FLOAT,
        feature VARCHAR(50),
        model_id VARCHAR(50)        
    )
    PARTITION BY LIST (osm_id);
    """)
    db_session.execute(create_table_query)
    db_session.commit()
    
    return