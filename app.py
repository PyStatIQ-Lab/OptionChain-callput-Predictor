import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Function to fetch data with error handling
def fetch_option_chain():
    url = "https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry=03-04-2025"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises exception for 4XX/5XX errors
        
        data = response.json()
        
        # Check if the expected data structure exists
        if 'data' not in data or 'strikePrices' not in data['data']:
            raise ValueError("Unexpected API response structure")
            
        return data
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None
    except ValueError as e:
        print(f"Data format error: {e}")
        return None

# Main analysis function
def analyze_option_chain(data):
    if data is None:
        print("No data available for analysis")
        return
    
    try:
        # Convert strike prices to DataFrame
        strike_prices = pd.DataFrame(data['data']['strikePrices'])
        
        # Get current spot price (approximate ATM strike)
        current_spot = strike_prices[strike_prices['isAtm'] == True]['strikePrice'].values[0]
        
        # Process call and put options
        def process_options(options_list):
            return pd.DataFrame([{
                'strikePrice': item['strikePrice'],
                'openInterest': item.get('openInterest', 0),
                'changeinOpenInterest': item.get('changeinOpenInterest', 0),
                'totalTradedVolume': item.get('totalTradedVolume', 0),
                'impliedVolatility': item.get('impliedVolatility', 0),
                'lastPrice': item.get('lastPrice', 0),
                'bidQty': item.get('bidQty', 0),
                'bidPrice': item.get('bidPrice', 0),
                'askPrice': item.get('askPrice', 0),
                'askQty': item.get('askQty', 0)
            } for item in options_list])
        
        calls = process_options(data['data']['callOptions'])
        puts = process_options(data['data']['putOptions'])
        
        # Merge calls and puts
        option_chain = pd.merge(calls, puts, on='strikePrice', suffixes=('_call', '_put'))
        
        # Add moneyness
        option_chain['moneyness'] = option_chain['strikePrice'].apply(
            lambda x: 'ITM' if x < current_spot else 'OTM' if x > current_spot else 'ATM'
        )
        
        return option_chain, current_spot
    
    except Exception as e:
        print(f"Error processing data: {e}")
        return None, None

# Function to display analysis
def display_analysis(option_chain, current_spot):
    if option_chain is None:
        return
    
    print(f"\nCurrent Spot Price (Approx): {current_spot}")
    print(f"Expiry Date: 03-04-2025")
    print(f"Total Strike Prices Available: {len(option_chain)}\n")
    
    # Top 5 ITM and OTM calls and puts
    itm_calls = option_chain[option_chain['moneyness'] == 'ITM'].sort_values('strikePrice', ascending=False).head(5)
    otm_calls = option_chain[option_chain['moneyness'] == 'OTM'].sort_values('strikePrice', ascending=True).head(5)
    itm_puts = option_chain[option_chain['moneyness'] == 'ITM'].sort_values('strikePrice', ascending=True).head(5)
    otm_puts = option_chain[option_chain['moneyness'] == 'OTM'].sort_values('strikePrice', ascending=False).head(5)
    
    print("=== Top 5 ITM Calls ===")
    print(itm_calls[['strikePrice', 'lastPrice_call', 'openInterest_call', 'impliedVolatility_call']])
    
    print("\n=== Top 5 OTM Calls ===")
    print(otm_calls[['strikePrice', 'lastPrice_call', 'openInterest_call', 'impliedVolatility_call']])
    
    print("\n=== Top 5 ITM Puts ===")
    print(itm_puts[['strikePrice', 'lastPrice_put', 'openInterest_put', 'impliedVolatility_put']])
    
    print("\n=== Top 5 OTM Puts ===")
    print(otm_puts[['strikePrice', 'lastPrice_put', 'openInterest_put', 'impliedVolatility_put']])

# Main execution
if __name__ == "__main__":
    print("Fetching Nifty 50 option chain data...")
    data = fetch_option_chain()
    option_chain, current_spot = analyze_option_chain(data)
    
    if option_chain is not None:
        display_analysis(option_chain, current_spot)
        
        # Plotting
        plt.figure(figsize=(15, 10))
        
        # OI Plot
        plt.subplot(2, 1, 1)
        plt.plot(option_chain['strikePrice'], option_chain['openInterest_call'], label='Call OI', color='green')
        plt.plot(option_chain['strikePrice'], option_chain['openInterest_put'], label='Put OI', color='red')
        plt.axvline(x=current_spot, color='blue', linestyle='--', label='Current Spot')
        plt.title('Open Interest by Strike Price')
        plt.legend()
        
        # Price Plot
        plt.subplot(2, 1, 2)
        plt.plot(option_chain['strikePrice'], option_chain['lastPrice_call'], label='Call Price', color='green')
        plt.plot(option_chain['strikePrice'], option_chain['lastPrice_put'], label='Put Price', color='red')
        plt.axvline(x=current_spot, color='blue', linestyle='--', label='Current Spot')
        plt.title('Option Prices by Strike Price')
        plt.legend()
        
        plt.tight_layout()
        plt.show()
    else:
        print("Failed to analyze option chain data")
