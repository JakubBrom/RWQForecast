import osmnx as ox
import geopandas as gpd
import sys
import json
import uuid
import os
import time
from warnings import warn

if __name__ == "__main__":    
    try:
        # Example coordinates (latitude, longitude)
        lat = sys.argv[1]
        lon = sys.argv[2]
        dist = sys.argv[3]  # Distance in meters

        # Get water features within the specified distance from the point
        gdf = ox.features_from_point((float(lat), float(lon)), dist=float(dist), tags={"natural": "water"})
        gdf.set_crs('epsg:4326')
        gdf = gdf.reset_index()
        
        # Export the GeoDataFrame
        # If gdf is not empty
        if not gdf.empty:
            out_name = f"{uuid.uuid4()}.geojson"
            out_path = os.path.join(os.getcwd(), 'cache', out_name)
            gdf.to_file(out_path, driver='GeoJSON')
            
            # Check if the file is available
            t0 = time.time()
            while not os.path.exists(out_path):
                if time.time() - t0 > 360:                  # up to 6 minutes
                    warn(f"Data are not available.", stacklevel=2)
                time.sleep(0.1)
            
            print(out_path)
        else:
            print(json.dumps({"error": "No geometry found"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
