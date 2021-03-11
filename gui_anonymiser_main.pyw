r"""GUI allowing to anonymise .eeg files from Deltamed (coh3).

Compile the GUI:

pyinstaller.exe -F --clean  --add-data './data/;data'
-n Flash-Test-utils-GUI --windowed
--icon=data/logo.ico .\gui_main.pyw
"""
import ctypes
import json
import multiprocessing as mp
import os
import re
import shutil
import sys
import time

from functools import reduce

# pylint: disable=E0611
from PyQt5.QtCore import (
    pyqtSlot,
    Qt,
    QObject,
    pyqtSignal,
    QThreadPool,
    QRunnable,
)
from PyQt5.QtGui import (
    QStandardItemModel,
    QIcon,
    QStandardItem,
)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QFileDialog,
    QAbstractItemView
)

# Import Ui_MainWindow class from UiMainApp.py generated by uic module
from anonymiser_gui import Ui_MainWindow

# Worker class for the QThread handler
# https://stackoverflow.com/questions/50855210/how-to-pass-parameters-into-qrunnable-for-pyqt5

SCRIPT_PATH = os.path.dirname(__file__)
PREFERENCES_PATH = './data/preferences.config'
PREFERENCES_PATH = os.path.join(SCRIPT_PATH, PREFERENCES_PATH)

class Worker(QRunnable):  # pylint: disable=too-few-public-methods
    """Worker class to run a function in a QThread."""

    def __init__(self, function, *args, **kwargs):
        super().__init__()
        # Store constructor arguments (re-used for processing)
        self.function = function
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        """Run the function in the worker."""
        self.function(*self.args, **self.kwargs)


# class FileDialog(QFileDialog):
#     def __init__(self, *args, **kwargs):
#         super(FileDialog, self).__init__(*args, **kwargs)
#         self.setOption(QFileDialog.DontUseNativeDialog, True)
#         self.setFileMode(QFileDialog.ExistingFiles)

#     def accept(self):
#         super(FileDialog, self).accept()


def resource_path(relative_path: str):
    """Get absolute path to resource, works for dev and for PyInstaller.

    Args:
        relative_path: the path to resolve.

    Returns:
        The absolute path to the ressource.
    """
    base_path = getattr(
        sys,
        '_MEIPASS',
        os.path.dirname(os.path.abspath(__file__)),
    )

    return os.path.join(base_path, relative_path)


def split_keep_sep(string, separator):
    """Split a string according to a separator.

    Args:
        string: the string to split.
        separator: the separator to use and to keep.

    Returns:
        A list with the splited elements.
    """
    return reduce(
        lambda acc, elem: acc[:-1] + [acc[-1] + elem] if elem == separator
        else acc + [elem], re.split('(%s)' % re.escape(separator), string), [])


def list_files(path: str):
    """List all the files in a folder and subfolders.

    Args:
        path: the path to use as parent directory.
    Returns:
        A list of files.
    """
    files_list = set()

    for folder, _, files in os.walk(path):
        for file_ in files:
            files_list.add(os.path.join(folder, file_))

    return list(files_list)


def ensure_path(path: str):
    if not os.path.isdir(path):
        os.makedirs(path)


def extract_header(filename: str):
    header = []

    with open(filename, 'rb') as f:
        for line in f:
            header.extend(line)
            if len(header) > 719:
                header = [
                    char if isinstance(char, bytes) else bytes([char])
                    for char in header
                ]

                return header


def change_field(
    array, start: int, stop: int, content: list, filler: bytes = b'\x00'
):
    for index in range(start, stop):
        if index - start < len(content):
            array[index] = content[index - start]
        else:
            array[index] = filler

    return stop - start >= len(content)


def anonymise_eeg(
    original_file: str,
    destination_file: str,
    field_name: str = '',
    field_surname: str = '',
    field_birthdate: str = '',
    field_sex: str = '',
    field_folder: str = '',
    field_centre: str = '',
    field_comment: str = ''
):
    """Anonymaze an .eeg file.

    Args:
        orginale_file: path to the original file.
        destination_file: path to affect the anonymisation.
        field_name: patient name.
        field_surname: patient surname.
        field_birthdate: birthdate.
        field_sex: sex.
        field_folder: folder name.
        field_centre: centre name.
        field_comment: comment.
    """
    # Copy the original content
    content = extract_header(original_file)

    # Anonymise
    if field_name is None:
        pass
    else:
        change_field(content, 314, 364, field_name.encode('ascii'))

    if field_surname is None:
        pass
    else:
        change_field(content, 364, 394, field_surname.encode('ascii'))

    if field_birthdate is None:
        pass
    else:
        change_field(content, 394, 404, field_birthdate.encode('ascii'))

    if field_sex is None:
        pass
    else:
        change_field(content, 404, 405, field_sex.encode('ascii'))

    if field_folder is None:
        pass
    else:
        change_field(content, 405, 425, field_folder.encode('ascii'))

    if field_centre is None:
        pass
    else:
        change_field(content, 425, 464, field_centre.encode('ascii'))

    if field_comment is None:
        pass
    else:
        change_field(content, 464, 719, field_comment.encode('ascii'))

    ensure_path(path=os.path.dirname(destination_file))

    content = (
        char if isinstance(char, bytes) else bytes([char]) for char in content
    )

    if not os.path.isfile(destination_file):
        shutil.copyfile(original_file, destination_file + '.part')
        os.rename(destination_file + '.part', destination_file)

    with open(destination_file, 'rb+') as f:
        f.seek(0)

        for char in content:
            f.write(char if isinstance(char, bytes) else bytes([char]))

    return True


class MainApp(QMainWindow, Ui_MainWindow):
    """
    MainApp class inherit from QMainWindow and from
    Ui_MainWindow class in UiMainApp module.
    """
    progress_changed = pyqtSignal(int)
    progress_text_changed = pyqtSignal(str)
    stateChanged = pyqtSignal(bool)
    okChanged = pyqtSignal(bool)

    def __init__(self):
        """Constructor or the initialiser."""
        QMainWindow.__init__(self)
        # It is imperative to call self.setupUi (self) to initialise the GUI
        # This is defined in gui_autogenerated_template.py file automatically
        self.setupUi(self)
        self.base_title = 'EEG (coh3) anonymiser'
        self.setWindowTitle(self.base_title)
        # Maximize the window
        # self.showMaximized()

        # Desactivate the buttons
        self.OK.setEnabled(False)
        self.Cancel.setEnabled(False)
        self.stateChanged.connect(self.set_application_busy)
        self.cancel_process = mp.Queue(1)
        self.okChanged.connect(self.OK.setEnabled)

        # Set editable line to read only.
        # self.source.setReadOnly(True)
        self.destination.setReadOnly(True)

        # Set progress bar
        self.progress_bar.setValue(0)
        self.progress_changed.connect(self.progress_bar.setValue)
        self.progress_bar.setFormat('IDLE')
        self.progress_bar.setAlignment(Qt.AlignCenter) 
        self.progress_text_changed.connect(self.progress_bar.setFormat)

        # Set the slots
        self.path = ''
        self.load_perferences()
        if not os.path.isdir(self.path):
            self.path = ''
        self.save_preferences(path=self.path)

        self.OK.clicked.connect(self.anonymise)
        self.Cancel.clicked.connect(self.cancel)
        self.actionAbout.triggered.connect(self.show_about)
        self.actionOnline_documentation.triggered.connect(
            self.open_documentation
        )
        self.actionSelect_file_s.triggered.connect(self.select_files_browser)
        self.actionSelect_folder.triggered.connect(self.select_folder_browser)
        self.tool_source.clicked.connect(self.select_files_browser)
        self.tool_destination.clicked.connect(
            self.select_destination_folder_browser
        )
        self.name_check.stateChanged.connect(self.save_preferences)
        self.surname_check.stateChanged.connect(self.save_preferences)
        self.birthdate_check.stateChanged.connect(self.save_preferences)
        self.sex_check.stateChanged.connect(self.save_preferences)
        self.folder_check.stateChanged.connect(self.save_preferences)
        self.centre_check.stateChanged.connect(self.save_preferences)
        self.comment_check.stateChanged.connect(self.save_preferences)
        self.folder_as_name_check.stateChanged.connect(self.save_preferences)

        # List View
        self.source_list_model = QStandardItemModel()
        self.source.setModel(self.source_list_model)
        self.source.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Create a QThread to avoid to hang the main process
        self.threadpool = QThreadPool()
        self.files = []

    def keyPressEvent(self, event):  # pylint: disable=C0103
        """Intercept the key events.

        Args:
            self: self.
            event: the intercepted event.
        """
        # Close the program
        if event.key() == Qt.Key_Escape:
            self.close()

        # Maximize the window
        if event.key() == Qt.Key_F11:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

    def set_application_busy(self, state=False):
        self.Cancel.setEnabled(state)
        self.OK.setEnabled(not state)
        self.fields.setEnabled(not state)
        self.Source_box.setEnabled(not state)
        self.Destination_box.setEnabled(not state)

    def anonymise(self):
        if self.destination.text() == os.path.dirname(self.files[0]):
            result = self.show_overwrite_warning()
            if result != QMessageBox.Yes:
                return

        worker = Worker(self._anonymise)
        self.threadpool.start(worker)

    def _anonymise(self):
        # Enable Cancel and disable the interfaces.
        self.stateChanged.emit(True)

        name_check = self.name_check.isChecked()
        surname_check = self.surname_check.isChecked()
        birthdate_check = self.birthdate_check.isChecked()
        sex_check = self.sex_check.isChecked()
        folder_check = self.folder_check.isChecked()
        centre_check = self.centre_check.isChecked()
        comment_check = self.comment_check.isChecked()
        folder_as_name_check = self.folder_as_name_check.isChecked()

        name = '' if name_check else None
        surname = '' if surname_check else None
        birthdate = '' if birthdate_check else None
        sex = '' if sex_check else None
        folder = '' if folder_check else None
        centre = '' if centre_check else None
        comment = '' if comment_check else None

        destination_path = self.destination.text()

        filelist = self.files
        n_files = len(filelist)

        # Process the files
        for file_index, file_ in enumerate(filelist, start=1):

            # Stop the operation if the cancel flag is set.
            if not self.cancel_process.empty():
                if self.cancel_process.get():
                    self.progress_changed.emit(0)
                    break

            file_destination = os.path.join(
                destination_path,
                os.path.relpath(
                    file_,
                    self.path,
                )
            )

            if folder_as_name_check and name_check:
                name = os.path.basename(os.path.dirname(file_destination))

            self.progress_text_changed.emit(
                '{0} ({1}/{2})'.format(file_, file_index, n_files)
            )

            anonymise_eeg(
                file_,
                file_destination,
                field_name=name,
                field_surname=surname,
                field_birthdate=birthdate,
                field_sex=sex,
                field_folder=folder,
                field_centre=centre,
                field_comment=comment,
            )

            self.progress_changed.emit(int(file_index * 100 / n_files))

        # Disable Cancel and enable the interfaces.
        self.stateChanged.emit(False)
        self.progress_text_changed.emit('IDLE')
        # self.okChanged.emit(False)

    def cancel(self):
        # Set cancel flag
        if self.cancel_process.empty():
            self.cancel_process.put(True)

    def open_documentation(self):
        """Open program documentation."""
        from PyQt5.Qt import QUrl, QDesktopServices
        url = QUrl(
            'https://github.com/2010019970909/'
            'deltamed_coherence_openutils/wiki/Anonymiser-GUI'
        )
        QDesktopServices.openUrl(url)

    def show_about(self):
        """Show the about me."""
        msg = QMessageBox()
        msg.setWindowTitle('About')
        msg.setText(
            'This program has been programmed by Vincent Stragier.\n\n'
            'It has been created to anonymise .eeg (coh3) '
            'files from Deltamed (a Natus company).\n\n'
            'The program is under a GNU GPL and its '
            'source code is in part under a '
            'Creative Commons licence.'
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def show_overwrite_warning(self):
        """Show the overwrite warning."""
        msg = QMessageBox()
        msg.setWindowTitle('Overwriting Warning')
        msg.setIcon(QMessageBox.Warning)
        msg.setText(
            'The source path and the destination path are the same. '
            'You are going to overwrite the file(s).\n\n'
            'Do you want to continue and process the file(s) inplace?'
        )
        msg.setStandardButtons(QMessageBox.Yes|QMessageBox.Cancel)
        return msg.exec_()

    def select_files_browser(self):
        """Show the files browser."""
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setDirectory(self.path)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        # Filetype:
        # http://justsolve.archiveteam.org/wiki/NII
        # https://stackoverflow.com/a/27994762
        filters = ["Deltamed EEG files (*.eeg)", "All Files (*)"]
        dialog.setNameFilters(filters)
        dialog.selectNameFilter(filters[0])
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        dialog.setViewMode(QFileDialog.Detail)

        if dialog.exec_() == QFileDialog.Accepted:
            self.files = dialog.selectedFiles()
            filenames = sorted([
                '{0}'.format(os.path.basename(file_)) for file_ in self.files
            ])

            self.source_list_model.clear()
            for filename in filenames:
                item = QStandardItem()
                item.setText(filename)
                item.setIcon(QIcon(resource_path('ico/file.svg')))
                self.source_list_model.appendRow(item)

            self.OK.setEnabled(True)
            self.path = os.path.dirname(self.files[0])
            self.save_preferences(self.path)
            self.progress_bar.setValue(0)
            if self.destination.text() == '':
                self.destination.setText(self.path)

    # def select_folder_browser(self):
    #     worker = Worker(self._select_folder_browser)
    #     self.threadpool.start(worker)

    def select_folder_browser(self):
        """Show the files browser."""
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setDirectory(self.path)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setViewMode(QFileDialog.Detail)

        if dialog.exec_() == QFileDialog.Accepted:
            folder = dialog.selectedFiles()[0]

            self.source_list_model.clear()
            item = QStandardItem()
            item.setText(folder)
            item.setIcon(QIcon(resource_path('ico/folder.svg')))
            self.source_list_model.appendRow(item)

            self.path = folder
            self.save_preferences(self.path)
            self.progress_bar.setValue(0)
            if self.destination.text() == '':
                self.destination.setText(self.path)

            self.files = sorted([
                eeg for eeg in list_files(folder)
                if eeg.lower().endswith('.eeg')
            ], key=lambda x: os.path.basename(x))

            self.OK.setEnabled(True)
            

    def select_destination_folder_browser(self):
        """Show the files browser to select the destination."""
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setDirectory(self.path)
        dialog.setFileMode(QFileDialog.Directory)

        if dialog.exec_() == QFileDialog.Accepted:
            folder = dialog.selectedFiles()[0]

        self.destination.setText(folder)

    def load_perferences(self):
        try:
            preferences = json.load(open(resource_path(PREFERENCES_PATH)))

            self.name_check.setChecked(preferences['name_check'])
            self.surname_check.setChecked(preferences['surname_check'])
            self.birthdate_check.setChecked(preferences['birthdate_check'])
            self.sex_check.setChecked(preferences['sex_check'])
            self.folder_check.setChecked(preferences['folder_check'])
            self.centre_check.setChecked(preferences['centre_check'])
            self.comment_check.setChecked(preferences['comment_check'])
            self.folder_as_name_check.setChecked(
                preferences['folder_as_name_check']
            )
            self.path = preferences['path']

        except (
            FileNotFoundError,
            json.decoder.JSONDecodeError,
        ):
            self.save_preferences(
                path=os.path.join(os.path.dirname(sys.argv[0])),
            )

    def save_preferences(self, path: str = None):
        preferences = {
            'name_check': self.name_check.isChecked(),
            'surname_check': self.surname_check.isChecked(),
            'birthdate_check': self.birthdate_check.isChecked(),
            'sex_check': self.sex_check.isChecked(),
            'folder_check': self.folder_check.isChecked(),
            'centre_check': self.centre_check.isChecked(),
            'comment_check': self.comment_check.isChecked(),
            'folder_as_name_check': self.folder_as_name_check.isChecked(),
        }

        if isinstance(path, str) and os.path.isdir(path):
            preferences['path'] = path
        else:
            preferences['path'] = self.path

        if self.name_check.isChecked():
            self.folder_as_name_check.setEnabled(True)
        else:
            self.folder_as_name_check.setEnabled(False)

        # ensure_path(resource_path(os.path.dirname(PREFERENCES_PATH)))
        # with open(resource_path(PREFERENCES_PATH), 'w') as outfile:
        #     json.dump(preferences, outfile)
        ensure_path(os.path.dirname(PREFERENCES_PATH))
        with open(PREFERENCES_PATH, 'w') as outfile:
            json.dump(preferences, outfile)


if __name__ == '__main__':
    # For Windows set AppID to add an Icon in the taskbar
    # https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
    if sys.platform == 'win32':
        from ctypes import wintypes

        APPID = u'vincent_stragier.cetic.v1.0.0'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APPID)

        lpBuffer = wintypes.LPWSTR()
        ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(
            ctypes.cast(ctypes.byref(lpBuffer), wintypes.LPWSTR))
        # appid = lpBuffer.value
        ctypes.windll.kernel32.LocalFree(lpBuffer)

    app = QApplication(sys.argv)
    # Launch the main app.
    MyApplication = MainApp()
    MyApplication.show()  # Show the form
    # os.path.join(os.path.dirname(sys.argv[0]),'..', 'ico', 'fpms.svg')
    icon_path = resource_path('ico/fpms_anonymous.ico')
    app.setWindowIcon(QIcon(icon_path))
    MyApplication.setWindowIcon(QIcon(icon_path))
    sys.exit(app.exec_())  # Execute the app
