import io
from typing import Any

from matplotlib.figure import Figure
from reportlab.graphics.shapes import Drawing
from svglib.svglib import svg2rlg


def fig2rlg(fig: Figure, **kwargs: dict[str, Any]) -> Drawing:
    """Converts a matplotlib Figure into a reportlab Drawing."""

    imgdata = io.BytesIO()
    fig.savefig(
        imgdata,
        format="svg",
        bbox_inches="tight",
    )

    imgdata.seek(0)
    drawing = svg2rlg(imgdata)
    drawing.setProperties(kwargs)
    return drawing
