"""
Entry point for the SimBank Debit Card Generator (SIMULATION / TEST ONLY).
Run with:  python -m card_generator.main
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from card_generator.app import CardGeneratorWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SimBank Card Generator")
    window = CardGeneratorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
