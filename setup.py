from setuptools import setup

requires = [
    'requests',
    'pyandoc',
    'arrow',
    'jinja2',
    'click',
    'BeautifulSoup4',
    'marshmallow<3',
    'setuptools_scm'
]

doc_requires = [
    "sphinx",
    "sphinx_click",
    "sphinx_rtd_theme"
]

setup(
    name='docsteady',
    use_scm_version={'version_scheme': 'post-release'},
    setup_requires=['setuptools_scm'],
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
