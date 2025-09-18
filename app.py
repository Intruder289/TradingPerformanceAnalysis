import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(
    page_title="MT5 Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---

# Function to connect to MetaTrader 5
def connect_to_mt5():
    """Initializes and checks the connection to the MT5 terminal."""
    if not mt5.initialize():
        st.error("Failed to initialize MetaTrader 5. Make sure the terminal is running.")
        st.stop()
    return True

# Function to fetch trade history within a date range
@st.cache_data(ttl=600) # Cache data for 10 minutes
def get_trade_history(start_date, end_date):
    """Fetches trading deals, converts them to a pandas DataFrame."""
    deals = mt5.history_deals_get(start_date, end_date)
    if deals is None or len(deals) == 0:
        return pd.DataFrame() # Return empty dataframe if no deals

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # Convert timestamp to datetime
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.sort_values('time', inplace=True)
    return df

# --- Main Application UI ---

st.title("📈 MetaTrader 5 Performance Dashboard")
st.markdown("Analyze your trading performance with interactive charts and metrics.")

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("⚙️ User Controls")
    
    # Use today's date and 30 days ago as default
    today = datetime.now()
    default_start_date = today - timedelta(days=30)
    
    start_date = st.date_input("Start Date", value=default_start_date, help="Select the start date for analysis.")
    end_date = st.date_input("End Date", value=today, help="Select the end date for analysis.")

    # Convert dates to datetime objects for MT5
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    analyze_button = st.button("🚀 Analyze Performance", type="primary")

# --- Main Dashboard Area ---
if analyze_button:
    # Ensure dates are in the correct order
    if start_datetime >= end_datetime:
        st.error("Error: Start date must be before the end date.")
    else:
        with st.spinner("Connecting to MT5 and fetching data..."):
            connect_to_mt5()
            raw_data = get_trade_history(start_datetime, end_datetime)
            mt5.shutdown() # Disconnect after fetching data

        if raw_data.empty:
            st.warning("No account activity found for the selected period. Please select a different date range.")
        else:
            # Filter for actual Buy/Sell trades
            trade_data = raw_data[raw_data['type'].isin([mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL])].copy()
            
            # Filter for balance operations (deposits/withdrawals)
            balance_data = raw_data[raw_data['type'] == mt5.DEAL_TYPE_BALANCE].copy()

            if trade_data.empty:
                st.warning("No actual trades (Buys/Sells) found for the selected period. Only balance operations were detected.")
            else:
                # --- Performance Metrics Calculation ---
                net_profit = trade_data['profit'].sum()
                
                # Filter for only closing deals to calculate total trades
                closing_deals = trade_data[trade_data['entry'] == mt5.DEAL_ENTRY_OUT]
                total_trades = len(closing_deals)
                
                wins = closing_deals[closing_deals['profit'] > 0]
                losses = closing_deals[closing_deals['profit'] < 0]
                
                winning_trades = len(wins)
                losing_trades = len(losses)
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                total_profit = wins['profit'].sum()
                total_loss = abs(losses['profit'].sum())
                
                profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')
                
                avg_win = wins['profit'].mean() if winning_trades > 0 else 0
                avg_loss = abs(losses['profit'].mean()) if losing_trades > 0 else 0

                # --- Display Key Performance Indicators (KPIs) ---
                st.header("📊 Overall Performance")
                
                kpi_cols = st.columns(4)
                kpi_cols[0].metric(label="Net Profit ($)", value=f"${net_profit:,.2f}")
                kpi_cols[1].metric(label="Total Trades", value=f"{total_trades}")
                kpi_cols[2].metric(label="Win Rate (%)", value=f"{win_rate:.2f}%")
                kpi_cols[3].metric(label="Profit Factor", value=f"{profit_factor:.2f}")

                # --- Charts and Visualizations ---
                st.header("📈 Visual Analysis")

                # 1. Cumulative Profit (Equity Curve)
                trade_data['cumulative_profit'] = trade_data['profit'].cumsum()
                fig_equity = px.line(
                    trade_data, 
                    x='time', 
                    y='cumulative_profit', 
                    title='Equity Curve (Cumulative Profit from Trades)',
                    labels={'time': 'Date', 'cumulative_profit': 'Cumulative Profit ($)'}
                )
                fig_equity.update_layout(template='plotly_white')
                st.plotly_chart(fig_equity, use_container_width=True)

                # 2. Profit/Loss by Symbol
                profit_by_symbol = closing_deals.groupby('symbol')['profit'].sum().sort_values()
                fig_pnl_symbol = px.bar(
                    profit_by_symbol,
                    x=profit_by_symbol.index,
                    y='profit',
                    title='Profit & Loss by Symbol',
                    labels={'symbol': 'Symbol', 'profit': 'Total Profit ($)'},
                    color='profit',
                    color_continuous_scale=px.colors.diverging.RdYlGn,
                    text_auto='.2f'
                )
                fig_pnl_symbol.update_layout(template='plotly_white')
                st.plotly_chart(fig_pnl_symbol, use_container_width=True)

                # replace type with 'Buy' and 'Sell'
                trade_data['type'] = trade_data['type'].replace({mt5.DEAL_TYPE_BUY: 'Sell', mt5.DEAL_TYPE_SELL: 'Buy'})

                #filter out trades with profit 0
                trade_data = trade_data[trade_data['profit'] != 0]
                
                # --- Detailed History Sections ---
                with st.expander("📂 View Detailed Trade History"):
                    st.dataframe(
                        trade_data[[
                            'time', 'symbol', 'ticket', 'type', 
                             'volume', 'price', 'profit', 'comment'
                        ]],
                        use_container_width=True
                    )
                
                if not balance_data.empty:
                    with st.expander("💰 View Deposits & Withdrawals"):
                        st.dataframe(
                            balance_data[['time', 'ticket', 'profit']],
                            use_container_width=True
                        )
else:
    st.info("Please select a date range and click 'Analyze Performance' to begin.")

