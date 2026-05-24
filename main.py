"""
=============================================================================
CSE 430 - Compiler Design Lab Project
MAIN ENTRY POINT
=============================================================================
Run this file to launch the Mini Compiler GUI:
    python main.py
=============================================================================
"""

import os
os.environ['TK_SILENCE_DEPRECATION'] = '1'

import tkinter as tk
from gui import CompilerGUI

if __name__ == "__main__":
    window = tk.Tk()
    app    = CompilerGUI(window)
    window.mainloop()
