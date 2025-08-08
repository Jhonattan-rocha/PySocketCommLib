from setuptools import setup, find_packages
import os

# Read README file for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="PySocketCommLib",
    version="0.2.0",
    author="Jhonattan Rocha",
    author_email="jhonattan246rocha@gmail.com",
    description="A comprehensive Python library for low-level socket communication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Jhonattan-rocha/PySocketCommLib",
    project_urls={
        "Bug Tracker": "https://github.com/Jhonattan-rocha/PySocketCommLib/issues",
        "Documentation": "https://github.com/Jhonattan-rocha/PySocketCommLib/wiki",
        "Source Code": "https://github.com/Jhonattan-rocha/PySocketCommLib",
    },
    packages=find_packages(exclude=["tests*", "examples*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
        "Topic :: Database",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pysocketcomm=PySocketCommLib.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="socket, websocket, http, server, client, orm, database, async, threading",
)
