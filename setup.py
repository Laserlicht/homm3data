from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name='homm3data',
    packages=find_packages(include=['homm3data']),
    version='0.1.10',
    description='Decoding of Heroes Might of Magic III files',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Laserlicht',
    license = "MIT",
    keywords = "homm3 heroes iii might magic def lod pak",
    url = "https://github.com/Laserlicht/homm3data",
    install_requires=['pillow>=10.3.0', 'numpy>=1.26.4'],
    setup_requires=['pytest-runner', "twine==5.1.1"],
    tests_require=['pytest==8.3.3'],
    test_suite='tests',
)