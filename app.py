import requests
import pandas as pd
import matplotlib.pyplot as plt
import json

class OptionChainAnalyzer:
    def __init__(self):
        self.option_chain = None
        self.current_spot = None
        self.expiry_date = "03-04-2025"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_data(self):
        """Fetch option chain data from Upstox API with detailed error handling"""
        url = f"https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry={self.expiry_date}"
        
        print(f"\nAttempting to fetch data for {self.expiry_date}...")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            print(f"HTTP Status Code: {response.status_code}")
            
            # Debug: Print first 500 characters of response
            print("Response preview:", response.text[:500])
            
            response.raise_for_status()
            data = response.json()
            
            # Debug: Save raw response to file
            with open('upstox_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("Raw response saved to 'upstox_response.json'")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"\nERROR: Failed to fetch data")
            print(f"Type: {type(e).__name__}")
            print(f"Details: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print("\nERROR: Invalid JSON response")
            print(f"Details: {str(e)}")
            return None

    def process_data(self, data):
        """Process the API response with comprehensive validation"""
        if not data:
            print("No data to process")
            return None, None
            
        print("\nProcessing API response...")
        
        try:
            # Validate response structure
            if 'data' not in data:
                print("ERROR: 'data' key missing in response")
                return None, None
                
            if 'strikePrices' not in data['data']:
                print("ERROR: 'strikePrices' missing in response data")
                return None, None
                
            # Find ATM strike
            strikes = data['data']['strikePrices']
            atm_strike = next((s['strikePrice'] for s in strikes if s.get('isAtm', False)), None)
            
            if not atm_strike:
                print("WARNING: Could not determine ATM strike price")
                atm_strike = strikes[0]['strikePrice'] if strikes else None
                if not atm_strike:
                    print("ERROR: No strike prices found")
                    return None, None
                print(f"Using first strike {atm_strike} as ATM approximation")

            print(f"Current ATM strike: {atm_strike}")
            
            # Process options with full validation
            def safe_get(d, key, default=0):
                """Safely get values from dictionary with type conversion"""
                try:
                    val = d.get(key, default)
                    return float(val) if val is not None else default
                except (ValueError, TypeError):
                    return default

            def process_options(options):
                processed = []
                for opt in options:
                    try:
                        processed.append({
                            'strikePrice': float(opt['strikePrice']),
                            'openInterest': safe_get(opt, 'openInterest'),
                            'impliedVolatility': safe_get(opt, 'impliedVolatility'),
                            'lastPrice': safe_get(opt, 'lastPrice'),
                            'bidPrice': safe_get(opt, 'bidPrice'),
                            'askPrice': safe_get(opt, 'askPrice')
                        })
                    except Exception as e:
                        print(f"Warning: Skipping malformed option - {str(e)}")
                        continue
                return processed

            print("Processing call options...")
            calls = process_options(data['data']['callOptions'])
            print("Processing put options...")
            puts = process_options(data['data']['putOptions'])

            # Create DataFrames
            calls_df = pd.DataFrame(calls).add_suffix('_call')
            puts_df = pd.DataFrame(puts).add_suffix('_put')
            
            # Merge with outer join to handle missing strikes
            option_chain = pd.merge(
                calls_df.rename(columns={'strikePrice_call': 'strikePrice'}),
                puts_df.rename(columns={'strikePrice_put': 'strikePrice'}),
                on='strikePrice',
                how='outer'
            ).fillna(0)
            
            # Add moneyness classification
            option_chain['moneyness'] = option_chain['strikePrice'].apply(
                lambda x: 'ITM' if x < atm_strike else 'OTM' if x > atm_strike else 'ATM'
            )

            print(f"Successfully processed {len(option_chain)} strike prices")
            return option_chain, atm_strike
            
        except Exception as e:
            print(f"\nERROR: Data processing failed")
            print(f"Type: {type(e).__name__}")
            print(f"Details: {str(e)}")
            return None, None

    def analyze_strike(self, strike):
        """Analyze specific strike with full validation"""
        if self.option_chain is None:
            print("ERROR: Option chain data not loaded")
            return None
            
        try:
            strike = float(strike)
            strike_data = self.option_chain[self.option_chain['strikePrice'] == strike]
            
            if strike_data.empty:
                print(f"Strike {strike} not found in option chain")
                nearest = self.option_chain.iloc[(self.option_chain['strikePrice']-strike).abs().argsort()[:1]]
                print(f"Nearest available strike: {nearest['strikePrice'].values[0]}")
                return None
                
            strike_data = strike_data.iloc[0]
            
            return {
                'strike': strike,
                'moneyness': strike_data['moneyness'],
                'call': {
                    'price': strike_data['lastPrice_call'],
                    'oi': strike_data['openInterest_call'],
                    'iv': strike_data['impliedVolatility_call'],
                    'spread': strike_data['askPrice_call'] - strike_data['bidPrice_call']
                },
                'put': {
                    'price': strike_data['lastPrice_put'],
                    'oi': strike_data['openInterest_put'],
                    'iv': strike_data['impliedVolatility_put'],
                    'spread': strike_data['askPrice_put'] - strike_data['bidPrice_put']
                }
            }
            
        except Exception as e:
            print(f"\nERROR: Strike analysis failed")
            print(f"Type: {type(e).__name__}")
            print(f"Details: {str(e)}")
            return None

    def generate_recommendation(self, analysis):
        """Generate trading recommendation with scoring system"""
        if not analysis:
            return "No recommendation - invalid analysis data"
            
        try:
            call_score = put_score = 0
            factors = []
            
            # IV Comparison (lower is better)
            if analysis['call']['iv'] < analysis['put']['iv']:
                call_score += 1
                factors.append("Call has lower IV")
            else:
                put_score += 1
                factors.append("Put has lower IV")
                
            # OI Comparison (higher is better)
            if analysis['call']['oi'] > analysis['put']['oi']:
                call_score += 1
                factors.append("Call has higher OI")
            else:
                put_score += 1
                factors.append("Put has higher OI")
                
            # Spread Comparison (tighter is better)
            if analysis['call']['spread'] < analysis['put']['spread']:
                call_score += 1
                factors.append("Call has tighter spread")
            else:
                put_score += 1
                factors.append("Put has tighter spread")
                
            # Generate recommendation
            if call_score > put_score:
                return f"BUY CALL (Score {call_score}-{put_score})\nFactors: {', '.join(factors)}"
            elif put_score > call_score:
                return f"BUY PUT (Score {put_score}-{call_score})\nFactors: {', '.join(factors)}"
            else:
                return f"NEUTRAL (Score {call_score}-{put_score})\nFactors: {', '.join(factors)}"
                
        except Exception as e:
            print(f"Recommendation generation error: {str(e)}")
            return "No recommendation - analysis error"

    def plot_data(self):
        """Plot option chain data with error handling"""
        if self.option_chain is None or self.current_spot is None:
            print("Cannot plot - missing data")
            return
            
        try:
            plt.figure(figsize=(15, 10))
            
            # Price Plot
            plt.subplot(2, 1, 1)
            plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_call'], 
                    'g-', label='Call Price', alpha=0.7)
            plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_put'], 
                    'r-', label='Put Price', alpha=0.7)
            plt.axvline(x=self.current_spot, color='b', linestyle='--', label='ATM Strike')
            plt.title(f'Nifty 50 Option Chain - {self.expiry_date}')
            plt.xlabel('Strike Price')
            plt.ylabel('Option Price')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # Open Interest Plot
            plt.subplot(2, 1, 2)
            plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_call'], 
                    'g-', label='Call OI', alpha=0.7)
            plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_put'], 
                    'r-', label='Put OI', alpha=0.7)
            plt.axvline(x=self.current_spot, color='b', linestyle='--', label='ATM Strike')
            plt.title('Open Interest')
            plt.xlabel('Strike Price')
            plt.ylabel('Open Interest')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            print(f"\nERROR: Failed to generate plots")
            print(f"Details: {str(e)}")

    def run(self):
        """Main execution with user interaction"""
        print(f"\n{'='*50}")
        print(f"NIFTY 50 OPTION CHAIN ANALYZER")
        print(f"Expiry Date: {self.expiry_date}")
        print(f"{'='*50}")
        
        # Step 1: Fetch data
        raw_data = self.fetch_data()
        if not raw_data:
            print("\nFailed to fetch data. Possible reasons:")
            print("- API endpoint changed")
            print("- Authentication required")
            print("- Network issues")
            print("\nCheck the saved 'upstox_response.json' for details")
            return
            
        # Step 2: Process data
        self.option_chain, self.current_spot = self.process_data(raw_data)
        if self.option_chain is None:
            print("\nFailed to process data. Check the raw response format.")
            return
            
        print(f"\nData loaded successfully. Current ATM strike: {self.current_spot}")
        print(f"Available strikes from {self.option_chain['strikePrice'].min()} to {self.option_chain['strikePrice'].max()}")
        
        # Step 3: Interactive analysis
        while True:
            try:
                strike_input = input("\nEnter strike price to analyze (or 'q' to quit): ").strip()
                if strike_input.lower() == 'q':
                    break
                    
                strike = float(strike_input)
                analysis = self.analyze_strike(strike)
                
                if not analysis:
                    continue
                    
                print(f"\n{'='*50}")
                print(f"STRIKE ANALYSIS: {strike} ({analysis['moneyness']})")
                print(f"{'-'*50}")
                
                print("\nCALL OPTION:")
                print(f"Price: {analysis['call']['price']:.2f}")
                print(f"Open Interest: {analysis['call']['oi']:,.0f}")
                print(f"Implied Volatility: {analysis['call']['iv']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['call']['spread']:.2f}")
                
                print("\nPUT OPTION:")
                print(f"Price: {analysis['put']['price']:.2f}")
                print(f"Open Interest: {analysis['put']['oi']:,.0f}")
                print(f"Implied Volatility: {analysis['put']['iv']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['put']['spread']:.2f}")
                
                print("\nRECOMMENDATION:")
                print(self.generate_recommendation(analysis))
                print(f"{'='*50}")
                
                # Show plots
                self.plot_data()
                
            except ValueError:
                print("Please enter a valid number or 'q' to quit")
            except Exception as e:
                print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    analyzer = OptionChainAnalyzer()
    analyzer.run()
