import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from ice_setup.ice import __version__

class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)

setup(
    name='ice_setup',
    author='Red Hat, Inc.',
    license='MIT',
    version=__version__,
    packages=find_packages(),
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'ice_setup = ice_setup.ice:main',
        ],
    },
    tests_require=['pytest'],
    cmdclass = {'test': PyTest},
)
