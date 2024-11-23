from setuptools import find_packages, setup

setup(
    name='homm3data',
    packages=find_packages(include=['homm3data']),
    version='0.1.4',
    description='Decoding of Heroes Might of Magic III files',
    author='Laserlicht',
    license = "MIT",
    keywords = "homm3 heroes iii might magic def lod pak",
    url = "https://github.com/Laserlicht/homm3data",
    install_requires=['pillow>=10.3.0', 'numpy>=1.26.4'],
    setup_requires=['pytest-runner', "twine==5.1.1"],
    tests_require=['pytest==8.3.3'],
    test_suite='tests',
)