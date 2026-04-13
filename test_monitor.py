"""
Test script for Stock Monitor
This script performs a single check without continuous monitoring
"""

import yfinance as yf
from datetime import datetime
import os
from dotenv import load_dotenv

# ========================================
# CONFIGURATION - EDIT STOCKS HERE
# ========================================
# List of stocks to test (should match stock_monitor.py)
STOCKS_TO_TEST = [
    'BPCL.NS',        # Bharat Petroleum Corporation Limited
    'ASIANPAINT.NS'   # Asian Paints Limited
]

ALERT_THRESHOLD_PERCENT = 5  # Alert when within 5% of 52-week low
# ========================================

# Load environment variables
load_dotenv()

def test_stock_data(symbol):
    """
    Test fetching stock data for a given symbol
    """
    print(f"\n{'='*60}")
    print(f"Testing: {symbol}")
    print('='*60)
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Get current price
        hist = ticker.history(period='1d')
        if hist.empty:
            print(f"❌ No data available for {symbol}")
            return None
            
        current_price = hist['Close'].iloc[-1]
        
        # Get 52-week data
        hist_52w = ticker.history(period='1y')
        week_52_low = hist_52w['Low'].min()
        week_52_high = hist_52w['High'].max()
        
        # Get stock info
        info = ticker.info
        stock_name = info.get('longName', symbol)
        
        # Calculate distance from 52-week low
        distance = ((current_price - week_52_low) / week_52_low) * 100
        
        # Display results
        print(f"\n📊 Stock Information:")
        print(f"   Name: {stock_name}")
        print(f"   Symbol: {symbol}")
        print(f"\n💰 Current Price: Rs.{current_price:.2f}")
        print(f"\n📉 52-Week Range:")
        print(f"   Low:  Rs.{week_52_low:.2f}")
        print(f"   High: Rs.{week_52_high:.2f}")
        print(f"\n📈 Analysis:")
        print(f"   Distance from 52W Low: {distance:.2f}%")
        
        # Alert assessment
        if distance <= 0.5:
            status = "🔴 AT 52-WEEK LOW"
        elif distance <= ALERT_THRESHOLD_PERCENT:
            status = f"🟡 NEAR 52-WEEK LOW (Alert would be sent!)"
        else:
            status = f"🟢 Above 52-week low (No alert)"
        
        print(f"   Status: {status}")
        print(f"\n   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            'symbol': symbol,
            'name': stock_name,
            'current_price': current_price,
            '52_week_low': week_52_low,
            '52_week_high': week_52_high,
            'distance': distance
        }
        
    except Exception as e:
        print(f"❌ Error fetching data for {symbol}: {str(e)}")
        return None


def test_twilio_config():
    """
    Test Twilio configuration
    """
    print(f"\n{'='*60}")
    print("Testing Twilio Configuration")
    print('='*60)
    
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp = os.getenv('TWILIO_WHATSAPP_FROM')
    to_whatsapp = os.getenv('TWILIO_WHATSAPP_TO')
    
    if account_sid and account_sid != 'YOUR_TWILIO_ACCOUNT_SID':
        print(f"✅ TWILIO_ACCOUNT_SID: Configured")
    else:
        print(f"❌ TWILIO_ACCOUNT_SID: Not configured")
    
    if auth_token and auth_token != 'YOUR_TWILIO_AUTH_TOKEN':
        print(f"✅ TWILIO_AUTH_TOKEN: Configured")
    else:
        print(f"❌ TWILIO_AUTH_TOKEN: Not configured")
    
    if from_whatsapp:
        print(f"✅ From WhatsApp: {from_whatsapp}")
    else:
        print(f"❌ From WhatsApp: Not configured")
    
    if to_whatsapp and to_whatsapp != 'whatsapp:+919876543210':
        print(f"✅ To WhatsApp: {to_whatsapp}")
    else:
        print(f"❌ To WhatsApp: Not configured (using default)")
    
    print("\n💡 Tip: Copy .env.example to .env and add your credentials")


def main():
    """
    Main test function
    """
    print("\n" + "="*60)
    print(" 📈 Stock Monitor - Test Mode")
    print("="*60)
    print("\nThis script will perform a single check of the monitored stocks")
    print("without sending any WhatsApp notifications.\n")
    
    # Test stocks from configuration at top of file
    results = []
    for symbol in STOCKS_TO_TEST:
        result = test_stock_data(symbol)
        if result:
            results.append(result)
    
    # Test Twilio configuration
    test_twilio_config()
    
    # Summary
    print(f"\n{'='*60}")
    print(" 📊 Summary")
    print('='*60)
    
    if results:
        print(f"\n✅ Successfully fetched data for {len(results)} stock(s)")
        
        near_low = [r for r in results if r['distance'] <= ALERT_THRESHOLD_PERCENT]
        if near_low:
            print(f"\n⚠️  {len(near_low)} stock(s) near 52-week low:")
            for r in near_low:
                print(f"   - {r['name']}: Rs.{r['current_price']:.2f} ({r['distance']:.2f}% from low)")
        else:
            print(f"\n✅ No stocks near 52-week low at this time")
    else:
        print("\n❌ Could not fetch stock data. Please check your internet connection.")
    
    print("\n" + "="*60)
    print("\n💡 To start continuous monitoring, run: python stock_monitor.py")
    print("\n")


if __name__ == "__main__":
    main()
