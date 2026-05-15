"""
Population Forecaster Module
Forecasts population growth for 2025-2035
Uses exponential growth and Master Plan 2041 projections
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PopulationForecaster:
    """Forecast population growth for Phase 5 corridor"""
    
    def __init__(self, base_year: int = 2021):
        self.base_year = base_year
        self.forecast_years = None
        self.growth_rates = {}
    
    def calculate_cagr(self, population_2011: float, population_2021: float) -> float:
        """Calculate Compound Annual Growth Rate (CAGR)"""
        cagr = (population_2021 / population_2011) ** (1/10) - 1
        logger.info(f"Calculated CAGR: {cagr:.2%}")
        return cagr
    
    def forecast_linear(self, base_pop: float, cagr: float, start_year: int, end_year: int) -> pd.DataFrame:
        """Linear exponential forecast"""
        years = np.arange(start_year, end_year + 1)
        population = base_pop * (1 + cagr) ** (years - start_year)
        
        df = pd.DataFrame({
            'year': years,
            'population': population.astype(int),
            'method': 'Exponential Growth'
        })
        return df
    
    def forecast_master_plan(self, base_pop: float, start_year: int, end_year: int) -> pd.DataFrame:
        """Forecast using Delhi Master Plan 2041 projections"""
        # MP2041 assumes different growth rates by period
        # 2021-2030: Slower growth (2.2%), 2030-2041: Faster (2.8%)
        
        years = []
        population = []
        
        for year in range(start_year, end_year + 1):
            if year <= 2030:
                rate = 0.022
                pop = base_pop * (1 + rate) ** (year - start_year)
            else:
                # From 2021 to 2030
                pop_2030 = base_pop * (1 + 0.022) ** (2030 - start_year)
                # From 2030 to current year
                pop = pop_2030 * (1 + 0.028) ** (year - 2030)
            
            years.append(year)
            population.append(int(pop))
        
        df = pd.DataFrame({
            'year': years,
            'population': population,
            'method': 'Master Plan 2041'
        })
        return df
    
    def forecast_conservative(self, base_pop: float, start_year: int, end_year: int) -> pd.DataFrame:
        """Conservative forecast (lower growth)"""
        cagr = 0.018  # 1.8% annual growth
        
        years = np.arange(start_year, end_year + 1)
        population = base_pop * (1 + cagr) ** (years - start_year)
        
        df = pd.DataFrame({
            'year': years,
            'population': population.astype(int),
            'method': 'Conservative'
        })
        return df
    
    def forecast_aggressive(self, base_pop: float, start_year: int, end_year: int) -> pd.DataFrame:
        """Aggressive forecast (higher growth)"""
        cagr = 0.032  # 3.2% annual growth
        
        years = np.arange(start_year, end_year + 1)
        population = base_pop * (1 + cagr) ** (years - start_year)
        
        df = pd.DataFrame({
            'year': years,
            'population': population.astype(int),
            'method': 'Aggressive'
        })
        return df
    
    def get_density_forecast(self, population_forecast: pd.DataFrame, area_km2: float) -> pd.DataFrame:
        """Calculate population density from forecast"""
        forecast = population_forecast.copy()
        forecast['density'] = (forecast['population'] / area_km2).astype(int)
        return forecast
    
    def get_employment_forecast(self, population_forecast: pd.DataFrame, employment_ratio: float = 0.35) -> pd.DataFrame:
        """Estimate employment from population (assuming 35% are workforce)"""
        forecast = population_forecast.copy()
        forecast['workforce'] = (forecast['population'] * employment_ratio).astype(int)
        forecast['employment_multiplier'] = 1.5  # 1.5 jobs per workforce member
        forecast['total_jobs'] = (forecast['workforce'] * forecast['employment_multiplier']).astype(int)
        return forecast


def forecast_phase5_corridor():
    """Forecast population for entire Phase 5 corridor"""
    
    # Base data from Census 2021
    west_delhi_pop_2021 = 3_500_000
    area_km2 = 105.96
    
    forecaster = PopulationForecaster(base_year=2021)
    
    # Calculate CAGR from 2011-2021 (assumed 1.5%)
    west_delhi_pop_2011 = 3_040_000  # From Census 2011
    cagr = forecaster.calculate_cagr(west_delhi_pop_2011, west_delhi_pop_2021)
    
    # Generate three scenarios
    forecast_mp = forecaster.forecast_master_plan(west_delhi_pop_2021, 2021, 2035)
    forecast_conservative = forecaster.forecast_conservative(west_delhi_pop_2021, 2021, 2035)
    forecast_aggressive = forecaster.forecast_aggressive(west_delhi_pop_2021, 2021, 2035)
    
    # Add density
    forecast_mp = forecaster.get_density_forecast(forecast_mp, area_km2)
    forecast_conservative = forecaster.get_density_forecast(forecast_conservative, area_km2)
    forecast_aggressive = forecaster.get_density_forecast(forecast_aggressive, area_km2)
    
    # Add employment
    forecast_mp = forecaster.get_employment_forecast(forecast_mp)
    forecast_conservative = forecaster.get_employment_forecast(forecast_conservative)
    forecast_aggressive = forecaster.get_employment_forecast(forecast_aggressive)
    
    return forecast_mp, forecast_conservative, forecast_aggressive


# Example usage
if __name__ == "__main__":
    forecast_mp, forecast_cons, forecast_agg = forecast_phase5_corridor()
    
    print("\n📊 WEST DELHI POPULATION FORECAST (2021-2035)")
    print("=" * 80)
    
    print("\nMaster Plan 2041 Scenario:")
    print(forecast_mp[['year', 'population', 'density', 'total_jobs']].to_string(index=False))
    
    print("\nConservative Scenario:")
    print(forecast_cons[['year', 'population', 'density', 'total_jobs']].to_string(index=False))
    
    print("\nAggressive Scenario:")
    print(forecast_agg[['year', 'population', 'density', 'total_jobs']].to_string(index=False))
    
    # Summary statistics
    print("\n📈 FORECAST SUMMARY (2035 vs 2021):")
    print("=" * 80)
    for name, df in [("Master Plan 2041", forecast_mp), ("Conservative", forecast_cons), ("Aggressive", forecast_agg)]:
        pop_2021 = df[df['year'] == 2021]['population'].values[0]
        pop_2035 = df[df['year'] == 2035]['population'].values[0]
        growth = ((pop_2035 / pop_2021) - 1) * 100
        print(f"\n{name}:")
        print(f"  2021 Population: {pop_2021:,}")
        print(f"  2035 Population: {pop_2035:,}")
        print(f"  14-Year Growth: {growth:.1f}%")
        print(f"  CAGR: {(((pop_2035/pop_2021)**(1/14)) - 1)*100:.2f}%")
