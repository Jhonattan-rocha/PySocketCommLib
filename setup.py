from setuptools import setup, find_packages

setup(
    name='PySocketCommLib',
    version='0.1',
    author="https://github.com/Jhonattan-rocha",
    author_email="jhonattan246rocha@gmail.com",
    package_dir="./",
    packages=find_packages(),
    install_requires=[
        "cryptography"
    ],
)
