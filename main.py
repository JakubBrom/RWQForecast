from flask import request, jsonify, render_template, redirect, flash, url_for, Blueprint, current_app, session, Response, send_file
from flask_login import login_required, current_user
from sqlalchemy import exc, text
import osmnx as ox
import geopandas as gpd
import os
import time
import numpy as np
import pandas as pd
import json
from flask_mail import Message
from scipy.stats import sem, t
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import zoom
from datetime import datetime, timedelta
from . import db, mail, socketio
from .socketio_handlers import connected_users
from cryptography.fernet import Fernet
import openeo
from scipy.interpolate import griddata
from matplotlib import pyplot as plt

from .static.libs.AIHABs import AIHABs


main = Blueprint('main',__name__)

OPENEO_PROVIDER = 'CDSE'
OPENEO_BACKEND = "https://openeo.dataspace.copernicus.eu"

# DB tables
water_reservoirs = 'reservoirs'
user_reservoirs = 'user_reservoirs'
db_results = "wq_points_results"        # TODO: Změnit na imputovaná data!!!
db_user_credentials = 'user_credentials'
db_users = 'users'
db_models = 'models_table'

# Set the minimum area of the reservoir
min_area = 1.0      # TODO: possibly get it from the setting file

@main.route('/')
def index():
    return render_template('index.html')

@main.route("/profile")
@login_required
def profile():
    # Get number of OEO client credentials from DB 
    query = text(f"SELECT COUNT(*) FROM {db_user_credentials} WHERE user_id = '{current_user.id}';")
    
    with db.engine.connect() as conn:
        n_keys = conn.execute(query).scalar()
        conn.close()
    
    return render_template('profile.html', name=current_user.name, nkeys=n_keys)

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

@main.route("/oeo_credentials_howto")
@login_required
def oeo_credentials_howto():
    return render_template('oeo_howto.html')

@main.route("/oeo_form")
@login_required
def oeo_form():
    return render_template("credentials.html")

@main.route("/gallery")
def gallery():
    abs_path = os.path.dirname(os.path.abspath(__file__))
    
    # Maps
    maps_path = os.path.join(abs_path, 'static', 'images', 'gallery', 'maps')
    maps = os.listdir(maps_path)
    
    # Graphs
    graphs_path = os.path.join(abs_path, 'static', 'images', 'gallery', 'graphs')
    graphs = os.listdir(graphs_path)
    
    # Tables
    tables_path = os.path.join(abs_path, 'static', 'images', 'gallery', 'tables')
    tables = os.listdir(tables_path)
    
    # Photos
    photos_path = os.path.join(abs_path, 'static', 'images', 'gallery', 'photos')
    photos = os.listdir(photos_path)
    
    return render_template('gallery.html', maps=maps, graphs=graphs, tables=tables, photos=photos)

@main.route("/get_oeo_credentials", methods=["POST"])
@login_required
def get_oeo_credentials():
    """ Create the unique key for the clid and clse and save them to the DB """
    
    clid = request.form.get('clid')
    clse = request.form.get('clse')
    
    # Validation of credentials
    valid = ckeys_valid(clid, clse)
    
    if not valid:
        flash("The key is not valid. Use another one", "warning")
        
        return render_template("credentials.html")
    
    # Create the unique key for the clid and clse
    credential_key = clid[3:7] + clse[-4:] + "_" + str(current_user.id)
       
    # Encrypting the credentials
    openeo_secret_key = current_app.config.get('OPENEO_SECRET_KEY')
    cipher_suite = Fernet(openeo_secret_key.encode())
        
    encrypted_clid = cipher_suite.encrypt(clid.encode()).decode()
    encrypted_clse = cipher_suite.encrypt(clse.encode()).decode()
    
    # Saving data to the DB
    query = text(f"INSERT INTO {db_user_credentials} (user_id, clid, clse, credential_key) VALUES ({current_user.id}, '{encrypted_clid}', '{encrypted_clse}', '{credential_key}') ON CONFLICT DO NOTHING;")
    
    with db.engine.connect() as conn:
        conn.execute(query)
        conn.commit()
        conn.close()
    
    # Check the availability of the key
    get_available_key()
    
    flash("The OEO Credentials are available now. Try new analysis or add another credentials.", "info")
    
    return render_template("credentials.html")
    # return redirect(url_for("main.results"))     # TODO: je to ok??

def get_oeo_key_from_db():
    """ Get the OEO credentials from the DB """
    
    query_test = text(f"SELECT clid FROM {db_user_credentials} WHERE user_id = {current_user.id};")
    query_get_creds = text(f"SELECT clid, clse, credential_key FROM {db_user_credentials} WHERE user_id = {current_user.id} AND status = 'True';")
    
    with db.engine.connect() as conn:
        keys_exists = conn.execute(query_test).fetchone()
        keys_available = conn.execute(query_get_creds).fetchone()
        conn.close()
        
    return keys_exists, keys_available

def keys_decrypt(keys):
    """ Encrypt OEO credential keys taken from DB"""
    
    encrypted_clid = keys[0]
    encrypted_clse = keys[1]
    ckey = keys[2]

    # Decrypt the ckeys
    openeo_secret_key = current_app.config.get('OPENEO_SECRET_KEY')
    cipher_suite = Fernet(openeo_secret_key.encode())
    
    clid = cipher_suite.decrypt(encrypted_clid.encode()).decode()
    clse = cipher_suite.decrypt(encrypted_clse.encode()).decode()
    
    return clid, clse, ckey    

def ckeys_valid(clid, clse, ckey=None):
    
    try:
        conn = openeo.connect(OPENEO_BACKEND, auto_validate=False)
        conn.authenticate_oidc_client_credentials(provider_id=OPENEO_PROVIDER, client_id=clid, client_secret=clse)
        
        valid = True
        
    except:        
        valid = False
        if ckey:
            # Remove row for ckey from DB
            query = text(f"DELETE FROM {db_user_credentials} WHERE credential_key = '{ckey}';")
            
            with db.engine.connect() as conn:
                conn.execute(query)
                conn.commit()
                conn.close()
        
            flash(f"The credentials for {ckey} are not further valid. They has been removed from the database. Please set new one.", "warning")      
    
    return valid    

def get_available_key():
    """ Check the availability of OEO credentials in the DB or create new ones. If the credentials are blocked, wait for their release. """
    
    # Get the keys from the DB
    keys_exists, keys_available = get_oeo_key_from_db()
    
    if keys_exists is None:
        print("No keys found")
        
        return # redirect(url_for('main.oeo_form')), 302                    # TODO: správně přesměrovat
        # return render_template("credentials.html")

    if keys_available is None:
        print("No keys available - waiting")    # čekat na uvolnění klíče
        while True:
            keys_available = get_oeo_key_from_db()[1]
            if keys_available:
                break
            time.sleep(3)
            
        clid, clse, ckey = keys_decrypt(keys_available)
        
        print("Keys available")       
        
    else:
        print("Keys available")
        clid, clse, ckey = keys_decrypt(keys_available)
        valid = ckeys_valid(clid, clse, ckey)
        
        if not valid:
            return # redirect(url_for('main.oeo_form')), 302            # TODO: správně přesměrovat           
        
    return clid, clse, ckey

def release_lock_key(key, status=True):
    """ Release or lock a OEO credentials """
    
    query = text(f"UPDATE {db_user_credentials} SET status = '{status}' WHERE credential_key = '{key}';")
    
    with db.engine.connect() as conn:
        conn.execute(query)
        conn.commit()
        conn.close()        
    
    print(f"The credentials for {key} has been changed to {status}.")
    
    return

@main.route("/start-analysis")
@login_required
def run_analysis(osm_id=None, wq_feature=None):
    
    # Get variables from html/js        # TODO: tady asi budou nějaký vstupy pro analýzy   
    user_id = current_user.get_id()
    sid = connected_users.get(user_id)

    print("SID je: ", sid)

    # Get keys
    oeo_ckeys = get_available_key()
    
    if isinstance(oeo_ckeys, tuple):
        clid, clse, ckey = oeo_ckeys
        
        # Lock the keys
        release_lock_key(ckey, status=False)
        
        try:
            # Authenticate                  # TODO: Autentizace je už v analýze přímo
            conn = openeo.connect(OPENEO_BACKEND, auto_validate=False)
            conn.authenticate_oidc_client_credentials(provider_id=OPENEO_PROVIDER, client_id=clid, client_secret=clse)
            
            print("Authentication is OK. Starting the calculation process.")
            
            # Calculation
            if osm_id:
                aihabs = AIHABs()
                aihabs.client_id = clid
                aihabs.client_secret = clse
                aihabs.osm_id = osm_id
                aihabs.feature = wq_feature
                aihabs.db_name = current_app.config.get('DB_NAME')
                
                aihabs.run_analyse()
                
                print("The calculation finished!")       # TODO: doplnit výpis zpráv, odesílání e-mailů atd, 
                
        except Exception as e:
            socketio.emit("redirect", {"url": url_for('main.oeo_form', _external=True)}, room=sid)
            
        finally:
            release_lock_key(ckey, status=True)
            
        return redirect(url_for('main.results'))         # TODO: přesměrovat - kontrola --> možná nebude potřeba
    
    else:
        socketio.emit("redirect", {"url": url_for('main.oeo_form', _external=True)}, room=sid)
    
    return oeo_ckeys    


@socketio.on('select_and_start_analysis')
@main.route('/select_waterbody', methods=['POST'])
@login_required
def select_waterbody():
    
    # Get data from the frontend
    data = request.json
    osm_id = data.get("osm_id")                 # get OSM_ID from the map
    reserv_name = data.get("name")              # get name of the layer from the map
    lyr_point_position = data.get("firstVrt")   # get first vertex position of the layer
    wqf_name = data.get("wq_param")             # get wq_feature name

    user_id = current_user.get_id()
    print("User ID je: ", user_id)
    sid = connected_users.get(user_id)
    print("SID je: ", sid)

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
            # Send the Flash message
            socketio.emit("flash_message", {"category": "info", "message": f"Your request for analysis of water reservoir {reserv_name} ({osm_id}) has been accepted. The processing can take a long time (minutes to tens of minutes). We will inform you about the results."}, room=sid)
            
            # Transform to WGS 84
            gdf_sel_wgs = gdf_sel_utm.to_crs(epsg_orig)     # Convert to WGS 84
            gdf_sel_wgs.reset_index(drop=True, inplace=True)
            
            # Check if the 'name' cloumn exists
            if 'name' not in gdf_sel_wgs:
                gdf_sel_wgs['name'] = 'Noname'
   
            # Select the columns for the DB table
            gdf_select = gdf_sel_wgs[['osm_id', 'name', 'area', 'geometry']]

            # 4. Add the polygon (gdf) to the DB table
            gdf_select.to_postgis('reservoirs', db.engine, if_exists='append', index=False)
            
        else:
            print(f"The reservoir {reserv_name} is too small for the calculation.")
            # e_subject = 'The forecast has not been finished'
            # e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has not been finished. The reservoir is too small for the calculation.'
            # # Send the info e-mail
            # sendInfoEmail(current_user.email, e_subject, e_content)

            # return render_template("select_wr.html")
            socketio.emit("flash_message", {"category": "warning", "message": f"The reservoir {reserv_name} ({osm_id}) is too small for the calculation. Choose another one."}, room=sid)
            return render_template("select_wr.html")    # redirect(url_for('main.results'))

    else:
        print("The reservoir is already in the DB.")
        socketio.emit("flash_message", {"category": "info", "message": f"The reservoir {reserv_name} ({osm_id}) is already in the DB. The data will be updated. The processing can take a long time (minutes to tens of minutes). We will inform you about the results."}, room=sid)

    # 5. Clear the cache
    try:
        cdir = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(cdir, "cache")
        clear_old_cache(cache_path, 600)
    except Exception:
        pass

    # Add the reservoir to the table for current user # TODO: přidat info do DB o tom, že daná nádrž patří k danému uživateli
    query_wr_user_exists = text(f"SELECT EXISTS (SELECT * FROM {user_reservoirs} WHERE osm_id = '{osm_id}' AND user_id = '{current_user.id}')")
    try:
        result = db.session.execute(query_wr_user_exists)
        result = result.scalar()
        print(result)
    except exc.SQLAlchemyError as e:
        print(f"Error: {e}")
        result = False
        
    if not result:
        query_add_wr_user = text(f"INSERT INTO {user_reservoirs} (user_id, osm_id) VALUES ('{current_user.id}', '{osm_id}') ON CONFLICT DO NOTHING;")
        db.session.execute(query_add_wr_user)
        db.session.commit()

    # 6. Start the calculation process
    try:
        run_analysis(osm_id=osm_id, wq_feature=wqf_name)      # Run the calculation process
        
    except Exception as e:
        print(f"Error in the calculation process for {osm_id}: {e}")
        socketio.emit("flash_message", {"category": "warning", "message": f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has not been finished. The calculation process has failed.'}, room=sid)
        
        # Send the info e-mail
        e_subject = 'The forecast has not been finished'
        e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has not been finished. The calculation process has failed.'
        sendInfoEmail(current_user.email, e_subject, e_content)

        return render_template("select_wr.html")

    # 8. Send info e-mail
    print(f"Sending e-mail to: {current_user.email}")
    
    # Send the info e-mail
    e_subject = 'The forecast has been finished'
    results_url = url_for('main.results', _external=True)
    e_content = f'The forecast of the {wqf_name} for the reservoir {reserv_name} ({osm_id}) has been finished. The results are available at the results page: {results_url}.'
    
    sendInfoEmail(current_user.email, e_subject, e_content)

    return render_template("select_wr.html")

@main.route("/results")
@login_required
def results():
    return render_template("results.html")


@socketio.on('start_analysis')
def update_dataset(data):
    """The function updates datasets and provide the analysis of the data.
    """
    
    # Set SocketIO session
    user_id = current_user.get_id()
    sid = connected_users.get(user_id)    
    
    # Run the analysis
    try:
        # Get data
        osm_id = str(data.get('osm_id'))
        wq_feature = data.get('feature')
        reserv_name = data.get('wr_name')
        
        # Send the Flash message
        socketio.emit("flash_message", {"category": "info", "message": f"Your request for water reservoir {reserv_name} ({osm_id}) data update has been accepted. The processing can take a long time (minutes to tens of minutes). We will inform you about the results."}, room=sid)
    
        run_analysis(osm_id=osm_id, wq_feature=wq_feature)      # Run the calculation process
        
    except Exception as e:
        print(f"Error in the calculation process: {e}")
        socketio.emit("flash_message", {"category": "info", "message": f'The forecast of the {wq_feature} for the reservoir {reserv_name} ({osm_id}) has not been finished. The calculation process has failed.'}, room=sid)
        
        # Send the info e-mail
        e_subject = 'The forecast has not been finished'
        e_content = f'The forecast of the {wq_feature} for the reservoir {reserv_name} ({osm_id}) has not been finished. The calculation process has failed.'
        sendInfoEmail(current_user.email, e_subject, e_content)

        # return render_template("results.html")

    # 8. Send info e-mail
    print(f"Sending e-mail to: {current_user.email}")
    
    # Send the info e-mail
    e_subject = 'The forecast has been finished'
    results_url = url_for('main.results', _external=True)
    e_content = f'The forecast of the {wq_feature} for the reservoir {reserv_name} ({osm_id}) has been finished. The results are available at the results page: {results_url}.'
    
    sendInfoEmail(current_user.email, e_subject, e_content)
    
    # return render_template("results.html")

@main.route("/add_wr_to_map", methods=['POST'])
@login_required
def add_wr_to_map():
    """
    Get the water reservoirs from the DB and add them to the map.
    """

    if current_user.urole != 1:    
        # Get the water reservoirs from the DB
        # 1. Define list of OSM_IDs for particular user
        query = text(f"SELECT DISTINCT osm_id FROM {user_reservoirs} where user_id = {current_user.id}")  # Get the list of OSM_ID from the DB    
        
        # Get the list of OSM_IDs from the DB
        df_osm_ids = pd.read_sql_query(query, db.engine)
        osm_ids = df_osm_ids['osm_id'].tolist()
        
        # 2. Get the water reservoirs from the DB for list of OSM_IDs for the particular user
        query2 = text(f"SELECT * FROM {water_reservoirs} WHERE osm_id IN :osm_ids")                   # Selection of the reservoirs for the particular user
        gdf_reservoirs = gpd.read_postgis(query2, db.engine, geom_col='geometry', params={'osm_ids': tuple(osm_ids)})
        
    else:    
        # Selection for admin  
        query = text("SELECT * FROM reservoirs")  
        gdf_reservoirs = gpd.read_postgis(query, db.engine, geom_col='geometry')

    # 3. Add the reservoirs to the map
    json_data = jsonify(json.loads(gdf_reservoirs.to_json()))

    return json_data

@main.route("/set_wr_to_selectBox", methods=['GET'])
@login_required
def set_wr_to_selectBox():
    """
    Get the list of OSM_IDs and reservoir names from the DB and add the list to the selection box.
    """
    if current_user.urole != 1:
        # 1. Get the list of OSM_IDs and reservoir names from the DB for the particular user
        query = text(f"SELECT DISTINCT osm_id FROM {user_reservoirs} where user_id = {current_user.id}")  # Get the list of OSM_ID from the DB

        
        # Get the list of OSM_IDs from the DB
        df_osm_ids = pd.read_sql_query(query, db.engine)
        osm_ids = df_osm_ids['osm_id'].tolist()
        
        # 2. Get the water reservoirs from the DB for list of OSM_IDs for the particular user
        query2 = text("SELECT osm_id, name FROM reservoirs WHERE osm_id IN :osm_ids")                   # Selection of the reservoirs for the particular user
        df_data = pd.read_sql_query(query2, db.engine, params={'osm_ids': tuple(osm_ids)})
    
    else:
        # Get the list of OSM_IDs from the DB    
        df_data = pd.read_sql_query("SELECT DISTINCT osm_id, name FROM reservoirs", db.engine)
        
    df_data = df_data.sort_values(by=['name'])

    data_json = df_data.to_json(orient='records')
    
    return jsonify(data_json)

@main.route("/set_models_to_selectBox", methods=['POST'])
@login_required
def set_models_to_selectBox():
    """
    Get the list of prediction models (model IDs and model names) from the DB and add the list to the selection box.
    """
    
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']
    
    print(f"Getting the list of models for the reservoir: {osm_id}, feature: {feature}")
    
    # db_models = "models_smaz"     # XXX: For testing purposes only
    
    # Get the list of prediction models from the DB
    query = text(f"SELECT * FROM {db_models} WHERE feature = '{feature}'")  # Get the list of OSM_ID from the DB
    df_data = pd.read_sql_query(query, db.engine)
    
    # Sort the data
    df_data = sort_dataframe(df_data, osm_id)
    df_data = df_data.drop("pkl_file", axis=1)  # Drop the pkl_file column
    
    # Convert data to json
    data_json = df_data.to_json(orient='records')
    
    
    return jsonify(data_json)

@main.route("/ts_data", methods=['POST'])
@login_required
def ts_data():
    """Get the time series data for the particular reservoir.
    """
    
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']
    model_id = data['model_id']

    # Get the time series data for the particular reservoir from the DB
    query = text(f"SELECT date, feature_value FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND model_id = '{model_id}' ORDER BY date")  # Get the time series data for the particular reservoir
    
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
@login_required
def forecast_data():            # TODO: Přesměrovat na správnou tabulku
    """Get the forecast time series data for the particular reservoir."""
    
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']
    model_id = data['model_id']

    # Get the time series data for the particular reservoir from the DB
    query = text(f"SELECT date, feature_value FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND model_id = '{model_id}' ORDER BY date")  # Get the time series data for the particular reservoir
    
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

@main.route("/contourplot_data", methods=['POST'])
@login_required
def contourplot_data():         # TODO: doplnit model_id
    """Make an interpolation of the data for the particular reservoir and date.
    """
    # Get the data from the request
    data = request.json
    osm_id = str(data['osm_id'])
    feature = data['feature']
    date = data['date']
    fvalue = "feature_value"
    model_id = data['model_id']
    
    print(f"Interpolating the data for the reservoir: {osm_id}, feature: {feature}, date: {date}")
    
    # Test if tere is a data for the particular reservoir and date
    query = text(f"SELECT EXISTS (SELECT * FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date}' AND model_id = '{model_id}')")  # Get the time series data for the particular reservoir
    try:
        result = db.session.execute(query)
        result = result.scalar()
    except exc.SQLAlchemyError as e:
        print(f"Error: {e}")
        result = False
    
    if not result:
        print(f"No data for the reservoir {osm_id} and date {date}.")
        return jsonify({"error": "No data for the reservoir and date."}), 400
        
    # Get the data for the particular reservoir and date from the DB
    query = text(f"SELECT * FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date}' AND model_id = '{model_id}'")  # Get the time series data for the particular reservoir
    gdf_data = gpd.read_postgis(query, db.engine, geom_col='geometry')
    
    # Get reservoir polygon from the DB
    query_wr = text(f"SELECT geometry FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")  # Get the time series data for the particular reservoir
    gdf_wr = gpd.read_postgis(query_wr, db.engine, geom_col='geometry')

    # Rasterize data and mask 
    np_data, np_mask, gdf_data_utm, bounds = convert_data_to_nparray(gdf_data, gdf_wr, fvalue)

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
@login_required
def data_info():                                # TODO: dodělat! --> přidat odkaz na použitý model 
    """
    Information about water reservoir and dataset
    """
    
    # Get data from frontend
    data = request.json
    osm_id = data['osm_id']
    feature = data['feature']
    wr_name = data['wr_name']
    model_id = data['model_id']
    
    if not osm_id:
        return jsonify({"error": "No osm_id provided"}), 400
    
    # Get area from DB
    query_area = text(f"SELECT area FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")
    df_wr_area = pd.read_sql_query(query_area, db.engine)
    wr_area = df_wr_area.iloc[0, 0]
        
    # Get date interval for historical data  
    query_date = text(f"SELECT MIN(date) AS min_date, MAX(date) as max_date FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND model_id = '{model_id}'")
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
        
    # Get the prediction model data
    query_model = text(f"SELECT model_name, test_accuracy, is_default, osm_id FROM {db_models} WHERE model_id = '{model_id}'")
    df_model = pd.read_sql_query(query_model, db.engine)
    
    model_name = df_model.iloc[0, 0]
    test_accuracy = df_model.iloc[0, 1]
    is_default = df_model.iloc[0, 2]
    osm_id_model = df_model.iloc[0, 3]
    
    # Describe model validity 
    if not osm_id_model:
        if is_default:
            osm_id_model = "General model (default)"
        else:
            osm_id_model = "General model"
    else:
        if is_default:
            osm_id_model = wr_name + "(default)"
        else:
            osm_id_model = wr_name
    
    print(f"Model name: {model_name}, test accuracy: {test_accuracy}, is_default: {is_default}, osm_id: {osm_id_model}")
    
    # Stat. table - information about reservoir and TS dataset
    
    data = [
        {'info': 'Name', 'val1': wr_name, 'val2': ''},
        {'info': 'OSM_ID', 'val1': osm_id, 'val2': ''},
        {'info': 'Area (ha)', 'val1': wr_area, 'val2': ''},
        {'info': 'Feature', 'val1': feature, 'val2': ''},
        {'info': 'Data from-to', 'val1': formatted_min_date, 'val2': formatted_max_date},
        {'info': 'Prediction', 'val1': formatted_min_fdate, 'val2': formatted_max_fdate},
        {'info': 'Model', 'val1': 'Name:', 'val2': model_name},
        {'info': '', 'val1': 'ID:', 'val2': model_id},
        {'info': '', 'val1': 'Test accuracy:', 'val2': str(test_accuracy)},
        {'info': '', 'val1': 'Valid for reservoir:', 'val2': osm_id_model},
    ]
    
    return jsonify(data)

@main.route("/data_spatial_info", methods=['POST'])
@login_required
def data_spatial_info():                                # TODO: dodělat!
    """
    Information about water reservoir and about dataset
    """
    
    # Get data from frontend
    data = request.json
    osm_id = data['osm_id']
    feature = data['feature']
    wr_name = data['wr_name']
    date_str = data['sel_date']
    
    # Transforma date string to date object
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    formatted_date = date_obj.strftime('%d. %m. %Y')
    
    # Get Number of points
    query_points = text(f"SELECT COUNT(*) FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date_str}' AND model_id = '{model_id}'")
    df_points = pd.read_sql_query(query_points, db.engine)
    n_points = df_points['count'].values[0]
    
    # Interpolate the data and get the statistics    
    # Get the data for the particular reservoir and date from the DB
    query = text(f"SELECT * FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date_str}' AND model_id = '{model_id}'")  # Get the time series data for the particular reservoir
    gdf_data = gpd.read_postgis(query, db.engine, geom_col='geometry')
    
    # Get reservoir polygon from the DB
    query_wr = text(f"SELECT geometry FROM {water_reservoirs} WHERE osm_id = '{osm_id}'")  # Get the time series data for the particular reservoir
    gdf_wr = gpd.read_postgis(query_wr, db.engine, geom_col='geometry')
    
    # Interpolation of the data
    try:
        grid_lin_masked = interpolate_data(gdf_data, gdf_wr, fvalue='feature_value', mask=False)
    except Exception as e:
        print(f"Error in the interpolation: {e}")
        return jsonify({"error": "Interpolation failed."}), 500
    
    # Get the statistics
    mean = np.round(np.nanmean(grid_lin_masked), 2)
    median = np.round(np.nanmedian(grid_lin_masked), 2)
    max_val = np.round(np.nanmax(grid_lin_masked), 2)
    min_val = np.round(np.nanmin(grid_lin_masked), 2)
    stdev = np.round(np.nanstd(grid_lin_masked), 2)
    
    tab_data = [
        {'info': 'Name', 'val1': wr_name, 'val2': ''},
        {'info': 'OSM_ID', 'val1': osm_id, 'val2': ''},
        {'info': 'Feature', 'val1': feature, 'val2': ''},
        {'info': 'Date', 'val1': formatted_date, 'val2': ''},
        {'info': 'Model', 'val1': 'Name:', 'val2': 'AI_model_test_3'},      # TODO: doplnit ID modelu a podrobnosti k modelu (možná i odkaz na model a jeho popis)
        {'info': 'Statistics', 'val1': 'Number of points:', 'val2': str(n_points)},
        {'info': '', 'val1': 'Mean:', 'val2': str(mean)},        
        {'info': '', 'val1': 'Median:', 'val2': str(median)},
        {'info': '', 'val1': 'Max.', 'val2': str(max_val)},
        {'info': '', 'val1': 'Min.', 'val2': str(min_val)},
        {'info': '', 'val1': 'SD', 'val2': str(stdev)},
    ]
    
    return jsonify(tab_data)   

@main.route('/get_bounds', methods=['POST'])
@login_required
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

@main.route('/download_ts', methods=['GET'])
@login_required
def download_ts():
    """Download Time Series data for the dataset"""
    
    # Get the data from the request
    osm_id = request.args.get('osm_id')
    feature = request.args.get('feature')
    model_id = request.args.get('model_id')
    wr_name = request.args.get('wr_name')

    # Get the time series data for the particular reservoir from the DB
    query = text(f"SELECT date, feature_value FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND model_id = '{model_id}' ORDER BY date")  # Get the time series data for the particular reservoir
    
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
    
    # Convert the dataframe to CSV
    cdir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(cdir, "cache")
    file_name = f"{wr_name}_{osm_id}_{feature}.xlsx"
    filepath = os.path.join(cache_dir, file_name)
    
    aggregated.to_excel(filepath, sheet_name=f"{wr_name}_{feature}", index=False)    
    
    return send_file(
        filepath,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=file_name)

@main.route('/download_gpkg', methods=['GET'])
@login_required
def download_gpkg():    
    # Get data from the frontend
    osm_id = request.args.get('osm_id')
    feature = request.args.get('feature')
    date = request.args.get('date')
    model_id = request.args.get('model_id')
    wr_name = request.args.get('wr_name')
    
    print(f"Downloading the data for the reservoir: {wr_name} ({osm_id}), feature: {feature}, date: {date}, model_id: {model_id}")
    
    # Get data from DB
    query = text(f"SELECT * FROM {db_results} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND date = '{date}' and model_id = '{model_id}'")  # Get the time series data for the particular reservoir
    gdf_data = gpd.read_postgis(query, db.engine, geom_col='geometry')

    # Create GPKG file
    cdir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(cdir, "cache")
    file_name = f"{wr_name}_{osm_id}_{feature}_{date}.gpkg"
    filepath = os.path.join(cache_dir, file_name)
    gdf_data.to_file(filepath, driver='GPKG', layer='data')
    
    return send_file(
        filepath,
        mimetype="application/geopackage+sqlite3",
        as_attachment=True,
        download_name=file_name)

@main.route('/delete_ask')
def delete_ask():
    """Ask for account deleting confirmation"""
    
    flash("""
        <form action="/delete_account" method="post" style="display: inline;">
            <span>Do you realy want to delete this account?</span>
            <button type="submit" class="btn btn-danger btn-sm">Delete</button>
        </form>
        <a href="/" class="btn btn-secondary btn-sm ms-2">Cancel</a>
    """, 'warning')
    
    return redirect(url_for('main.profile'))

@main.route('/delete_account', methods=['POST'])
def delete_account():
    """Delete the user account and all data related to the user."""
    
    # Get the user ID
    user_id = current_user.id
    print(f"Deleting the account for user ID: {user_id}")    
    
    # Delete the user account from the DB
    
    query_del_user = text(f"DELETE FROM {db_users} WHERE id = {user_id};")
    querty_del_user_res = text(f"DELETE FROM {user_reservoirs} WHERE user_id = {user_id};")
    query_del_user_cred = text(f"DELETE FROM {db_user_credentials} WHERE user_id = {user_id};")
    
    db.session.execute(query_del_user)
    db.session.execute(querty_del_user_res)
    db.session.execute(query_del_user_cred)
    db.session.commit()
    
    print("User account has been deleted.")
    
    return redirect(url_for('main.index'))

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

def convert_data_to_nparray(gdf_data, gdf_mask, fvalue, mask_val=np.nan, pixel_size=10):    
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
    shapes_mask = ((geom, mask_val) for geom in gdf_mask_utm.geometry)
    
    np_mask = rasterize(
        shapes=shapes_mask,
        out_shape=(height, width),
        transform=transform,
        fill=0,  # Hodnota pro pixely bez bodů
        dtype="float32"
    )

    return np_data, np_mask, gdf_data_utm, bounds

def interpolate_data(gdf_data, gdf_wr, fvalue, mask=True):
    """Interpolate data using Scipy griddata linear interpolator and mask it with the reservoir polygon."""  
    
    # Rasterize data and mask 
    np_data, np_mask, gdf_data_utm, bounds = convert_data_to_nparray(gdf_data, gdf_wr, fvalue, mask_val=1.0)
    
    x_min, y_min, x_max, y_max = bounds
    
    # Define meshgrid for interpolation
    gdf_data_utm["x"] = gdf_data_utm.geometry.x
    gdf_data_utm["y"] = gdf_data_utm.geometry.y
    
    grid_x, grid_y = np.meshgrid(np.linspace(x_min, x_max, np.shape(np_mask)[1]), np.linspace(y_min, y_max, np.shape(np_mask)[0]))
    
    # Interpolation - Linear
    grid_lin = griddata(gdf_data_utm[['x', 'y']], gdf_data_utm[fvalue], (grid_x, grid_y), method='linear', fill_value=np.nan)
        
    # Mask the data
    if mask:    
        np_mask_nan = np.where(np_mask == 0.0, np.nan, np_mask)
        grid_lin = np.flipud(grid_lin) * np_mask_nan
    else:
        grid_lin = np.flipud(grid_lin)
    
    return grid_lin

def sort_dataframe(df, osm_id):
    """
    DataFrame sorting in context for osm_id and other priorities.
    """
    # Pomocný sloupec pro třídění podle priorit
    # 0: odpovídá osm_id
    # 1: není žádné osm_id (None)
    # 2: jiný než zadaný osm_id
    df['sort_priority'] = df['osm_id'].apply(
        lambda x: 0 if x == osm_id else (1 if pd.isna(x) else 2)
    )

    # Pomocný sloupec pro výběr defaultního modelu, pokud není osm_id
    df['is_default_rank'] = ~df['is_default']  # True → 0, False → 1 (opačně, kvůli řazení)

    # Seřazení dle priorit
    df_sorted = df.sort_values(
        by=['sort_priority', 'is_default_rank', 'test_accuracy'],
        ascending=[True, True, False]
    ).drop(columns=['sort_priority', 'is_default_rank'])

    return df_sorted


if __name__ == '__main__':
    # main.run(debug=True)
    main.run(host="0.0.0.0", port=8080, debug=True)