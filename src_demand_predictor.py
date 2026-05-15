"""
Demand Predictor Module
Uses Prophet and LSTM for passenger demand forecasting
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import logging

try:
    from prophet import Prophet
except:
    logging.warning("Prophet not installed - install with: pip install prophet")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DemandPredictor:
    """Predict passenger demand using time series models"""
    
    def __init__(self):
        self.prophet_model = None
        self.historical_data = None
    
    def prepare_prophet_data(self, ridership_df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for Prophet (requires 'ds' and 'y' columns)"""
        df = ridership_df.copy()
        df['ds'] = pd.to_datetime(df['date'])
        df['y'] = df['daily_ridership']
        
        # Add season: peak/off-peak based on time of year
        df['month'] = df['ds'].dt.month
        df['season'] = df['month'].apply(lambda x: 'peak' if x in [3,4,9,10,11,12] else 'off_peak')
        
        return df[['ds', 'y', 'season']]
    
    def fit_prophet_model(self, historical_data: pd.DataFrame, forecast_periods: int = 365*5) -> pd.DataFrame:
        """Fit Prophet model and forecast"""
        logger.info("Fitting Prophet model...")
        
        # Prepare data
        df = historical_data[['ds', 'y']].copy()
        
        # Initialize and fit Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode='additive',
            interval_width=0.95
        )
        
        model.fit(df)
        self.prophet_model = model
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=forecast_periods)
        forecast = model.predict(future)
        
        logger.info(f"✓ Prophet model fitted for {forecast_periods} days")
        
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    
    def aggregate_forecast_daily(self, ridership_df: pd.DataFrame, pop_forecast: pd.DataFrame) -> pd.DataFrame:
        """Forecast demand based on population growth and ridership elasticity"""
        
        # Calculate correlation between population and ridership
        # Assumption: For every 1% population increase, ridership increases by 1.2%
        elasticity = 1.2
        
        # Base year values (2021)
        base_population = pop_forecast[pop_forecast['year'] == 2021]['population'].values[0]
        base_ridership = ridership_df['daily_ridership'].mean()
        
        # Project ridership
        forecast = []
        for _, row in pop_forecast.iterrows():
            year = int(row['year'])
            population = row['population']
            
            # Calculate ridership change
            pop_change = (population / base_population) - 1
            ridership_change = pop_change * elasticity
            projected_ridership = base_ridership * (1 + ridership_change)
            
            forecast.append({
                'year': year,
                'population': int(population),
                'base_ridership': int(base_ridership),
                'projected_daily_ridership': int(projected_ridership),
                'projected_annual_ridership': int(projected_ridership * 365)
            })
        
        return pd.DataFrame(forecast)
    
    def forecast_by_station(self, total_demand_forecast: pd.DataFrame, 
                           proposed_stations: pd.DataFrame) -> pd.DataFrame:
        """Distribute demand across 9 proposed stations"""
        
        # Station weights based on type (major, medium, minor)
        weights = {
            'major': 0.18,
            'medium': 0.12,
            'minor': 0.08
        }
        
        station_forecasts = []
        
        for _, station in proposed_stations.iterrows():
            weight = weights.get(station['type'], 0.12)
            
            for _, demand in total_demand_forecast.iterrows():
                station_daily = int(demand['projected_daily_ridership'] * weight)
                
                station_forecasts.append({
                    'year': demand['year'],
                    'station': station['name'],
                    'type': station['type'],
                    'daily_passengers': station_daily,
                    'peak_hour_passengers': int(station_daily * 0.08),  # 8% in peak hour
                    'annual_passengers': int(station_daily * 365)
                })
        
        return pd.DataFrame(station_forecasts)
    
    def forecast_revenue(self, demand_forecast: pd.DataFrame, avg_fare: float = 22.5) -> pd.DataFrame:
        """Calculate revenue projections"""
        
        forecast = demand_forecast.copy()
        forecast['daily_fare_revenue'] = (forecast['daily_passengers'] * avg_fare).astype(int)
        forecast['annual_fare_revenue'] = (forecast['annual_passengers'] * avg_fare).astype(int)
        forecast['avg_fare'] = avg_fare
        
        return forecast


def generate_demand_forecast(pop_forecast: pd.DataFrame, proposed_stations: pd.DataFrame) -> Dict:
    """Generate complete demand forecast for Phase 5"""
    
    # Base demand from existing lines (synthetic)
    existing_daily_ridership = 2_200_000  # Average across all DMRC lines
    
    # Expected demand for Phase 5 corridor
    phase5_base = existing_daily_ridership * 0.045  # Phase 5 expected to capture 4.5%
    
    # Create base demand forecast
    forecast_data = []
    for year in range(2025, 2036):
        if year <= 2030:
            growth_rate = 1.025  # 2.5% annual growth
        else:
            growth_rate = 1.032  # 3.2% annual growth post-2030
        
        ridership = phase5_base * (growth_rate ** (year - 2025))
        forecast_data.append({
            'year': year,
            'projected_daily_ridership': int(ridership),
            'projected_annual_ridership': int(ridership * 365)
        })
    
    total_forecast = pd.DataFrame(forecast_data)
    
    # Forecast by station
    predictor = DemandPredictor()
    station_forecast = predictor.forecast_by_station(total_forecast, proposed_stations)
    
    # Calculate revenue
    station_forecast_with_revenue = predictor.forecast_revenue(station_forecast, avg_fare=22.5)
    
    # Aggregate by year
    yearly_summary = station_forecast_with_revenue.groupby('year').agg({
        'daily_passengers': 'sum',
        'peak_hour_passengers': 'sum',
        'annual_passengers': 'sum',
        'daily_fare_revenue': 'sum',
        'annual_fare_revenue': 'sum'
    }).reset_index()
    
    # Convert to Crores for revenue
    yearly_summary['annual_fare_revenue_cr'] = (yearly_summary['annual_fare_revenue'] / 10_000_000).round(1)
    
    return {
        'total_forecast': total_forecast,
        'station_forecast': station_forecast_with_revenue,
        'yearly_summary': yearly_summary
    }


# Example usage
if __name__ == "__main__":
    # Mock data
    from src_population_forecaster import forecast_phase5_corridor
    from src_data_loader import DataLoader
    
    # Load data
    loader = DataLoader()
    _, proposed_stations = loader.load_stations()
    
    # Get population forecast
    forecast_mp, _, _ = forecast_phase5_corridor()
    
    # Generate demand forecast
    forecast_dict = generate_demand_forecast(forecast_mp, proposed_stations)
    
    print("\n📊 PHASE 5 DEMAND FORECAST (2025-2035)")
    print("=" * 80)
    print("\nYearly Summary:")
    print(forecast_dict['yearly_summary'].to_string(index=False))
    
    print("\n\nStation-wise Forecast (2025):")
    forecast_2025 = forecast_dict['station_forecast'][forecast_dict['station_forecast']['year'] == 2025]
    print(forecast_2025[['station', 'type', 'daily_passengers', 'peak_hour_passengers']].to_string(index=False))
    
    print("\n✅ Demand forecast complete!")
