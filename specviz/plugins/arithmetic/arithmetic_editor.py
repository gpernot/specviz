import astropy.units as u
import ast
import math
import numpy as np
import os
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QMainWindow,QInputDialog,QApplication, QDialog,
                            QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem,
                            QMessageBox)
import specutils
from specutils import Spectrum1D
import sys
import uuid

from ...core.items import DataItem
from ...core.plugin import plugin
from ...utils import UI_PATH

@plugin('Arithmetic')
class EquationEditor(QDialog):
    def __init__(self, *args, **kwargs):
        """Equation editor main dialog. From this view you can add, edit, and remove
        arithmetic attributes."""

        super().__init__(parent=None)
        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         ".", "arithmetic_editor.ui")), self)
        
        self.button_add_derived.clicked.connect(self.showDialog)
        self.button_edit_derived.clicked.connect(self.edit_expression)
        self.button_remove_derived.clicked.connect(self.remove_expression)
        
        self.is_editmode=False

        self.setModal(True)
        
    @plugin.tool_bar(name="Arithmetic", icon=QIcon(":/icons/014-calculator.svg"))
    def on_action_triggerd(self):
        """Trigger the arithmetic UI when button is clicked.
        """
        self.model_items = self.hub.data_items
        self.show()

    def set_equation(self, eq_name=None, eq_expression=None):
        """Place equation in main dialog.

        Parameters
        ----------
        eq_name: str
            Name of the expression
        eq_expression: str
            Text of raw expression
        """
       
        # If there is a current item selected in the tree,
        # then see if the name of equation being passed from the
        # editor matches the new of the selected item and edit.
        current_item = self.list_derived_components.currentItem()
        if current_item and eq_name == current_item.text(0):
            current_item.setText(1, eq_expression)
        else:
            new_row = QTreeWidgetItem()
            new_row.setText(0, eq_name)
            new_row.setText(1, eq_expression)

            self.list_derived_components.addTopLevelItem(new_row)
    
    def edit_expression(self):
        """Edit selected expression in main dialog
        """
        
        if not self.list_derived_components.currentItem():
            QMessageBox.warning(self, "No Spectrum1D Objects", 
                                "There is no specified expression to edit!")
        else:
            current_item = self.list_derived_components.currentItem()
            label = current_item.text(0)
            equation = current_item.text(1)

            self.remove_arithmetic(current_item)

            self.editor = Editor(self, label=label, equation=equation, parent=self)

    def remove_expression(self):
        """Remove selected expression in main diaglog
        """
        if not self.list_derived_components.currentItem():
            QMessageBox.warning(self, "No Spectrum1D Objects", 
                                "There is no specified expression to remove!")
        else:
            # Get current selected item and it's index in the QTreeWidget.
            current_item = self.list_derived_components.currentItem()
            index = self.list_derived_components.indexOfTopLevelItem(current_item)
            
            self.list_derived_components.takeTopLevelItem(index)

    def showDialog(self):  
        """Show arithmetic editor
        """ 
        self.editor = Editor(self, parent=self)     

    def find_matches(self, eq_name):
        """Checks for matching names
        """
        matches = self.list_derived_components.findItems(eq_name, Qt.MatchExactly, 0)
        matches = [item.text(0) for item in matches]
        return matches
    
    def remove_arithmetic(self, current_item):
        """Remove arithmetic line
        """
        # Get the name of the arithmetic.
        data_name = current_item.text(0)
        
        # Get the names from the data items.
        data = self.hub.workspace.model.items
        model_names = [item.name for item in data]

        # Remove data by matching location in data items by name.
        # Hacky... if a user changes the name via the data collection list,  
        # then I don't think this will work.
        self.hub.workspace.model.remove_data(identifier=data[model_names.index(data_name)].identifier)

class Editor(QDialog):
    tip_text = ("<b>Note:</b> Attribute names in the expression should be surrounded "
                "by {{ }} brackets (e.g. {{{example}}}), and you can use "
                "Numpy functions using np.&lt;function&gt;, as well as any "
                "other function defined in your config.py file.<br><br>"
                "<b>Example expressions:</b><br><br>"
                "  - Subtract 10 from '{example}': {{{example}}} - 10<br>"
                "  - Scale '{example}' to [0:1]: ({{{example}}} - np.min({{{example}}})) / np.ptp({{{example}}})<br>"
                "  - Multiply '{example}' by pi: {{{example}}} * np.pi<br>"
                "  - Use masking: {{{example}}} * ({{{example}}} &lt; 1)<br>")

    placeholder_text = ("Type any mathematical expression here - "
                        "you can include attribute names from the "
                        "drop-down below by selecting them and "
                        "clicking 'Insert'.")
    
    def __init__(self, equation_editor, label=None, equation=None, parent=None):
        """Dialog where you specify equation names and expressions.
        """
        
        super(Editor, self).__init__(parent)
        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         ".", "equation_editor.ui")), self)
    
        self._equation_editor = equation_editor
        
        if not self._equation_editor.model_items:
            self.msgbox = QMessageBox.warning(self._equation_editor, "No Spectrum1D Objects", 
                                "There is no data loaded into your SpecViz session!")
        else:
            self.is_addmode = label is None

            if label is not None:
                self.text_label.setText(label)
                self.text_label.setDisabled(True)
            else:
                self.text_label.setPlaceholderText("New attribute name")
            if equation is not None:
                self.expression.insertPlainText(equation)
            else:
                self.expression.setPlaceholderText(self.placeholder_text)

            # Set options for spec1d objects to select.        
            self.combosel_data.addItems([item.name for item in self._equation_editor.model_items])
            # Set options for spec1d attributes.
            self.combosel_component.addItems(['wavelength', 'velocity',
                                              'frequency', 'flux'])

            self.button_insert.clicked.connect(self._insert_component)
            
            self.button_ok.clicked.connect(self._assign_components)
            self.button_cancel.clicked.connect(self._close_dialog)

            self.text_label.textChanged.connect(self._update_status)
            self.expression.textChanged.connect(self._update_status)
            self._update_status()

            self.setModal(True)
            self.show()

    def _get_eq_name(self):
        return self.text_label.text().strip()

    def _get_raw_command(self):
        return self.expression.toPlainText().strip() 

    def _insert_component(self):
        label = self.combosel_data.currentText()
        self.expression.insertPlainText('{' + label + '}' + '.' + self.combosel_component.currentText())
    
    def _assign_components(self):
        # Assign values for name and expression in TreeWidget
        self.eq_name = self._get_eq_name()
        self.eq_expression = self._get_raw_command()
        
        # Set up equation in QTreeWidget object.
        self._equation_editor.set_equation(self.eq_name, self.eq_expression)
            
        # Create data item from Spectrum1D object.
        data = DataItem("New Data", data=self.evaluated_arith, identifier=uuid.uuid4())

        # Add data to data collection.
        self._equation_editor.hub.workspace.model.add_data(spec=data, name=self.eq_name)
        
        self._close_dialog()
    
    def _close_dialog(self):
        self.close()

    def _item_from_name(self, name):
        return next((x.spectrum for x in self._equation_editor.model_items if x.name == name))
    
    def _update_status(self):
        # If the text hasn't changed, no need to check again
        if hasattr(self, '_cache') and self._cache == (self.text_label.text(), self._get_raw_command()):
            return

        if self.text_label.text() == "":
            self.label_status.setStyleSheet('color: red')
            self.label_status.setText("Component name not set")
            self.button_ok.setEnabled(False)
        
        elif (self.is_addmode and
              self.text_label.text() in self._equation_editor.find_matches(self.text_label.text())
        ):
            self.label_status.setStyleSheet('color: red')
            self.label_status.setText("Component name already exists.")
            self.button_ok.setEnabled(False)

        elif self._get_raw_command() == "":
            self.label_status.setText("")
            self.button_ok.setEnabled(False)
        
        else:
            try:
                dict_map = {x.name: "self._item_from_name('{}')".format(x.name) for x in self._equation_editor.model_items}
                raw_str = self._get_raw_command()
                self.evaluated_arith = eval(raw_str.format(**dict_map))
                if not isinstance(self.evaluated_arith, specutils.spectra.spectrum1d.Spectrum1D):
                    raise ValueError("Arithmetic Editor must return Spectrum1D object not {}".format(type(self.evaluated_arith)))
            except SyntaxError:
                self.label_status.setStyleSheet('color: red')
                self.label_status.setText("Incomplete or invalid syntax")
                self.button_ok.setEnabled(False)
            except Exception as exc:
                self.label_status.setStyleSheet('color: red')
                self.label_status.setText(str(exc))
                self.button_ok.setEnabled(False)
            else:
                self.label_status.setStyleSheet('color: green')
                self.label_status.setText("Valid expression")
                self.button_ok.setEnabled(True)
        
        self._cache = self.text_label.text(), self._get_raw_command()