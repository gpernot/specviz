from ..widgets.plots.base_plot import BasePlot

from qtpy.QtWidgets import *

import pyqtgraph as pg


class PlotSubWindow(QMainWindow):
    inactive_color = pg.mkPen(color=(0, 0, 0, 75))
    active_color = pg.mkPen(color=(0, 0, 0, 255))

    def __init__(self, **kwargs):
        super(PlotSubWindow, self).__init__(**kwargs)
        # Public
        self._plot_widget = None
        self._plot_item = None

        # Private
        self._containers = []
        self._tool_bar = None

    @property
    def tool_bar(self):
        if self._tool_bar is None:
            self._tool_bar = self.findChild(QToolBar)

        return self._tool_bar

    def get_roi_mask(self, layer=None, container=None):
        return self._plot_widget.get_roi_mask(
                container if container is not None else self.get_container(
                        layer))

    def action(self, name):
        # TODO: Revisit this sometime in the future.
        for act in self.findChildren(QAction):
            if act.objectName() == name:
                return act

    def initialize(self):
        self._plot_widget = BasePlot(parent=self)
        self._plot_item = self._plot_widget._plot_item
        self.setCentralWidget(self._plot_widget)

    def add_container(self, container):
        self._containers.append(container)

        self._plot_item.addItem(container.plot)
        self.set_labels()

    def get_container(self, layer):
        for container in self._containers:
            if container.layer == layer:
                return container

    def change_unit(self, new_unit):
        for plot_container in self._containers:
            plot_container.change_unit(new_unit)

    def set_labels(self):
        self._plot_item.setLabels(bottom=str(self._containers[0].units[0]))

    def set_active_plot(self, layer):
        for container in self._containers:
            if container.layer == layer:
                container.set_pen(self.active_color)
            else:
                container.set_pen(self.inactive_color)
