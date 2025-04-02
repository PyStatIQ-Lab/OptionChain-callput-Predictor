import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Fetch data from Upstox API
url = "https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry=03-04-2025"
response = requests.get(url)
data = response.json()

# Convert to DataFrame
df = pd.DataFrame(data['data']['strikePrices'])

# Calculate current spot price (approximate ATM strike)
current_spot = df[df['isAtm'] == True]['strikePrice'].values[0]

# Process call and put options
def process_options(options_list):
    return pd.DataFrame([{
        'strikePrice': item['strikePrice'],
        'openInterest': item['openInterest'],
        'changeinOpenInterest': item['changeinOpenInterest'],
        'totalTradedVolume': item['totalTradedVolume'],
        'impliedVolatility': item['impliedVolatility'],
        'lastPrice': item['lastPrice'],
        'bidQty': item['bidQty'],
        'bidPrice': item['bidPrice'],
        'askPrice': item['askPrice'],
        'askQty': item['askQty']
    } for item in options_list])

calls = process_options(data['data']['callOptions'])
puts = process_options(data['data']['putOptions'])

# Merge calls and puts
option_chain = pd.merge(calls, puts, on='strikePrice', suffixes=('_call', '_put'))

# Add moneyness
option_chain['moneyness'] = option_chain['strikePrice'].apply(
    lambda x: 'ITM' if x < current_spot else 'OTM' if x > current_spot else 'ATM'
)

# Display basic info
print(f"Current Spot Price (Approx): {current_spot}")
print(f"Expiry Date: 03-04-2025")
print(f"Total Strike Prices Available: {len(option_chain)}")

# Function to analyze options
def analyze_options(strike_input=None):
    if strike_input:
        try:
            strike = float(strike_input)
            if strike not in option_chain['strikePrice'].values:
                print(f"Strike price {strike} not found in the option chain.")
                return
        except ValueError:
            print("Please enter a valid strike price number.")
            return
    
    # Top 5 ITM and OTM calls and puts
    itm_calls = option_chain[option_chain['moneyness'] == 'ITM'].sort_values('strikePrice', ascending=False).head(5)
    otm_calls = option_chain[option_chain['moneyness'] == 'OTM'].sort_values('strikePrice', ascending=True).head(5)
    itm_puts = option_chain[option_chain['moneyness'] == 'ITM'].sort_values('strikePrice', ascending=True).head(5)
    otm_puts = option_chain[option_chain['moneyness'] == 'OTM'].sort_values('strikePrice', ascending=False).head(5)
    
    # Display analysis
    print("\n=== Top 5 ITM Calls ===")
    print(itm_calls[['strikePrice', 'lastPrice_call', 'openInterest_call', 'impliedVolatility_call']])
    
    print("\n=== Top 5 OTM Calls ===")
    print(otm_calls[['strikePrice', 'lastPrice_call', 'openInterest_call', 'impliedVolatility_call']])
    
    print("\n=== Top 5 ITM Puts ===")
    print(itm_puts[['strikePrice', 'lastPrice_put', 'openInterest_put', 'impliedVolatility_put']])
    
    print("\n=== Top 5 OTM Puts ===")
    print(otm_puts[['strikePrice', 'lastPrice_put', 'openInterest_put', 'impliedVolatility_put']])
    
    # If specific strike is provided
    if strike_input:
        specific = option_chain[option_chain['strikePrice'] == strike].iloc[0]
        print(f"\n=== Analysis for Strike {strike} ===")
        print(f"Call Option: Last Price={specific['lastPrice_call']}, OI={specific['openInterest_call']}, IV={specific['impliedVolatility_call']}%")
        print(f"Put Option: Last Price={specific['lastPrice_put']}, OI={specific['openInterest_put']}, IV={specific['impliedVolatility_put']}%")
        
        # Simple recommendation (very basic - real analysis would be more complex)
        call_iv = specific['impliedVolatility_call']
        put_iv = specific['impliedVolatility_put']
        
        if call_iv < put_iv:
            print("\nRecommendation: Call option might be relatively cheaper based on IV")
        else:
            print("\nRecommendation: Put option might be relatively cheaper based on IV")
    
    # Plot OI and Price trends
    plt.figure(figsize=(15, 8))
    
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

# Interactive input
while True:
    print("\nOptions Analysis Dashboard")
    print("1. Show top ITM/OTM options")
    print("2. Analyze specific strike price")
    print("3. Exit")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        analyze_options()
    elif choice == '2':
        strike = input("Enter strike price to analyze: ")
        analyze_options(strike)
    elif choice == '3':
        break
    else:
        print("Invalid choice. Please try again.")
