import json
import os
import time
import openeo
import warnings
import scipy.signal
import uuid

import pandas as pd
import numpy as np
import geopandas as gpd

from datetime import datetime, timedelta
from sqlalchemy import exc, text
from shapely.geometry import Point

from .get_random_points import get_sampling_points


def authenticate_OEO():
    # Authenticate
    connection = openeo.connect(url="openeo.dataspace.copernicus.eu")
    connection.authenticate_oidc()

    return connection

def getLastDateInDB(osm_id, db_session, db_table):
    """
    Get last date in db table for particular OSM id

    :param osm_id: OSM object id
    :param db_sessin: Database session
    :param db_table: Database table
    :return: Last date in the database table for particular OSM id
    """

    engine = db_session.get_bind()

    try:              
        # Define SQL query
        sql_query = text("SELECT MAX(date) FROM {db_table} WHERE osm_id = '{osm_id}'".format(
            osm_id=str(osm_id), db_table=db_table))

        # Running SQL query, conversion to DataFrame
        df = pd.read_sql(sql_query, engine)

        # Get last date
        last_date = df.iloc[0,0]

    except exc.NoSuchTableError:
        print("The date does not exist in the database. The default value will be set.")
        last_date = None

    return last_date

def process_s2_points_OEO(client_id, client_secret, osm_id, point_layer, start_date, end_date, db_session, db_table, oeo_backend_url="https://openeo.dataspace.copernicus.eu", max_cc=30, cloud_mask=True):
    """
    The function processes Sentinel-2 satellite data from the Copernicus Dataspace Ecosystem. The function
    retrieves data based on the specified parameters (cloud mask) for randomly selected points within the reservoir (
    point layer). The S2 data are downloaded for defined time period. The data are stored to the PostGIS database.
    The output is a GeoDataFrame.

    Parameters:
    :param connection: OpenEO connection
    :param osm_id: OSM object id
    :param point_layer: Point layer (GeoDataFrame)
    :param start_date: Start date
    :param end_date: End date
    :param db_session: Database session
    :param db_table: Sentinel-2 bands data database table
    :param max_cc: Maximum cloud cover
    :param cloud_mask: Apply cloud mask
    :return: GeoDataFrame with Sentinel-2 data for the randomly selected points for the defined time period
    """

    # Authenticate Open EO account
    connection = openeo.connect(url=oeo_backend_url, auto_validate=False)
    connection.authenticate_oidc_client_credentials(client_id=client_id, client_secret=client_secret)

    # Transform input GeoDataFrame layer into json
    points = json.loads(point_layer.to_json())

    # Connect to PostGIS
    engine = db_session.get_bind()

    # Get bands names
    collection_info = connection.describe_collection("SENTINEL2_L2A")
    bands = collection_info['cube:dimensions']['bands']
    band_list = bands['values'][0:15]

    # Getting data
    datacube = connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=[start_date, end_date],
        max_cloud_cover=max_cc,
        bands=band_list,
    )

    # Apply cloud mask etc.
    if cloud_mask:

        scl = datacube.band("SCL")
        mask = ~((scl == 6) | (scl == 2))

        # 2D gaussian kernel
        g = scipy.signal.windows.gaussian(11, std=1.6)
        kernel = np.outer(g, g)
        kernel = kernel / kernel.sum()

        # Morphological dilation of mask: convolution + threshold
        mask = mask.apply_kernel(kernel)
        mask = mask > 0.1

        datacube_masked = datacube.mask(mask)

    else:
        datacube_masked = datacube

    # Datacube aggregation
    aggregated = datacube_masked.aggregate_spatial(
        geometries=points,
        reducer="mean",
    )

    # Run the job
    job = aggregated.create_job(title=f"{osm_id}_{start_date}_{end_date}", out_format="CSV")

    # Get job ID
    jobid = job.job_id

    print(f"Job ID: {jobid}")

    # Start the job
    try:
        job.start_and_wait()

    except Exception as e:
        print(e)
        engine.dispose()
        return jobid

    # Download the results
    try:
        if job.status() == 'finished':
            # Create temporary CSV file
            csv_file = f"{uuid.uuid4()}.csv"
            csv_path = os.path.join(os.getcwd(), 'cache', csv_file)       # XXX: přesměrovat do tmp složky

            # Download the results
            job.get_results().download_file(csv_path)

            # Check if the file is available
            print("Waiting for data to be available...")
            t0 = time.time()
            while not os.path.exists(csv_path):
                if time.time() - t0 > 360:                  # up to 6 minutes
                    print(f"Data are not available.")
                time.sleep(1)

            df = pd.read_csv(csv_path, skip_blank_lines=True)

            print(f"Sentinel-2 data for period from {start_date} to {end_date} has been uploaded to the DB!")
            

            print("Writing data to the PostGIS table:")
            # Convert to GeoDataFrame
            if not df.empty:
                
                # Convert date do isoformat
                df['date'] = pd.to_datetime(df['date']).dt.date

                # Remove missing values
                df_all = df.dropna(axis=0, how='any')

                # Rename columns
                df_all = df_all.rename(columns={'feature_index': 'PID'})
                for i in range(0, len(band_list)):
                    df_all = df_all.rename(columns={'avg(band_{})'.format(i): band_list[i]})

                # Add OSM id
                df_all['osm_id'] = osm_id

                # Convert to GeoDataFrame
                latlon = pd.DataFrame(point_layer['PID'])
                latlon['lat'] = point_layer.geometry.y
                latlon['lon'] = point_layer.geometry.x
                df_all = df_all.merge(latlon, on='PID', how='left')

                geometries = [Point(xy) for xy in zip(df_all['lon'], df_all['lat'])]
                gdf_out = gpd.GeoDataFrame(df_all, geometry=geometries, crs='epsg:4326')
                gdf_out.rename(columns={'PID':'pid', 'B01':'b01', 'B02':'b02', 'B03':'b03', 'B04':'b04', 'B05':'b05', 'B06':'b06', 'B07':'b07', 'B08':'b08', 'B8A':'b8a', 'B09':'b09', 'B11':'b11', 'B12':'b12', 'WVP':'wvp', 'AOT':'aot', 'SCL':'scl'}, inplace=True)                

                # Save the results to the database
                # Check if the db table partition exists for the particular OSM id
                query = text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{db_table}_{osm_id}')")
                result = db_session.execute(query)
                table_exists = result.scalar()
                
                if not table_exists:
                    create_part_query = text(f"CREATE TABLE {db_table}_{osm_id} PARTITION OF {db_table} FOR VALUES IN ('{osm_id}');")
                    db_session.execute(create_part_query)
                    db_session.commit()
                
                # Write to PostGIS
                gdf_out.to_postgis(db_table, con=engine, if_exists='append', index=False)
                
                print('OK')
                
            else:
                print(f'Dataset for time priod from {start_date} to {end_date} is empty.')              

            # Remove the temporary file
            print(f"Removing temporary file {csv_file}")
            if os.path.exists(csv_path):
                os.remove(csv_path)

            return jobid

        else:
            print(f"Data are not available.")
            
            return jobid

    except Exception as e:
        print(e)
        print(f"Data are not available.")
        
        return jobid

def check_job_error(connection, jobid=None):
    """
    Check if the dataset is empty

    :param connection: OpenEO connection
    :param jobid:
    :return:
    """
    # Connection to OEO
    if not connection or connection is None:
        warnings.warn("Connection to OpenEO is not established!", stacklevel=2)
        
        return

    # Check if the error is in the log
    if jobid is not None:
        status = connection.job(jobid).status()

        if status == 'error':

            # Check if the data are available
            log = connection.job(jobid).logs()

            for i in log:

                # subs_fail = "Exception during Spark execution"
                subs_nodata = "NoDataAvailable"

                if subs_nodata in i['message']:
                    print("No data available for the time window and spatial extent")
                    return False

            # In case of unspecific error
            print("Unspecific error...")
            return True

        # In case the job was ok
        else:
            print("Dataset OK")
            return False

    # In case job_id does not exist
    else:
        print("Unspecific error... Job ID does not exist")
        return True

def get_s2_points_OEO(client_id, client_secret, osm_id, db_session, db_table_reservoirs, db_table_points, db_table_S2_points_data, oeo_backend_url="https://openeo.dataspace.copernicus.eu",
                       start_date=None, end_date=None, n_points_max=10000, **kwargs):
    """
    This function is a wrapper for the get_sentinel2_data function. It calls it with the defined parameters,
    manage the time windows and the database connection.

    :param connection: OpenEO connection
    :param osm_id: OSM water reservoir id
    :param db_session: Database session
    :param db_table_reservoirs: Database table with water reservoirs
    :param db_table_points: Database table with points for reservoirs
    :param db_table_S2_points_data: Database table with Sentinel-2 data where the data are stored
    :param start_date: Start date
    :param end_date: End date
    :param n_points_max: Maximum number of points for water reservoir
    :param kwargs: Kwargs
    :return: None
    """

    print(f"Running the analysis for the reservoir with OSM ID: {osm_id}")
    
    # Get points
    point_layer = get_sampling_points(osm_id, db_session, db_table_reservoirs, db_table_points)

    # Check if table exists and create new one if not
    query = text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{db_table_S2_points_data}');")
    result = db_session.execute(query)
    exists = result.scalar()
    
    print(f"Table {db_table_S2_points_data} exists: {exists}")

    # Set start date
    if exists:
        # Get last date from database
        st_date = getLastDateInDB(osm_id, db_session, db_table_S2_points_data)

    else:
        # Create the Sentinel-2 points data table in the DB
        create_db_table(db_session, db_table_S2_points_data)
        st_date = None

    if st_date is not None:
        st_date = st_date + timedelta(days=1)
    else:
        if start_date is None:
            start_date = '2015-06-01'

        st_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    
    # Set end date
    if end_date is None:
        end_date = datetime.now().date()  # Up to today
    else:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    if st_date >= end_date:
        print(f'Data for period from {st_date} to {end_date} are not available. Data will not be downloaded')

        return

    print(f'Data for period from {st_date} to {end_date} will be downloaded')

    # Set time windows
    # Create chunks for time series
    # Get possible length of steps (chunks)
    n_points: int = len(point_layer)

    step_length = int(n_points_max) // (n_points/100)

    n_days = (end_date - st_date).days

    n_chunks = n_days // step_length + 1

    # Create time windows
    t_delta = int((end_date - st_date).days / n_chunks)

    if t_delta < 2:
        t_delta = 2

    freq = '{tdelta}D'.format(tdelta=t_delta)
    date_range = pd.date_range(start=st_date, end=end_date, freq=freq)
    slots = [(date_range[i].date().isoformat(), (date_range[i + 1] - timedelta(days=1)).date().isoformat()) for i in
             range(len(date_range) - 1)]

    # Get Sentinel-2 data - run the job
    # Loop over the time windows
    for i in range(len(slots)):
        print(f"Data for time slot from {slots[i][0]} to {slots[i][1]} will be downloaded")

        # Try to get Sentinel-2 data for the time window. There are 2 attempts
        dataset_err = True

        # Attempt to get Sentinel-2 data
        attempt_no = 1
        while dataset_err:
            try:
                print(f"Attempt no. {attempt_no} to get Sentinel 2 data.")
                jobid = process_s2_points_OEO(client_id, client_secret, osm_id, point_layer, slots[i][0], slots[i][1], db_session, db_table_S2_points_data, oeo_backend_url=oeo_backend_url)
                print(f"Job ID: {jobid}")
                dataset_err = False

            except Exception as e:
                print(f"Attempt no. {attempt_no} to get Sentinel 2 data failed. Error: {str(e)}")
                jobid = None

            # # Check if there is an error in the job
            # dataset_err = check_job_error(connection, jobid)

            if dataset_err:
                warnings.warn(f"Attempt no. {attempt_no} to get Sentinel 2 data failed.", stacklevel=2)
                time.sleep(5)
                if attempt_no == 3:
                    break
            attempt_no = attempt_no + 1

    return

def create_db_table(db_session, s2_point_data_table):
    create_table_query = text(f"""
    CREATE TABLE IF NOT EXISTS {s2_point_data_table} (        
        date DATE,
        pid	bigint,
        b01	FLOAT,
        b02	FLOAT,
        b03	FLOAT,
        b04	FLOAT,
        b05	FLOAT,
        b06	FLOAT,
        b07	FLOAT,
        b08	FLOAT,
        b8a	FLOAT,
        b09	FLOAT,
        b11	FLOAT,
        b12	FLOAT,
        wvp	FLOAT,
        aot	FLOAT,
        scl	FLOAT,
        osm_id	VARCHAR(50),
        lat	FLOAT,
        lon	FLOAT,
        geometry geometry(Point, 4326)
    )
    PARTITION BY LIST (osm_id);
    """)
    db_session.execute(create_table_query)
    db_session.commit()
    
    return
