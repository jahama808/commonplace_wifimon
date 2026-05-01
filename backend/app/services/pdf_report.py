"""Synchronous PDF report builder (SPEC §5.7).

reportlab + matplotlib produce the PDF. Both are sync libs, so the caller
runs this in an executor (`asyncio.run_in_executor`).

The builder is decoupled from the DB — it takes a typed `ReportData`
dataclass so it can be exercised with fixture data in tests.

Layout (SPEC §5.7):
  1. Title page: property name, "WiFi Network Report", HST timestamp.
  2. Device Inventory: total/online/offline; eero models table; per-device
     details table (location, model, current connected count, status).
  3. Connected Devices by SSID (page break before): one stacked bar chart
     per selected SSID, last 24 sample points, with a network-color legend
     table beneath.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime

import matplotlib

# Use a non-interactive backend — there's no display in the worker process.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ──────────────────────────────────────────────────────────────────────────────
# Input data shape
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class DeviceRow:
    location: str
    model: str
    connected_count: int
    status: str  # "online" / "offline"


@dataclass
class SsidChart:
    """One stacked-bar chart panel.

    `timestamps` is the shared x-axis; `series` is `{network_name: counts}`
    where each network's counts have the same length as `timestamps`.
    `colors` maps `network_name → hex string` so the legend lines up.
    """

    ssid: str
    timestamps: list[datetime]
    series: dict[str, list[int]]
    colors: dict[str, str]


@dataclass
class ReportData:
    property_name: str
    generated_at_hst: datetime
    total_eeros: int
    online_eeros: int
    offline_eeros: int
    eero_models: dict[str, int]  # model_name → count
    devices: list[DeviceRow]
    ssid_charts: list[SsidChart] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────────

# Match the warm-dark palette of the dashboard so on-screen review of the
# rendered PDF doesn't feel jarring. Picked for paper readability though.
_NETWORK_PALETTE = [
    "#3aa9bd",  # teal
    "#cf9234",  # gold
    "#7e5fcc",  # violet
    "#c1693a",  # orange
    "#3aa066",  # green
    "#3a78c8",  # blue
    "#c63a4f",  # rose
    "#9aa636",  # olive
]

OK_COLOR = colors.HexColor("#2f8c4f")
BAD_COLOR = colors.HexColor("#bd3a40")
LINE_COLOR = colors.HexColor("#cccccc")
TITLE_COLOR = colors.HexColor("#1a1a1a")


def _styles() -> dict[str, ParagraphStyle]:
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=s["Title"], fontSize=24, textColor=TITLE_COLOR, spaceAfter=18
        ),
        "h1": ParagraphStyle(
            "h1", parent=s["Heading1"], fontSize=16, spaceAfter=10, textColor=TITLE_COLOR
        ),
        "h2": ParagraphStyle(
            "h2", parent=s["Heading2"], fontSize=13, spaceAfter=6
        ),
        "body": s["BodyText"],
        "subtle": ParagraphStyle("subtle", parent=s["BodyText"], textColor=colors.gray),
    }


def _stat_table(data: ReportData) -> Table:
    rows = [
        ["Total Eero Units", str(data.total_eeros)],
        ["Online", str(data.online_eeros)],
        ["Offline", str(data.offline_eeros)],
    ]
    t = Table(rows, colWidths=[2.5 * inch, 1.5 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE_COLOR),
                ("TEXTCOLOR", (1, 1), (1, 1), OK_COLOR),
                ("TEXTCOLOR", (1, 2), (1, 2), BAD_COLOR if data.offline_eeros else colors.black),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    return t


def _models_table(data: ReportData) -> Table:
    rows: list[list[str]] = [["Model", "Count"]]
    if not data.eero_models:
        rows.append(["—", "—"])
    else:
        for model, n in sorted(data.eero_models.items(), key=lambda x: -x[1]):
            rows.append([model, str(n)])
    t = Table(rows, colWidths=[3.5 * inch, 1.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, LINE_COLOR),
                ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE_COLOR),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _devices_table(data: ReportData) -> Table:
    rows: list[list[str]] = [["Location", "Model", "Connected", "Status"]]
    if not data.devices:
        rows.append(["—", "—", "—", "—"])
    else:
        for d in data.devices:
            rows.append([d.location, d.model, str(d.connected_count), d.status.upper()])
    t = Table(rows, colWidths=[2.0 * inch, 1.8 * inch, 1.0 * inch, 1.0 * inch])
    style = TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, LINE_COLOR),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE_COLOR),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]
    )
    # Color the status cells.
    for i, d in enumerate(data.devices, start=1):
        style.add(
            "TEXTCOLOR",
            (3, i),
            (3, i),
            OK_COLOR if d.status == "online" else BAD_COLOR,
        )
    t.setStyle(style)
    return t


def _render_chart_image(chart: SsidChart, *, width_inches: float = 6.5, height_inches: float = 3.0) -> bytes:
    """Render one stacked-bar chart as PNG bytes.

    Last 24 sample points (SPEC §5.7), one stack per network. Network color
    consistency comes from the caller-provided `chart.colors` mapping.
    """
    fig, ax = plt.subplots(figsize=(width_inches, height_inches), dpi=150)

    if not chart.timestamps or not chart.series:
        ax.text(0.5, 0.5, "No samples in window", ha="center", va="center",
                transform=ax.transAxes, color="#888", fontsize=11)
        ax.set_axis_off()
    else:
        # Last 24 sample points
        ts = chart.timestamps[-24:]
        x = list(range(len(ts)))
        bottoms = [0] * len(ts)
        for name, values in chart.series.items():
            v = values[-len(ts):]
            ax.bar(x, v, bottom=bottoms, label=name, color=chart.colors.get(name, "#888"), width=0.8)
            bottoms = [b + (vv or 0) for b, vv in zip(bottoms, v, strict=True)]

        # X-axis: pick ~6 evenly-spaced timestamps as labels (HH:MM HST format)
        if len(ts) >= 6:
            tick_idx = [int(i * (len(ts) - 1) / 5) for i in range(6)]
        else:
            tick_idx = list(range(len(ts)))
        ax.set_xticks(tick_idx)
        ax.set_xticklabels([ts[i].strftime("%H:%M") for i in tick_idx], fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel("Devices", fontsize=9)
        ax.set_title(f"SSID: {chart.ssid}", fontsize=11, loc="left")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle=":", color="#dddddd", linewidth=0.6)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _legend_table(chart: SsidChart) -> Table:
    rows: list[list[str]] = [["Network", "Color"]]
    for name in chart.series:
        rows.append([name, chart.colors.get(name, "—")])
    t = Table(rows, colWidths=[3.5 * inch, 1.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE_COLOR),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    # Color-swatch the second column
    for i, (name, _) in enumerate(chart.series.items(), start=1):
        c = chart.colors.get(name, "#888888")
        t.setStyle(
            TableStyle([("BACKGROUND", (1, i), (1, i), colors.HexColor(c))])
        )
    return t


def assign_chart_colors(network_names: list[str]) -> dict[str, str]:
    """Stable color assignment from the report palette."""
    return {name: _NETWORK_PALETTE[i % len(_NETWORK_PALETTE)] for i, name in enumerate(network_names)}


def build_pdf(data: ReportData) -> bytes:
    """Render the report to PDF bytes. Sync — call via `run_in_executor`."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=f"{data.property_name} — WiFi Network Report",
    )
    styles = _styles()
    story: list = []

    # Title page
    story.append(Paragraph(data.property_name, styles["title"]))
    story.append(Paragraph("WiFi Network Report", styles["h1"]))
    story.append(
        Paragraph(
            f"Generated {data.generated_at_hst.strftime('%A, %B %-d, %Y · %H:%M HST')}",
            styles["subtle"],
        )
    )
    story.append(Spacer(1, 0.4 * inch))

    # Device Inventory
    story.append(Paragraph("Device Inventory", styles["h1"]))
    story.append(_stat_table(data))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Models", styles["h2"]))
    story.append(_models_table(data))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Device Details", styles["h2"]))
    story.append(_devices_table(data))

    # Per-SSID charts (page break before, one chart per SSID)
    if data.ssid_charts:
        story.append(PageBreak())
        story.append(Paragraph("Connected Devices by SSID", styles["h1"]))
        story.append(
            Paragraph(
                "Last 24 sample points. One stack per common-area network.",
                styles["subtle"],
            )
        )
        story.append(Spacer(1, 0.15 * inch))

        for chart in data.ssid_charts:
            png = _render_chart_image(chart)
            story.append(Image(io.BytesIO(png), width=6.5 * inch, height=3.0 * inch))
            story.append(Spacer(1, 0.05 * inch))
            story.append(_legend_table(chart))
            story.append(Spacer(1, 0.3 * inch))

    doc.build(story)
    return buf.getvalue()
