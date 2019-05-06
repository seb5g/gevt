import distutils.dir_util
from distutils.command import build
import os, sys, re
try:
    import setuptools
    from setuptools import setup, find_packages
    from setuptools.command import install
except ImportError:
    sys.stderr.write("Warning: could not import setuptools; falling back to distutils.\n")
    from distutils.core import setup
    from distutils.command import install
from gevt.version import get_version

with open('README.md') as fd:
    long_description = fd.read()

setupOpts = dict(
    name='gevt',
    description='Gestionnaire de Volontaires et de Tâches',
    long_description=long_description,
    license='MIT',
    url='',
    author='Sébastien Weber',
    author_email='seba.weber@gmail.com',
    classifiers = [
        "Programming Language :: Python :: 3",
        #"Development Status :: 1 - Beta",
        "Environment :: Other Environment",
        #"Intended Audience :: Association/Organisation",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: User Interfaces",
        ],
)


class Build(build.build):
    """
    * Clear build path before building
    """

    def run(self):
        global path

        ## Make sure build directory is clean
        buildPath = os.path.join(path, self.build_lib)
        if os.path.isdir(buildPath):
            distutils.dir_util.remove_tree(buildPath)


        ret = build.build.run(self)



setup(
    version=get_version(),
    # cmdclass={'build': Build,},
    #           'install': Install,
    #           'deb': helpers.DebCommand,
    #           'test': helpers.TestCommand,
    #           'debug': helpers.DebugCommand,
    #           'mergetest': helpers.MergeTestCommand,
    #           'style': helpers.StyleCommand},
    packages=find_packages(),
    #package_dir={'examples': 'examples'},  ## install examples along with the rest of the source
    package_data={'': ['*.rst'],
                'gevt.examples': ['*.gev', '*.csv'],
                'gevt.icons.Icons': ['*.png']},
    install_requires = [
        'numpy',
        'yattag',
        'yawrap',
        'pyqtgraph==0.10',
        'python-dateutil',
        'tables',
        ],
    #console =
    entry_points={
            'console_scripts': ['gevt = gevt.gevt:start_gevt',]
        },
    **setupOpts
)

