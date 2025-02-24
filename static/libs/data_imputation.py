import pandas as pd
import geopandas as gpd
import numpy as np
import statsmodels.api as sm

from sqlalchemy import create_engine, text
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import SVR
from sklearn.impute import SimpleImputer

from AIHABs_wrappers import measure_execution_time


def create_dataset(db_name, user, osm_id, feature, model_id, db_wq_results, db_table_history, freq='W'):
    """
    Creates a dataset with time series of water quality feature and meteo data, along with the geometry and prepare it for missing data imputation.

    :param db_name: Database name
    :param user: Database user
    :param osm_id: OSM object id
    :param feature: Water quality feature
    :param model_id: Quality feature model ID
    :param db_wq_results: Water quality results PostGIS table
    :param db_table_history: Historical meteo data PostGIS table
    :param freq: Time scale (W - weekly, D - daily, M - monthly)
    :return: Dataset with time series of water quality feature and meteo data; Geometry GeoDataFrame
    """

    # Connect to PostGIS
    engine = create_engine('postgresql://{user}@/{db_name}'.format(user=user, db_name=db_name))

    # Define SQL queries for features, history and forecast
    query_feature = text(
        "SELECT * FROM {db_table} WHERE osm_id = '{osm_id}' AND feature = '{feature}' AND model_id = '{model_id}'".format(
            db_table=db_wq_results, osm_id=osm_id, feature=feature, model_id=model_id))
    query_history = text(
        "SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(db_table=db_table_history, osm_id=osm_id))

    # Get feature data from PostGIS
    df_feature = gpd.read_postgis(query_feature, engine, geom_col='geometry')

    # Drop duplicates
    df_feature.reset_index()
    df_feature = df_feature.drop_duplicates(ignore_index=True, subset=['date', 'PID'])

    # Get geometry from the second dataframe
    df_geo = df_feature[['PID', 'geometry']]
    df_geo = df_geo[['PID', 'geometry']].drop_duplicates()

    # Get meteo data from PostGIS
    df_meteo = pd.read_sql(query_history, engine)
    engine.dispose()

    # Convert fetaure data to matrix
    df = df_feature.pivot(index='date', columns='PID', values='feature_value')
    df = df.reset_index()
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # Create complete time series of features
    full_range = pd.date_range(start=df.index.min(), end=df.index.max())
    df_full = pd.DataFrame(index=full_range)
    df_full = df_full.join(df)

    # Add meteo data to the dataset
    df_meteo = df_meteo.set_index('date')
    df_full = df_full.join(df_meteo, how='left')

    # Drop unnecessary columns
    df_full.drop(columns=['osm_id'], inplace=True)

    # Rescale daily data to weekly data
    df_full = df_full.resample(freq).median()

    # Outliers detection and replacing
    # Replacing outliers occurred in the winter months
    winter_months_mask = df_full.index.month.isin([11, 12, 1, 2])
    df_full.loc[winter_months_mask] = df_full.loc[winter_months_mask].where(
        df_full.loc[winter_months_mask] <= df_full.mean(), np.nan)

    # Detection and replacing outliers in the dataset
    for col in df_full.columns[1:]:
        df_full[col] = detect_and_replace_outliers(df_full[col])

    return df_full, df_geo


@measure_execution_time
def data_imputation(db_name, user, osm_id, feature, model_id, db_wq_results, db_table_history, freq='W', t_shift=1):
    """
    Imputes missing values in a dataset using a combination of simple imputation, data normalization, and support vector regression.

    :param db_name: Database name
    :param user: Database user
    :param osm_id: OSM object id
    :param feature: Water quality feature
    :param model_id: Quality feature model ID
    :param db_wq_results: Water quality results PostGIS table
    :param db_table_history: Historical meteo data PostGIS table
    :param freq: Time scale (W - weekly, D - daily, M - monthly)
    :param t_shift: Time shift in days for predictors (for weekly time scale is recommended to use t_shift = 1, for daily time scale is recommended to use t_shift = 7)
    :return: GeoDataFrame with imputed data; GeoDataFrame with data smoothed with lowess method
    """

    # Get datasets and geometry
    df_full, df_geometry = create_dataset(db_name, user, osm_id, feature, model_id, db_wq_results, db_table_history, freq=freq)

    # Splitting data to predictors (X) and target (y)
    X = df_full[[
        'temperature_2m_max',
        'temperature_2m_min',
        'shortwave_radiation_sum'
    ]].shift(t_shift).values

    y = df_full.drop(columns=[
        'weather_code',
        'temperature_2m_max',
        'temperature_2m_min',
        'daylight_duration',
        'sunshine_duration',
        'precipitation_sum',
        'wind_speed_10m_max',
        'wind_direction_10m_dominant',
        'shortwave_radiation_sum'])

    # Make a copy of y for next step
    y_original = y.copy()
    y = y.values  # convert y to Numpy array

    # Mask and imputation of missing values
    # Imputation of missing values
    imputer = SimpleImputer(strategy='median')
    X_imputed = imputer.fit_transform(X)

    # Data normalization
    scaler_X = MinMaxScaler()
    scaler_y = MinMaxScaler()

    X_scaled = scaler_X.fit_transform(X_imputed)
    y_scaled = scaler_y.fit_transform(y)

    # Predictions of the missing values using SVR
    y_predicted_scaled = train_and_predict_svr(X_scaled, y_scaled)

    # Inverting results to the original scale of the target variable
    y_predicted = scaler_y.inverse_transform(y_predicted_scaled)
    y_predicted = np.where(y_predicted < 0, 0, y_predicted)

    # Replacing NaNs by the predicted values
    for i in range(y.shape[1]):
        y[:, i][np.isnan(y[:, i])] = y_predicted[:, i][np.isnan(y[:, i])]

    # Renaming columns
    y_original.index.name = 'date'
    col_names = y_original.columns

    # Converting back to DataFrame
    df_filled = pd.DataFrame(y, index=y_original.index, columns=col_names)

    # Using lowess smoothing
    df_lowess = data_smoothing(df_filled)

    # Melting data to the original shape (for both filled data and lowess smoothing)
    df_filled_melt = data_melting_2_gdf(df_filled, df_geometry)
    df_lowess_melt = data_melting_2_gdf(df_lowess, df_geometry)

    return df_filled_melt, df_lowess_melt


def detect_and_replace_outliers(series):
    """
    Detects and replaces outliers in a given series using the interquartile range (IQR) to detect outliers in a given series.

    :param series: The series to detect and replace outliers in.
    :return: The series with outliers replaced by NaN values.
    """

    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return series.where((series >= lower_bound) & (series <= upper_bound), np.nan)


def train_and_predict_svr(X, y):
    """
    Trains a Support Vector Regression (SVR) model and predicts the missing values in the dataset.

    :param X: Scaled environmental variables. Each row represents a sample and each column represents a feature.
    :param y: Scaled feature values. The target variable, where each row represents a sample and each column represents a feature.
    :return: Matrix of predictions. Each row represents a sample and each column represents a feature.
    """

    predictions = np.zeros(y.shape)
    for i in range(y.shape[1]):
        y_column = y[:, i]
        mask = ~np.isnan(y_column)  # Masking of the missing values

        # Model training using SVR
        svr = SVR(kernel='rbf', C=100, gamma=0.1, epsilon=0.1)
        svr.fit(X[mask], y_column[mask])

        # Prediction for each column
        predictions[:, i] = svr.predict(X)
    return predictions


def data_smoothing(df):
    """
    Smoothes all time series in the given DataFrame using the local regression Lowess method.

    :param df: The dataframe to be smoothed.
    :return: Smoothed dataframe.
    """

    lowess_results = []

    for i in df.columns:
        lowess = sm.nonparametric.lowess(df[i], df.index, frac=0.02)
        lowess_df = pd.DataFrame(lowess, columns=['date', i])
        lowess_df['date'] = pd.to_datetime(lowess_df['date'])
        lowess_df.set_index('date', inplace=True)

        lowess_results.append(lowess_df[i])

    lowess_df_all = pd.concat(lowess_results, axis=1)

    return lowess_df_all


def data_melting_2_gdf(df1, df2):
    """
    Melts a given DataFrame into a long format and merges it with geometry to create a GeoDataFrame.

    :param df1: The DataFrame to be melted.
    :param df2: The DataFrame with geometry information.
    :return: The melted and merged GeoDataFrame.
    """

    df = df1.reset_index()
    df['date'] = pd.to_datetime(df['date'])

    # Melt the dataframe
    df_melt = pd.melt(df, id_vars=['date'], value_vars=df.columns[1:])
    df_melt = df_melt.rename(columns={'variable': 'PID', 'value': 'feature_value'})

    # Merge the dataframes and convert do GeoDataFrame
    df_melt = df_melt.merge(df2, on='PID', how='left')
    df_melt = gpd.GeoDataFrame(df_melt, geometry='geometry')

    # Set datetime index
    df_melt = df_melt.set_index('date')

    return df_melt
