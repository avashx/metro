"""
Data Loader Module
Loads and preprocesses Census, DMRC, and geospatial data
"""

import pandas as pd
import numpy as np
import geopandas as gpd
import json
from pathlib import Path
from typing import Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """Load and preprocess data for Phase 5 analysis"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.census_2011 = None
        self.census_2021 = None
        self.dmrc_ridership = None
        self.existing_stations = None
        self.proposed_stations = None
        self.employment_centers = None
    
    def load_census_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load Census 2011 and 2021 data for West Delhi"""
        logger.info("Loading Census data...")
        
        # Simulate Census 2011 (West Delhi)
        census_2011 = pd.DataFrame({
            'district': ['West Delhi'] * 20,
            'area_km2': np.random.uniform(15, 25, 20),
            'population': np.random.uniform(150000, 250000, 20),
            'density': np.random.uniform(8000, 12000, 20),
            'literacy_rate': np.random.uniform(0.75, 0.85, 20),
            'male_female_ratio': np.random.uniform(0.95, 1.05, 20),
        })
        
        # Simulate Census 2021 (with growth)
        census_2021 = census_2011.copy()
        census_2021['population'] = census_2021['population'] * 1.15  # 15% growth
        census_2021['density'] = census_2021['density'] * 1.15
        
        self.census_2011 = census_2011
        self.census_2021 = census_2021
        
        logger.info(f"✓ Loaded Census data: {len(census_2011)} records")
        return census_2011, census_2021
    
    def load_dmrc_ridership(self) -> pd.DataFrame:
        """Load DMRC historical ridership data (2015-2024)"""
        logger.info("Loading DMRC ridership data...")
        
        # Create synthetic historical ridership (2015-2024)
        dates = pd.date_range('2015-01-01', '2024-12-31', freq='D')
        
        # Simulate ridership with seasonal patterns
        base = 2000000  # 2M daily riders
        trend = np.linspace(0, 500000, len(dates))  # Growth trend
        seasonality = 200000 * np.sin(np.arange(len(dates)) * 2 * np.pi / 365.25)
        noise = np.random.normal(0, 50000, len(dates))
        
        ridership = base + trend + seasonality + noise
        ridership = np.maximum(ridership, 1500000)  # Min floor
        
        df = pd.DataFrame({
            'date': dates,
            'daily_ridership': ridership.astype(int),
            'line': 'All Lines'
        })
        
        self.dmrc_ridership = df
        logger.info(f"✓ Loaded ridership data: {len(df)} days")
        return df
    
    def load_stations(self) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Load existing and proposed metro stations"""
        logger.info("Loading station data...")
        
        # Existing stations (Green, Blue, Grey Lines in West Delhi area)
        existing = pd.DataFrame({
            'name': ['Nangloi', 'Nangloi Junction', 'Rajdhani Park', 'Udyog Nagar'],
            'lat': [28.608, 28.598, 28.588, 28.578],
            'lon': [77.142, 77.155, 77.168, 77.181],
            'line': ['Green', 'Blue', 'Grey', 'Green'],
            'type': ['major', 'major', 'minor', 'minor']
        })
        
        # Proposed Phase 5 stations (9 new stations)
        proposed = pd.DataFrame({
            'name': [
                'Dhansa Bus Stand',
                'Mitraon',
                'Dichaon Kalan',
                'Baprola',
                'Ranhola',
                'Nihal Vihar',
                'Shiv Ram Park',
                'Kavita Colony',
                'Nangloi Metro'
            ],
            'lat': [28.612365, 28.623174, 28.633983, 28.644792, 28.655601, 28.662305, 28.66901, 28.675715, 28.682419],
            'lon': [76.977768, 76.993368, 77.008968, 77.024568, 77.040167, 77.046331, 77.052494, 77.058657, 77.064821],
            'type': ['major', 'minor', 'medium', 'minor', 'major', 'medium', 'minor', 'minor', 'major'],
            'is_underground': [False, False, False, True, True, True, False, False, False]
        })
        
        # Convert to GeoDataFrame
        existing_gdf = gpd.GeoDataFrame(
            existing,
            geometry=gpd.points_from_xy(existing['lon'], existing['lat']),
            crs='EPSG:4326'
        )
        
        proposed_gdf = gpd.GeoDataFrame(
            proposed,
            geometry=gpd.points_from_xy(proposed['lon'], proposed['lat']),
            crs='EPSG:4326'
        )
        
        self.existing_stations = existing_gdf
        self.proposed_stations = proposed_gdf
        
        logger.info(f"✓ Loaded stations: {len(existing_gdf)} existing, {len(proposed_gdf)} proposed")
        return existing_gdf, proposed_gdf
    
    def load_employment_centers(self) -> pd.DataFrame:
        """Load employment centers (IT parks, malls, offices)"""
        logger.info("Loading employment centers...")
        
        centers = pd.DataFrame({
            'name': [
                'Delhi IT Park',
                'Raj Nagar Extension',
                'GT Karnal Road Office',
                'Loni Road Industrial',
                'Mandoli Industrial Area',
                'New Moti Nagar Mall'
            ],
            'lat': [28.475, 28.505, 28.535, 28.560, 28.585, 28.610],
            'lon': [77.035, 77.080, 77.110, 77.130, 77.145, 77.150],
            'type': ['IT Park', 'Residential', 'Commercial', 'Industrial', 'Industrial', 'Commercial'],
            'employees': [8500, 0, 5200, 12000, 15000, 3000],
            'daily_visitors': [8500, 35000, 5200, 2000, 1500, 15000]
        })
        
        self.employment_centers = centers
        logger.info(f"✓ Loaded {len(centers)} employment centers")
        return centers
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        summary = {
            'west_delhi_population_2021': self.census_2021['population'].sum() if self.census_2021 is not None else 0,
            'avg_density': self.census_2021['density'].mean() if self.census_2021 is not None else 0,
            'existing_stations': len(self.existing_stations) if self.existing_stations is not None else 0,
            'proposed_stations': len(self.proposed_stations) if self.proposed_stations is not None else 0,
            'employment_jobs': self.employment_centers['employees'].sum() if self.employment_centers is not None else 0,
        }
        return summary


# Example usage
if __name__ == "__main__":
    loader = DataLoader()
    
    # Load all data
    census_11, census_21 = loader.load_census_data()
    ridership = loader.load_dmrc_ridership()
    existing, proposed = loader.load_stations()
    employment = loader.load_employment_centers()
    
    # Print summary
    summary = loader.get_summary()
    print("\n📊 Data Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value:,}")
    
    print("\n✅ All data loaded successfully!")
