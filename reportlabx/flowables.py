from hashlib import sha256

from reportlab.lib import colors
from reportlab.lib.sequencer import getSequencer
from reportlab.lib.styles import ListStyle, ParagraphStyle
from reportlab.platypus import *
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    HRFlowable,
    LIIndenter,
    Paragraph,
    Spacer,
)
from reportlab.platypus.flowables import _Container, _listWrapOn
from reportlab.platypus.tableofcontents import *


class GroupFlowable(_Container, Flowable):
    """A Flowable that groups multiple flowables togehter.

    This is based on the ListFlowable code, but without the ability to make
    bullet points or enumerations.
    """

    def __init__(
        self,
        flowables: list[Flowable],
        style: ListStyle = None,
        **kwds,
    ):
        self._flowables = flowables

        if style:
            if not isinstance(style, ListStyle):
                raise ValueError(
                    "%s style argument not a ListStyle" % self.__class__.__name__
                )
            self.style = style

        # Use the default ListStyle, but adjust the leftIndent to 0.
        for k, v in ListStyle.defaults.items():
            setattr(self, "_" + k, kwds.get(k, getattr(style, k, v)))
            self._leftIndent = 0

        for k in ("spaceBefore", "spaceAfter"):
            v = kwds.get(k, getattr(style, k, None))
            if v is not None:
                setattr(self, k, v)

        self._content = self._getContent()
        del self._flowables
        self._dims = None

    def wrap(self, availWidth, availHeight):
        if self._dims != availWidth:
            self.width, self.height = _listWrapOn(self._content, availWidth, self.canv)
            self._dims = availWidth
        return self.width, self.height

    def split(self, availWidth, availHeight):
        return self._content

    def _makeLIIndenter(
        self,
        flowable: Flowable,
        params: dict = None,
    ):
        if params:
            leftIndent = params.get("leftIndent", self._leftIndent)
            rightIndent = params.get("rightIndent", self._rightIndent)
            spaceBefore = params.get("spaceBefore", None)
            spaceAfter = params.get("spaceAfter", None)
            return LIIndenter(
                flowable,
                leftIndent,
                rightIndent,
                None,
                spaceBefore=spaceBefore,
                spaceAfter=spaceAfter,
            )
        else:
            return LIIndenter(flowable, self._leftIndent, self._rightIndent, None)

    def _getContent(self):
        story = []
        i = 0
        for f in self._flowables:
            fparams = {}
            if not i:
                i += 1
                spaceBefore = getattr(self, "spaceBefore", None)
                if spaceBefore is not None:
                    fparams["spaceBefore"] = spaceBefore

            story.append(self._makeLIIndenter(f, params=fparams))

        spaceAfter = getattr(self, "spaceAfter", None)
        if spaceAfter is not None:
            f = story[-1]
            f.__dict__["spaceAfter"] = max(f.__dict__.get("spaceAfter", 0), spaceAfter)
        return story


class Heading(Paragraph):
    """A Heading is a Paragraph that includes the handling of adding it to the
    TOC or Outline of a PDF file.

    Additionally it automatically provides numbering and nested numbering of
    the headings and takes care of the correct chaining.
    This means, if a new heading is created, it automatically resets the
    counter for all subheadings.

    To get this functionality work, the handle_afterFlowable method must be
    called from the DocTemplate's afterFlowable method for each instance.
    """

    def __init__(
        self,
        text: str,
        level: int,
        style: ParagraphStyle = None,
        numbered=True,
        add_to_toc=True,
        add_to_outline=True,
        **kwargs,
    ):
        self._level = level
        self._bookmark_name = None
        self._numbered = numbered
        self._add_to_toc = add_to_toc
        self._add_to_outline = add_to_outline

        # Create dynamic sequencer and chain it together, beginning with "h0"
        # for level=0. This ensures that the numbering is automatically reset
        # if the number of the header one level above increases.
        #
        # This generate a typical TOC numbering, like:
        #
        # 1 Section (level=0)
        # 1.1 Subsection (level=1)
        # 1.1.1 Subsubsection (level=2)
        # 1.1.2 Subsubsection (level=2)
        # 1.2 Subsection (level=1)
        # 2 Section (level=0)
        # 2.1 Subsection (level=1)
        # ...
        #
        sequencer = getSequencer()
        for i in range(0, level + 1):
            sequencer._getCounter(f"h{i}")
            if i > 0:
                sequencer.chain(f"h{i-1}", f"h{i}")

        if numbered:
            # Generate a template of the form '%(h1)s.%(h2+)s'.
            template = ".".join(
                [f"%(h{i}{'+' if i == level else ''})s" for i in range(0, level + 1)]
            )

            # Put the template and the actual text together
            text = f"<seq template='{template}'/> {text}"

        # Create bookmark name for this heading, based on the unique SHA256
        # hash algorithm.
        self._bookmark_name = sha256(str(text).encode()).hexdigest()

        # Add an anchor to the heading.
        text = f"<a name='{self._bookmark_name}'/>{text}"

        super().__init__(text, style, kwargs)

    # This code is based on https://www.reportlab.com/snippets/13/.
    #
    # Entries to the table of contents can be done either manually by
    # calling the addEntry method on the TableOfContents object or automatically
    # by sending a 'TOCEntry' notification in the afterFlowable method of
    # the DocTemplate. The data to be passed to notify is a list
    # of three or four items containing a level number, the entry text, the page
    # number and an optional destination key which the entry should point to.
    # This list will usually be created in a document template's method like
    # afterFlowable(), making notifiaction calls using the notify() method
    # with appropriate data.
    def handle_afterFlowable(self, doc: BaseDocTemplate):
        # Register TOC entries.
        text = self.getPlainText()

        if self._add_to_toc:
            entry = (self._level, text, doc.page, self._bookmark_name)
            doc.notify("TOCEntry", entry)

        if self._add_to_outline:
            key = sha256(str(self._bookmark_name + str(doc.page)).encode()).hexdigest()
            doc.canv.bookmarkPage(key)
            doc.canv.addOutlineEntry(text, key, self._level)


class Signature(GroupFlowable):
    """A simple Signature that provides a horizontal line and additional
    information.
    """

    def __init__(
        self,
        name: str,
        location: str,
        date: str,
        style: ParagraphStyle = None,
        qualification: str = None,
    ):
        story: list[Flowable] = []

        # Add a horizontal line with enough space before it.
        story.append(
            HRFlowable(
                width="40%",
                thickness=0.5,
                color=colors.black,
                hAlign="LEFT",
                spaceBefore=96,
                spaceAfter=8,
            )
        )

        story.append(Paragraph(name, style))

        if qualification:
            story.append(Paragraph(qualification, style))

        story.append(Spacer(0, 24))
        story.append(Paragraph(f"{location}, {date}", style))

        super().__init__(story)
