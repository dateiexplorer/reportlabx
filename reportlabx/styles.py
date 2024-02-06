from reportlab.lib import pagesizes
from reportlab.lib.styles import StyleSheet1
from reportlab.lib.units import cm


class StyleSheet(StyleSheet1):
    """A StyleSheet for styling the reports.

    Use this StyleSheet to apply a general style for all reports.
    """

    def __init__(self):
        super().__init__()

        self.pagesize = pagesizes.A4
        self.page_margin = (3.0 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm)
        self.page_padding = (6, 6, 6, 6)
