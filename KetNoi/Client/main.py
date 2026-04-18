import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from mvc.controller.client_controller import ClientController
from mvc.view.client_view_pyqt import ClientView

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("QuanNet")
    app.setApplicationName("ClientMangNet")
    view = ClientView(None)
    controller = ClientController(view)
    view.controller = controller
    view._connect_signals()
    view.show()
    QTimer.singleShot(0, controller.try_startup_autoconnect)
    sys.exit(app.exec())