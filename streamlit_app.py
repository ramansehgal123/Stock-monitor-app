"""
Indian Stock Market Monitor - NIFTY 50 + Custom Stocks + Portfolio Tracking
Streamlit Web App

Features:
- 26-week & 52-week low/high tracking
- Portfolio stocks with high alerts (selling opportunities)
- NIFTY 50 integration
- Alert cooldown mechanism
- Comprehensive metrics and charts
"""

import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from twilio.rest import Client
import time
import json

# ========================================
# CONFIGURATION
# ========================================

def get_nifty50_symbols():
    """Get NIFTY 50 stock symbols"""
    return [
        'RELIANCE.NS','TCS.NS','INFY.NS','HDFCBANK.NS','ICICIBANK.NS',
        'KOTAKBANK.NS','SBIN.NS','BHARTIARTL.NS','ITC.NS','LT.NS',
        'HINDUNILVR.NS','ASIANPAINT.NS','AXISBANK.NS','BAJFINANCE.NS',
        'BAJAJFINSV.NS','MARUTI.NS','M&M.NS','SUNPHARMA.NS',
        'DRREDDY.NS','CIPLA.NS','DIVISLAB.NS','ULTRACEMCO.NS','TITAN.NS',
        'NESTLEIND.NS','POWERGRID.NS','NTPC.NS','ONGC.NS','COALINDIA.NS',
        'JSWSTEEL.NS','TATASTEEL.NS','HINDALCO.NS','GRASIM.NS','ADANIENT.NS',
        'ADANIPORTS.NS','SBILIFE.NS','HDFCLIFE.NS','INDUSINDBK.NS',
        'TECHM.NS','WIPRO.NS','HCLTECH.NS','LTIM.NS','BRITANNIA.NS',
        'EICHERMOT.NS','HEROMOTOCO.NS','BAJAJ-AUTO.NS','UPL.NS',
        'APOLLOHOSP.NS','SHRIRAMFIN.NS','SBICARD.NS'
        # Note: TATAMOTORS.NS removed due to data issues
    ]

DEFAULT_CUSTOM_STOCKS = ['BPCL.NS', 'ASIANPAINT.NS']
DEFAULT_LOW_ALERT_THRESHOLD = 3  # Low alerts
DEFAULT_HIGH_ALERT_THRESHOLD = 7  # High alerts (portfolio only)
ALERT_COOLDOWN_SECONDS = 3600  # 1 hour

# ========================================
# PAGE CONFIGURATION
# ========================================

st.set_page_config(
    page_title="Stock Monitor - NIFTY 50 + Portfolio",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stAlert {padding: 1rem; margin: 1rem 0;}
    .metric-card {background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0;}
    .portfolio-badge {background-color: #FFD700; padding: 0.2rem 0.5rem; border-radius: 0.3rem; font-size: 0.8rem; font-weight: bold;}
    .nifty-badge {background-color: #4CAF50; color: white; padding: 0.2rem 0.5rem; border-radius: 0.3rem; font-size: 0.8rem;}
</style>
""", unsafe_allow_html=True)

# ========================================
# SESSION STATE INITIALIZATION
# ========================================

if 'last_check_time' not in st.session_state:
    st.session_state.last_check_time = None
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = []
if 'last_alert' not in st.session_state:
    st.session_state.last_alert = {}

# ========================================
# HELPER FUNCTIONS
# ========================================

def pct_from_low(price, low):
    """Calculate percentage distance from low"""
    return ((price - low) / low) * 100

def pct_from_high(price, high):
    """Calculate percentage distance from high"""
    return ((high - price) / high) * 100

def should_send_alert(symbol):
    """Check if alert cooldown has passed"""
    if symbol not in st.session_state.last_alert:
        return True
    time_since_alert = time.time() - st.session_state.last_alert[symbol]
    return time_since_alert > ALERT_COOLDOWN_SECONDS

def get_cooldown_remaining(symbol):
    """Get remaining cooldown time in minutes"""
    if symbol not in st.session_state.last_alert:
        return 0
    elapsed = time.time() - st.session_state.last_alert[symbol]
    remaining = max(0, ALERT_COOLDOWN_SECONDS - elapsed)
    return int(remaining / 60)

# ========================================
# DATA FETCHING
# ========================================

@st.cache_data(ttl=600)  # Cache for 10 minutes to reduce API calls
def get_stock_data(symbol, retry_count=0):
    """Fetch comprehensive stock data including 26W and 52W highs/lows"""
    max_retries = 3
    
    try:
        # Add delay to avoid rate limiting
        if retry_count > 0:
            time.sleep(2 * retry_count)  # Exponential backoff
        
        ticker = yf.Ticker(symbol)
        
        # Get 1-year data (includes current price and 52W data)
        hist_52w = ticker.history(period='1y')
        if hist_52w.empty:
            return None
        
        current_price = hist_52w['Close'].iloc[-1]
        low_52 = hist_52w['Low'].min()
        high_52 = hist_52w['High'].max()
        
        # Get 26-week data from the same 1y data to avoid extra API call
        hist_26w = hist_52w.tail(130)  # Approximately 26 weeks (6 months)
        low_26 = hist_26w['Low'].min()
        high_26 = hist_26w['High'].max()
        
        # Get stock name (with fallback to avoid API call if it fails)
        try:
            info = ticker.info
            stock_name = info.get('longName', symbol)
        except:
            stock_name = symbol  # Fallback to symbol if info fails
        
        # Calculate distances
        d26_low = pct_from_low(current_price, low_26)
        d52_low = pct_from_low(current_price, low_52)
        d26_high = pct_from_high(current_price, high_26)
        d52_high = pct_from_high(current_price, high_52)
        
        return {
            'symbol': symbol,
            'name': stock_name,
            'price': current_price,
            'low_26': low_26,
            'high_26': high_26,
            'low_52': low_52,
            'high_52': high_52,
            'd26_low': d26_low,
            'd52_low': d52_low,
            'd26_high': d26_high,
            'd52_high': d52_high,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a rate limit error
        if "Too Many Requests" in error_msg or "429" in error_msg:
            if retry_count < max_retries:
                st.warning(f"Rate limit hit for {symbol}. Retrying... ({retry_count + 1}/{max_retries})")
                time.sleep(3)  # Wait 3 seconds before retry
                return get_stock_data(symbol, retry_count + 1)
            else:
                st.error(f"Rate limit exceeded for {symbol}. Please try again in a few minutes.")
                return None
        else:
            st.error(f"Error fetching {symbol}: {error_msg}")
            return None

# ========================================
# WHATSAPP ALERTS
# ========================================

def send_whatsapp_alert(stock_data, alert_type, low_threshold, high_threshold, portfolio_stocks):
    """Send WhatsApp notification with comprehensive info"""
    try:
        # Get credentials from Streamlit secrets
        account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
        auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
        from_whatsapp = st.secrets.get("TWILIO_WHATSAPP_FROM", "")
        to_whatsapp = st.secrets.get("TWILIO_WHATSAPP_TO", "")
        
        if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
            st.warning("Twilio credentials not configured in secrets.")
            return False
        
        # Check cooldown
        if not should_send_alert(stock_data['symbol']):
            remaining = get_cooldown_remaining(stock_data['symbol'])
            st.info(f"Alert cooldown active. Next alert in {remaining} minutes.")
            return False
        
        client = Client(account_sid, auth_token)
        
        # Build message based on alert type
        is_portfolio = stock_data['symbol'] in portfolio_stocks
        
        if alert_type == "HIGH":
            message = (
                f"NEAR 52W HIGH (YOUR STOCK)\n\n"
                f"{stock_data['name']} ({stock_data['symbol']})\n\n"
                f"Price: {stock_data['price']:.2f}\n\n"
                f"52W High: {stock_data['high_52']:.2f} ({stock_data['d52_high']:.2f}% below)\n\n"
                f"{stock_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            # Low alert with full context
            if stock_data['d26_low'] <= low_threshold and stock_data['d52_low'] <= low_threshold:
                alert_msg = "NEAR BOTH 26W & 52W LOWS"
            elif stock_data['d52_low'] <= low_threshold:
                alert_msg = "NEAR 52W LOW"
            else:
                alert_msg = "NEAR 26W LOW"
            
            message = (
                f"{alert_msg}\n\n"
                f"{stock_data['name']} ({stock_data['symbol']})\n\n"
                f"Price: {stock_data['price']:.2f}\n\n"
                f"26W Low: {stock_data['low_26']:.2f} ({stock_data['d26_low']:.2f}%)\n"
                f"52W Low: {stock_data['low_52']:.2f} ({stock_data['d52_low']:.2f}%)\n\n"
                f"26W High: {stock_data['high_26']:.2f} ({stock_data['d26_high']:.2f}% below)\n"
                f"52W High: {stock_data['high_52']:.2f} ({stock_data['d52_high']:.2f}% below)\n\n"
                f"{stock_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        client.messages.create(
            body=message,
            from_=from_whatsapp,
            to=to_whatsapp
        )
        
        # Update cooldown
        st.session_state.last_alert[stock_data['symbol']] = time.time()
        return True
        
    except Exception as e:
        st.error(f"Error sending WhatsApp: {str(e)}")
        return False

# ========================================
# CHART CREATION
# ========================================

def create_stock_chart(symbol, stock_data):
    """Create comprehensive chart with 26W and 52W lines"""
    try:
        ticker = yf.Ticker(symbol)
        hist_data = ticker.history(period='1y')
        
        if hist_data.empty:
            return None
        
        fig = go.Figure()
        
        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=hist_data.index,
            open=hist_data['Open'],
            high=hist_data['High'],
            low=hist_data['Low'],
            close=hist_data['Close'],
            name='Price'
        ))
        
        # Add 26-week lines
        fig.add_hline(
            y=stock_data['low_26'],
            line_dash="dot",
            line_color="orange",
            annotation_text="26W Low",
            annotation_position="right"
        )
        fig.add_hline(
            y=stock_data['high_26'],
            line_dash="dot",
            line_color="lightgreen",
            annotation_text="26W High",
            annotation_position="right"
        )
        
        # Add 52-week lines
        fig.add_hline(
            y=stock_data['low_52'],
            line_dash="dash",
            line_color="red",
            annotation_text="52W Low",
            annotation_position="left"
        )
        fig.add_hline(
            y=stock_data['high_52'],
            line_dash="dash",
            line_color="green",
            annotation_text="52W High",
            annotation_position="left"
        )
        
        fig.update_layout(
            title=f"{stock_data['name']} - 1 Year Price Chart",
            yaxis_title="Price (â‚¹)",
            xaxis_title="Date",
            height=450,
            xaxis_rangeslider_visible=False
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating chart: {str(e)}")
        return None

# ========================================
# MAIN APP
# ========================================

def main():
    # Header
    st.title("Indian Stock Market Monitor")
    st.markdown("**NIFTY 50 + Custom Stocks + Portfolio Tracking with 26W & 52W Analysis**")
    
    # Rate limit info
    if st.session_state.last_check_time:
        minutes_since_check = (datetime.now() - st.session_state.last_check_time).seconds // 60
        if minutes_since_check < 10:
            st.info(f"Data is cached (refreshed {minutes_since_check} min ago). Yahoo Finance has rate limits - please wait 10 minutes between refreshes for best results.")
    
    # Declare variables that will be set in sidebar
    auto_refresh_enabled = False
    refresh_interval = 10
    enable_whatsapp = False
    
    # ========================================
    # SIDEBAR CONFIGURATION
    # ========================================
    
    with st.sidebar:
        st.header("Configuration")
        
        # Stock selection mode
        stock_mode = st.radio(
            "Stock Selection Mode",
            ["Custom Stocks", "NIFTY 50", "NIFTY 50 + Custom"],
            index=0
        )
        
        # Custom stocks input
        if stock_mode in ["Custom Stocks", "NIFTY 50 + Custom"]:
            st.subheader("Custom Stocks")
            custom_input = st.text_area(
                "Enter stock symbols (one per line)",
                value="\n".join(DEFAULT_CUSTOM_STOCKS),
                height=100,
                help="NSE stocks: SYMBOL.NS (e.g., BPCL.NS)"
            )
            custom_stocks = [s.strip() for s in custom_input.split('\n') if s.strip()]
        else:
            custom_stocks = []
        
        # Portfolio stocks
        st.subheader("Portfolio Stocks")
        st.caption("Stocks you own - will get HIGH alerts too")
        portfolio_input = st.text_area(
            "Enter portfolio stocks (one per line)",
            value="",
            height=80,
            help="Get alerts when these stocks are near 52W high (selling opportunity)"
        )
        portfolio_stocks = [s.strip() for s in portfolio_input.split('\n') if s.strip()]
        
        # Alert thresholds
        st.markdown("---")
        st.subheader("Alert Thresholds")
        
        low_alert_threshold = st.slider(
            "Low Alert (%)",
            min_value=1,
            max_value=10,
            value=DEFAULT_LOW_ALERT_THRESHOLD,
            help="Alert when stock is within this % of 26W/52W low"
        )
        
        high_alert_threshold = st.slider(
            "High Alert (%) - Portfolio Only",
            min_value=1,
            max_value=15,
            value=DEFAULT_HIGH_ALERT_THRESHOLD,
            help="Alert when portfolio stock is within this % of 52W high"
        )
        
        # WhatsApp alerts
        st.markdown("---")
        enable_whatsapp = st.checkbox("Enable WhatsApp Alerts")
        
        # Auto-refresh settings
        st.markdown("---")
        st.subheader("Auto-Refresh")
        auto_refresh_enabled = st.checkbox("Enable Auto-Refresh", value=False)
        
        if auto_refresh_enabled:
            refresh_interval = st.selectbox(
                "Refresh Interval",
                options=[5, 10, 15, 30],
                index=1,
                format_func=lambda x: f"{x} minutes",
                help="How often to automatically refresh data"
            )
        else:
            refresh_interval = 10  # Default when disabled
        
        # Manual refresh button
        st.markdown("---")
        if st.button("Refresh Now", type="primary", use_container_width=True):
            st.session_state.last_check_time = None
            st.rerun()
        
        # Last check time and countdown
        if st.session_state.last_check_time:
            st.caption(f"Last checked: {st.session_state.last_check_time.strftime('%H:%M:%S')}")
            
            if auto_refresh_enabled:
                elapsed = (datetime.now() - st.session_state.last_check_time).seconds
                remaining = (refresh_interval * 60) - elapsed
                
                if remaining > 0:
                    mins, secs = divmod(remaining, 60)
                    st.caption(f"Next refresh in: {mins}m {secs}s")
                else:
                    st.caption("Refreshing now...")
    
    # ========================================
    # DETERMINE STOCKS TO MONITOR
    # ========================================
    
    if stock_mode == "NIFTY 50":
        stocks_to_track = get_nifty50_symbols()
    elif stock_mode == "NIFTY 50 + Custom":
        stocks_to_track = list(set(custom_stocks + get_nifty50_symbols() + portfolio_stocks))
    else:
        stocks_to_track = list(set(custom_stocks + portfolio_stocks))
    
    if not stocks_to_track:
        st.warning("Please add at least one stock symbol in the sidebar")
        return
    
    # ========================================
    # FETCH STOCK DATA
    # ========================================
    
    with st.spinner(f"Fetching data for {len(stocks_to_track)} stocks..."):
        stock_data_list = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Batch processing to avoid rate limits
        batch_size = 5  # Process 5 stocks at a time
        
        for batch_start in range(0, len(stocks_to_track), batch_size):
            batch_end = min(batch_start + batch_size, len(stocks_to_track))
            batch = stocks_to_track[batch_start:batch_end]
            
            for symbol in batch:
                status_text.text(f"Fetching {symbol}... ({batch_start + batch.index(symbol) + 1}/{len(stocks_to_track)})")
                data = get_stock_data(symbol)
                if data:
                    stock_data_list.append(data)
                time.sleep(0.5)  # 500ms delay between each stock
                progress_bar.progress((batch_start + batch.index(symbol) + 1) / len(stocks_to_track))
            
            # Longer delay between batches
            if batch_end < len(stocks_to_track):
                time.sleep(2)  # 2 second delay between batches
        
        progress_bar.empty()
        status_text.empty()
        st.session_state.stock_data = stock_data_list
        st.session_state.last_check_time = datetime.now()
    
    # Show summary of failed stocks if any
    failed_count = len(stocks_to_track) - len(stock_data_list)
    if failed_count > 0:
        st.warning(f"{failed_count} stock(s) could not be loaded. Data may be unavailable or symbol invalid.")
    
    if not stock_data_list:
        st.error("No stock data available. Please check your internet connection and stock symbols.")
        return
    
    # ========================================
    # CATEGORIZE STOCKS
    # ========================================
    
    nifty50_list = get_nifty50_symbols()
    
    # Low alerts (26W or 52W)
    low_26_stocks = [s for s in stock_data_list if s['d26_low'] <= low_alert_threshold]
    low_52_stocks = [s for s in stock_data_list if s['d52_low'] <= low_alert_threshold]
    low_both_stocks = [s for s in stock_data_list if s['d26_low'] <= low_alert_threshold and s['d52_low'] <= low_alert_threshold]
    
    # High alerts (portfolio only)
    high_stocks = [s for s in stock_data_list if s['symbol'] in portfolio_stocks and s['d52_high'] <= high_alert_threshold]
    
    # ========================================
    # SUMMARY METRICS
    # ========================================
    
    st.header("Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Stocks", len(stock_data_list))
    with col2:
        st.metric("Near 26W Low", len(low_26_stocks))
    with col3:
        st.metric("Near 52W Low", len(low_52_stocks))
    with col4:
        st.metric("Near Both Lows", len(low_both_stocks))
    with col5:
        st.metric("Portfolio Near High", len(high_stocks))
    
    # ========================================
    # ALERTS SECTION
    # ========================================
    
    st.header("Alerts")
    
    # HIGH ALERTS (Portfolio stocks near 52W high)
    if high_stocks:
        st.success(f"**{len(high_stocks)} Portfolio Stock(s) Near 52-Week HIGH** - Selling Opportunity!")
        
        for stock in high_stocks:
            with st.expander(f"{stock['name']} ({stock['symbol']}) - Portfolio", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Current Price:** â‚¹{stock['price']:.2f}")
                    st.markdown(f"**52-Week High:** â‚¹{stock['high_52']:.2f}")
                    st.markdown(f"**Distance from High:** {stock['d52_high']:.2f}% below")
                    st.success("Consider selling for profit!")
                
                with col2:
                    if enable_whatsapp:
                        if st.button(f"Alert", key=f"high_{stock['symbol']}"):
                            if send_whatsapp_alert(stock, "HIGH", low_alert_threshold, high_alert_threshold, portfolio_stocks):
                                st.success("Sent!")
    
    # LOW ALERTS
    if low_both_stocks:
        st.warning(f"**{len(low_both_stocks)} Stock(s) Near BOTH 26W & 52W Lows**")
        
        for stock in low_both_stocks:
            is_portfolio = stock['symbol'] in portfolio_stocks
            is_nifty = stock['symbol'] in nifty50_list
            
            badges = ""
            if is_portfolio:
                badges += '<span class="portfolio-badge">PORTFOLIO</span> '
            if is_nifty:
                badges += '<span class="nifty-badge">NIFTY 50</span>'
            
            with st.expander(f"{stock['name']} ({stock['symbol']})", expanded=True):
                if badges:
                    st.markdown(badges, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown("**Low Levels:**")
                    st.markdown(f"26W Low: {stock['low_26']:.2f} ({stock['d26_low']:.2f}%)")
                    st.markdown(f"52W Low: {stock['low_52']:.2f} ({stock['d52_low']:.2f}%)")
                
                with col2:
                    st.markdown("**High Levels:**")
                    st.markdown(f"26W High: {stock['high_26']:.2f} ({stock['d26_high']:.2f}% below)")
                    st.markdown(f"52W High: {stock['high_52']:.2f} ({stock['d52_high']:.2f}% below)")
                
                with col3:
                    st.markdown(f"**Price:** {stock['price']:.2f}")
                    if enable_whatsapp:
                        if st.button(f" ",key=f"low_{stock['symbol']}"):
                            if send_whatsapp_alert(stock, "LOW", low_alert_threshold, high_alert_threshold, portfolio_stocks):
                                st.success("âœ…")
    
    elif low_52_stocks or low_26_stocks:
        # Get unique count by symbols (not dict objects)
        unique_symbols = set([s['symbol'] for s in low_26_stocks] + [s['symbol'] for s in low_52_stocks])
        st.info(f"**{len(unique_symbols)} Stock(s) Near Low Levels**")
    else:
        st.success("No stocks at alert levels")
    
    # ========================================
    # DETAILED STOCK VIEW
    # ========================================
    
    st.header("Detailed Stock Analysis")
    
    # Filter options
    filter_option = st.radio(
        "Show:",
        ["All Stocks", "Alerts Only", "Portfolio Only", "NIFTY 50 Only"],
        horizontal=True
    )
    
    if filter_option == "Alerts Only":
        filtered_stocks = [s for s in stock_data_list if 
                          s['d26_low'] <= low_alert_threshold or 
                          s['d52_low'] <= low_alert_threshold or
                          (s['symbol'] in portfolio_stocks and s['d52_high'] <= high_alert_threshold)]
    elif filter_option == "Portfolio Only":
        filtered_stocks = [s for s in stock_data_list if s['symbol'] in portfolio_stocks]
    elif filter_option == "NIFTY 50 Only":
        filtered_stocks = [s for s in stock_data_list if s['symbol'] in nifty50_list]
    else:
        filtered_stocks = stock_data_list
    
    # Sort options
    sort_by = st.selectbox(
        "Sort by:",
        ["Name", "26W Low Distance", "52W Low Distance", "52W High Distance", "Price"]
    )
    
    if sort_by == "26W Low Distance":
        filtered_stocks = sorted(filtered_stocks, key=lambda x: x['d26_low'])
    elif sort_by == "52W Low Distance":
        filtered_stocks = sorted(filtered_stocks, key=lambda x: x['d52_low'])
    elif sort_by == "52W High Distance":
        filtered_stocks = sorted(filtered_stocks, key=lambda x: x['d52_high'])
    elif sort_by == "Price":
        filtered_stocks = sorted(filtered_stocks, key=lambda x: x['price'], reverse=True)
    else:
        filtered_stocks = sorted(filtered_stocks, key=lambda x: x['name'])
    
    st.info(f"Showing {len(filtered_stocks)} of {len(stock_data_list)} stocks")
    
    # Create tabs
    if filtered_stocks:
        for stock in filtered_stocks:
            is_portfolio = stock['symbol'] in portfolio_stocks
            is_nifty = stock['symbol'] in nifty50_list
            
            badge_text = ""
            if is_portfolio:
                badge_text += ""
            if is_nifty:
                badge_text += ""
            
            with st.expander(f"{badge_text}{stock['name']} ({stock['symbol']})"):
                # Metrics row
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    st.metric("Price", f"{stock['price']:.2f}")
                with col2:
                    st.metric("26W Low", f"{stock['low_26']:.2f}", f"{stock['d26_low']:.1f}%")
                with col3:
                    st.metric("52W Low", f"{stock['low_52']:.2f}", f"{stock['d52_low']:.1f}%")
                with col4:
                    st.metric("26W High", f"{stock['high_26']:.2f}", f"-{stock['d26_high']:.1f}%")
                with col5:
                    st.metric("52W High", f"{stock['high_52']:.2f}", f"-{stock['d52_high']:.1f}%")
                with col6:
                    # Alert indicators
                    if stock['d26_low'] <= low_alert_threshold and stock['d52_low'] <= low_alert_threshold:
                        st.error("Both Lows")
                    elif stock['d52_low'] <= low_alert_threshold:
                        st.warning("52W Low")
                    elif stock['d26_low'] <= low_alert_threshold:
                        st.info("26W Low")
                    if is_portfolio and stock['d52_high'] <= high_alert_threshold:
                        st.success("Near High")
                
                # Chart
                fig = create_stock_chart(stock['symbol'], stock)
                if fig:
                    st.plotly_chart(fig, width='stretch')
    
    # ========================================
    # DATA TABLE
    # ========================================
    
    st.header("Data Table")
    
    df = pd.DataFrame(filtered_stocks)
    
    # Add badges column
    df['badges'] = df['symbol'].apply(lambda x: 
        ('' if x in portfolio_stocks else '') + 
        ('' if x in nifty50_list else '')
    )
    
    # Format columns
    df_display = df[[
        'badges', 'name', 'symbol', 'price',
        'low_26', 'd26_low', 'low_52', 'd52_low',
        'high_26', 'd26_high', 'high_52', 'd52_high'
    ]].copy()
    
    df_display.columns = [
        '', 'Stock Name', 'Symbol', 'Price',
        '26W Low', '% from 26W Low', '52W Low', '% from 52W Low',
        '26W High', '% from 26W High', '52W High', '% from 52W High'
    ]
    
    # Format numbers
    for col in ['Price', '26W Low', '52W Low', '26W High', '52W High']:
        df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}")
    
    for col in ['% from 26W Low', '% from 52W Low', '% from 26W High', '% from 52W High']:
        df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(df_display, width='stretch', hide_index=True)
    
    # Download button
    csv = df_display.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name=f"stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # ========================================
    # AUTO-REFRESH LOGIC
    # ========================================
    
    if auto_refresh_enabled and st.session_state.last_check_time:
        # Check if it's time to auto-refresh
        elapsed_seconds = (datetime.now() - st.session_state.last_check_time).seconds
        refresh_threshold = refresh_interval * 60  # Convert to seconds
        
        if elapsed_seconds >= refresh_threshold:
            st.info("Auto-refreshing data...")
            time.sleep(1)  # Brief pause for user to see message
            st.session_state.last_check_time = None
            st.rerun()
        else:
            # Schedule next check in 5 seconds to update countdown
            time.sleep(5)
            st.rerun()

if __name__ == "__main__":
    main()
