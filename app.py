import requests
import pandas as pd
import matplotlib.pyplot as plt
import json
from datetime import datetime

class OptionChainAnalyzer:
    def __init__(self):
        self.option_chain = None
        self.current_spot = None
        self.expiry_date = "03-04-2025"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_data(self):
        """Fetch option chain data from Upstox API"""
        url = f"https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry={self.expiry_date}"
        
        print(f"\nFetching data for expiry {self.expiry_date}...")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            print(f"HTTP Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                return None
                
            data = response.json()
            
            # Save raw data for debugging
            with open('option_chain.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("Raw data saved to 'option_chain.json'")
            
            return data
            
        except Exception as e:
            print(f"Failed to fetch data: {str(e)}")
            return None

    def process_data(self, data):
        """Process the API response into a structured DataFrame"""
        if not data or 'data' not in data:
            print("Invalid data format received")
            return None, None
            
        try:
            # Get ATM strike price
            strikes = data['data']['strikePrices']
            atm_strike = next((s['strikePrice'] for s in strikes if s.get('isAtm', False)), None)
            
            if not atm_strike:
                print("Warning: Could not determine ATM strike, using first strike")
                atm_strike = strikes[0]['strikePrice'] if strikes else None
                if not atm_strike:
                    print("Error: No strike prices found")
                    return None, None

            print(f"Current ATM strike: {atm_strike}")

            # Process calls and puts
            def process_options(options):
                processed = []
                for opt in options:
                    try:
                        processed.append({
                            'strikePrice': float(opt['strikePrice']),
                            'lastPrice': float(opt.get('lastPrice', 0)),
                            'openInterest': float(opt.get('openInterest', 0)),
                            'changeinOpenInterest': float(opt.get('changeinOpenInterest', 0)),
                            'impliedVolatility': float(opt.get('impliedVolatility', 0)),
                            'bidPrice': float(opt.get('bidPrice', 0)),
                            'askPrice': float(opt.get('askPrice', 0)),
                            'totalTradedVolume': float(opt.get('totalTradedVolume', 0))
                        })
                    except Exception as e:
                        print(f"Skipping malformed option: {str(e)}")
                        continue
                return processed

            calls = process_options(data['data']['callOptions'])
            puts = process_options(data['data']['putOptions'])

            # Create DataFrames
            calls_df = pd.DataFrame(calls).add_suffix('_call')
            puts_df = pd.DataFrame(puts).add_suffix('_put')
            
            # Merge DataFrames
            option_chain = pd.merge(
                calls_df.rename(columns={'strikePrice_call': 'strikePrice'}),
                puts_df.rename(columns={'strikePrice_put': 'strikePrice'}),
                on='strikePrice',
                how='outer'
            ).fillna(0)
            
            # Add moneyness
            option_chain['moneyness'] = option_chain['strikePrice'].apply(
                lambda x: 'ITM' if x < atm_strike else 'OTM' if x > atm_strike else 'ATM'
            )

            return option_chain, atm_strike
            
        except Exception as e:
            print(f"Data processing failed: {str(e)}")
            return None, None

    def analyze_strike(self, strike):
        """Analyze a specific strike price"""
        if self.option_chain is None:
            print("Option chain data not loaded")
            return None
            
        try:
            strike = float(strike)
            strike_data = self.option_chain[self.option_chain['strikePrice'] == strike]
            
            if strike_data.empty:
                print(f"Strike {strike} not found")
                # Find nearest strike
                nearest = self.option_chain.iloc[(self.option_chain['strikePrice']-strike).abs().argsort()[:1]]
                print(f"Nearest available strike: {nearest['strikePrice'].values[0]}")
                return None
                
            strike_data = strike_data.iloc[0]
            
            return {
                'strike': strike,
                'moneyness': strike_data['moneyness'],
                'call': {
                    'lastPrice': strike_data['lastPrice_call'],
                    'openInterest': strike_data['openInterest_call'],
                    'impliedVolatility': strike_data['impliedVolatility_call'],
                    'bidAskSpread': strike_data['askPrice_call'] - strike_data['bidPrice_call']
                },
                'put': {
                    'lastPrice': strike_data['lastPrice_put'],
                    'openInterest': strike_data['openInterest_put'],
                    'impliedVolatility': strike_data['impliedVolatility_put'],
                    'bidAskSpread': strike_data['askPrice_put'] - strike_data['bidPrice_put']
                }
            }
            
        except Exception as e:
            print(f"Strike analysis failed: {str(e)}")
            return None

    def generate_recommendation(self, analysis):
        """Generate trading recommendation"""
        if not analysis:
            return "No recommendation - invalid analysis data"
            
        call_score = put_score = 0
        factors = []
        
        # IV comparison (lower is better)
        if analysis['call']['impliedVolatility'] < analysis['put']['impliedVolatility']:
            call_score += 1
            factors.append("Lower call IV")
        else:
            put_score += 1
            factors.append("Lower put IV")
            
        # OI comparison (higher is better)
        if analysis['call']['openInterest'] > analysis['put']['openInterest']:
            call_score += 1
            factors.append("Higher call OI")
        else:
            put_score += 1
            factors.append("Higher put OI")
            
        # Spread comparison (tighter is better)
        if analysis['call']['bidAskSpread'] < analysis['put']['bidAskSpread']:
            call_score += 1
            factors.append("Tighter call spread")
        else:
            put_score += 1
            factors.append("Tighter put spread")
            
        if call_score > put_score:
            return f"BUY CALL (Score {call_score}-{put_score})\nReasons: {', '.join(factors)}"
        elif put_score > call_score:
            return f"BUY PUT (Score {put_score}-{call_score})\nReasons: {', '.join(factors)}"
        else:
            return f"NEUTRAL (Score {call_score}-{put_score})\nReasons: {', '.join(factors)}"

    def plot_chain(self):
        """Plot option chain data"""
        if self.option_chain is None:
            print("No data to plot")
            return
            
        plt.figure(figsize=(15, 10))
        
        # Price Plot
        plt.subplot(2, 1, 1)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_call'], 'g-', label='Call Price')
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_put'], 'r-', label='Put Price')
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='ATM Strike')
        plt.title(f'Nifty 50 Option Prices (Expiry: {self.expiry_date})')
        plt.xlabel('Strike Price')
        plt.ylabel('Option Price')
        plt.legend()
        plt.grid(True)
        
        # Open Interest Plot
        plt.subplot(2, 1, 2)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_call'], 'g-', label='Call OI')
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_put'], 'r-', label='Put OI')
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='ATM Strike')
        plt.title('Open Interest')
        plt.xlabel('Strike Price')
        plt.ylabel('Open Interest')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()

    def run(self):
        """Main execution"""
        print(f"\nNifty 50 Option Chain Analyzer")
        print(f"Expiry Date: {self.expiry_date}")
        print("="*50)
        
        # Fetch and process data
        raw_data = self.fetch_data()
        if not raw_data:
            print("\nFailed to fetch data. Possible reasons:")
            print("- API requires authentication")
            print("- Network issues")
            print("- Invalid response format")
            print("\nCheck 'option_chain.json' for raw response")
            return
            
        self.option_chain, self.current_spot = self.process_data(raw_data)
        if self.option_chain is None:
            print("\nFailed to process data")
            return
            
        print(f"\nData loaded successfully. Current ATM: {self.current_spot}")
        print(f"Available strikes: {self.option_chain['strikePrice'].min()} to {self.option_chain['strikePrice'].max()}")
        
        # Interactive analysis
        while True:
            strike = input("\nEnter strike price to analyze (or 'q' to quit): ").strip()
            if strike.lower() == 'q':
                break
                
            try:
                strike = float(strike)
                analysis = self.analyze_strike(strike)
                
                if not analysis:
                    continue
                    
                print("\n" + "="*50)
                print(f"Analysis for Strike: {analysis['strike']} ({analysis['moneyness']})")
                print("-"*50)
                
                print("\nCALL OPTION:")
                print(f"Last Price: {analysis['call']['lastPrice']:.2f}")
                print(f"Open Interest: {analysis['call']['openInterest']:,.0f}")
                print(f"Implied Volatility: {analysis['call']['impliedVolatility']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['call']['bidAskSpread']:.2f}")
                
                print("\nPUT OPTION:")
                print(f"Last Price: {analysis['put']['lastPrice']:.2f}")
                print(f"Open Interest: {analysis['put']['openInterest']:,.0f}")
                print(f"Implied Volatility: {analysis['put']['impliedVolatility']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['put']['bidAskSpread']:.2f}")
                
                print("\nRECOMMENDATION:")
                print(self.generate_recommendation(analysis))
                print("="*50)
                
                # Show plots
                self.plot_chain()
                
            except ValueError:
                print("Please enter a valid number or 'q' to quit")

if __name__ == "__main__":
    analyzer = OptionChainAnalyzer()
    analyzer.run()
