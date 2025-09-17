import dill
from sqlalchemy import text
import pandas as pd
import geopandas as gpd
import json
import sys
from db import SessionLocal
import os
import uuid
import time
from warnings import warn

def get_model_from_db(model_id, db_session, db_models):
    """
    Function for getting prediction model from the database.

    :param model_id: Model ID
    :param db_session: Database session
    :param db_models: Database table with AI models
    :return: Model object
    """

    # Get prediction model from DB and model ID
    query = text(f"SELECT pkl_file FROM {db_models} WHERE model_id = :model_id")
    result = db_session.execute(query, {"model_id": model_id}).fetchone()

    if result is None:
        raise ValueError(f"No model found with model_id: {model_id}")

    pkl_data = result[0]
    
    # Load the model from the binary data using dill
    try:
        AI_model = dill.loads(pkl_data)
        
    except Exception as e:
        raise ValueError(f"Error loading model with model_id {model_id}: {e}")
    
    return AI_model

if __name__ == "__main__":
    db_session = SessionLocal()
    
    # Get data
    model_id = sys.argv[1]
    db_models = sys.argv[2]
    csv_path = sys.argv[3]
    
    # Reading Sentinel-2 data
    df = pd.read_csv(csv_path, skip_blank_lines=True)
    
    # Set output
    out_dir = os.path.split(csv_path)[0]
    out_name = f"{uuid.uuid4()}.csv"
    out_path = os.path.join(os.getcwd(), 'cache', out_name)
    out_df = pd.DataFrame()

    # Get model from the DB
    try:
        model = get_model_from_db(model_id, db_session, db_models)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    
    # Predict data using model
    try:    
        pred_values = model.predict(df)
        out_df['fvalues'] = pred_values
        out_df.to_csv(out_path)
        
        # Check if the file is available
        t0 = time.time()
        while not os.path.exists(csv_path):
            if time.time() - t0 > 360:                  # up to 6 minutes
                warn("The path to predicted data does not exists...", stacklevel=2)
            
            time.sleep(0.01)         

        # Export path to data
        print(out_path)

    except Exception as e:
        print(json.dumps({"error": str(e)}))
    
    

