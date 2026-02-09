import pandas as pd
import plotly.express as px

# Read data from Excel file
excel_file = "./Status.xlsx"  # Replace with your actual Excel file path
df = pd.read_excel(excel_file)

df["x_label"] = (
    df["Program"]
    + ":"
    + df["Active Release"]
    + " "
    + df["Active Release EndDate"].dt.strftime("%Y-%m-%d")
)

date_range = pd.date_range(
    df["Active Release StartDate"].min(),
    df["Active Release EndDate"].max() + pd.DateOffset(months=11),
    freq="MS",
)

text = df["Features in Active Release"] + " " + df["Upcoming Items"]

# Create Gantt chart using Plotly Express
fig = px.timeline(
    df,
    x_start="Active Release StartDate",
    x_end="Active Release EndDate",
    y="x_label",
    color="Active Release PercentComplete",
    # color_discrete_map=[(0, "grey"), (1, "green"), (100, "blue")]
    color_continuous_scale=[(0, "grey"), (0.5, "green"), (1, "blue")],
    range_color=[0, 1],
    # color_descrete_sequence=["grey", "green", "blue"],
    # labels={
    #    "PercentComplete": "Percent Complete",
    # },
    text=text,
)

# fig.update_traces(textposition='outside')
# Customize the layout
# annotation = px.graph_objects.layout.Annotation()
fig.update_layout(
    title="Advanced Service Engineering Projects",
    xaxis=dict(
        title="2024-2026",
        showgrid=True,
        zeroline=True,
        showline=True,
        showticklabels=True,
        type="date",
        range=[
            df["Active Release StartDate"].min(),
            df["Active Release EndDate"].max() + pd.DateOffset(months=3),
        ],
        tickmode="array",
        tickvals=date_range,
        ticktext=[dt.strftime("%b") for dt in date_range],
    ),
    yaxis=dict(
        title="Releases",
        showgrid=True,
        zeroline=True,
        showline=True,
        showticklabels=True,
    ),
    width=1000,
    height=500,
)

fig2 = px.bar(
    data_frame=df,
    x="Program",
    y="Backlog",
    title="ASE Projects Backlog by Program",
    labels={"Backlog": "Backlog Hours", "Program": "Program"},
    color="Program",
    text="Backlog",
    width=1000,
    height=500,
)
fig3 = px.bar(
    data_frame=df,
    x="Program",
    y="Active Release Remaining",
    title="ASE Projects Work Remaining by Program",
    labels={"Active Release Remaining": "Remaining Hours", "Program": "Program"},
    color="Program",
    text="Active Release Remaining",
    width=1000,
    height=500,
)

# Save Gantt chart as an image
fig.write_image("status_gantt_chart_image.png")
fig2.write_image("backlog_bar_chart_image.png")
fig3.write_image("active_bar_chart_image.png")
