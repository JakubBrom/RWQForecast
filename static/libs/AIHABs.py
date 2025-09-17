# Imports
from sqlalchemy import exc, text
from datetime import datetime, timedelta
from warnings import warn

from .get_S2_points_OpenEO import get_s2_points_OEO
from .calculate_features import calculate_feature
from .get_meteo import getHistoricalMeteoData, getPredictedMeteoData
# from .data_imputation import data_imputation

class AIHABs:

    def __init__(self):
        """
        Initializes the AIHABs class with default values for various attributes.

        This method authenticates the OpenEO program after starting the program by calling the authenticate_OEO function. It sets the following attributes with default values:

        - db_table_reservoirs: the name of the table for water reservoirs (default: "water_reservoirs")
        - db_table_points: the name of the table for selected points (default: "selected_points")
        - db_table_S2_points_data: the name of the table for S2 points data (default: "s2_points_eo_data")
        - db_features_table: the name of the table for water quality point results (default: "wq_points_results")
        - db_models: the name of the table for models (default: "models_table")
        - db_table_forecast: the name of the table for meteo forecast (default: "meteo_forecast")
        - db_table_history: the name of the table for meteo history (default: "meteo_history")
        - model_name: the name of the model (default: None)
        - default_model: a flag indicating if it's a default model (default: False)
        - osm_id: the OpenStreetMap ID
        - feature: the feature to be analyzed (default: "ChlA")
        - meteo_features: a list of meteo features to be used for analysis (default: ["weather_code", "temperature_2m_max", "temperature_2m_min", "daylight_duration", "sunshine_duration", "precipitation_sum", "wind_speed_10m_max", "wind_direction_10m_dominant", "shortwave_radiation_sum"])
        - freq: the frequency of the analysis: W - weekly, D - daily, M - monthly (default: "D")
        - t_shift: the time shift (default: 1)
        - forecast_days: the number of forecast days (weeks or months) (default: 16)
        """

        # Authenticate after starting the program
        self.client_id = None
        self.client_secret = None
        self.oeo_backend = "https://openeo.dataspace.copernicus.eu"

        self.db_table_reservoirs = "reservoirs"
        self.db_table_points = "selected_points"
        self.db_table_S2_points_data = "sentinel2_data_points"  # db_bands_table
        self.db_features_table = "wq_points_results"
        self.db_models = "models_table"
        self.db_table_forecast = "meteo_forecast"
        self.db_table_history = "meteo_history"
        self.db_access_date = "last_access"

        self.model_id = None

        self.osm_id: str = "123456"
        self.feature = "ChlA"
        self.meteo_features = ["weather_code", "temperature_2m_max", "temperature_2m_min", "daylight_duration",
                      "sunshine_duration", "precipitation_sum", "wind_speed_10m_max", "wind_direction_10m_dominant",
                      "shortwave_radiation_sum"]

        self.freq = 'D'
        self.t_shift = 3
        self.forecast_days = 16

    def run_analyse(self, db_session):
        """Run the data analysis."""
        
        # Get last access to CDSE for particular osm_id
        continue_calc = self.last_access(self.osm_id, db_session, self.db_access_date)  
    
        if continue_calc:
            try:
                # get Sentinel-2 data
                get_s2_points_OEO(self.client_id, self.client_secret, self.osm_id, db_session, self.db_table_reservoirs, self.db_table_points, self.db_table_S2_points_data, oeo_backend_url=self.oeo_backend)
                print("Sentinel-2 data downloaded")
                
                # get meteodata
                # get historical meteodata
                getHistoricalMeteoData(self.osm_id, self.meteo_features, db_session, self.db_table_history, self.db_table_reservoirs)
                # get predicted meteodata
                getPredictedMeteoData(self.osm_id, self.meteo_features, db_session, self.db_table_forecast, self.db_table_reservoirs, self.forecast_days)
                print("Meteo data downloaded")            
                
                # Update the last access date
                self.setLastAccessDate(self.osm_id, db_session, self.db_access_date)
                print(f"Last access date for the reservoir {self.osm_id} has been updated.")
                
            except Exception as e:
                warn(f'Error during data downloading: {e}', stacklevel=2)          
        
        else:            
            print(f"Data for the reservoir {self.osm_id} are up to date.")        

        # calculate WQ features --> new AI models
        calculate_feature(self.feature, self.osm_id, db_session, self.db_table_S2_points_data, self.db_features_table, self.db_models, self.model_id)
        print("Water quality features calculated")
        

        # imputation of missing values (based on SVR model)
        # if model_id is not None:
        #     gdf_imputed, gdf_smooth = data_imputation(self.db_name, self.user, self.osm_id, self.feature, self.model_id, self.db_features_table, self.db_table_history, freq=self.freq, t_shift=self.t_shift)
        # else:
        #     gdf_imputed = None
        #     gdf_smooth = None
        # # run AI time series analysis

        # return gdf_imputed, gdf_smooth
        return
    
    def last_access(self, osm_id, db_session, db_access_date, n_days=1):
        """
        Get the last access date to CDSE for the reservoir

        :param osm_id: OSM object id
        :param db_name: Database name
        :param user: Database user
        :param db_access: Database table with access
        :return: Continue calculation (bool)
        """
        
        # Test if the date for the osm_id exists
        query = text(f"SELECT EXISTS (SELECT 1 FROM {db_access_date} WHERE osm_id = '{osm_id}')")
        
        result = db_session.execute(query).scalar()
        
        # If the date exists, get the last access date and update the date if it is older than today - n_days   
        if result:
            query = text("SELECT MAX(date) FROM {db_table} WHERE osm_id = '{osm_id}'".format(db_table=db_access_date, osm_id=osm_id))        
            
            today = datetime.now().date()

            last_access = db_session.execute(query).scalar()
            
            print(last_access)
            
            if last_access < today - timedelta(days=n_days):            
                continue_calc = True
            else:
                continue_calc = False
                
        # If the date does not exist, add the date to the table
        else:            
            continue_calc = True       

        print(f"Continue calculation: {continue_calc}")

        return continue_calc

    def setLastAccessDate(self, osm_id, db_session, db_access_date):
        """Set the last access date to data sources (CDSE, Open-Meteo) to the database."""
        
        # Test if the date for the osm_id exists
        query = text(f"SELECT EXISTS (SELECT 1 FROM {db_access_date} WHERE osm_id = '{osm_id}')")
        
        result = db_session.execute(query).scalar()
        
        # If the date exists, get the last access date and update the date if it is older than today - n_days   
        if result:
            query = text("UPDATE {db_table} SET date = '{today}' WHERE osm_id = '{osm_id}'".format(db_table=db_access_date, today=datetime.now().date(), osm_id=osm_id))
                
            db_session.execute(query)
            db_session.commit()
        # If the date does not exist, add the date to the table
        else:
            query = text("INSERT INTO {db_table} (osm_id, date) VALUES ('{osm_id}', '{today}')".format(db_table=db_access_date, osm_id=osm_id, today=datetime.now().date()))
            db_session.execute(query)
            db_session.commit()
        
        return

