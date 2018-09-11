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

doc_requires = [
    "sphinx",
    "sphinx_click",
    "sphinx_rtd_theme"
]

setup(
    name='docsteady',
    version='1.0rc2',
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
    },
    extras_require={'docs': doc_requires}
)
