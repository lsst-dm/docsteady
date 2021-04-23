.. _install:

####################
Installing docsteady
####################


Create a conda environment based on the `docsteady` conda package::

   conda create --name docsteady-env docsteady -c lsst-dm -c conda-forge

Ensure that the conda configuration file  `.condarc` does not include the conda-forge channel.

To use docsteady, activate the environment as follows::

   conda activate docsteady-env

This environment will provide all dependencies that are required to run docsteady.

It is recommended to use the provided conda environment also for development activities, see :ref:`developer page <developer>`.
