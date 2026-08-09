"""
Entry point for the SimBank ATM Simulator (SIMULATION / TEST ONLY).
Run with:  python -m atm_simulator.main
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from atm_simulator.app import ATMWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SimBank ATM Simulator")
    window = ATMWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
