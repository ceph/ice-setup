from setuptools import setup, find_packages
from ice_setup.ice import __version__

setup(
    name='ice_setup',
    author='Red Hat, Inc.',
    license='MIT',
    version=__version__,
    packages=find_packages(),
    zip_safe=False,
)
