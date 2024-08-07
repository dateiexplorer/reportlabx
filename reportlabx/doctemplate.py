from reportlab.lib.sequencer import Sequencer, setSequencer
from reportlab.platypus import BaseDocTemplate, Flowable

from reportlabx.styles import StyleSheet


class BaseDocTemplate(BaseDocTemplate):
    """Base template for all reports with additional features."""

    def __init__(self, filename, **kw) -> None:
        super().__init__(filename, **kw)

        self.totalPages: int = None
        self.showBoundary = kw.get("showBoundary", False)

        self.style: StyleSheet = kw.get("style", StyleSheet())
        self.pagesize = self.style.pagesize

        # Margin
        self.topMargin = self.style.pageMargin[0]
        self.rightMargin = self.style.pageMargin[1]
        self.bottomMargin = self.style.pageMargin[2]
        self.leftMargin = self.style.pageMargin[3]

        # Padding
        self.topPadding = self.style.pagePadding[0]
        self.rightPadding = self.style.pagePadding[1]
        self.bottomPadding = self.style.pagePadding[2]
        self.leftPadding = self.style.pagePadding[3]

        self.frameWidth = self.width - self.leftPadding - self.rightPadding
        self.frameHeight = self.height - self.topPadding - self.bottomPadding

    # Override multiBuild method to make one additional pass to support
    # total pages.
    # This is a workaround, because either anchors or the canvasmaker
    # function can be used, but not both at the same time.
    # During the build process the toal page numbers of the PDF is not
    # known. So we need multiple builds to support this feature.
    #
    # Additionally, processing the multiBuild function multiple times can
    # cause a reportlab.platypus.doctemplate.LayoutError as mentioned
    # in this post: https://stackoverflow.com/a/3566689.
    # This is why we need to override this function.
    def multiBuild(
        self,
        story: list[Flowable],
        maxPasses: int = 10,
        **buildKwds,
    ) -> int:
        """Makes multiple passes until all indexing flowables are happy.
        After all cross-referencing is done, one additional pass is done to
        support the use of the total pages of the generated PDF file.

        Returns number of passes.
        """

        # Reset the sequencer for each build. This is necessary, because
        # reportlab uses a global sequencer (e.g., by using getSequencer) which
        # is not getting reset for new builds.
        setSequencer(Sequencer())

        self._indexingFlowables: list[Flowable] = []
        # Scan the story and keep a copy.
        for thing in story:
            if thing.isIndexing():
                self._indexingFlowables.append(thing)

        # Better fix for filename is a 'file' problem.
        self._doSave = 0
        passes = 0
        mbe = []
        self._multiBuildEdits = mbe.append
        while 1:
            passes += 1
            if self._onProgress:
                self._onProgress("PASS", passes)

            for fl in self._indexingFlowables:
                fl.beforeBuild()

            # Work with a copy of the story, since it is consumed.
            tempStory = story[:]
            self.build(tempStory, **buildKwds)

            for fl in self._indexingFlowables:
                fl.afterBuild()

            happy = self._allSatisfied()

            if happy and self.totalPages is not None:
                self._doSave = 0
                self.canv.save()
                break
            # If all cross-references are solved, do one additional run
            # setting the totalPages attribute.
            if happy:
                self.totalPages = self.page
            if passes > maxPasses:
                raise IndexError(
                    "Index entries not resolved after %d passes" % maxPasses
                )

            # Work through any edits.
            while mbe:
                e = mbe.pop(0)
                e[0](*e[1:])

        del self._multiBuildEdits
        return passes

    def afterFlowable(self, flowable: Flowable) -> None:
        """Overrides the afterFlowable method.

        This method is called after a Flowable was added to the document
        to do further modifications.
        """

        super().afterFlowable(flowable)

        # Check if the flowable object registers a handler function and execute
        # it.
        if hasattr(flowable, "handle_afterFlowable"):
            method = getattr(flowable, "handle_afterFlowable")
            if callable(method):
                method(self)
