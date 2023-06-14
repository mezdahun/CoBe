from distutils.core import setup

from setuptools import find_packages

setup(
    name='CoBe - ScienceOfIntelligence',
    description='Scientific demonstrator to showcase collective behavioral model and to provide a merged environment,'
                'where robotics, human behavior and simulations meet.',
    version='0.1.0',
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
        ],
        'cobe-master': [
            'pyzbar',  # for QR code reading, on non-windows system additional steps needed
            'opencv-python==4.7.0.72',
            'matplotlib',
            'scipy'
        ]
    },
    entry_points={
        'console_scripts': ["cobe-eye-start=cobe.vision.eye:main",
                            "cobe-master-start=cobe.app:main",
                            "cobe-master-cleanup-docker=cobe.app:cleanup_inf_servers",
                            "cobe-master-shutdown-eyes=cobe.app:shutdown_eyes",
                            "cobe-master-calibrate=cobe.app:calibrate",
                            "cobe-pmodule-start-docker=cobe.pmodule.pmodule:entry_start_docker_container",
                            "cobe-pmodule-stop-docker=cobe.pmodule.pmodule:entry_cleanup_docker_container"]
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Operating System :: Other OS',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    test_suite='tests',
    zip_safe=False
)
