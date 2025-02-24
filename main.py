from flask import Flask, request, jsonify, render_template, redirect, flash, url_for, Blueprint, current_app
from flask_login import login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, exc, text
from geoalchemy2 import Geometry
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon
import os
import time
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import smtplib
import json
from flask_mail import Message
from dotenv import load_dotenv
from scipy.stats import sem, t
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import zoom
from datetime import datetime, timedelta
from . import db, mail


main = Blueprint('main',__name__)

# DB tables
water_reservoirs = 'reservoirs'
db_results = "wq_points_results"        # TODO: Změnit na imputovaná data!!!

# Create the AIHABs object
# aihabs = AIHABs()     # TODO: create the AIHABs object, uncomment the line
# aihabs.db_name = db_name
# aihabs.db_table_reservoirs = water_reservoirs
# aihabs.freq = 'D'
# aihabs.t_shift = 3

# Set the minimum area of the reservoir
min_area = 1.0      # TODO: possibly get it from the setting file

@main.route('/')
def index():
    return render_template('index.html')

@main.route("/profile")
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@main.route("/home")
def home():
    return render_template('index.html')

@main.route("/select")
@login_required
def select_wr():
    return render_template('select_wr.html')

@main.route("/processing")
@login_required
def processing():
    return render_template('processing.html')

@main.route("/about")
def about():
    return render_template('about.html')

@main.route("/ackn")
def acknowledgement():
    return render_template('ackn.html')

@main.route("/contacts")
def contacts():
    return render_template('contacts.html')

@main.route("/gdpr")
def gdpr():
    return render_template('gdpr.html')

@main.route('/select_waterbody', methods=['POST'])
@login_required
def select_waterbody():
    
    # Get data from the frontend
    data = request.json
    osm_id = data.get("osm_id")                 # get OSM_ID from the map
    reserv_name = data.get("name")              # get name of the layer from the map
    lyr_point_position = data.get("firstVrt")   # get first vertex position of the layer
    wqf_name = data.get("wq_param")           # get wq_feature number (0: ChlA default)

    # Get layer from OSMNX for particular OSM_ID and save it to database
    # 1. Check if the reservoir is already in the DB
    query = text(f"SELECT EXISTS (SELECT * FROM {water_reservoirs} WHERE osm_id = '{osm_id}')")
    try:
        result = db.session.execute(query)
        result = result.scalar()
    except exc.SQLAlchemyError as e:
        print(f"Error: {e}")
        result = False

    # 2. Download a polygon for the particular OSM_ID from the OSMNX
    if not result:
        # Get data from OSMNX
        gdf = ox.features_from_point((lyr_point_position['lat'], lyr_point_position['lng']),tags={"natural":"water"}, dist=20)
        gdf['osm_id'] = gdf.index.get_level_values('id')

        # Select the polygon with corresponding OSM_ID
        gdf_sel_orig = gdf[gdf['osm_id'] == np.int64(osm_id)]

        # 3 Calculate the area of the polygon        
        epsg_orig = "EPSG:4326"
        epsg_new = gdf_sel_orig.estimate_utm_crs()
        gdf_utm = gdf_sel_orig.to_crs(epsg_new)

        if 'area' not in gdf_utm.columns:
            gdf_utm['area'] = gdf_utm.area/10000
            gdf_utm["area"] = gdf_utm["area"].round(2)

        # Select the polygon with the area >= min_area
        gdf_sel_utm = gdf_utm.loc[(gdf_utm['area'] >= min_area)]

        # Conversion to WGS 84
        if not gdf_sel_utm.empty:
            gdf_sel_wgs = gdf_sel_utm.to_crs(epsg_orig)     # Convert to WGS 84
            gdf_sel_wgs.reset_index(drop=True, inplace=True)
    
            # Select the columns for the DB table
            gdf_select = gdf_sel_wgs[['osm_id', 'name', 'area', 'geometry']]

            # 4. Add the polygon (gdf) to the DB table
            gdf_select.to_postgis('reservoirs', db.engine, if_exists='append', index=False)
            
        else:
            print("The reservoir is too small for the calculation.")
            e_subject = 'The forecast has not been finished'
            e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has not been finished. The reservoir is too small for the calculation.'
            # Send the info e-mail
            sendInfoEmail(current_user.email, e_subject, e_content)

            # return render_template("select_wr.html")
            flash("The reservoir is too small for the calculation.", 'warning')
            return redirect(url_for('main.results'))
            # TODO: Vypsat chybovou hlášku na stránku

    else:
        print("The reservoir is already in the DB.")

    # 5. Clear the cache
    try:
        cache_path = "cache"
        clear_old_cache(cache_path, 600)
    except Exception:
        pass

    # 6. Start the calculation process  # TODO: Uncomment the code
    # Set the parameters for the AIHABs object
    # aihabs.osm_id = osm_id    

    # Run the calculation process
    # try:
    #     aihabs.run_analyse()      # Run the calculation process. TODO: finish the function
    # except Exception as e:
    #     print(f"Error in the calculation process: {e}")
    #     e_subject = 'The forecast has not been finished'
    #     e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has not been finished. The calculation process has failed.'
    #     # Send the info e-mail
    #     sendInfoEmail(current_user.email, e_subject, e_content)

    #     return render_template("select_wr.html")

    # 7. Add the OSM_ID to the list of OSM_IDs for the particular user      # TODO: add the OSM_ID to the list of OSM_IDs for the particular user

    # 8. Send info e-mail
    print(f"Sending e-mail to: {current_user.email}")
    
    # Define the e-mail subject and content
    e_subject = 'The forecast has been finished'
    results_url = url_for('main.results', _external=True)
    e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has been finished. The results are available at the results page: {results_url}.'

    # Send the info e-mail
    sendInfoEmail(current_user.email, e_subject, e_content)

    return render_template("select_wr.html")

@main.route("/results")
@login_required
def results():
    return render_template("results.html")

@main.route("/results", methods=['POST'])
def addDataToMap():
    """Get the water reservoirs from the DB and add them to the map.
    """

    # Get the water reservoirs from the DB
    # 1. Define list of OSM_IDs for particular user     # TODO: get the list from the DB - odkomentovat a upravit vstupy
    # user_table = 'users'
    # user_id = ...                                         # TODO: get the user_id from the DB
    # query = text(f"SELECT DISTINCT osm_id FROM {user_table} where user_id = {user_id}")  # Get the list of OSM_ID from the DB
    # query2 = text("SELECT * FROM reservoirs WHERE osm_id IN :osm_ids")                   # Selection of the reservoirs for the particular user
    
    # # Get the list of OSM_IDs from the DB
    # df_osm_ids = pd.read_sql_query(query, db.engine)
    # osm_ids = df_osm_ids['osm_id'].tolist()
    
    # # 2. Get the water reservoirs from the DB for list of OSM_IDs for the particular user
    # gdf_reservoirs = gpd.read_postgis(query2, db.engine, geom_col='geometry', params={'osm_ids': tuple(osm_ids)})
    
    # Pracovní verze    
    query = text("SELECT * FROM reservoirs")            # TODO: smaž po doplnění    
    gdf_reservoirs = gpd.read_postgis(query, db.engine, geom_col='geometry')

    # 3. Add the reservoirs to the map
    json_data = jsonify(json.loads(gdf_reservoirs.to_json()))

    return json_data

@main.route("/get_data", methods=['GET'])
def set_data_to_selectBox():
    """
    Get the list of OSM_IDs and reservoir names from the DB and add the list to the selection box.
    """
    # 1. Get the list of OSM_IDs and reservoir names from the DB for the particular user
    # user_table = 'users'
    # user_id = ...                                         # TODO: get the user_id from the DB
    # query = text(f"SELECT DISTINCT osm_id FROM {user_table} where user_id = {user_id}")  # Get the list of OSM_ID from the DB
    # query2 = text("SELECT osm_id, name FROM reservoirs WHERE osm_id IN :osm_ids")                   # Selection of the reservoirs for the particular user
    
    # # Get the list of OSM_IDs from the DB
    # df_osm_ids = pd.read_sql_query(query, db.engine)
    # osm_ids = df_osm_ids['osm_id'].tolist()
    
    # # 2. Get the water reservoirs from the DB for list of OSM_IDs for the particular user
    # df_data = pd.read_sql_query(query2, db.engine)
    
    
    # Get the list of OSM_IDs from the DB    
    df_data = pd.read_sql_query("SELECT osm_id, name FROM reservoirs", db.engine)       # TODO: smaž po doplnění

    data_json = df_data.to_json(orient='records')
    
    return jsonify(data_json)

@main.route("/ts_data", methods=['POST'])
def ts_data():
    """Get the time series data for the particular reservoir.
    """
    
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']

    # Get the time series data for the particular reservoir from the DB
    query = text(f"SELECT date, feature_value FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' ORDER BY date")  # Get the time series data for the particular reservoir
    
    df = pd.read_sql_query(query, db.engine)

    # Calculation of median and mean for dates
    aggregated = df.groupby('date')['feature_value'].agg(
        mean='mean',
        median='median'
    ).reset_index()

    # Add confidence interval to the dataframe
    ci = df.groupby('date')['feature_value'].apply(confidence_interval).reset_index(name='ci')
    aggregated['ci_lower'] = ci['ci'].apply(lambda x: x[0])
    aggregated['ci_upper'] = ci['ci'].apply(lambda x: x[1])
    
    # Convert the date to string
    aggregated["date"] = pd.to_datetime(aggregated["date"]).dt.strftime('%Y-%m-%d')
    
    # Convert the dataframe to JSON
    data_json = aggregated.to_json(orient='records')
    data_json = json.loads(data_json)

    return jsonify({'data': data_json})

@main.route("/forecast_data", methods=['POST'])
def forecast_data():
    """Get the forecast time series data for the particular reservoir."""
    
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']

    # Get the time series data for the particular reservoir from the DB
    query = text(f"SELECT date, feature_value FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' ORDER BY date")  # Get the time series data for the particular reservoir
    
    df = pd.read_sql_query(query, db.engine)

    # Calculation of median and mean for dates
    aggregated = df.groupby('date')['feature_value'].agg(
        mean='mean',
        median='median'
    ).reset_index()

    # Add confidence interval to the dataframe
    ci = df.groupby('date')['feature_value'].apply(confidence_interval).reset_index(name='ci')
    aggregated['ci_lower'] = ci['ci'].apply(lambda x: x[0])
    aggregated['ci_upper'] = ci['ci'].apply(lambda x: x[1])
    
    # Convert the date to string
    aggregated["date"] = pd.to_datetime(aggregated["date"]).dt.strftime('%Y-%m-%d')
    
    # Convert the dataframe to JSON
    data_json = aggregated.to_json(orient='records')
    data_json = json.loads(data_json)

    return jsonify({'data': data_json})

@main.route("/interpolate_data", methods=['POST'])
def interpolate_data():
    """Make an interpolation of the data for the particular reservoir and date.
    """
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']
    date = data['date']
    fvalue = "feature_value"
    
    print(f"Interpolating the data for the reservoir: {osm_id}, feature: {feature}, date: {date}")
        
    # Get the data for the particular reservoir and date from the DB
    query = text(f"SELECT * FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date}'")  # Get the time series data for the particular reservoir
    gdf_data = gpd.read_postgis(query, db.engine, geom_col='geometry')
    
    # Get reservoir polygon from the DB
    query_wr = text(f"SELECT geometry FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")  # Get the time series data for the particular reservoir
    gdf_wr = gpd.read_postgis(query_wr, db.engine, geom_col='geometry')

    # Rasterize data and mask 
    np_data, np_mask = convert_data_to_nparray(gdf_data, gdf_wr, fvalue)

    # Otočení obrazu
    np_array = np.flipud(np_data)
    np_mask = np.flipud(np_mask)
    
    # Data reduction
    n_min = 50000
    
    n_vals = np_array.shape[0] * np_array.shape[1]
    
    if n_vals > n_min:
        rel = np.sqrt(n_min/n_vals)

        new_rows = np_array.shape[0] * rel
        new_cols = np_array.shape[1] * rel
            
        # Cílové rozlišení (např. 100x100)
        target_shape = (int(new_rows), int(new_cols))

        # Výpočet měřítka převzorkování
        scale_y = target_shape[0] / np_array.shape[0]
        scale_x = target_shape[1] / np_array.shape[1]

        # Inicializace nové matice
        np_array_new = np.full(target_shape, np.nan)

        # Najít pozice nenulových hodnot
        y_coords, x_coords = np.where(~np.isnan(np_array))

        # Převod souřadnic do nové matice
        new_y_coords = (y_coords * scale_y).astype(int)
        new_x_coords = (x_coords * scale_x).astype(int)

        # Zapsání hodnot do nové matice
        for old_y, old_x, new_y, new_x in zip(y_coords, x_coords, new_y_coords, new_x_coords):
            np_array_new[new_y, new_x] = np_array[old_y, old_x]

        # Resampling of the mask
        p_r = new_rows/np_array.shape[0]
        p_c = new_cols/np_array.shape[1]

        np_mask_new = zoom(np_mask, (p_r,p_c), order = 0, grid_mode=True, mode = 'grid-constant') 

    else:
        np_array_new = np_array
        np_mask_new = np_mask
    
    # Replacing np.nan to None
    lyr_list = [np_array_new, np_mask_new]
    cleaned_lyrs = []    
    
    for lyr in lyr_list:
        z_cleaned = lyr.tolist()  # Změní numpy pole na seznamy
        for i in range(len(z_cleaned)):
            z_cleaned[i] = [None if np.isnan(val) else val for val in z_cleaned[i]]
        cleaned_lyrs.append(z_cleaned)
    
    x = list(range(np_array.shape[1]))  # Odpovídá počtu sloupců
    y = list(range(np_array.shape[0]))  # Odpovídá počtu řádků
    
    data = {
        'x': x,
        'y': y,
        'z': cleaned_lyrs[0],
        'm': cleaned_lyrs[1]}
    
    # Convert the data to json for the export 
    return jsonify(data)

@main.route("/data_info", methods=['POST'])
def data_info():                                # TODO: dodělat! --> přidat odkaz na použitý model 
    """
    Information about water reservoir and dataset
    """
    
    # Get data from frontend
    data = request.json
    osm_id = data['osm_id']
    feature = data['feature']
    wr_name = data['wr_name']
    
    # Get area from DB
    query_area = text(f"SELECT area FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")
    df_wr_area = pd.read_sql_query(query_area, db.engine)
    wr_area = df_wr_area.iloc[0, 0]
        
    # Get date interval for historical data  
    query_date = text(f"SELECT MIN(date) AS min_date, MAX(date) as max_date FROM {db_results} WHERE osm_id = '{osm_id}'")
    df_dates = pd.read_sql_query(query_date, db.engine)
    min_date = df_dates.iloc[0, 0]
    max_date = df_dates.iloc[0, 1]
    
    if min_date is None or max_date is None:
        # If data no exists in the DB 
        formatted_min_date = "No data"
        formatted_max_date = "No data"
        formatted_min_fdate = "No data"
        formatted_max_fdate = "No data"
        
    else:
        # date_obj_min = datetime.strptime(min_date, '%Y-%m-%d')
        formatted_min_date = min_date.strftime('%d. %m. %Y')
        # date_obj_max = datetime.strptime(max_date, '%Y-%m-%d')
        formatted_max_date = max_date.strftime('%d. %m. %Y')
        
        # Get datums for prediction                 # TODO: Změnit podle skutečných dat
        pred_min_date = max_date + timedelta(1)
        pred_max_date = datetime.now() + timedelta(15)
        # formatted_min_fdate = pred_min_date.strftime('%d. %m. %Y')    # TODO: Odkomentovat
        # formatted_max_fdate = pred_max_date.strftime('%d. %m. %Y')
        formatted_min_fdate = "No data"
        formatted_max_fdate = "No data"
        
    
    # TODO: Get prediction model name 
    
    data = [
        {'info': 'Name', 'val1': wr_name, 'val2': ''},
        {'info': 'OSM_ID', 'val1': osm_id, 'val2': ''},
        {'info': 'Area (ha)', 'val1': wr_area, 'val2': ''},
        {'info': 'Feature', 'val1': feature, 'val2': ''},
        {'info': 'Data from-to', 'val1': formatted_min_date, 'val2': formatted_max_date},
        {'info': 'Prediction', 'val1': formatted_min_fdate, 'val2': formatted_max_fdate},
        {'info': 'Model', 'val1': 'Name:', 'val2': 'AI_model_test_3'},
        {'info': '-', 'val1': 'ID:', 'val2': 'f0f13295-2068-436a-a900-a7fff15ec9a7'},
        {'info': '-', 'val1': 'Test accuracy:', 'val2': '0.87'},
        {'info': '-', 'val1': 'Valid for reservoir:', 'val2': 'Default'},
    ]
    
    return jsonify(data)

@main.route("/data_spatial_info", methods=['POST'])
def data_spatial_info():                                # TODO: dodělat!
    """
    Information about water reservoir and about dataset
    """
    
    date_str = '2022-06-19'
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    formatted_date = date_obj.strftime('%d. %m. %Y')
    
    data = [
        {'info': 'Name', 'val1': 'Velký Tisý', 'val2': ''},
        {'info': 'OSM_ID', 'val1': 15444638, 'val2': ''},
        {'info': 'Area (ha)', 'val1': 211.36, 'val2': ''},
        {'info': 'Feature', 'val1': 'ChlA', 'val2': ''},
        {'info': 'Date', 'val1': formatted_date, 'val2': ''},
        {'info': 'Model', 'val1': 'Name:', 'val2': 'AI_model_test_3'},
        {'info': 'Statistics', 'val1': 'Mean:', 'val2': '250.44'},
        {'info': '', 'val1': 'Number of points:', 'val2': '85'},
        {'info': '', 'val1': 'Median:', 'val2': '211.5'},
        {'info': '', 'val1': 'Max.', 'val2': '421.5'},
        {'info': '', 'val1': 'Min.', 'val2': '112.4'},
    ]
    
    return jsonify(data)   

@main.route('/get_bounds', methods=['POST'])
def get_bounds():
    """
    The function returns bounding box for the selected reservoir to the backend for zooming map.
    """
    
    data = request.json
    osm_id = str(data['osm_id'])
    
    # Get data from DB
    query = text(f"SELECT geometry FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")
    gdf = gpd.read_postgis(query, db.engine, geom_col='geometry')
    
    bbounds = gdf.total_bounds     
    
    bounds = {
        "southWest": {"lat": bbounds[1], "lng": bbounds[0]},
        "northEast": {"lat": bbounds[3], "lng": bbounds[2]}
    }
    
    return jsonify(bounds)    

@main.route('/download_ts', methods=['POST'])
def download_ts():
    """Download Time Series data for the dataset"""
    
    # Get data from DB
    # Calculate statistics (mean, median, max, min...)
    # Create GeoJson file
    
    return 

# Custom error pages
# Invalid URL
@main.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# Interval server error
@main.errorhandler(500)
def page_not_found(e):
    return render_template("500.html"), 500

def clear_old_cache(cache_dir, max_age_seconds=3600):
    """
    Remove the cache files older than max_age_seconds seconds.
    """

    now = time.time()
    for filename in os.listdir(cache_dir):
        filepath = os.path.join(cache_dir, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                os.remove(filepath)
    return

def sendInfoEmail(e_adress, subject, content):
    """
    Send an info e-mail about finishing the calculation process.

    :param e_adress: The e-mail adress to whom be the e-mail send
    :param subject: E-mail subject
    :param content: E-mail content
    """

    # msg = EmailMessage()
    # msg['Subject'] = subject
    # msg['From'] = current_app.config('MAIL_USERNAME')         # define e-mail adress
    # msg['To'] = e_adress
    # msg.set_content(f'{content}\n\nYour AIHABs Team')

    # try:
    #     with smtplib.SMTP_SSL(current_app.config('MAIL_SERVER'), current_app.config('MAIL_PORT')) as s:  # define SMTP server
    #         # s.starttls()
    #         print(f"Logging in to the e-mail server: {current_app.config('MAIL_SERVER')}")
    #         s.login(current_app.config('MAIL_USERNAME'), current_app.config('MAIL_PASSWORD')) # Použijte heslo aplikace!
    #         print("Logged in to the e-mail server.")
    #         s.send_message(msg)
    #         print("The e-mail has been sent.")
    #     print(f"The e-mail has been sent to address: {e_adress}")
    # except Exception as e:
    #     print(f"E-mail sending error: {e}")
        
    try:
        msg = Message(subject, sender=current_app.config['MAIL_USERNAME'], recipients=[e_adress])
        msg.body = content
            
        mail.send(msg)
        
        print(f"The e-mail has been sent to address: {e_adress}")
    except Exception as e:
        print(f"Error in sending the e-mail: {str(e)}")
        

def confidence_interval(data, confidence=0.95):
    n = len(data)
    if n < 2:
        return (np.nan, np.nan)  # Pokud má datum málo hodnot
    mean = np.mean(data)
    se = sem(data)
    h = se * t.ppf((1 + confidence) / 2., n-1)
    return mean - h, mean + h

def convert_data_to_nparray(gdf_data, gdf_mask, fvalue, pixel_size=10):    
    """Rasterize the original data and mask of the WR"""
    
    # Transform CRS
    epsg_new = gdf_data.estimate_utm_crs()
    gdf_data_utm = gdf_data.to_crs(epsg_new)
    gdf_mask_utm = gdf_mask.to_crs(epsg_new)
    
    # Get the bounds of the raster
    bounds = gdf_mask_utm.total_bounds
    x_min, y_min, x_max, y_max = bounds
    
    width = int((x_max - x_min) / pixel_size)
    height = int((y_max - y_min) / pixel_size)
    
    # Rasterize the data
    transform = from_origin(x_min, y_max, pixel_size, pixel_size)
    
    # WQ data
    shapes = ((geom, value) for geom, value in zip(gdf_data_utm.geometry, gdf_data_utm[fvalue]))
    
    np_data = rasterize(
        shapes=shapes,
        out_shape=(height, width),
        transform=transform,
        fill=np.nan,  # Hodnota pro pixely bez bodů
        dtype="float32"
    )
    
    # Rasterize mask
    shapes_mask = ((geom, np.nan) for geom in gdf_mask_utm.geometry)
    
    np_mask = rasterize(
        shapes=shapes_mask,
        out_shape=(height, width),
        transform=transform,
        fill=0,  # Hodnota pro pixely bez bodů
        dtype="float32"
    )
 
    return np_data, np_mask

if __name__ == '__main__':
    # main.run(debug=True)
    main.run(host="0.0.0.0", port=8080, debug=True)