.. _developer:

####################
Developing docsteady
####################

.. _release_new_version:

Releasing a new version
########################

0) conda activate docsteady-dev (environment used for development)
    ( if not created previously conda create --name docsteady-dev docsteady -c lsst-dm -c conda-forge )

1) In the branch, create the tag and push it

2) conda build recipe/

3) on a different terminal activate the base conda env, where you  have anaconda installed, and you have logged in
       (You may need to anaconda login - credentials in 1password)

4) copy and paste the anaconda upload command line proposed at the end of the build, and add --user lsst-dm:
       (otherwise it will be uploaded to the user logged in) e.g.
       ``` anaconda upload --user lsst-dm /usr/local/anaconda3/conda-bld/noarch/docsteady-2.0_0_gae9669c-py_0.tar.bz2 ```

5) merge the branch



Developing
##########

docsteady is a pure python tool but  depends on ``pandoc``, which is a C++ compiled library available only as a conda package.
It has been observed that any small change in the version of pandoc may lead to unexpected changes in the resulting LaTeX~format.

Therefore, in order to ensure the expected pandoc behavior, it is important to set-up the conda environment corresponding to the latest docsteady working version.
The environment set-up is explained in section :ref:`install<install>`.

The docsteady source code is available at `On github <https://github.com/lsst-dm/docsteady>`

To test changes done locally in the source code, use the following procedure:

- (if not already available) create the environment as specified in section :ref:`install<install>`
- activate the environment: ``conda activate docsteady-env``
- clone docsteady repository and checkout a ticket branch
- do your changes
- install the updates in the docsteady-env environment: ``python setup.py install``
- activate the same docsteady-env environment in a different terminal to test the new changes
- once the changes are OK, commit them in the repository and open a PR for merging the branch to master



.. _docproc:

Documentation Procedure
#######################

This is the general approach for docsteady generated documents:

- Create a document handle in DocuShare
- Use the document handle to create a repository in GitHub using sqrbot-jr, which will also create the corresponding landing page in lsst.io
- Configure a :ref:`github action<githubaction>` 
- Render the document to a ticket branch, or to the \textbf{jira-sync} special branch. Never auto-generate the document directly to master
- Ensure that the document is correctly published in the corresponding LSST The Docs landing page and that everybody who is interested can access it.
- Create a GitHub Pull Request to let contributors and stakeholders comment on the changes.
- When a set of activities are completed, and all comments have been addressed, merge the branch/PR to master.
- In case the special \textbf{jira-sync} branch is used, after merging it to master, delete it  and recreate from the latest master. Documentation tags corresponding to official issues of the document in Docushare can also be done in the jira-sync special branch.


.. _auth:

Authentication
##############

Two generic set of credentials to access the Jira REST API and the Jira database have been defined.
These credentials are available at ``1password.com``, in the LSST-IT architecture vault, but not yet integrated into docsteady.
In order to use these credentials, they have to be configured using environment variables, added as options from the command line, or entered when prompted, as specified in this technical note.

For the githubaction these should be added as secrets in the organisation.


