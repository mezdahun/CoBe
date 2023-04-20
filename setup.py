from distutils.core import setup

from setuptools import find_packages

setup(
    name='CoBe - ScienceOfIntelligence',
    description='Scientific demonstrator to showcase collective behavioral model and to provide a merged environment,'
                'where robotics, human behavior and simulations meet.',
    version='0.0.1',
    url='https://github.com/mezdahun/CoBe',
    maintainer='David Mezey, David James and Palina Bartashevich @ SCIoI',
    packages=find_packages(exclude=['tests']),
    package_data={'cobe': ['*.txt']},
    python_requires=">=3.6",
    install_requires=[
        'Pyro5',
        'msgpack',
        'numpy'
    ],
    extras_require={
        'test': [
            'bandit',
            'flake8',
            'pytest',
            'pytest-cov'
        ]
    },
    entry_points={
        'console_scripts': ["cobe-eye-start=cobe.vision.eye:main"]
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Operating System :: Other OS',
        'Programming Language :: Python :: 3.8'
    ],
    test_suite='tests',
    zip_safe=False
)
