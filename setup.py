#!/usr/bin/env python3
"""Setup script for TikTok Uploader."""

from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
def read_requirements(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="tiktok-uploader",
    version="2.0.0",
    author="TikTok Uploader Team",
    description="Автоматический загрузчик видео на TikTok с использованием Selenium",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
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
    ],
    python_requires=">=3.8",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements_dev.txt"),
    },
    entry_points={
        "console_scripts": [
            "tiktok-uploader=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.yaml", "*.yml", "*.json"],
    },
)