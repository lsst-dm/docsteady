from setuptools import setup

requires = [
    'requests',
    'pyandoc',
    'arrow',
    'jinja2',
    'click'
]

setup(
    name='docsteady',
    version='0.5',
    packages=['docsteady'],
    url='https://github.com/lsst-dm/docsteady',
    license='GPL',
    author='Brian Van Klaveren',
    author_email='bvan@slac.stanford.edu',
    description='Docsteady Document Printer',
    install_requires=requires,
    entry_points={
        'console_scripts': [
            'docsteady = docsteady:main',
        ],
    }

)
