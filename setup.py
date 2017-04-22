from setuptools import setup, find_packages
import re

def extract_version(filename):
    with open(filename) as source:
        regex = r'__version__\s*=\s*([\'"])([^\1]+)\1'
        match = re.search(regex, source.read())
        return match.group(2)


version = extract_version('xrayvision/__init__.py')

setup(
    name='xrayvision',
    version=version,
    author='Matthew Thompson',
    author_email='matt@britecore.com',
    packages=find_packages(),
    url='https://github.com/IntuitiveWebSolutions/xrayvision',
    license='LICENSE.txt',
    description='AWS X-Ray tracing for python',
    long_description=open('README.md').read(),
    install_requires=open('requirements.txt').read().split(),
    setup_requires=['pytest-runner'],
    tests_require=['pytest', 'mock', 'pytest-cov']
)
