from stem_separator.ui import MainWindow

def test_ui_module_exposes_main_window():
    assert MainWindow.__name__ == "MainWindow"
