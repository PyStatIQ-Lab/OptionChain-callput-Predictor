import requests
import pandas as pd
import matplotlib.pyplot as plt

class OptionChainAnalyzer:
    def __init__(self):
        self.option_chain = None
        self.current_spot = None
        self.expiry_date = "10-04-2025"  # Fixed expiry date
    
    def fetch_data(self):
        """Fetch option chain data from Upstox API"""
        url = f"https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry={self.expiry_date}"
        
        try:
            print(f"\nFetching Nifty 50 option chain for {self.expiry_date}...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {str(e)}")
            return None

    def process_data(self, data):
        """Process raw API data into structured DataFrame"""
        if not data or 'data' not in data:
            print("Invalid API response")
            return None, None
        
        try:
            # Get ATM strike price
            strikes = data['data']['strikePrices']
            atm_strike = next((s['strikePrice'] for s in strikes if s.get('isAtm', False)), None)
            
            if not atm_strike:
                print("ATM strike not found")
                return None, None

            # Process calls and puts
            def process_options(options):
                return pd.DataFrame([{
                    'strikePrice': opt['strikePrice'],
                    'openInterest': opt.get('openInterest', 0),
                    'impliedVolatility': opt.get('impliedVolatility', 0),
                    'lastPrice': opt.get('lastPrice', 0),
                    'bidPrice': opt.get('bidPrice', 0),
                    'askPrice': opt.get('askPrice', 0)
                } for opt in options])

            calls = process_options(data['data']['callOptions'])
            puts = process_options(data['data']['putOptions'])

            # Merge DataFrames
            option_chain = pd.merge(
                calls.add_suffix('_call'),
                puts.add_suffix('_put'),
                left_on='strikePrice_call',
                right_on='strikePrice_put'
            ).rename(columns={'strikePrice_call': 'strikePrice'}).drop('strikePrice_put', axis=1)
            
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
            print("Data not loaded")
            return None
            
        try:
            strike_data = self.option_chain[self.option_chain['strikePrice'] == strike].iloc[0]
            
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
        except IndexError:
            print(f"Strike {strike} not found")
            return None

    def generate_recommendation(self, analysis):
        """Generate trading recommendation"""
        if not analysis:
            return "No analysis available"
        
        call_score = 0
        put_score = 0
        
        # Compare IV (lower is better)
        if analysis['call']['iv'] < analysis['put']['iv']:
            call_score += 1
        else:
            put_score += 1
            
        # Compare OI (higher is better)
        if analysis['call']['oi'] > analysis['put']['oi']:
            call_score += 1
        else:
            put_score += 1
            
        # Compare spread (tighter is better)
        if analysis['call']['spread'] < analysis['put']['spread']:
            call_score += 1
        else:
            put_score += 1
            
        if call_score > put_score:
            return f"BUY CALL (Score {call_score}-{put_score}) - Lower IV, Higher OI, Tighter Spread"
        elif put_score > call_score:
            return f"BUY PUT (Score {put_score}-{call_score}) - Lower IV, Higher OI, Tighter Spread"
        else:
            return "NEUTRAL - No clear advantage"

    def plot_data(self):
        """Plot option chain data"""
        if self.option_chain is None:
            return
            
        plt.figure(figsize=(15, 10))
        
        # Price Plot
        plt.subplot(2, 1, 1)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_call'], 'g-', label='Call Price')
        plt.plot(self.option_chain['strikePrice'], self.option_chain['lastPrice_put'], 'r-', label='Put Price')
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='Current Spot')
        plt.title(f'Nifty 50 Option Prices (Expiry: {self.expiry_date})')
        plt.xlabel('Strike Price')
        plt.ylabel('Option Price')
        plt.legend()
        plt.grid(True)
        
        # Open Interest Plot
        plt.subplot(2, 1, 2)
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_call'], 'g-', label='Call OI')
        plt.plot(self.option_chain['strikePrice'], self.option_chain['openInterest_put'], 'r-', label='Put OI')
        plt.axvline(x=self.current_spot, color='b', linestyle='--', label='Current Spot')
        plt.title('Open Interest')
        plt.xlabel('Strike Price')
        plt.ylabel('Open Interest')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()

    def run(self):
        """Main execution"""
        # Load data
        data = self.fetch_data()
        if not data:
            return
            
        self.option_chain, self.current_spot = self.process_data(data)
        if self.option_chain is None:
            return
            
        print(f"\nCurrent Spot (Approx): {self.current_spot}")
        print(f"Available strikes: {self.option_chain['strikePrice'].tolist()}")
        
        # Strike analysis loop
        while True:
            try:
                strike = float(input("\nEnter strike price to analyze (0 to exit): "))
                if strike == 0:
                    break
                    
                analysis = self.analyze_strike(strike)
                if not analysis:
                    continue
                    
                print("\n" + "="*50)
                print(f"Analysis for Strike: {strike} ({analysis['moneyness']})")
                print("-"*50)
                print("CALL OPTION:")
                print(f"Price: {analysis['call']['price']}")
                print(f"Open Interest: {analysis['call']['oi']}")
                print(f"Implied Volatility: {analysis['call']['iv']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['call']['spread']:.2f}")
                
                print("\nPUT OPTION:")
                print(f"Price: {analysis['put']['price']}")
                print(f"Open Interest: {analysis['put']['oi']}")
                print(f"Implied Volatility: {analysis['put']['iv']:.2f}%")
                print(f"Bid-Ask Spread: {analysis['put']['spread']:.2f}")
                
                print("\nRECOMMENDATION:")
                print(self.generate_recommendation(analysis))
                print("="*50)
                
                # Show plots
                self.plot_data()
                
            except ValueError:
                print("Please enter a valid number")

if __name__ == "__main__":
    analyzer = OptionChainAnalyzer()
    analyzer.run()
