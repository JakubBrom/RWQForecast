import os

import numpy as np
import pandas as pd
import geopandas as gpd

from shapely.geometry import Polygon, Point
from scipy.spatial import Delaunay, Voronoi
from sqlalchemy import create_engine, text
from multiprocessing import Pool
from AIHABs_wrappers import measure_execution_time


def points_clip(points, polygon):
    """
    Clip points to the polygon
    :param points: GeoDataFrame with points
    :param polygon: GeoDataFrame with polygons
    :return: Clipped points (GeoDataFrame)
    """
    return points[points.intersects(polygon)]


def point_mesh(polygon, distance_lat=0.01, distance_lon=0.01):
    """
    Create a grid of points based on the bounding box of the input polygon.

    :param polygon: A GeoDataFrame representing a polygon.
    :param distance_lat: The distance between grid points in latitude. Default 0.01° for EPSG:4326.
    :param distance_lon: The distance between grid points in longitude. Default 0.01° for EPSG:4326.
    :return: A GeoDataFrame containing the grid points.
    """

    # Get the bounding box of the polygon
    minx, miny, maxx, maxy = polygon.total_bounds

    # Calculate the number of grid points based on the distance and bounding box size
    num_points_lat = int((maxy - miny)/distance_lat)
    num_points_lon = int((maxx - minx)/distance_lon)

    # Create the grid points
    latitudes = np.linspace(miny, maxy, num_points_lat)
    longitudes = np.linspace(minx, maxx, num_points_lon)
    grid_points = [Point(lon, lat) for lat in latitudes for lon in longitudes]

    # Convert the grid points into a GeoDataFrame
    gdf_grid = gpd.GeoDataFrame(geometry=grid_points)

    return gdf_grid


def delaunay_centroids(vertices):
    """
    Perform Delaunay triangulation on the given vertices and return a GeoDataFrame
    containing the centroids of the Voronoi regions.

    :param vertices: The vertices for the Delaunay triangulation. Points geometry.
    :return: A GeoDataFrame containing the centroids of the Delaunay triangles.
    """

    # Calculate Delaunay triangulation
    tri = Delaunay(vertices)

    # Get triangles
    triangles = np.array([Polygon(vertices[simplex]) for simplex in tri.simplices])
    gdf_triangles = gpd.GeoDataFrame(geometry=triangles)

    # Centroids of the triangles
    centroids = gdf_triangles['geometry'].centroid
    gdf_centroids = gpd.GeoDataFrame(geometry=centroids)

    return gdf_centroids


def voronoi_centroids(vertices):
    """
    Perform Voronoi triangulation on the given vertices and return a GeoDataFrame
    containing the centroids of the Voronoi regions.

    :param vertices: The vertices for the Voronoi triangulation. Points geometry.
    :return: A GeoDataFrame containing the centroids of the Voronoi triangles.
    """
    # Calculate Voronoi triangulation
    vor = Voronoi(vertices)

    # Get valid regions
    valid_regions = [region for region in vor.regions if -1 not in region and len(region) > 0]

    # Get Voronoi polygons
    vor_polygons = [Polygon(vor.vertices[region]) for region in valid_regions]
    gdf_polygons = gpd.GeoDataFrame(geometry=vor_polygons)

    # Centroids of the polygons
    centroids = gdf_polygons['geometry'].centroid
    gdf_centroids = gpd.GeoDataFrame(geometry=centroids)

    return gdf_centroids


def get_vertices(polygon):
    """
    Extracts the coordinates of the vertices of the given polygon, including both exterior and interior coordinates if present.

    :param polygon: A polygon object from which to extract the vertices.
    :return: An array of coordinates representing the vertices of the polygon.
    """

    # Extract exterior coordinates
    exterior_coords = np.array(polygon.exterior.coords)

    # Extract interior coordinates if present
    gdf = gpd.GeoDataFrame(geometry=[polygon], crs='epsg:4326')
    geometry = gdf.geometry[0]

    if len(geometry.interiors) > 0:
        # Extract interior coordinates
        interior_coords = np.concatenate([np.array(interior.coords) for interior in polygon.interiors])

        # Combine exterior and interior coordinates
        all_coords = np.vstack([exterior_coords, interior_coords])

    else:
        # Combine exterior coordinates
        all_coords = exterior_coords

    return all_coords


def generate_points_in_polygon(in_gdf_polygon, lake_buffer=-20, n_points_km=100, n_max_points=5000, **kwargs):
    """
    Generate points within a polygon with respect of its complexity, and clip them with a buffer zone.

    :param in_gdf_polygon: The input polygon as a GeoDataFrame.
    :param lake_buffer: The buffer distance inside the selected water reservoir. Defaults to -20.
    :param n_points_km: The number of points per square kilometer in the area of the reservoir. Defaults to 100.
    :param n_max_points: The maximum number of points to be generated. Defaults to 5000.

    :returns: - The generated points clipped with the buffer layer (GeoDataFrame).
              - The randomly selected points within the buffer layer (GeoDataFrame).
              - The buffer layer in the original coordinate reference system (GeoDataFrame).
    """

    # Simplyfy input polygon
    polygon_geom = in_gdf_polygon['geometry'][0].simplify(0.0001, preserve_topology=True)
    gdf_polygon = gpd.GeoDataFrame(geometry=[polygon_geom], crs=in_gdf_polygon.crs)

    # Get the vertices of the polygon
    vertices = get_vertices(polygon_geom)

    # Get random points
    gdf_Delaunay_centroids = delaunay_centroids(vertices)
    gdf_Voronoi_centroids = voronoi_centroids(vertices)
    gdf_mesh = point_mesh(gdf_polygon)

    # Concatenate all centroids
    gdf_centroids = gpd.pd.concat([gdf_Delaunay_centroids, gdf_Voronoi_centroids, gdf_mesh], ignore_index=True)

    # Sample centroids for decreasing number of points in the dataset
    if len(gdf_centroids) > 10000:
        gdf_centroids = gdf_centroids.sample(10000)

    # Create a buffer zone inside the selected water reservoir
    # Get original CRS of the input layer
    try:
        epsg_orig = in_gdf_polygon.crs()
    except:
        epsg_orig = 'epsg:4326'

    # Convert selected layer to UTM CRS
    epsg_new = in_gdf_polygon.estimate_utm_crs()
    gdf_polygon_utm = gdf_polygon.to_crs(epsg_new)

    # Remove buffer zone of the selected water reservoir
    gdf_buffer_utm = gdf_polygon_utm.buffer(lake_buffer)

    # Cover the buffer layer to the original CRS
    gdf_buffer_wgs = gdf_buffer_utm.to_crs(epsg_orig)
    buffer_wgs_geometry = gdf_buffer_wgs.geometry.iloc[0]

    # Clip centroids with the buffer layer
    num_processes = os.cpu_count()
    chunk_size = len(gdf_centroids) // num_processes
    points_subsets = [gdf_centroids.iloc[i * chunk_size: (i + 1) * chunk_size] for i in range(num_processes)]

    with Pool(num_processes) as pool:
        results = pool.starmap(points_clip, [(subset, buffer_wgs_geometry) for subset in points_subsets])
    gdf_centroids_clipped = gpd.GeoDataFrame(pd.concat(results))

    # Calculate area of the reservoir
    area = gdf_polygon_utm.area.values[0] / 10000

    # Get number of points for the area
    n_points = int(area * n_points_km / 100) + 1

    n_centroids_clipped = len(gdf_centroids_clipped)

    if n_points <= n_points_km:
        n_points = min(n_points_km, n_centroids_clipped)
    else:
        n_points = min(n_points, n_centroids_clipped, n_max_points)

    print(f'Number of points for the reservoir: {n_points}')

    # Sample points
    gdf_centroids_selected = gdf_centroids_clipped.sample(n=n_points)
    gdf_centroids_selected = gpd.GeoDataFrame(gdf_centroids_selected, geometry='geometry', crs='epsg:4326')

    return gdf_centroids_clipped, gdf_centroids_selected, gdf_buffer_wgs


@measure_execution_time
def get_sampling_points(osm_id, db_name, user, db_table_reservoirs, db_table_points, **kwargs):
    """

    :param osm_id: OSM object id
    :param db_name: Database name
    :param user: Database user
    :param db_table_reservoirs: Database table with water reservoirs polygons
    :param db_table_points: Database table with points for reservoir polygons
    :param kwargs: Additional parameters
    :return: The randomly selected points within the buffer layer of reservoirs (GeoDataFrame). Points for reservoirs are stored in the db_table_points database table.
    """

    # Connect to PostGIS
    engine = create_engine('postgresql://{user}@/{db_name}'.format(user=user, db_name=db_name))

    # Check if points table exists and create new one if not
    query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tab_name}')".format(tab_name=db_table_points))

    with engine.connect() as connection:
        result = connection.execute(query)
        exists = result.scalar()

    if exists:
        # Check if are the data available in the table
        query = text("SELECT EXISTS (SELECT 1 FROM {db_table} WHERE osm_id = '{osm_id}')".format(db_table=db_table_points, osm_id=str(osm_id)))
        with engine.connect() as connection:
            result = connection.execute(query)
            data_exists = result.scalar()

        if data_exists:
            query = text("SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(db_table=db_table_points, osm_id=str(osm_id)))
            points_selected = gpd.read_postgis(query, engine, geom_col='geometry')

            return points_selected

    # Get polygon of the reservoir from the DB
    sql_query = "SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(osm_id=str(osm_id), db_table=db_table_reservoirs)
    gdf = gpd.read_postgis(sql_query, engine, geom_col='geometry')
    polygon = gpd.GeoDataFrame(gdf, geometry='geometry', crs='epsg:4326')

    # Produce random points in the reservoir polygon
    points_selected = generate_points_in_polygon(polygon, **kwargs)[1]
    points_selected['osm_id'] = str(osm_id)  # Add osm_id
    points_selected['PID'] = [i for i in range(len(points_selected))]

    # Insert points into the DB table
    points_selected.to_postgis(db_table_points, con=engine, if_exists='append', index=False)
    engine.dispose()

    return points_selected
