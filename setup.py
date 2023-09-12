from distutils.core import setup

from setuptools import find_packages

setup(
    name='CoBe - ScienceOfIntelligence',
    description='Scientific demonstrator to showcase collective behavioral model and to provide a merged environment,'
                'where robotics, human behavior and simulations meet.',
    version='1.0',
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
        'cobe-eye-orin': [
            'roboflow'  # todo: add broken dependencies here
        ],
        'cobe-eye-jetson': [
            'roboflow'
        ],
        'cobe-master': [
            'opencv-python==4.7.0.72',
            'matplotlib',
            'scipy',
            'pynput',
            'psutil',
            'fabric',
            'tinyflux',
            'filterpy'
        ]
    },
    entry_points={
        'console_scripts': ["cobe-eye-start=cobe.vision.eye:main",
                            "cobe-master-start-eyeserver=cobe.app:start_eyeserver",
                            "cobe-master-stop-eyeserver=cobe.app:stop_eyeserver",
                            "cobe-master-start=cobe.app:main",
                            "cobe-master-start-multieye=cobe.app:main_multieye",
                            "cobe-master-start-multieye-kalman=cobe.app:main_multieye_kalman",
                            "cobe-master-cleanup-docker=cobe.app:cleanup_inf_servers",
                            "cobe-master-shutdown-eyes=cobe.app:shutdown_eyes",
                            "cobe-master-calibrate=cobe.app:calibrate",
                            "cobe-master-test-stream=cobe.app:test_stream",
                            "cobe-master-collect-pngs=cobe.app:collect_pngs",
                            "cobe-master-check-crop-zoom=cobe.app:collect_pngs",
                            "cobe-rendering-shutdown=cobe.app:shutdown_rendering",
                            "cobe-rendering-startup=cobe.app:startup_rendering",
                            "cobe-pmodule-start-docker=cobe.pmodule.pmodule:entry_start_docker_container",
                            "cobe-pmodule-stop-docker=cobe.pmodule.pmodule:entry_cleanup_docker_container",
                            "cobe-database-start=cobe.app:start_database"]
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
