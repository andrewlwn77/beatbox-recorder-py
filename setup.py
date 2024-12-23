from setuptools import setup, find_packages

setup(
    name="beatbox-recorder",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[],
    python_requires=">=3.7",
)