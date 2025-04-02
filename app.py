import requests
import pandas as pd
import matplotlib.pyplot as plt

def fetch_option_chain():
    """Fetch option chain data from Upstox API"""
    url = "https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry=03-04-2025"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

def process_option_chain(data):
    """Process the raw API data into a structured DataFrame"""
    if not data or 'data' not in data:
        print("Invalid or empty API response")
        return None, None
    
    try:
        # Extract strike prices
        strikes = data['data']['strikePrices']
        current_spot = next((s['strikePrice'] for s in strikes if s.get('isAtm', False)), None)
        
        if current_spot is None:
            print("Could not determine current spot price")
            return None, None

        # Process calls and puts
        def process_options(options):
            return [{
                'strikePrice': opt['strikePrice'],
                'openInterest': opt.get('openInterest', 0),
                'changeinOpenInterest': opt.get('changeinOpenInterest', 0),
                'totalTradedVolume': opt.get('totalTradedVolume', 0),
                'impliedVolatility': opt.get('impliedVolatility', 0),
                'lastPrice': opt.get('lastPrice', 0),
                'bidPrice': opt.get('bidPrice', 0),
                'askPrice': opt.get('askPrice', 0)
            } for opt in options]

        calls = process_options(data['data']['callOptions'])
        puts = process_options(data['data']['putOptions'])

        # Create DataFrames
        calls_df = pd.DataFrame(calls).add_suffix('_call')
        puts_df = pd.DataFrame(puts).add_suffix('_put')
        
        # Merge on strike price
        option_chain = pd.merge(
            calls_df.rename(columns={'strikePrice_call': 'strikePrice'}),
            puts_df.rename(columns={'strikePrice_put': 'strikePrice'}),
            on='strikePrice'
        )
        
        # Add moneyness
        option_chain['moneyness'] = option_chain['strikePrice'].apply(
            lambda x: 'ITM' if x < current_spot else 'OTM' if x > current_spot else 'ATM'
        )

        return option_chain, current_spot

    except Exception as e:
        print(f"Data processing error: {e}")
        return None, None

def display_analysis(option_chain, current_spot):
    """Display the option chain analysis"""
    if option_chain is None or current_spot is None:
        return

    print(f"\nCurrent Spot Price (Approx): {current_spot}")
    print(f"Expiry Date: 03-04-2025")
    print(f"Total Strike Prices Available: {len(option_chain)}\n")

    # Top 5 ITM and OTM options
    for option_type in ['call', 'put']:
        for moneyness in ['ITM', 'OTM']:
            df = option_chain[option_chain['moneyness'] == moneyness]
            if option_type == 'call':
                df = df.sort_values('strikePrice', ascending=(moneyness == 'OTM'))
            else:
                df = df.sort_values('strikePrice', ascending=(moneyness == 'ITM'))
            
            print(f"=== Top 5 {moneyness} {option_type.title()}s ===")
            print(df.head(5)[[
                'strikePrice', 
                f'lastPrice_{option_type}', 
                f'openInterest_{option_type}', 
                f'impliedVolatility_{option_type}'
            ]])
            print()

def plot_option_chain(option_chain, current_spot):
    """Plot option chain data"""
    if option_chain is None or current_spot is None:
        return

    plt.figure(figsize=(15, 10))
    
    # Open Interest Plot
    plt.subplot(2, 1, 1)
    plt.plot(option_chain['strikePrice'], option_chain['openInterest_call'], 'g-', label='Call OI')
    plt.plot(option_chain['strikePrice'], option_chain['openInterest_put'], 'r-', label='Put OI')
    plt.axvline(x=current_spot, color='b', linestyle='--', label='Current Spot')
    plt.title('Open Interest by Strike Price')
    plt.xlabel('Strike Price')
    plt.ylabel('Open Interest')
    plt.legend()
    
    # Price Plot
    plt.subplot(2, 1, 2)
    plt.plot(option_chain['strikePrice'], option_chain['lastPrice_call'], 'g-', label='Call Price')
    plt.plot(option_chain['strikePrice'], option_chain['lastPrice_put'], 'r-', label='Put Price')
    plt.axvline(x=current_spot, color='b', linestyle='--', label='Current Spot')
    plt.title('Option Prices by Strike Price')
    plt.xlabel('Strike Price')
    plt.ylabel('Option Price')
    plt.legend()
    
    plt.tight_layout()
    plt.show()

def main():
    """Main execution function"""
    print("Fetching Nifty 50 option chain data...")
    data = fetch_option_chain()
    
    if data is None:
        print("Failed to fetch data")
        return
    
    option_chain, current_spot = process_option_chain(data)
    
    if option_chain is not None and current_spot is not None:
        display_analysis(option_chain, current_spot)
        plot_option_chain(option_chain, current_spot)
    else:
        print("Failed to process option chain data")

if __name__ == "__main__":
    main()
