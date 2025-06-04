import pyvista as pv
import traceback

print(f"PyVista version: {pv.__version__}")

try:
    print("\nTesting basic PyVista Plotter...")
    # Test with a basic Plotter first, not BackgroundPlotter
    plotter = pv.Plotter(notebook=False, off_screen=True) # Ensure off_screen for non-interactive test
    print("pv.Plotter initialized successfully.")
    sphere = pv.Sphere()
    plotter.add_mesh(sphere)
    print("Sphere added to pv.Plotter.")
    # plotter.screenshot('test_pv_basic.png') # Optional: save a screenshot
    # print("Screenshot from pv.Plotter saved as test_pv_basic.png")
    plotter.close()
    print("pv.Plotter closed.")
except Exception as e:
    print(f"ERROR during basic PyVista Plotter test: {e}")
    traceback.print_exc()

try:
    print("\nTesting PyVistaQt BackgroundPlotter...")
    from pyvistaqt import BackgroundPlotter
    # Attempt to get QApplication instance if available, otherwise None
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None: # pragma: no cover
            print("No QApplication instance found, attempting to create one for BackgroundPlotter test.")
            # For a minimal script, we might need to create one if BackgroundPlotter expects it
            # However, BackgroundPlotter(app=None) should also work.
            # app = QApplication([]) # Uncomment if BackgroundPlotter specifically needs an active app
            pass 
    except ImportError:
        app = None
        print("PySide6 not available for app instance in BackgroundPlotter test.")

    plotter_qt = BackgroundPlotter(show=False, app=app)
    print("pyvistaqt.BackgroundPlotter initialized successfully.")
    sphere_qt = pv.Sphere()
    plotter_qt.add_mesh(sphere_qt)
    print("Sphere added to BackgroundPlotter.")
    # plotter_qt.screenshot('test_pv_qt.png') # Optional
    # print("Screenshot from BackgroundPlotter saved as test_pv_qt.png")
    plotter_qt.close()
    print("BackgroundPlotter closed.")
except Exception as e:
    print(f"ERROR during PyVistaQt BackgroundPlotter test: {e}")
    traceback.print_exc()

print("\nMinimal test script finished.") 