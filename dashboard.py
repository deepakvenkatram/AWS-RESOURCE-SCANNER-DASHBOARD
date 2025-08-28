import streamlit as st
import pandas as pd
import plotly.express as px

# Load data
@st.cache_data
def load_data(csv_file):
    return pd.read_csv(csv_file)

st.title("AWS Resource Audit Dashboard")

csv_path = st.file_uploader("Upload your AWS audit CSV file", type=["csv"])

if csv_path:
    df = load_data(csv_path)

    # Summary stats
    st.header("Summary")
    st.write(f"Total Resources: {len(df)}")
    resource_counts = df["ResourceType"].value_counts()
    st.bar_chart(resource_counts)

    # Filter by ResourceType
    resource_filter = st.multiselect("Select Resource Types", df["ResourceType"].unique(), default=df["ResourceType"].unique())
    filtered_df = df[df["ResourceType"].isin(resource_filter)]

    # Show table
    st.header("Filtered Resources")
    st.dataframe(filtered_df)

    # Pie chart for Resource Status
    status_counts = filtered_df["Status"].value_counts()
    fig_pie = px.pie(names=status_counts.index, values=status_counts.values, title="Resource Status Distribution")
    st.plotly_chart(fig_pie)

    # Cost overview
    st.header("Estimated Monthly Cost Overview")
    cost_df = filtered_df[filtered_df["EstimatedMonthlyCostUSD"].apply(lambda x: isinstance(x, (int, float)))]
    if not cost_df.empty:
        cost_by_type = cost_df.groupby("ResourceType")["EstimatedMonthlyCostUSD"].sum().reset_index()
        fig_cost = px.bar(cost_by_type, x="ResourceType", y="EstimatedMonthlyCostUSD", title="Cost by Resource Type", labels={"EstimatedMonthlyCostUSD": "Cost (USD)"})
        st.plotly_chart(fig_cost)
    else:
        st.write("No cost data available.")

else:
    st.info("Upload your AWS resource audit CSV file to get started.")

