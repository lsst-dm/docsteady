docsteady
=========

docsteady is a python package (and optionally Docker container) that talks to
Jira and the Adaptavist Test Management system to output Test folders and
Test plans to a variety of documents by utilizing pandoc.

# Quickstart

Create a conda environment based on the `docsteady` conda package::

   conda create --name docsteady-env docsteady -c lsst-dm -c conda-forge


Credentials are needed by `docsteady` to log into JIRA. The easiest way to do this is
by setting up the following environment variables::

  export ZEPHYR_TOKEN=<jira-token>
  export JIRA_PASSWORD=<password>


The defaults of docsteady are to build documents based on DM defaults. The
following commands are available:
* `generate-spec`: to generate a Test Specification (baselining test cases)
* `generate-report`: for test plans and reports
* `generate-vcd`: to generate the Verification Control Documents
* `baseline-ve`: to generate Verification Elements baseline documents.

See [the docsteady documentation](https://docsteady.lsst.io/).


# Developers

Please refer to the [Developer Guide](https://docsteady.lsst.io/developer.html) for contribution information.

