from setuptools import setup

setup(
    name='tft-version-control',
    version='0.1',
    py_modules=['libtft'],
    entry_points={
        'console_scripts': [
            'tft = libtft:main',
        ],
    },
)
