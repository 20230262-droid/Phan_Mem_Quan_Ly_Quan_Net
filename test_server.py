import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from PyQt6.QtWidgets import QApplication
from mvc.view.server_view_pyqt import ServerView
from mvc.controller.server_controller import ServerController

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = ServerView(None)
    controller = ServerController(view)
    view.controller = controller
    view._connect_signals()
    view.show()
    print("Server GUI started successfully!")
    sys.exit(app.exec())