import pandas as pd
import plotly.express as px

# Read data from Excel file
excel_file = "./Schedule.xlsx"  # Replace with your actual Excel file path
df = pd.read_excel(excel_file)

df["x_label"] = df["Program"] + ":" + \
                df["Release"] + " " + \
                df["EndDate"].dt.strftime('%Y-%m-%d')

date_range = pd.date_range(df["StartDate"].min(), df["EndDate"].max() + pd.DateOffset(months=11), freq='MS')

# Create Gantt chart using Plotly Express
fig = px.timeline(
    df,
    x_start="StartDate",
    x_end="EndDate",
    y="x_label",
    color="PercentComplete",
    #color_discrete_map=[(0, "grey"), (1, "green"), (100, "blue")]
    color_continuous_scale=[(0, "grey"), (0.5, "green"), (1, "blue")],
    range_color=[0, 1],
    #color_descrete_sequence=["grey", "green", "blue"],
    labels={"PercentComplete": "Percent Complete",
            },
    text="Feature"
)

#fig.update_traces(textposition='outside')
# Customize the layout
#annotation = px.graph_objects.layout.Annotation()
fig.update_layout(
    title="Advanced Service Engineering Projects",
    xaxis=dict(
        title="2024-2026",
        showgrid=True,
        zeroline=True,
        showline=True,
        showticklabels=True,
        type="date",
        range=[df["StartDate"].min(), df["EndDate"].max() + pd.DateOffset(months=3)],
        tickmode="array",
        tickvals=date_range,
        ticktext=[dt.strftime("%b") for dt in date_range],
    ),
    yaxis=dict(title="Releases", showgrid=True, zeroline=True, showline=True, showticklabels=True),
    width=1000,
    height=500
)

# Save Gantt chart as an image
fig.write_image("gantt_chart_image.png")
