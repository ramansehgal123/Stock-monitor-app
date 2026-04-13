"""
Indian Stock Market Monitor - 52-Week Low Tracker
Streamlit Web App
"""

import streamlit as st
import yfinance as yf
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from twilio.rest import Client
import time

# ========================================
# CONFIGURATION - EDIT STOCKS HERE
# ========================================
DEFAULT_STOCKS = [
    'BPCL.NS',        # Bharat Petroleum Corporation Limited
    'ASIANPAINT.NS'   # Asian Paints Limited
]

DEFAULT_ALERT_THRESHOLD = 5  # Alert when within 5% of 52-week low
# ========================================

# Page configuration
st.set_page_config(
    page_title="Stock 52-Week Low Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stAlert {
        padding: 1rem;
        margin: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_check_time' not in st.session_state:
    st.session_state.last_check_time = None
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = []
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

def get_stock_data(symbol):
    """Fetch stock data from Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get current price
        hist = ticker.history(period='1d')
        if hist.empty:
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
        
        return {
            'symbol': symbol,
            'name': stock_name,
            'current_price': current_price,
            '52_week_low': week_52_low,
            '52_week_high': week_52_high,
            'distance': distance,
            'timestamp': datetime.now()
        }
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def send_whatsapp_alert(stock_data, threshold):
    """Send WhatsApp notification using Twilio"""
    try:
        # Get credentials from Streamlit secrets
        account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
        auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
        from_whatsapp = st.secrets.get("TWILIO_WHATSAPP_FROM", "")
        to_whatsapp = st.secrets.get("TWILIO_WHATSAPP_TO", "")
        
        if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
            st.warning("⚠️ Twilio credentials not configured in secrets. WhatsApp alerts disabled.")
            return False
        
        client = Client(account_sid, auth_token)
        
        message = (
            f"🚨 STOCK ALERT - 52 WEEK LOW 🚨\n\n"
            f"Stock: {stock_data['name']}\n"
            f"Symbol: {stock_data['symbol']}\n\n"
            f"Current Price: ₹{stock_data['current_price']:.2f}\n"
            f"52-Week Low: ₹{stock_data['52_week_low']:.2f}\n"
            f"52-Week High: ₹{stock_data['52_week_high']:.2f}\n\n"
            f"📊 Distance from 52W Low: {stock_data['distance']:.2f}%\n\n"
            f"⚠️ Stock is {'AT' if stock_data['distance'] <= 0.5 else 'NEAR'} its 52-week low!\n"
            f"Time: {stock_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        client.messages.create(
            body=message,
            from_=from_whatsapp,
            to=to_whatsapp
        )
        return True
    except Exception as e:
        st.error(f"Error sending WhatsApp: {str(e)}")
        return False

def create_stock_chart(hist_data, stock_data):
    """Create an interactive price chart"""
    fig = go.Figure()
    
    # Add candlestick chart
    fig.add_trace(go.Candlestick(
        x=hist_data.index,
        open=hist_data['Open'],
        high=hist_data['High'],
        low=hist_data['Low'],
        close=hist_data['Close'],
        name='Price'
    ))
    
    # Add 52-week low line
    fig.add_hline(
        y=stock_data['52_week_low'],
        line_dash="dash",
        line_color="red",
        annotation_text="52W Low",
        annotation_position="right"
    )
    
    # Add 52-week high line
    fig.add_hline(
        y=stock_data['52_week_high'],
        line_dash="dash",
        line_color="green",
        annotation_text="52W High",
        annotation_position="right"
    )
    
    fig.update_layout(
        title=f"{stock_data['name']} - 1 Year Price Chart",
        yaxis_title="Price (₹)",
        xaxis_title="Date",
        height=400,
        xaxis_rangeslider_visible=False
    )
    
    return fig

def main():
    # Header
    st.title("📈 Indian Stock Market 52-Week Low Monitor")
    st.markdown("Real-time monitoring of stocks approaching their 52-week low")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Stock selection
        stock_input = st.text_area(
            "Stocks to Monitor (one per line)",
            value="\n".join(DEFAULT_STOCKS),
            height=100,
            help="Enter NSE stock symbols with .NS suffix (e.g., BPCL.NS)"
        )
        stocks_to_track = [s.strip() for s in stock_input.split('\n') if s.strip()]
        
        # Alert threshold
        alert_threshold = st.slider(
            "Alert Threshold (%)",
            min_value=1,
            max_value=20,
            value=DEFAULT_ALERT_THRESHOLD,
            help="Alert when stock is within this % of 52-week low"
        )
        
        # Auto-refresh
        st.markdown("---")
        auto_refresh = st.checkbox("🔄 Auto-refresh (every 5 minutes)", value=False)
        
        if auto_refresh:
            st.info("📊 Auto-refresh enabled. Data will update every 5 minutes.")
        
        # Manual refresh button
        if st.button("🔃 Refresh Now", type="primary", use_container_width=True):
            st.session_state.last_check_time = None
            st.rerun()
        
        # WhatsApp alerts
        st.markdown("---")
        enable_whatsapp = st.checkbox("📱 Enable WhatsApp Alerts")
        
        if enable_whatsapp:
            st.info("💡 Configure Twilio credentials in Streamlit secrets")
        
        # Last check time
        if st.session_state.last_check_time:
            st.markdown("---")
            st.caption(f"Last checked: {st.session_state.last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Main content
    if not stocks_to_track:
        st.warning("⚠️ Please add at least one stock symbol in the sidebar")
        return
    
    # Fetch stock data
    with st.spinner("📊 Fetching stock data..."):
        stock_data_list = []
        for symbol in stocks_to_track:
            data = get_stock_data(symbol)
            if data:
                stock_data_list.append(data)
        
        st.session_state.stock_data = stock_data_list
        st.session_state.last_check_time = datetime.now()
    
    if not stock_data_list:
        st.error("❌ No stock data available. Please check your internet connection and stock symbols.")
        return
    
    # Summary metrics
    st.header("📊 Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Stocks Monitored", len(stock_data_list))
    
    near_low_stocks = [s for s in stock_data_list if s['distance'] <= alert_threshold]
    with col2:
        st.metric(
            "Near 52W Low",
            len(near_low_stocks),
            delta=f"{len(near_low_stocks)} stocks" if near_low_stocks else "All clear"
        )
    
    with col3:
        avg_distance = sum(s['distance'] for s in stock_data_list) / len(stock_data_list)
        st.metric("Avg Distance from Low", f"{avg_distance:.1f}%")
    
    # Alert section
    if near_low_stocks:
        st.warning(f"⚠️ **{len(near_low_stocks)} stock(s) near 52-week low!**")
        
        for stock in near_low_stocks:
            with st.expander(f"🔴 {stock['name']} ({stock['symbol']})", expanded=True):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Current Price:** ₹{stock['current_price']:.2f}")
                    st.markdown(f"**52-Week Low:** ₹{stock['52_week_low']:.2f}")
                    st.markdown(f"**52-Week High:** ₹{stock['52_week_high']:.2f}")
                    st.markdown(f"**Distance from Low:** {stock['distance']:.2f}%")
                    
                    # Status indicator
                    if stock['distance'] <= 0.5:
                        st.error("🔴 AT 52-WEEK LOW")
                    else:
                        st.warning(f"🟡 NEAR 52-WEEK LOW")
                
                with col2:
                    if enable_whatsapp:
                        if st.button(f"📱 Send Alert", key=f"alert_{stock['symbol']}"):
                            if send_whatsapp_alert(stock, alert_threshold):
                                st.success("✅ Alert sent!")
                            else:
                                st.error("❌ Failed to send alert")
    else:
        st.success("✅ No stocks near 52-week low at this time")
    
    # Detailed stock information
    st.header("📈 Stock Details")
    
    # Create tabs for each stock
    if len(stock_data_list) > 1:
        tabs = st.tabs([f"{s['name'][:20]}... ({s['symbol']})" for s in stock_data_list])
    else:
        tabs = [st.container()]
    
    for idx, (tab, stock) in enumerate(zip(tabs, stock_data_list)):
        with tab:
            # Stock metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Current Price", f"₹{stock['current_price']:.2f}")
            with col2:
                st.metric("52W Low", f"₹{stock['52_week_low']:.2f}")
            with col3:
                st.metric("52W High", f"₹{stock['52_week_high']:.2f}")
            with col4:
                st.metric("Distance", f"{stock['distance']:.2f}%")
            
            # Price chart
            try:
                ticker = yf.Ticker(stock['symbol'])
                hist_data = ticker.history(period='1y')
                
                if not hist_data.empty:
                    fig = create_stock_chart(hist_data, stock)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chart data not available")
            except Exception as e:
                st.error(f"Error creating chart: {str(e)}")
            
            # Additional info
            with st.expander("📋 Additional Information"):
                st.markdown(f"**Stock Name:** {stock['name']}")
                st.markdown(f"**Symbol:** {stock['symbol']}")
                st.markdown(f"**Last Updated:** {stock['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Data table
    st.header("📊 Data Table")
    df = pd.DataFrame(stock_data_list)
    df['current_price'] = df['current_price'].apply(lambda x: f"₹{x:.2f}")
    df['52_week_low'] = df['52_week_low'].apply(lambda x: f"₹{x:.2f}")
    df['52_week_high'] = df['52_week_high'].apply(lambda x: f"₹{x:.2f}")
    df['distance'] = df['distance'].apply(lambda x: f"{x:.2f}%")
    df = df[['name', 'symbol', 'current_price', '52_week_low', '52_week_high', 'distance']]
    df.columns = ['Stock Name', 'Symbol', 'Current Price', '52W Low', '52W High', 'Distance from Low']
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(300)  # Wait 5 minutes
        st.rerun()

if __name__ == "__main__":
    main()
