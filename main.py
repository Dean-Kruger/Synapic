import sys
import os

# Ensure src is in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src.ui.app import App

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
