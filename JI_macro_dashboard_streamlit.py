import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Merchant Transaction Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
    )

if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False

with st.expander("Upload File"):
    if not st.session_state.file_uploaded:
        # Add a file uploader widget
        uploaded_file = st.file_uploader("Choose file containing transactions data", type=["xlsx", "xlsm", "csv"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file, dtype={'MERCHANT_ID': str})

            # Convert the LAST_TRXN_DATE column to datetime
            df['LAST_TRXN_DATE'] = pd.to_datetime(df['LAST_TRXN_DATE'])

            # Format the column to only show the date
            df['LAST_TRXN_DATE'] = df['LAST_TRXN_DATE'].dt.date

            st.session_state.file_uploaded = True
            st.session_state.df = df

if st.session_state.file_uploaded:
    df = st.session_state.df
    # Dropdown to select a merchant
    with st.sidebar:
        st.title('Merchant Transaction Dashboard')

        selected_merchant = st.selectbox(
            "Select a Merchant",
            options=df['TRADING_NAME'].unique()
        )

        # Filter DataFrame based on selected merchant to get unique MERCHANT_IDs
        unique_ids = list(df[df['TRADING_NAME'] == selected_merchant]['MERCHANT_ID'].unique())
        unique_ids.insert(0, "All MIDs")

        # Select a Merchant ID
        selected_merchant_id = st.selectbox(
            "Select a Merchant ID",
            options=unique_ids
        )

        st.title('JI Calculation Settings')
        current_month = st.number_input('Enter the current month (1-12)', min_value=1, max_value=12, value=1)
        mdr_on_us = st.number_input('Enter MDR for ON US transactions (%)', value=0.00)
        mdr_off_us = st.number_input('Enter MDR for OFF US transactions (%)', value=0.00)
        mdr_intl = st.number_input('Enter MDR for INTL transactions (%)', value=0.00)

    # Create a function to classify the card types into VC, MC, JCB, CUP
    def classify_card_type(card_type):
        if 'VC' in card_type:
            return 'VC'
        elif 'MC' in card_type:
            return 'MC'
        elif 'JCB' in card_type:
            return 'JCB'
        elif 'CUP' in card_type:
            return 'CUP'
        else:
            return 'Other'

    # Apply this function to your DataFrame to create a new column for the broader card type category
    df['Super_Card_Type'] = df['CARD_TYPE'].apply(classify_card_type)

    # Create a function to classify txns into ON US, OFF US, INTL
    def classify_transaction(card_type):
        if card_type == 'VC ON US' or card_type == 'MC ON US':
            return 'ON US'
        elif 'INT' in card_type:
            return 'INTL'
        elif card_type == 'JCB' or card_type == 'CUP':
            return 'Other'
        else:
            return 'OFF US'
        
    df['Transaction_Type'] = df['CARD_TYPE'].apply(classify_transaction)

    # Display transactions for the selected merchant
    if selected_merchant_id == "All MIDs":
        # Filter data for the selected merchant without specific ID filtering
        merchant_data = df[df['TRADING_NAME'] == selected_merchant]
    else:
        # Filter data for both the selected merchant and specific ID
        merchant_data = df[(df['TRADING_NAME'] == selected_merchant) & (df['MERCHANT_ID'] == selected_merchant_id)]

    txn_card_type = merchant_data.groupby('Super_Card_Type')['MTD_VOL'].sum().reset_index()
    txn_card_type['Formatted MTD_VOL'] = txn_card_type['MTD_VOL'].apply(lambda x: "${:,.2f}".format(x))
    fig_bar = px.bar(txn_card_type, 
                    x='Super_Card_Type', 
                    y='MTD_VOL', 
                    labels={'Super_Card_Type': 'Card Type', 'MTD_VOL': 'Monthly Txn Volume'}, 
                    title='Total Transactions by Card Type',
                    hover_data={'Formatted MTD_VOL': True},
                    color_discrete_sequence=['#FF4B4B'])

    # Update hover information to show the currency formatted values
    fig_bar.update_traces(hovertemplate="Txn Volume: %{customdata[0]}<extra></extra>")

    merchant_data_pie = merchant_data[~merchant_data['CARD_TYPE'].isin(['JCB', 'CUP'])]
    on_off_intl_txn = merchant_data_pie.groupby('Transaction_Type')['MTD_VOL'].sum().reset_index()

    # Convert sums to currency format for hover display
    on_off_intl_txn['Formatted MTD_VOL'] = on_off_intl_txn['MTD_VOL'].apply(lambda x: "${:,.2f}".format(x))

    fig_pie = px.pie(on_off_intl_txn, 
                    values='MTD_VOL', 
                    names='Transaction_Type', 
                    title='ON US / OFF US / INTL Transactions (Only for Master & Visa)',
                    hover_data={'Formatted MTD_VOL': True},
                    color_discrete_sequence=['#FF4B4B', '#F77C7C', '#F0F2F6'])

    # Update hover information to show the currency formatted values
    fig_pie.update_traces(hovertemplate="<b>%{label}</b><br>Monthly Txn Volume: %{customdata[0]}<extra></extra>")

    # Calculation for JI
    def format_currency(value):
        """Helper function to format numeric values as currency (USD)."""
        return "${:,.2f}".format(value)

    def calculate_ji_amounts(merchant_data):
        # Assuming df has columns 'Transaction_Type' and 'MTD_VOL'
        ji_amounts = {
            'ON US': merchant_data[merchant_data['Transaction_Type'] == 'ON US']['MTD_VOL'].sum() * (mdr_on_us / 100),
            'OFF US': merchant_data[merchant_data['Transaction_Type'] == 'OFF US']['MTD_VOL'].sum() * (mdr_off_us / 100),
            'INTL': merchant_data[merchant_data['Transaction_Type'] == 'INTL']['MTD_VOL'].sum() * (mdr_intl / 100)
        }
        total_ji_mtd = sum(ji_amounts.values())
        estimated_annual_ji = (total_ji_mtd / current_month) * 12
        # Format currency values
        ji_amounts = {k: format_currency(v) for k, v in ji_amounts.items()}
        total_ji_mtd = format_currency(total_ji_mtd)
        estimated_annual_ji = format_currency(estimated_annual_ji)
        return ji_amounts, total_ji_mtd, estimated_annual_ji

    ji_amounts, total_ji_mtd, estimated_annual_ji = calculate_ji_amounts(merchant_data)

    # Create two main columns for the dashboard
    col1, col2 = st.columns((3, 1))

    # Column 1 - Left
    with col1:
        # Sub-columns for charts side by side on top
        pie_col, bar_col = st.columns(2)
        with pie_col:
            # Display pie chart
            st.plotly_chart(fig_pie, use_container_width=True)
        with bar_col:
            # Display bar chart
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Table of transactions for the selected merchant at the bottom
        st.write("Transactions for selected merchant:")
        st.dataframe(merchant_data,hide_index=True)  # Assuming 'merchant_data' holds the filtered data

    # Column 2 - Right
    with col2:
        # Display JI Summary and Projections on top
        st.header('JI Summary')
        ji_df = pd.DataFrame(ji_amounts.items(), columns=['Transaction Type', 'JI Amount MTD'])
        st.dataframe(ji_df,hide_index=True)
        st.subheader('Total and Annual JI Projections')
        st.metric(label="Total JI Amount MTD", value=total_ji_mtd)
        st.metric(label="Estimated Annual JI Amount", value=estimated_annual_ji)

        # Summary Table of Monthly Transaction Volumes for Distinct Card Types at the bottom
        summary_df = merchant_data.groupby('CARD_TYPE')['MTD_VOL'].sum().reset_index()
        summary_df['MTD_VOL'] = summary_df['MTD_VOL'].apply(lambda x: "${:,.2f}".format(x))
        st.dataframe(summary_df,hide_index=True)

    # Ensure to adjust the plotly charts to fill the width
    fig_bar.update_layout(autosize=True)
    fig_pie.update_layout(autosize=True)

else:
    st.write("Please upload a file to proceed.")