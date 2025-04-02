import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

class OptionChainAnalyzer:
    def __init__(self):
        self.option_chain = None
        self.current_spot = None
        self.expiry_date = None
        
    def get_user_input(self):
        """Get expiry date and strike price from user"""
        while True:
            print("\nAvailable expiry dates (example):")
            print("1. 03-04-2025")
            print("2. 10-04-2025")
            print("3. 17-04-2025")
            print("4. Custom date")
            
            choice = input("Select expiry date (1-4): ")
            
            if choice == '1':
                self.expiry_date = "03-04-2025"
                break
            elif choice == '2':
                self.expiry_date = "10-04-2025"
                break
            elif choice == '3':
                self.expiry_date = "17-04-2025"
                break
            elif choice == '4':
                self.expiry_date = input("Enter custom date (DD-MM-YYYY): ")
                try:
                    datetime.strptime(self.expiry_date, "%d-%m-%Y")
                    break
                except ValueError:
                    print("Invalid date format. Please use DD-MM-YYYY")
            else:
                print("Invalid choice. Please try again.")
    
    def fetch_data(self):
        """Fetch option chain data from Upstox API"""
        url = f"https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry={self.expiry_date}"
        
        try:
            print(f"\nFetching data for expiry {self.expiry_date}...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {str(e)}")
            return None

    def process_data(self, data):
        """Process raw API data into structured DataFrame"""
        if not data or 'data' not in data:
            print("Invalid API response structure")
            return None, None
        
        try:
            # Extract strike prices and find ATM strike
            strikes = data['data']['strikePrices']
            atm_strike = next((s['strikePrice'] for s in strikes if s.get('isAtm', False)), None)
            
            if not atm_strike:
                print("Could not determine ATM strike price")
                return None, None

            # Process calls and puts
            def process_options(options):
                processed = []
                for opt in options:
                    try:
                        processed.append({
                            'strikePrice': opt['strikePrice'],
                            'openInterest': float(opt.get('openInterest', 0)),
                            'changeinOpenInterest': float(opt.get('changeinOpenInterest', 0)),
                            'totalTradedVolume': float(opt.get('totalTradedVolume', 0)),
                            'impliedVolatility': float(opt.get('impliedVolatility', 0)),
                            'lastPrice': float(opt.get('lastPrice', 0)),
                            'bidPrice': float(opt.get('bidPrice', 0)),
                            'askPrice': float(opt.get('askPrice', 0))
                        })
                    except (KeyError, ValueError) as e:
                        print(f"Skipping malformed option data: {str(e)}")
                        continue
                return processed

            calls = process_options(data['data']['callOptions'])
            puts = process_options(data['data']['putOptions'])

            # Create DataFrames
            calls_df = pd.DataFrame(calls).add_suffix('_call')
            puts_df = pd.DataFrame(puts).add_suffix('_put')
            
            # Merge on strike price
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
            print(f"Data processing error: {str(e)}")
            return None, None

    def analyze_strike(self, strike):
        """Analyze specific strike price"""
        if self.option_chain is None:
            print("Option chain data not loaded")
            return None
            
        try:
            strike_data = self.option_chain[self.option_chain['strikePrice'] == strike].iloc[0]
            
            analysis = {
                'strike': strike,
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
            
            # Generate recommendation
            call_score = 0
            put_score = 0
            
            # IV comparison (lower is better)
            if analysis['call']['impliedVolatility'] < analysis['put']['impliedVolatility']:
                call_score += 1
            else:
                put_score += 1
                
            # OI comparison (higher is better)
            if analysis['call']['openInterest'] > analysis['put']['openInterest']:
                call_score += 1
            else:
                put_score += 1
                
            # Spread comparison (tighter is better)
            if analysis['call']['bidAskSpread'] < analysis['put']['bidAskSpread']:
                call_score += 1
            else:
                put_score += 1
                
            if call_score > put_score:
                analysis['recommendation'] = f"Consider CALL option (Score: {call_score}-{put_score})"
            elif put_score > call_score:
                analysis['recommendation'] = f"Consider PUT option (Score: {put_score}-{call_score})"
            else:
                analysis['recommendation'] = "Neutral - no clear advantage"
            
            return analysis
            
        except IndexError:
            print(f"Strike price {strike} not found in option chain")
            return None
        except Exception as e:
            print(f"Strike analysis failed: {str(e)}")
            return None

    def plot_chain(self):
        """Visualize the option chain data"""
        if self.option_chain is None or self.current_spot is None:
            print("No data to plot")
            return
            
        plt.figure(figsize=(15, 12))
        
        # Open Interest Plot
        plt.subplot(3, 1, 1)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_call'], 
                'g-', label='Call OI', alpha=0.7)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_put'], 
                'r-', label='Put OI', alpha=0.7)
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='Current Spot')
        plt.title(f'Open Interest by Strike Price (Expiry: {self.expiry_date})')
        plt.xlabel('Strike Price')
        plt.ylabel('Open Interest')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        
        # Price Plot
        plt.subplot(3, 1, 2)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_call'], 
                'g-', label='Call Price', alpha=0.7)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_put'], 
                'r-', label='Put Price', alpha=0.7)
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='Current Spot')
        plt.title('Option Prices by Strike Price')
        plt.xlabel('Strike Price')
        plt.ylabel('Option Price')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        
        # Implied Volatility Plot
        plt.subplot(3, 1, 3)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['impliedVolatility_call'], 
                'g-', label='Call IV', alpha=0.7)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['impliedVolatility_put'], 
                'r-', label='Put IV', alpha=0.7)
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='Current Spot')
        plt.title('Implied Volatility by Strike Price')
        plt.xlabel('Strike Price')
        plt.ylabel('Implied Volatility (%)')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        plt.show()

    def run_analysis(self):
        """Main analysis workflow"""
        self.get_user_input()
        raw_data = self.fetch_data()
        
        if raw_data is None:
            return
            
        self.option_chain, self.current_spot = self.process_data(raw_data)
        
        if self.option_chain is None or self.current_spot is None:
            return
            
        print("\n" + "="*50)
        print(f"Current Spot (Approx): {self.current_spot}")
        print(f"Expiry Date: {self.expiry_date}")
        print(f"Total Strikes Available: {len(self.option_chain)}")
        print("="*50 + "\n")
        
        # Show available strike prices
        print("Available Strike Prices:")
        print(self.option_chain['strikePrice'].unique())
        
        # Get strike price from user
        while True:
            try:
                strike = float(input("\nEnter strike price to analyze: "))
                analysis = self.analyze_strike(strike)
                
                if analysis:
                    print("\nStrike Analysis Results:")
                    print("-"*30)
                    print(f"Strike Price: {analysis['strike']}")
                    print(f"Moneyness: {self.option_chain[self.option_chain['strikePrice'] == strike]['moneyness'].values[0]}")
                    
                    print("\nCall Option:")
                    print(f"Last Price: {analysis['call']['lastPrice']}")
                    print(f"Open Interest: {analysis['call']['openInterest']}")
                    print(f"Implied Volatility: {analysis['call']['impliedVolatility']:.2f}%")
                    print(f"Bid-Ask Spread: {analysis['call']['bidAskSpread']:.2f}")
                    
                    print("\nPut Option:")
                    print(f"Last Price: {analysis['put']['lastPrice']}")
                    print(f"Open Interest: {analysis['put']['openInterest']}")
                    print(f"Implied Volatility: {analysis['put']['impliedVolatility']:.2f}%")
                    print(f"Bid-Ask Spread: {analysis['put']['bidAskSpread']:.2f}")
                    
                    print("\nRecommendation:")
                    print(analysis['recommendation'])
                    
                    # Plot the data
                    self.plot_chain()
                    
                    another = input("\nAnalyze another strike? (y/n): ").lower()
                    if another != 'y':
                        break
            except ValueError:
                print("Please enter a valid strike price number")

if __name__ == "__main__":
    analyzer = OptionChainAnalyzer()
    analyzer.run_analysis()
