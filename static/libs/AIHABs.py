# Imports
from .get_S2_points_OpenEO import get_s2_points_OEO
from .calculate_features import calculate_feature
from .get_meteo import getHistoricalMeteoData, getPredictedMeteoData
from .data_imputation import data_imputation

class AIHABs:

    def __init__(self):
        """
        Initializes the AIHABs class with default values for various attributes.

        This method authenticates the OpenEO program after starting the program by calling the authenticate_OEO function. It sets the following attributes with default values:
        - db_name: the name of the database (default: "postgres")
        - user: the username for the database (default: "postgres")
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
        self.provider_id = "CDSE"
        self.client_id = None
        self.client_secret = None
        self.oeo_backend = "https://openeo.dataspace.copernicus.eu"

        self.db_name = "postgres"
        self.user = "postgres"
        self.db_table_reservoirs = "reservoirs"
        self.db_table_points = "selected_points"
        self.db_table_S2_points_data = "s2_points_eo_data"  # db_bands_table
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


    def run_analyse(self):

        # get Sentinel-2 data
        get_s2_points_OEO(self.provider_id, self.client_id, self.client_secret, self.osm_id, self.db_name, self.user, self.db_table_reservoirs, self.db_table_points, self.db_table_S2_points_data, self.db_access_date, oeo_backend_url=self.oeo_backend)

        # calculate WQ features --> new AI models
        calculate_feature(self.feature, self.osm_id, self.db_name, self.user, self.db_table_S2_points_data, self.db_features_table, self.db_models, self.model_id)

        # get meteodata
        # get historical meteodata
        getHistoricalMeteoData(self.osm_id, self.meteo_features, self.user, self.db_name, self.db_table_history, self.db_table_reservoirs)
        # get predicted meteodata
        getPredictedMeteoData(self.osm_id, self.meteo_features, self.user, self.db_name, self.db_table_forecast, self.db_table_reservoirs, self.forecast_days)

        # imputation of missing values (based on SVR model)
        # if model_id is not None:
        #     gdf_imputed, gdf_smooth = data_imputation(self.db_name, self.user, self.osm_id, self.feature, self.model_id, self.db_features_table, self.db_table_history, freq=self.freq, t_shift=self.t_shift)
        # else:
        #     gdf_imputed = None
        #     gdf_smooth = None
        # # run AI time series analysis

        # return gdf_imputed, gdf_smooth
        return

