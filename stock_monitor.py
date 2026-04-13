"""
Indian Stock Market Monitor - NIFTY 50 + Custom Stocks + Portfolio Tracking

Features:
- Low alerts (26W & 52W) → Watchlist
- High alerts (52W) → Only for your portfolio stocks
- Low alerts also include HIGH values (for upside visibility)
"""

import yfinance as yf
import time
from datetime import datetime
import os
from twilio.rest import Client
import logging
from dotenv import load_dotenv

# ========================================
# CONFIGURATION
# ========================================

CUSTOM_STOCKS = [
    'BPCL.NS',
    'ASIANPAINT.NS'
]

PORTFOLIO_STOCKS = [
   
]

ALERT_THRESHOLD_PERCENT = 3          # LOW alerts
HIGH_ALERT_THRESHOLD_PERCENT = 7     # HIGH alerts (portfolio only)
CHECK_INTERVAL_SECONDS = 300

# ========================================

def get_nifty50_symbols():
    return [
        'RELIANCE.NS','TCS.NS','INFY.NS','HDFCBANK.NS','ICICIBANK.NS',
        'KOTAKBANK.NS','SBIN.NS','BHARTIARTL.NS','ITC.NS','LT.NS',
        'HINDUNILVR.NS','ASIANPAINT.NS','AXISBANK.NS','BAJFINANCE.NS',
        'BAJAJFINSV.NS','MARUTI.NS','M&M.NS','TATAMOTORS.NS','SUNPHARMA.NS',
        'DRREDDY.NS','CIPLA.NS','DIVISLAB.NS','ULTRACEMCO.NS','TITAN.NS',
        'NESTLEIND.NS','POWERGRID.NS','NTPC.NS','ONGC.NS','COALINDIA.NS',
        'JSWSTEEL.NS','TATASTEEL.NS','HINDALCO.NS','GRASIM.NS','ADANIENT.NS',
        'ADANIPORTS.NS','SBILIFE.NS','HDFCLIFE.NS','INDUSINDBK.NS',
        'TECHM.NS','WIPRO.NS','HCLTECH.NS','LTIM.NS','BRITANNIA.NS',
        'EICHERMOT.NS','HEROMOTOCO.NS','BAJAJ-AUTO.NS','UPL.NS',
        'APOLLOHOSP.NS','SHRIRAMFIN.NS','SBICARD.NS'
    ]

# ========================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class StockMonitor:
    def __init__(self, stocks_config, twilio_config, check_interval=300):
        self.stocks = stocks_config
        self.check_interval = check_interval
        self.alert_threshold = stocks_config.get('alert_threshold_percent', 5)
        self.high_alert_threshold = HIGH_ALERT_THRESHOLD_PERCENT

        self.twilio_client = Client(
            twilio_config['account_sid'],
            twilio_config['auth_token']
        )
        self.from_whatsapp = twilio_config['from_whatsapp']
        self.to_whatsapp = twilio_config['to_whatsapp']

        self.last_alert = {}
        self.alert_cooldown = 3600

    # ========================================

    def get_stock_data(self, symbol):
        try:
            ticker = yf.Ticker(symbol)

            hist = ticker.history(period='1d')
            if hist.empty:
                return None
            current_price = hist['Close'].iloc[-1]

            hist_26w = ticker.history(period='6mo')
            low_26 = hist_26w['Low'].min()
            high_26 = hist_26w['High'].max()

            hist_52w = ticker.history(period='1y')
            low_52 = hist_52w['Low'].min()
            high_52 = hist_52w['High'].max()

            info = ticker.info
            stock_name = info.get('longName', symbol)

            return {
                'symbol': symbol,
                'name': stock_name,
                'price': current_price,
                'low_26': low_26,
                'high_26': high_26,
                'low_52': low_52,
                'high_52': high_52,
                'timestamp': datetime.now()
            }

        except Exception as e:
            logging.error(f"Error fetching {symbol}: {e}")
            return None

    # ========================================

    def pct_from_low(self, price, low):
        return ((price - low) / low) * 100

    def pct_from_high(self, price, high):
        return ((high - price) / high) * 100

    def should_send_alert(self, symbol):
        if symbol not in self.last_alert:
            return True
        return (time.time() - self.last_alert[symbol]) > self.alert_cooldown

    # ========================================

    def send_whatsapp_notification(self, message):
        try:
            msg = self.twilio_client.messages.create(
                body=message,
                from_=self.from_whatsapp,
                to=self.to_whatsapp
            )
            logging.info(f"WhatsApp sent: {msg.sid}")
            return True
        except Exception as e:
            logging.error(f"WhatsApp error: {e}")
            return False

    # ========================================

    def check_stock(self, symbol):
        data = self.get_stock_data(symbol)
        if not data:
            return

        d26_low = self.pct_from_low(data['price'], data['low_26'])
        d52_low = self.pct_from_low(data['price'], data['low_52'])
        d26_high = self.pct_from_high(data['price'], data['high_26'])
        d52_high = self.pct_from_high(data['price'], data['high_52'])

        logging.info(
            f"\n{data['name']} ({symbol})\n"
            f"Price: ₹{data['price']:.2f}\n\n"
            f"📉 26W Low: ₹{data['low_26']:.2f} | {d26_low:.2f}% above\n"
            f"📈 26W High: ₹{data['high_26']:.2f} | {d26_high:.2f}% below\n\n"
            f"📉 52W Low: ₹{data['low_52']:.2f} | {d52_low:.2f}% above\n"
            f"📈 52W High: ₹{data['high_52']:.2f} | {d52_high:.2f}% below\n"
            f"{'-'*50}"
        )

        # ALERT LOGIC
        trigger_26_low = d26_low <= self.alert_threshold
        trigger_52_low = d52_low <= self.alert_threshold

        is_portfolio = symbol in PORTFOLIO_STOCKS
        trigger_high = d52_high <= self.high_alert_threshold if is_portfolio else False

        if trigger_26_low or trigger_52_low or trigger_high:
            if not self.should_send_alert(symbol):
                return

            if trigger_high:
                alert_type = "💰 NEAR 52W HIGH (YOUR STOCK)"
            elif trigger_26_low and trigger_52_low:
                alert_type = "🔥 NEAR BOTH 26W & 52W LOWS"
            elif trigger_52_low:
                alert_type = "🚨 NEAR 52W LOW"
            else:
                alert_type = "⚠️ NEAR 26W LOW"

            # MESSAGE
            if trigger_high:
                message = (
                    f"{alert_type}\n\n"
                    f"📊 {data['name']} ({symbol})\n\n"
                    f"💰 Price: ₹{data['price']:.2f}\n\n"
                    f"📈 52W High: ₹{data['high_52']:.2f} ({d52_high:.2f}% below)\n\n"
                    f"⏰ {data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                message = (
                    f"{alert_type}\n\n"
                    f"📊 {data['name']} ({symbol})\n\n"
                    f"💰 Price: ₹{data['price']:.2f}\n\n"

                    f"📉 26W Low: ₹{data['low_26']:.2f} ({d26_low:.2f}%)\n"
                    f"📉 52W Low: ₹{data['low_52']:.2f} ({d52_low:.2f}%)\n\n"

                    f"📈 26W High: ₹{data['high_26']:.2f} ({d26_high:.2f}% below)\n"
                    f"📈 52W High: ₹{data['high_52']:.2f} ({d52_high:.2f}% below)\n\n"

                    f"⏰ {data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                )

            if self.send_whatsapp_notification(message):
                self.last_alert[symbol] = time.time()

    # ========================================

    def monitor(self):
        logging.info("🚀 Starting Stock Monitor")

        while True:
            try:
                logging.info("\n" + "="*60)
                logging.info(f"Checking at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logging.info("="*60)

                for symbol in self.stocks['symbols']:
                    self.check_stock(symbol)
                    time.sleep(2)

                logging.info(f"\nNext check in {self.check_interval} seconds...")
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logging.info("Stopped by user")
                break
            except Exception as e:
                logging.error(f"Loop error: {e}")
                time.sleep(60)

# ========================================

def main():
    nifty50 = get_nifty50_symbols()
    all_stocks = list(set(CUSTOM_STOCKS + nifty50 + PORTFOLIO_STOCKS))

    stocks_config = {
        'symbols': all_stocks,
        'alert_threshold_percent': ALERT_THRESHOLD_PERCENT
    }

    twilio_config = {
        'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
        'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
        'from_whatsapp': os.getenv('TWILIO_WHATSAPP_FROM'),
        'to_whatsapp': os.getenv('TWILIO_WHATSAPP_TO')
    }

    monitor = StockMonitor(
        stocks_config=stocks_config,
        twilio_config=twilio_config,
        check_interval=CHECK_INTERVAL_SECONDS
    )

    monitor.monitor()

# ========================================

if __name__ == "__main__":
    main()