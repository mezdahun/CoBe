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
        ],
        'cobe-thymio': [
            'opencv-python==4.4.0.46',
            'numpy==1.20.1',
            'picamera==1.13',
            'pandas==1.2.0',
            'influxdb==5.3.1',
            'scipy==1.6.0',
            'psutil==5.8.0',
            'pycairo==1.20.0',
            'PyGObject==3.38.0',
            'dbus-python==1.2.16',
            'typing-extensions==3.7.4.3',
        ]
    },
    entry_points={
        'console_scripts': ["cobe-eye-start=cobe.vision.eye:main",                                          # EYE
                            "cobe-vision-start-eyeserver=cobe.app:start_eyeserver",                         # VISION
                            "cobe-vision-stop-eyeserver=cobe.app:stop_eyeserver",
                            "cobe-vision-calibrate=cobe.app:calibrate",
                            "cbv-stop-eyeserver=cobe.app:start_eyeserver",                                  # VISION-SHORT
                            "cbv-start-eyeserver=cobe.app:start_eyeserver",
                            "cbv-calibrate=cobe.app:calibrate",
                            "cobe-master-start=cobe.app:main",                                              # MASTER
                            "cobe-master-start-multieye=cobe.app:main_multieye",
                            "cobe-master-start-multieye-kalman=cobe.app:main_multieye_kalman",
                            "cobe-master-cleanup-docker=cobe.app:cleanup_inf_servers",
                            "cobe-master-shutdown-eyes=cobe.app:shutdown_eyes",
                            "cobe-master-test-stream=cobe.app:test_stream",
                            "cobe-master-collect-pngs=cobe.app:collect_pngs",
                            "cobe-master-check-crop-zoom=cobe.app:collect_pngs",
                            "cbm-start=cobe.app:main",                                                      # MASTER-SHORT
                            "cbm-start-multieye=cobe.app:main_multieye",
                            "cbm-start-multieye-kalman=cobe.app:main_multieye_kalman",
                            "cbm-cleanup-docker=cobe.app:cleanup_inf_servers",
                            "cbm-shutdown-eyes=cobe.app:shutdown_eyes",
                            "cbm-test-stream=cobe.app:test_stream",
                            "cbm-collect-pngs=cobe.app:collect_pngs",
                            "cbm-check-crop-zoom=cobe.app:collect_pngs",
                            "cobe-rendering-shutdown=cobe.app:shutdown_rendering",                          # RENDERING
                            "cobe-rendering-startup=cobe.app:startup_rendering",
                            "cobe-pmodule-start-docker=cobe.pmodule.pmodule:entry_start_docker_container",  # PMODULE
                            "cobe-pmodule-stop-docker=cobe.pmodule.pmodule:entry_cleanup_docker_container",
                            "cbp-start-docker=cobe.pmodule.pmodule:entry_start_docker_container",           # PMODULE-SHORT
                            "cbp-stop-docker=cobe.pmodule.pmodule:entry_cleanup_docker_container",
                            "cobe-database-start=cobe.app:start_database",                                  # DATABASE
                            "cbd-start=cobe.app:start_database",                                            # DATABASE-SHORT
                            "cobe-thymio-remote=cobe.app:thymio_remote_control",                            # THYMIO
                            "cobe-thymio-start-thymioserver=cobe.app:start_thymioserver",
                            "cobe-thymio-autopilot=cobe.app:thymio_autopilot",
                            "cbt-start-thymioserver=cobe.app:start_thymioserver",                           # THYMIO-SHORT
                            "cbt-remote=cobe.app:thymio_remote_control",
                            "cbt-autopilot=cobe.app:thymio_autopilot",
                            "cbmeta-start=cobe.metaprotocols:single_human"                     # METAPROTOCOLS
                            ]
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
