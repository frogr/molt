from setuptools import setup

setup(
    name="molt",
    version="0.1.0",
    description="Moltbook CLI for AI agents",
    author="austnomaton",
    author_email="austin@austn.net",
    url="https://github.com/austnomaton/molt",
    py_modules=["molt"],
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "molt=molt:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
