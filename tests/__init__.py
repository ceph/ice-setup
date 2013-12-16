import os
import imp
try:
    import setup
except ImportError:
    absolute_dir = os.path.dirname(os.path.abspath(__file__))
    setup_dir_path = os.path.dirname(absolute_dir)
    setup_path = os.path.join(setup_dir_path, 'setup')

    setup = imp.load_source('setup', setup_path)
