#!/usr/bin/env python3
# ==============================================================================
# setup.py   –  REX 4.0   Installation Script
# ==============================================================================

from pathlib import Path
from setuptools import setup, find_packages

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    requirements = [
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
else:
    requirements = []

setup(
    # ── Metadata ──────────────────────────────────────────────────────────
    name="rex-voice-assistant",
    version="4.0.0",
    description="Intelligent, offline-first, JARVIS-like voice assistant for Windows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="REX Development Team",
    author_email="dev@rex-assistant.local",
    url="https://github.com/yourusername/rex",
    license="Proprietary",
    
    # ── Package Discovery ─────────────────────────────────────────────────
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    include_package_data=True,
    
    # ── Dependencies ──────────────────────────────────────────────────────
    python_requires=">=3.10",
    install_requires=requirements,
    
    # ── Entry Points ──────────────────────────────────────────────────────
    entry_points={
        "console_scripts": [
            "rex=main:main",
        ],
    },
    
    # ── Classifiers ───────────────────────────────────────────────────────
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Home Automation",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
    ],
    
    # ── Keywords ──────────────────────────────────────────────────────────
    keywords="voice assistant ai speech recognition tts automation jarvis",
    
    # ── Project URLs ──────────────────────────────────────────────────────
    project_urls={
        "Documentation": "https://github.com/yourusername/rex/blob/main/README.md",
        "Source": "https://github.com/yourusername/rex",
        "Tracker": "https://github.com/yourusername/rex/issues",
    },
)