from setuptools import setup

requires = [
    'requests',
    'pyandoc',
    'arrow',
    'jinja2',
    'click',
    'BeautifulSoup4',
    'marshmallow<3'
]

setup(
    name='docsteady',
    version='1.0pre1',
    packages=['docsteady'],
    url='https://github.com/lsst-dm/docsteady',
    license='GPL',
    author='Brian Van Klaveren',
    author_email='bvan@slac.stanford.edu',
    description='Docsteady Document Printer',
    install_requires=requires,
    package_data={'docsteady': ['templates/*.jinja2']},
    entry_points={
        'console_scripts': [
            'docsteady = docsteady:cli',
        ],
    }
)
