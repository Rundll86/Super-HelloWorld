"""Setup.py — Package configuration for Super-HelloWorld."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="super-helloworld",
    version="1.0.0",
    author="Enterprise Architecture Team",
    description="Enterprise-grade Hello World printing infrastructure",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/enterprise/super-helloworld",
    packages=find_packages(where="src", exclude=["tests", "tests.*"]),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Logging",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.10",
    install_requires=[
        "structlog>=23.1.0",
        "colorama>=0.4.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.0",
            "black>=23.9.0",
            "mypy>=1.5.0",
            "bandit>=1.7.5",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "super-helloworld=src.cli:run_cli",
        ],
    },
)
