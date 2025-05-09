from setuptools import setup, find_packages

setup(
    name='PySocketCommLib',
    version='0.1',
    author='https://github.com/Jhonattan-rocha',
    author_email='jhonattan246rocha@gmail.com',
    packages=find_packages(),  # Agora procura pacotes no diretório atual
    install_requires=[
        "cryptography"
    ],
)
