import requests
import pandas as pd
import matplotlib.pyplot as plt
from typing import Tuple, Optional

class OptionChainAnalyzer:
    def __init__(self):
        self.option_chain = None
        self.current_spot = None
        self.expiry_date = "03-04-2025"
        
    def fetch_data(self) -> Optional[dict]:
        """Fetch option chain data from Upstox API"""
        url = f"https://service.upstox.com/option-analytics-tool/open/v1/strategy-chains?assetKey=NSE_INDEX%7CNifty+50&strategyChainType=PC_CHAIN&expiry={self.expiry_date}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {str(e)}")
            return None

    def process_data(self, data: dict) -> Tuple[Optional[pd.DataFrame], Optional[float]]:
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

            # Process calls and puts with proper error handling
            def process_options(options: list) -> list:
                processed = []
                for opt in options:
                    try:
                        processed.append({
                            'strikePrice': opt['strikePrice'],
                            'openInterest': float(opt.get('openInterest', 0)),
                            'changeinOpenInterest': float(opt.get('changeinOpenInterest', 0)),
                            'totalTradedVolume': float(opt.get('totalTradedVolume', 0)),
                            'impliedVolatility': float(opt.get('impliedVolatility', opt.get('impliedVolatility', 0))),
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

            # Create DataFrames with consistent column names
            calls_df = pd.DataFrame(calls).add_suffix('_call')
            puts_df = pd.DataFrame(puts).add_suffix('_put')
            
            # Merge on strike price with validation
            try:
                option_chain = pd.merge(
                    calls_df.rename(columns={'strikePrice_call': 'strikePrice'}),
                    puts_df.rename(columns={'strikePrice_put': 'strikePrice'}),
                    on='strikePrice',
                    how='outer'
                ).fillna(0)
                
                # Calculate moneyness
                option_chain['moneyness'] = option_chain['strikePrice'].apply(
                    lambda x: 'ITM' if x < atm_strike else 'OTM' if x > atm_strike else 'ATM'
                )
                
                return option_chain, atm_strike
                
            except Exception as e:
                print(f"Data merge failed: {str(e)}")
                return None, None

        except Exception as e:
            print(f"Data processing error: {str(e)}")
            return None, None

    def analyze_strike(self, strike: float) -> Optional[dict]:
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
                },
                'recommendation': self._generate_recommendation(strike_data)
            }
            
            return analysis
            
        except IndexError:
            print(f"Strike price {strike} not found in option chain")
            return None
        except Exception as e:
            print(f"Strike analysis failed: {str(e)}")
            return None

    def _generate_recommendation(self, strike_data: pd.Series) -> str:
        """Generate trading recommendation based on multiple factors"""
        call_iv = strike_data['impliedVolatility_call']
        put_iv = strike_data['impliedVolatility_put']
        call_oi = strike_data['openInterest_call']
        put_oi = strike_data['openInterest_put']
        call_spread = strike_data['askPrice_call'] - strike_data['bidPrice_call']
        put_spread = strike_data['askPrice_put'] - strike_data['bidPrice_put']
        
        factors = []
        
        if call_iv < put_iv:
            factors.append("lower IV in calls")
        else:
            factors.append("lower IV in puts")
            
        if call_oi > put_oi * 1.2:
            factors.append("higher OI in calls")
        elif put_oi > call_oi * 1.2:
            factors.append("higher OI in puts")
            
        if call_spread < put_spread * 0.8:
            factors.append("tighter spreads in calls")
        elif put_spread < call_spread * 0.8:
            factors.append("tighter spreads in puts")
            
        if not factors:
            return "Neutral - no clear advantage"
            
        return f"Consider {strike_data['moneyness']} {'call' if 'calls' in ' '.join(factors) else 'put'} " + \
               f"due to {', '.join(factors)}"

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
        plt.title('Open Interest by Strike Price')
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
        """Run complete analysis workflow"""
        print(f"Fetching Nifty 50 option chain data for expiry {self.expiry_date}...")
        raw_data = self.fetch_data()
        
        if raw_data is None:
            return
            
        self.option_chain, self.current_spot = self.process_data(raw_data)
        
        if self.option_chain is None or self.current_spot is None:
            return
            
        print("\n" + "="*50)
        print(f"Current Spot (Approx): {self.current_spot}")
        print(f"Total Strikes Available: {len(self.option_chain)}")
        print("="*50 + "\n")
        
        # Display top options
        for moneyness in ['ITM', 'OTM']:
            for option_type in ['call', 'put']:
                title = f"Top 5 {moneyness} {option_type.upper()} Options"
                print("\n" + title)
                print("-"*len(title))
                
                df = self.option_chain[self.option_chain['moneyness'] == moneyness]
                sort_asc = (option_type == 'put') if moneyness == 'ITM' else (option_type == 'call')
                cols = ['strikePrice', f'lastPrice_{option_type}', 
                        f'openInterest_{option_type}', f'impliedVolatility_{option_type}']
                
                display(df.sort_values('strikePrice', ascending=sort_asc)
                       .head(5)[cols].to_string(index=False))
        
        # Plot the data
        self.plot_chain()
        
        # Interactive strike analysis
        while True:
            print("\nOptions:")
            print("1. Analyze specific strike")
            print("2. Exit")
            choice = input("Enter your choice: ")
            
            if choice == '1':
                try:
                    strike = float(input("Enter strike price to analyze: "))
                    analysis = self.analyze_strike(strike)
                    
                    if analysis:
                        print("\nStrike Analysis:")
                        print(f"Strike: {analysis['strike']}")
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
                        
                except ValueError:
                    print("Please enter a valid strike price")
            elif choice == '2':
                break
            else:
                print("Invalid choice")

if __name__ == "__main__":
    analyzer = OptionChainAnalyzer()
    analyzer.run_analysis()
