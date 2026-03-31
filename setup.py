from setuptools import setup, find_packages

setup(
    name="blockchain-demo",
    version="0.3.0",
    description="Demo funcional de blockchain estilo Bitcoin para red LAN",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "cryptography>=41.0.0",
        "pycryptodome>=3.20.0",
        "websockets>=12.0",
        "Flask>=3.0.0",
        "colorama>=0.4.6",
    ],
)
